"""Overlay orphan detection (keys not present in current RAW)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_overlay(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"by_symbol_id": {}, "by_file_id": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def valid_symbol_ids(raw_doc: dict[str, Any]) -> set[str]:
    return {s["id"] for s in raw_doc.get("symbols", [])}


def valid_file_ids(raw_doc: dict[str, Any]) -> set[str]:
    return {f["id"] for f in raw_doc.get("files", [])}


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


def report_orphans(overlay_path: Path | str, raw_path: Path | str) -> dict[str, Any]:
    raw_doc = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    overlay = load_overlay(overlay_path)
    sym = overlay_orphan_keys(overlay, raw_doc)
    fil = overlay_orphan_file_keys(overlay, raw_doc)
    return {
        "schema_version": 0,
        "overlay_path": str(Path(overlay_path).resolve()),
        "raw_path": str(Path(raw_path).resolve()),
        "orphan_symbol_ids": sym,
        "orphan_file_ids": fil,
        "orphan_count": len(sym) + len(fil),
    }
