"""overlay-migrate: rewrite overlay keys from diff.remap."""

from __future__ import annotations

import json
from pathlib import Path

from raw_indexer.index import index_repo
from raw_indexer.overlay import overlay_orphan_keys
from raw_indexer.overlay_migrate import migrate_overlay_from_remap, migrate_overlay_files


def test_migrate_symbol_high(tmp_path: Path) -> None:
    remap = {
        "symbols": {
            "high": [
                {
                    "from_id": "sym:old.py:pkg.f",
                    "to_id": "sym:new.py:pkg.f",
                    "confidence": "high",
                }
            ],
            "medium": [],
            "ambiguous_qualified_name": [],
            "ambiguous_kind_name_dir": [],
        },
        "files": {"medium": [], "ambiguous_basename": []},
    }
    overlay = {
        "schema_version": 0,
        "by_symbol_id": {
            "sym:old.py:pkg.f": {"displayName": "F"},
        },
        "by_file_id": {},
    }
    new_ov, rep = migrate_overlay_from_remap(overlay, remap)
    assert "sym:old.py:pkg.f" not in new_ov["by_symbol_id"]
    assert new_ov["by_symbol_id"]["sym:new.py:pkg.f"]["displayName"] == "F"
    assert rep["symbols_moved"]


def test_migrate_merge_collision(tmp_path: Path) -> None:
    remap = {
        "symbols": {
            "high": [
                {
                    "from_id": "sym:a.py:pkg.f",
                    "to_id": "sym:b.py:pkg.f",
                    "confidence": "high",
                }
            ],
            "medium": [],
            "ambiguous_qualified_name": [],
            "ambiguous_kind_name_dir": [],
        },
        "files": {"medium": [], "ambiguous_basename": []},
    }
    overlay = {
        "by_symbol_id": {
            "sym:a.py:pkg.f": {"displayName": "From A"},
            "sym:b.py:pkg.f": {"userDescription": "Existing B"},
        },
        "by_file_id": {},
    }
    new_ov, rep = migrate_overlay_from_remap(overlay, remap)
    assert "sym:a.py:pkg.f" not in new_ov["by_symbol_id"]
    merged = new_ov["by_symbol_id"]["sym:b.py:pkg.f"]
    assert merged["displayName"] == "From A"
    assert merged["userDescription"] == "Existing B"
    assert rep["symbols_merged"]


def test_migrate_file_medium() -> None:
    remap = {
        "symbols": {"high": [], "medium": [], "ambiguous_qualified_name": [], "ambiguous_kind_name_dir": []},
        "files": {
            "medium": [
                {
                    "from_id": "file:src/old/x.py",
                    "to_id": "file:src/new/x.py",
                    "confidence": "medium",
                }
            ],
            "ambiguous_basename": [],
        },
    }
    overlay = {
        "by_file_id": {"file:src/old/x.py": {"displayName": "X"}},
        "by_symbol_id": {},
    }
    new_ov, rep = migrate_overlay_from_remap(overlay, remap)
    assert "file:src/old/x.py" not in new_ov["by_file_id"]
    assert new_ov["by_file_id"]["file:src/new/x.py"]["displayName"] == "X"
    assert rep["files_moved"]


def test_migrate_end_to_end_move(tmp_path: Path) -> None:
    """Move function between modules: overlay on old id → migrate → valid for new RAW."""
    src = tmp_path / "proj" / "src" / "mvpkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a.py").write_text("def add():\n    return 42\n", encoding="utf-8")
    (src / "b.py").write_text("# x\n", encoding="utf-8")
    root = tmp_path / "proj"
    before = index_repo(root)
    old_sym = next(s["id"] for s in before["symbols"] if s["name"] == "add")

    (src / "a.py").write_text("# moved\n", encoding="utf-8")
    (src / "b.py").write_text("def add():\n    return 42\n", encoding="utf-8")
    after = index_repo(root)
    new_sym = next(s["id"] for s in after["symbols"] if s["name"] == "add")

    overlay = {
        "schema_version": 0,
        "by_symbol_id": {old_sym: {"displayName": "Add fn"}},
        "by_file_id": {},
    }
    p_old = tmp_path / "before.json"
    p_new = tmp_path / "after.json"
    p_old.write_text(json.dumps(before), encoding="utf-8")
    p_new.write_text(json.dumps(after), encoding="utf-8")
    p_ov = tmp_path / "ov.json"
    p_ov.write_text(json.dumps(overlay), encoding="utf-8")

    new_ov, _diff, rep = migrate_overlay_files(p_old, p_new, p_ov, include_medium=True)
    assert rep["symbols_moved"] or rep["symbols_merged"]
    orphans = overlay_orphan_keys(new_ov, after)
    assert old_sym not in new_ov["by_symbol_id"]
    assert new_sym in new_ov["by_symbol_id"]
    assert new_sym not in orphans
