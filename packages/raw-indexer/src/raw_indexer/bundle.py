"""Phase 5: formal bundle schema + apply (patch + optional overlay) + reindex + validate."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from raw_indexer.apply_patch import apply_unified_patch
from raw_indexer.index import index_repo
from raw_indexer.overlay import (
    load_overlay,
    overlay_orphan_directory_keys,
    overlay_orphan_file_keys,
    overlay_orphan_keys,
    overlay_orphan_root_keys,
)
from raw_indexer.validate import validate_repo

BUNDLE_SCHEMA_VERSION = 0


@dataclass
class ApplyBundleResult:
    ok: bool
    apply_exit_code: int
    validate_exit_code: int | None = None
    raw_file_count: int | None = None
    raw_symbol_count: int | None = None
    overlay_written: bool = False
    errors: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _coerce_overlay_fragment(body: Any) -> dict[str, Any]:
    """Subset of overlay fields for merge; raises ValueError on bad types."""
    if not isinstance(body, dict):
        raise ValueError("bundle.overlay must be an object")
    by_sym = body.get("by_symbol_id")
    by_file = body.get("by_file_id")
    if by_sym is not None and not isinstance(by_sym, dict):
        raise ValueError("bundle.overlay.by_symbol_id must be an object")
    if by_file is not None and not isinstance(by_file, dict):
        raise ValueError("bundle.overlay.by_file_id must be an object")
    by_dir = body.get("by_directory_id")
    if by_dir is not None and not isinstance(by_dir, dict):
        raise ValueError("bundle.overlay.by_directory_id must be an object")
    by_root = body.get("by_root_id")
    if by_root is not None and not isinstance(by_root, dict):
        raise ValueError("bundle.overlay.by_root_id must be an object")
    sv = body.get("schema_version")
    if sv is not None and not isinstance(sv, int):
        raise ValueError("bundle.overlay.schema_version must be an integer")
    return {
        "schema_version": int(sv) if isinstance(sv, int) else 0,
        "by_symbol_id": dict(by_sym) if isinstance(by_sym, dict) else {},
        "by_file_id": dict(by_file) if isinstance(by_file, dict) else {},
        "by_directory_id": dict(by_dir) if isinstance(by_dir, dict) else {},
        "by_root_id": dict(by_root) if isinstance(by_root, dict) else {},
    }


def parse_bundle(doc: Any) -> dict[str, Any]:
    """
    Validate bundle JSON shape. Returns a dict with schema_version, unified_diff, optional overlay.
    """
    if not isinstance(doc, dict):
        raise ValueError("bundle must be a JSON object")
    sv = doc.get("schema_version", 0)
    if sv != BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"unsupported bundle schema_version: {sv!r} (expected {BUNDLE_SCHEMA_VERSION})")
    diff = doc.get("unified_diff", "")
    if not isinstance(diff, str):
        raise ValueError("bundle.unified_diff must be a string")
    has_overlay = "overlay" in doc
    if not diff.strip() and not has_overlay:
        raise ValueError("bundle needs non-empty unified_diff or a bundle.overlay section")
    out: dict[str, Any] = {"schema_version": BUNDLE_SCHEMA_VERSION, "unified_diff": diff}
    if has_overlay:
        out["overlay"] = _coerce_overlay_fragment(doc["overlay"])
    return out


def load_bundle(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    return parse_bundle(json.loads(p.read_text(encoding="utf-8")))


def merge_overlay_delta(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Deep-enough merge: delta symbol/file/directory entries merge field-wise into base."""
    b_sym = dict(base.get("by_symbol_id") or {})
    b_fil = dict(base.get("by_file_id") or {})
    b_dir = dict(base.get("by_directory_id") or {})
    b_root = dict(base.get("by_root_id") or {})
    d_sym = delta.get("by_symbol_id") or {}
    d_fil = delta.get("by_file_id") or {}
    d_dir = delta.get("by_directory_id") or {}
    d_root = delta.get("by_root_id") or {}
    for sid, ent in d_sym.items():
        if not isinstance(ent, dict):
            raise ValueError(f"overlay entry for symbol {sid!r} must be an object")
        prev = dict(b_sym.get(sid) or {})
        prev.update(ent)
        b_sym[sid] = prev
    for fid, ent in d_fil.items():
        if not isinstance(ent, dict):
            raise ValueError(f"overlay entry for file {fid!r} must be an object")
        prev = dict(b_fil.get(fid) or {})
        prev.update(ent)
        b_fil[fid] = prev
    for did, ent in d_dir.items():
        if not isinstance(ent, dict):
            raise ValueError(f"overlay entry for directory {did!r} must be an object")
        prev = dict(b_dir.get(did) or {})
        prev.update(ent)
        b_dir[did] = prev
    for rid, ent in d_root.items():
        if not isinstance(ent, dict):
            raise ValueError(f"overlay entry for root {rid!r} must be an object")
        prev = dict(b_root.get(rid) or {})
        prev.update(ent)
        b_root[rid] = prev
    return {
        "schema_version": int(delta.get("schema_version") or base.get("schema_version") or 0),
        "by_symbol_id": b_sym,
        "by_file_id": b_fil,
        "by_directory_id": b_dir,
        "by_root_id": b_root,
    }


