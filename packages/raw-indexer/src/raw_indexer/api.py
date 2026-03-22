"""Phase 3: small HTTP shell for RAW + overlay (FastAPI)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from raw_indexer.bundle import apply_bundle
from raw_indexer.index import index_repo, write_index
from raw_indexer.overlay import (
    overlay_orphan_directory_keys,
    overlay_orphan_file_keys,
    overlay_orphan_keys,
    overlay_orphan_root_keys,
)
from raw_indexer.update_map import run_update_map


class ReindexBody(BaseModel):
    """Optional override for POST /reindex (defaults from env)."""

    repo_root: str | None = Field(
        default=None,
        description="Repository root to index; else BRAINSTORM_GOLDEN_REPO",
    )


class ApplyBundleBody(BaseModel):
    """
    Change package for POST /apply-bundle (Phase 5).

    Repo root is **BRAINSTORM_GOLDEN_REPO** (Option A — one deployment per project).
    If ``overlay`` is set, it is merged into ``BRAINSTORM_PUBLIC_DIR/overlay.json`` after
    the patch, validated against a fresh index of the repo.
    """

    schema_version: int = Field(default=0, description="Must be 0")
    unified_diff: str = Field(
        default="",
        description="Unified diff for patch -p1 from repo root; may be empty if overlay-only",
    )
    overlay: dict[str, Any] | None = Field(
        default=None,
        description="Optional overlay fragment (by_symbol_id / by_file_id / by_directory_id) to merge",
    )
    dry_run: bool = Field(default=False, description="patch --dry-run only; disallowed if overlay set")
    skip_validate: bool = Field(default=False, description="Skip pytest/typecheck after apply")
    pytest_only: bool = Field(
        default=False,
        description="If validating, pytest only (no typecheck)",
    )


def _bundle_dict_from_body(body: ApplyBundleBody) -> dict[str, Any]:
    d: dict[str, Any] = {"schema_version": body.schema_version, "unified_diff": body.unified_diff}
    if body.overlay is not None:
        d["overlay"] = body.overlay
    return d


def _public_dir() -> Path:
    env = os.environ.get("BRAINSTORM_PUBLIC_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise HTTPException(
                status_code=500,
                detail=f"BRAINSTORM_PUBLIC_DIR is not a directory: {p}",
            )
        return p
    cwd_pub = Path.cwd() / "poc-brainstorm-ui" / "public"
    if cwd_pub.is_dir():
        return cwd_pub.resolve()
    raise HTTPException(
        status_code=500,
        detail="Set BRAINSTORM_PUBLIC_DIR to poc-brainstorm-ui/public (or run uvicorn from repo root).",
    )


def _raw_path() -> Path:
    return _public_dir() / "raw.json"


def _overlay_path() -> Path:
    return _public_dir() / "overlay.json"


def _golden_repo() -> Path:
    env = os.environ.get("BRAINSTORM_GOLDEN_REPO", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise HTTPException(
                status_code=500,
                detail=f"BRAINSTORM_GOLDEN_REPO is not a directory: {p}",
            )
        return p
    raise HTTPException(
        status_code=500,
        detail="Set BRAINSTORM_GOLDEN_REPO to the repo root to index (e.g. fixtures/golden-fastapi).",
    )


def _normalize_overlay(body: dict[str, Any]) -> dict[str, Any]:
    by_sym = body.get("by_symbol_id")
    by_file = body.get("by_file_id")
    by_dir = body.get("by_directory_id")
    by_root = body.get("by_root_id")
    if by_sym is not None and not isinstance(by_sym, dict):
        raise HTTPException(status_code=422, detail="by_symbol_id must be an object")
    if by_file is not None and not isinstance(by_file, dict):
        raise HTTPException(status_code=422, detail="by_file_id must be an object")
    if by_dir is not None and not isinstance(by_dir, dict):
        raise HTTPException(status_code=422, detail="by_directory_id must be an object")
    if by_root is not None and not isinstance(by_root, dict):
        raise HTTPException(status_code=422, detail="by_root_id must be an object")
    sv = body.get("schema_version")
    if sv is not None and not isinstance(sv, int):
        raise HTTPException(status_code=422, detail="schema_version must be an integer")
    return {
        "schema_version": int(sv) if isinstance(sv, int) else 0,
        "by_symbol_id": dict(by_sym) if isinstance(by_sym, dict) else {},
        "by_file_id": dict(by_file) if isinstance(by_file, dict) else {},
        "by_directory_id": dict(by_dir) if isinstance(by_dir, dict) else {},
        "by_root_id": dict(by_root) if isinstance(by_root, dict) else {},
    }


app = FastAPI(
    title="Brainstorm API",
    description="RAW + overlay for the brainstorm POC (Phase 3).",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/raw")
def get_raw() -> JSONResponse:
    path = _raw_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.get("/overlay")
def get_overlay() -> JSONResponse:
    path = _overlay_path()
    if not path.is_file():
        return JSONResponse(
            content={
                "schema_version": 0,
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {},
            },
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.patch("/overlay")
def patch_overlay(body: dict[str, Any]) -> JSONResponse:
    raw_path = _raw_path()
    if not raw_path.is_file():
        raise HTTPException(status_code=400, detail="raw.json must exist before patching overlay")
    raw_doc = json.loads(raw_path.read_text(encoding="utf-8"))
    overlay = _normalize_overlay(body)
    sym_orphans = overlay_orphan_keys(overlay, raw_doc)
    file_orphans = overlay_orphan_file_keys(overlay, raw_doc)
    dir_orphans = overlay_orphan_directory_keys(overlay, raw_doc)
    root_orphans = overlay_orphan_root_keys(overlay)
    if sym_orphans or file_orphans or dir_orphans or root_orphans:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Overlay contains keys not present in RAW",
                "orphan_symbol_ids": sym_orphans,
                "orphan_file_ids": file_orphans,
                "orphan_directory_ids": dir_orphans,
                "orphan_root_ids": root_orphans,
            },
        )
    out = _overlay_path()
    out.write_text(json.dumps(overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return JSONResponse(content=overlay)


@app.post("/reindex")
def reindex(body: ReindexBody | None = None) -> dict[str, Any]:
    root = Path(body.repo_root).expanduser().resolve() if body and body.repo_root else _golden_repo()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    doc = index_repo(root)
    raw_out = _raw_path()
    write_index(doc, raw_out)
    return {
        "ok": True,
        "wrote": str(raw_out),
        "symbol_count": len(doc.get("symbols", [])),
        "file_count": len(doc.get("files", [])),
    }


@app.post("/apply-bundle")
def apply_bundle_http(body: ApplyBundleBody) -> JSONResponse:
    """
    Apply a change package to **BRAINSTORM_GOLDEN_REPO**, then refresh **public/raw.json**
    so GET /raw matches the repo after success.
    """
    root = _golden_repo()
    bundle_dict = _bundle_dict_from_body(body)
    overlay_path = _overlay_path() if body.overlay is not None else None
    res = apply_bundle(
        root,
        bundle_dict,
        overlay_path=overlay_path,
        dry_run=body.dry_run,
        skip_validate=body.skip_validate,
        pytest_only=body.pytest_only,
    )
    if res.ok and not body.dry_run:
        doc = index_repo(root)
        write_index(doc, _raw_path())
    payload = res.to_json_dict()
    if not res.ok:
        return JSONResponse(status_code=422, content=payload)
    return JSONResponse(content=payload)


@app.post("/update-map")
def update_map() -> JSONResponse:
    """
    **Update map** — AI (DeepSeek) fills ``displayName`` / ``userDescription`` in
    ``overlay.json``. Requires ``DEEPSEEK_API_KEY`` unless ``UPDATE_MAP_DRY_RUN=1``.

    Refreshes ``raw.json`` from ``BRAINSTORM_GOLDEN_REPO`` first.
    """
    root = _golden_repo()
    doc = index_repo(root)
    write_index(doc, _raw_path())
    result = run_update_map(root, _overlay_path(), doc)
    if not result.get("ok"):
        return JSONResponse(status_code=503, content=result)
    return JSONResponse(content=result)
