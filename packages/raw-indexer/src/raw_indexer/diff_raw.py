"""Compare two RAW JSON documents (v0 schema) + Phase 4 remap hints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raw_indexer.remap_hints import build_remap_hints


def _load(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _file_map(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["path"]: f for f in doc.get("files", [])}


def _sym_map(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in doc.get("symbols", [])}


def diff_raw_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    fa, fb = _file_map(a), _file_map(b)
    sa, sb = _sym_map(a), _sym_map(b)

    paths_a, paths_b = set(fa), set(fb)
    files_added = sorted(paths_b - paths_a)
    files_removed = sorted(paths_a - paths_b)
    files_changed: list[dict[str, Any]] = []
    for p in sorted(paths_a & paths_b):
        if fa[p]["sha256"] != fb[p]["sha256"]:
            files_changed.append(
                {
                    "path": p,
                    "old_sha256": fa[p]["sha256"],
                    "new_sha256": fb[p]["sha256"],
                }
            )

    ids_a, ids_b = set(sa), set(sb)
    sym_added = sorted(ids_b - ids_a)
    sym_removed = sorted(ids_a - ids_b)
    sym_changed: list[dict[str, Any]] = []
    for sid in sorted(ids_a & ids_b):
        ca, cb = sa[sid], sb[sid]
        keys = ("kind", "name", "line", "end_line", "qualified_name", "file_id")
        if any(ca.get(k) != cb.get(k) for k in keys):
            sym_changed.append(
                {"id": sid, "before": {k: ca.get(k) for k in keys}, "after": {k: cb.get(k) for k in keys}}
            )

    remap = build_remap_hints(
        a,
        b,
        sym_removed=sym_removed,
        sym_added=sym_added,
        files_removed=files_removed,
        files_added=files_added,
        sa=sa,
        sb=sb,
    )

    return {
        "schema_version": 0,
        "files": {
            "added": files_added,
            "removed": files_removed,
            "changed": files_changed,
        },
        "symbols": {
            "added": sym_added,
            "removed": sym_removed,
            "changed": sym_changed,
        },
        "remap": remap,
    }


def diff_raw(old_path: Path | str, new_path: Path | str) -> dict[str, Any]:
    return diff_raw_dicts(_load(old_path), _load(new_path))


def format_diff_report(d: dict[str, Any]) -> str:
    return json.dumps(d, indent=2, sort_keys=True) + "\n"
