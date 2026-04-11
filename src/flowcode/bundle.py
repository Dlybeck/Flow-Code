"""Bundle schema + overlay merge primitives.

Note: apply_bundle (patch + validate pipeline) has been removed from this module.
That orchestration concern belongs in the calling layer (e.g. SlowCode).
This module provides the schema validation and overlay merge primitives only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BUNDLE_SCHEMA_VERSION = 0


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
    by_flow = body.get("by_flow_node_id")
    if by_flow is not None and not isinstance(by_flow, dict):
        raise ValueError("bundle.overlay.by_flow_node_id must be an object")
    sv = body.get("schema_version")
    if sv is not None and not isinstance(sv, int):
        raise ValueError("bundle.overlay.schema_version must be an integer")
    return {
        "schema_version": int(sv) if isinstance(sv, int) else 0,
        "by_symbol_id": dict(by_sym) if isinstance(by_sym, dict) else {},
        "by_file_id": dict(by_file) if isinstance(by_file, dict) else {},
        "by_directory_id": dict(by_dir) if isinstance(by_dir, dict) else {},
        "by_root_id": dict(by_root) if isinstance(by_root, dict) else {},
        "by_flow_node_id": dict(by_flow) if isinstance(by_flow, dict) else {},
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
    """Deep-enough merge: delta symbol/file/directory/flow entries merge field-wise into base."""
    b_sym = dict(base.get("by_symbol_id") or {})
    b_fil = dict(base.get("by_file_id") or {})
    b_dir = dict(base.get("by_directory_id") or {})
    b_root = dict(base.get("by_root_id") or {})
    b_flow = dict(base.get("by_flow_node_id") or {})
    d_sym = delta.get("by_symbol_id") or {}
    d_fil = delta.get("by_file_id") or {}
    d_dir = delta.get("by_directory_id") or {}
    d_root = delta.get("by_root_id") or {}
    d_flow = delta.get("by_flow_node_id") or {}
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
    for fid, ent in d_flow.items():
        if not isinstance(ent, dict):
            raise ValueError(f"overlay entry for flow node {fid!r} must be an object")
        prev = dict(b_flow.get(fid) or {})
        prev.update(ent)
        b_flow[fid] = prev
    return {
        "schema_version": int(delta.get("schema_version") or base.get("schema_version") or 0),
        "by_symbol_id": b_sym,
        "by_file_id": b_fil,
        "by_directory_id": b_dir,
        "by_root_id": b_root,
        "by_flow_node_id": b_flow,
    }
