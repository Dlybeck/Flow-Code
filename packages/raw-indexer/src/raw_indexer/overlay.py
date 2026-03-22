"""Overlay orphan detection (keys not present in current RAW)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_OVERLAY_ID = "raw-root"


def load_overlay(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {
            "by_symbol_id": {},
            "by_file_id": {},
            "by_directory_id": {},
            "by_root_id": {},
            "by_flow_node_id": {},
        }
    return json.loads(p.read_text(encoding="utf-8"))


def valid_flow_node_ids(raw_doc: dict[str, Any]) -> set[str] | None:
    """
    Node ids from the current execution IR built from RAW.
    Returns None if IR cannot be built (caller should skip flow overlay orphan check).
    """
    try:
        from raw_indexer.execution_ir.python_from_raw import build_execution_ir_from_raw

        ir = build_execution_ir_from_raw(raw_doc)
    except Exception:
        return None
    return {
        str(n["id"])
        for n in ir.get("nodes", [])
        if isinstance(n, dict) and n.get("id")
    }


def overlay_orphan_flow_keys(overlay: dict[str, Any], raw_doc: dict[str, Any]) -> list[str]:
    """Flow overlay keys not present in execution IR from current RAW."""
    valid = valid_flow_node_ids(raw_doc)
    keys = set(overlay.get("by_flow_node_id", {}).keys())
    if valid is None:
        return []
    return sorted(keys - valid)


def valid_symbol_ids(raw_doc: dict[str, Any]) -> set[str]:
    return {s["id"] for s in raw_doc.get("symbols", [])}


def valid_file_ids(raw_doc: dict[str, Any]) -> set[str]:
    return {f["id"] for f in raw_doc.get("files", [])}


def valid_directory_ids(raw_doc: dict[str, Any]) -> set[str]:
    """
    Stable dir:path keys used by the graph (derived from file paths, aligned with RAW index ids).
    """
    out: set[str] = set()
    for f in raw_doc.get("files", []):
        rel = str(f.get("path", ""))
        if not rel or "/" not in rel:
            continue
        parts = rel.split("/")
        for i in range(len(parts) - 1):
            out.add("dir:" + "/".join(parts[: i + 1]))
    return out


def overlay_orphan_keys(overlay: dict[str, Any], raw_doc: dict[str, Any]) -> list[str]:
    """Symbol overlay keys that are not in RAW (SPEC: overlay_keys − valid_raw_ids)."""
    valid = valid_symbol_ids(raw_doc)
    keys = set(overlay.get("by_symbol_id", {}).keys())
    return sorted(keys - valid)


def overlay_orphan_file_keys(overlay: dict[str, Any], raw_doc: dict[str, Any]) -> list[str]:
    """File overlay keys that are not in RAW."""
    valid = valid_file_ids(raw_doc)
    keys = set(overlay.get("by_file_id", {}).keys())
    return sorted(keys - valid)


def overlay_orphan_directory_keys(overlay: dict[str, Any], raw_doc: dict[str, Any]) -> list[str]:
    valid = valid_directory_ids(raw_doc)
    keys = set(overlay.get("by_directory_id", {}).keys())
    return sorted(keys - valid)


def overlay_orphan_root_keys(overlay: dict[str, Any]) -> list[str]:
    """Only raw-root is valid for by_root_id."""
    keys = set(overlay.get("by_root_id", {}).keys())
    allowed = {ROOT_OVERLAY_ID}
    return sorted(keys - allowed)


def report_orphans(overlay_path: Path | str, raw_path: Path | str) -> dict[str, Any]:
    raw_doc = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    overlay = load_overlay(overlay_path)
    sym = overlay_orphan_keys(overlay, raw_doc)
    fil = overlay_orphan_file_keys(overlay, raw_doc)
    d = overlay_orphan_directory_keys(overlay, raw_doc)
    r = overlay_orphan_root_keys(overlay)
    flow = overlay_orphan_flow_keys(overlay, raw_doc)
    return {
        "schema_version": 0,
        "overlay_path": str(Path(overlay_path).resolve()),
        "raw_path": str(Path(raw_path).resolve()),
        "orphan_symbol_ids": sym,
        "orphan_file_ids": fil,
        "orphan_directory_ids": d,
        "orphan_root_ids": r,
        "orphan_flow_node_ids": flow,
        "orphan_count": len(sym) + len(fil) + len(d) + len(r) + len(flow),
    }
