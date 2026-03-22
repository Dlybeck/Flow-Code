"""Phase 3: small HTTP shell for RAW + overlay (FastAPI)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from raw_indexer.index import index_repo, write_index
from raw_indexer.overlay import overlay_orphan_file_keys, overlay_orphan_keys


class ReindexBody(BaseModel):
    """Optional override for POST /reindex (defaults from env)."""

    repo_root: str | None = Field(
        default=None,
        description="Repository root to index; else BRAINSTORM_GOLDEN_REPO",
    )


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
    if by_sym is not None and not isinstance(by_sym, dict):
        raise HTTPException(status_code=422, detail="by_symbol_id must be an object")
    if by_file is not None and not isinstance(by_file, dict):
        raise HTTPException(status_code=422, detail="by_file_id must be an object")
    sv = body.get("schema_version")
    if sv is not None and not isinstance(sv, int):
        raise HTTPException(status_code=422, detail="schema_version must be an integer")
    return {
        "schema_version": int(sv) if isinstance(sv, int) else 0,
        "by_symbol_id": dict(by_sym) if isinstance(by_sym, dict) else {},
        "by_file_id": dict(by_file) if isinstance(by_file, dict) else {},
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
            content={"schema_version": 0, "by_symbol_id": {}, "by_file_id": {}},
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
    if sym_orphans or file_orphans:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Overlay contains keys not present in RAW",
                "orphan_symbol_ids": sym_orphans,
                "orphan_file_ids": file_orphans,
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