def apply_bundle(
    repo: Path | str,
    bundle: dict[str, Any],
    *,
    overlay_path: Path | None = None,
    dry_run: bool = False,
    skip_validate: bool = False,
    pytest_only: bool = False,
) -> ApplyBundleResult:
    """
    Apply bundle.unified_diff with patch(1), optionally merge overlay (validated against fresh RAW),
    then run validate_repo unless skip_validate.

    If bundle contains ``overlay``, ``overlay_path`` must be set (file written after patch + reindex).
    """
    repo_p = Path(repo).resolve()
    errors: list[str] = []
    try:
        parsed = parse_bundle(bundle)
    except ValueError as e:
        return ApplyBundleResult(ok=False, apply_exit_code=1, errors=[str(e)])

    if "overlay" in parsed and overlay_path is None:
        return ApplyBundleResult(
            ok=False,
            apply_exit_code=1,
            errors=["bundle contains overlay but overlay_path was not provided"],
        )

    if dry_run and "overlay" in parsed:
        return ApplyBundleResult(
            ok=False,
            apply_exit_code=1,
            errors=["--dry-run is not supported when bundle includes overlay (cannot validate post-patch RAW)"],
        )

    diff_text = parsed["unified_diff"].strip()
    code = 0
    if diff_text:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".patch",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(parsed["unified_diff"])
            patch_path = Path(tmp.name)

        try:
            code = apply_unified_patch(repo_p, patch_path, dry_run=dry_run)
        finally:
            patch_path.unlink(missing_ok=True)

        if code != 0:
            errors.append(f"patch exited with code {code}")
            return ApplyBundleResult(ok=False, apply_exit_code=code, errors=errors)

    if dry_run:
        return ApplyBundleResult(ok=True, apply_exit_code=0, errors=[])

    raw_doc = index_repo(repo_p)
    raw_file_count = len(raw_doc.get("files", []))
    raw_symbol_count = len(raw_doc.get("symbols", []))

    overlay_written = False
    if "overlay" in parsed:
        assert overlay_path is not None
        op = Path(overlay_path)
        existing = (
            load_overlay(op)
            if op.is_file()
            else {
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {},
            }
        )
        try:
            merged = merge_overlay_delta(existing, parsed["overlay"])
        except ValueError as e:
            return ApplyBundleResult(
                ok=False,
                apply_exit_code=0,
                raw_file_count=raw_file_count,
                raw_symbol_count=raw_symbol_count,
                errors=[str(e)],
            )
        sym_o = overlay_orphan_keys(merged, raw_doc)
        fil_o = overlay_orphan_file_keys(merged, raw_doc)
        dir_o = overlay_orphan_directory_keys(merged, raw_doc)
        root_o = overlay_orphan_root_keys(merged)
        if sym_o or fil_o or dir_o or root_o:
            msg = "overlay would contain orphan keys not in RAW after patch"
            if sym_o:
                msg += f"; orphan_symbol_ids={sym_o[:10]}"
                if len(sym_o) > 10:
                    msg += "…"
            if fil_o:
                msg += f"; orphan_file_ids={fil_o[:10]}"
                if len(fil_o) > 10:
                    msg += "…"
            if dir_o:
                msg += f"; orphan_directory_ids={dir_o[:10]}"
                if len(dir_o) > 10:
                    msg += "…"
            if root_o:
                msg += f"; orphan_root_ids={root_o[:10]}"
                if len(root_o) > 10:
                    msg += "…"
            return ApplyBundleResult(
                ok=False,
                apply_exit_code=0,
                raw_file_count=raw_file_count,
                raw_symbol_count=raw_symbol_count,
                errors=[msg],
            )
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        overlay_written = True

    val_code: int | None = None
    if not skip_validate:
        val_code = validate_repo(repo_p, pytest_only=pytest_only)
        if val_code != 0:
            errors.append(f"validate exited with code {val_code}")
            return ApplyBundleResult(
                ok=False,
                apply_exit_code=0,
                validate_exit_code=val_code,
                raw_file_count=raw_file_count,
                raw_symbol_count=raw_symbol_count,
                overlay_written=overlay_written,
                errors=errors,
            )

    return ApplyBundleResult(
        ok=True,
        apply_exit_code=0,
        validate_exit_code=val_code,
        raw_file_count=raw_file_count,
        raw_symbol_count=raw_symbol_count,
        overlay_written=overlay_written,
        errors=[],
    )
