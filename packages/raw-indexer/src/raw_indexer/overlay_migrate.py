"""Rewrite overlay.json keys using diff.remap heuristics (Phase 4 exit)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from raw_indexer.diff_raw import diff_raw


def _merge_entry(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Prefer non-empty values from b, then a."""
    out = dict(a)
    for k, v in b.items():
        if v is None or v == "":
            continue
        if k not in out or out[k] in (None, ""):
            out[k] = v
    return out


def migrate_overlay_from_remap(
    overlay: dict[str, Any],
    remap: dict[str, Any],
    *,
    include_medium: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Apply symbol/file remap suggestions to by_symbol_id / by_file_id.

    Returns (new_overlay, report). Does not mutate the input overlay.
    """
    out = copy.deepcopy(overlay)
    by_sym: dict[str, Any] = dict(out.get("by_symbol_id") or {})
    by_fil: dict[str, Any] = dict(out.get("by_file_id") or {})

    report: dict[str, Any] = {
        "symbols_moved": [],
        "symbols_merged": [],
        "files_moved": [],
        "files_merged": [],
        "skipped": [],
    }

    sym_section = remap.get("symbols") or {}
    pairs: list[dict[str, Any]] = list(sym_section.get("high") or [])
    if include_medium:
        pairs.extend(sym_section.get("medium") or [])

    for item in pairs:
        old_id = item.get("from_id")
        new_id = item.get("to_id")
        if not old_id or not new_id or old_id == new_id:
            continue
        if old_id not in by_sym:
            report["skipped"].append(
                {"kind": "symbol", "from_id": old_id, "reason": "no_overlay_entry"},
            )
            continue
        entry = by_sym.pop(old_id)
        if new_id in by_sym:
            merged = _merge_entry(entry, by_sym[new_id])
            by_sym[new_id] = merged
            report["symbols_merged"].append(
                {
                    "from_id": old_id,
                    "to_id": new_id,
                    "confidence": item.get("confidence"),
                }
            )
        else:
            by_sym[new_id] = entry
            report["symbols_moved"].append(
                {
                    "from_id": old_id,
                    "to_id": new_id,
                    "confidence": item.get("confidence"),
                }
            )

    file_section = remap.get("files") or {}
    file_pairs: list[dict[str, Any]] = list(file_section.get("medium") or [])

    for item in file_pairs:
        old_id = item.get("from_id")
        new_id = item.get("to_id")
        if not old_id or not new_id or old_id == new_id:
            continue
        if old_id not in by_fil:
            report["skipped"].append(
                {"kind": "file", "from_id": old_id, "reason": "no_overlay_entry"},
            )
            continue
        entry = by_fil.pop(old_id)
        if new_id in by_fil:
            merged = _merge_entry(entry, by_fil[new_id])
            by_fil[new_id] = merged
            report["files_merged"].append(
                {
                    "from_id": old_id,
                    "to_id": new_id,
                    "confidence": item.get("confidence"),
                }
            )
        else:
            by_fil[new_id] = entry
            report["files_moved"].append(
                {
                    "from_id": old_id,
                    "to_id": new_id,
                    "confidence": item.get("confidence"),
                }
            )

    out["by_symbol_id"] = by_sym
    out["by_file_id"] = by_fil
    if "schema_version" not in out:
        out["schema_version"] = 0
    return out, report


def migrate_overlay_files(
    old_raw_path: Path | str,
    new_raw_path: Path | str,
    overlay_path: Path | str,
    *,
    include_medium: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load paths, diff, migrate. Returns (new_overlay, diff, report)."""
    diff = diff_raw(old_raw_path, new_raw_path)
    remap = diff.get("remap") or {}
    overlay = json.loads(Path(overlay_path).read_text(encoding="utf-8"))
    new_ov, report = migrate_overlay_from_remap(overlay, remap, include_medium=include_medium)
    return new_ov, remap, report
