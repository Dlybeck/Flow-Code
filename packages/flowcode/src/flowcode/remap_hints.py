"""Heuristic remap hints between two RAW snapshots (Phase 4 — overlay / id drift).

Suggestions are for human or scripted follow-up; they are not proof of identity.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any


def _path_for_file_id(doc: dict[str, Any], file_id: str) -> str | None:
    for f in doc.get("files", []):
        if f.get("id") == file_id:
            return str(f.get("path", ""))
    return None


def _parent_dir_posix(path: str) -> str:
    if not path:
        return ""
    return Path(path).parent.as_posix()


def build_remap_hints(
    old_doc: dict[str, Any],
    new_doc: dict[str, Any],
    *,
    sym_removed: list[str],
    sym_added: list[str],
    files_removed: list[str],
    files_added: list[str],
    sa: dict[str, dict[str, Any]],
    sb: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    removed_objs = [sa[i] for i in sym_removed if i in sa]
    added_objs = [sb[i] for i in sym_added if i in sb]

    used_rem: set[str] = set()
    used_add: set[str] = set()

    by_qn_r: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in removed_objs:
        qn = str(s.get("qualified_name", ""))
        by_qn_r[qn].append(s)
    by_qn_a: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in added_objs:
        qn = str(s.get("qualified_name", ""))
        by_qn_a[qn].append(s)

    sym_high: list[dict[str, Any]] = []
    amb_qn: list[dict[str, Any]] = []

    common_qn = set(by_qn_r) & set(by_qn_a)
    for qn in sorted(common_qn):
        rs, ass = by_qn_r[qn], by_qn_a[qn]
        if len(rs) == 1 and len(ass) == 1:
            sym_high.append(
                {
                    "from_id": rs[0]["id"],
                    "to_id": ass[0]["id"],
                    "qualified_name": qn,
                    "confidence": "high",
                    "reason": "unique_qualified_name_match",
                }
            )
            used_rem.add(rs[0]["id"])
            used_add.add(ass[0]["id"])
        elif rs and ass:
            amb_qn.append(
                {
                    "qualified_name": qn,
                    "removed_ids": [x["id"] for x in rs],
                    "added_ids": [x["id"] for x in ass],
                }
            )

    remaining_r = [s for s in removed_objs if s["id"] not in used_rem]
    remaining_a = [s for s in added_objs if s["id"] not in used_add]

    key_r: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in remaining_r:
        path = _path_for_file_id(old_doc, str(s.get("file_id", "")))
        d = _parent_dir_posix(path or "")
        key = (str(s.get("kind", "")), str(s.get("name", "")), d)
        key_r[key].append(s)

    key_a: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in remaining_a:
        path = _path_for_file_id(new_doc, str(s.get("file_id", "")))
        d = _parent_dir_posix(path or "")
        key = (str(s.get("kind", "")), str(s.get("name", "")), d)
        key_a[key].append(s)

    sym_medium: list[dict[str, Any]] = []
    amb_key: list[dict[str, Any]] = []

    for key in sorted(set(key_r) & set(key_a), key=lambda k: (k[2], k[1], k[0])):
        rs, ass = key_r[key], key_a[key]
        kind, name, pdir = key
        if len(rs) == 1 and len(ass) == 1:
            sym_medium.append(
                {
                    "from_id": rs[0]["id"],
                    "to_id": ass[0]["id"],
                    "confidence": "medium",
                    "reason": "unique_kind_name_parent_dir_match",
                    "kind": kind,
                    "name": name,
                    "parent_dir": pdir,
                }
            )
        elif rs and ass:
            amb_key.append(
                {
                    "kind": kind,
                    "name": name,
                    "parent_dir": pdir,
                    "removed_ids": [x["id"] for x in rs],
                    "added_ids": [x["id"] for x in ass],
                }
            )

    rb: dict[str, list[str]] = defaultdict(list)
    for p in files_removed:
        rb[Path(p).name].append(p)
    ab: dict[str, list[str]] = defaultdict(list)
    for p in files_added:
        ab[Path(p).name].append(p)

    file_medium: list[dict[str, Any]] = []
    amb_file: list[dict[str, Any]] = []

    for name in sorted(set(rb) & set(ab)):
        rlist, alist = rb[name], ab[name]
        if len(rlist) == 1 and len(alist) == 1:
            file_medium.append(
                {
                    "from_id": f"file:{rlist[0]}",
                    "to_id": f"file:{alist[0]}",
                    "confidence": "medium",
                    "reason": "unique_basename_match",
                    "basename": name,
                }
            )
        elif rlist and alist:
            amb_file.append(
                {
                    "basename": name,
                    "removed_paths": sorted(rlist),
                    "added_paths": sorted(alist),
                }
            )

    return {
        "note": (
            "Heuristic suggestions for overlay key migration and human review — "
            "not proof of logical sameness."
        ),
        "symbols": {
            "high": sym_high,
            "medium": sym_medium,
            "ambiguous_qualified_name": amb_qn,
            "ambiguous_kind_name_dir": amb_key,
        },
        "files": {
            "medium": file_medium,
            "ambiguous_basename": amb_file,
        },
    }
