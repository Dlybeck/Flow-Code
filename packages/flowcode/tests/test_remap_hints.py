"""Phase 4: remap hints inside flowcode diff (symbols + files)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from flowcode.diff_raw import diff_raw_dicts
from flowcode.index import index_repo
from flowcode.remap_hints import build_remap_hints


def _minimal_raw(
    *,
    files: list[dict],
    symbols: list[dict],
    edges: list | None = None,
) -> dict:
    return {
        "schema_version": 0,
        "indexer": "test",
        "root": "/tmp",
        "files": files,
        "symbols": symbols,
        "edges": edges or [],
    }


def test_identical_docs_empty_remap() -> None:
    doc = _minimal_raw(
        files=[{"id": "file:a.py", "path": "a.py", "sha256": "1"}],
        symbols=[
            {
                "id": "sym:a.py:m.mod.f",
                "kind": "function",
                "name": "f",
                "qualified_name": "m.mod.f",
                "file_id": "file:a.py",
                "line": 1,
                "end_line": 1,
            }
        ],
    )
    d = diff_raw_dicts(doc, json.loads(json.dumps(doc)))
    assert d["symbols"]["added"] == []
    assert d["symbols"]["removed"] == []
    assert d["remap"]["symbols"]["high"] == []
    assert d["remap"]["symbols"]["medium"] == []
    assert d["remap"]["files"]["medium"] == []


def test_symbol_high_unique_qualified_name() -> None:
    old = _minimal_raw(
        files=[
            {"id": "file:old.py", "path": "old.py", "sha256": "1"},
        ],
        symbols=[
            {
                "id": "sym:old.py:pkg.f",
                "kind": "function",
                "name": "f",
                "qualified_name": "pkg.f",
                "file_id": "file:old.py",
                "line": 1,
                "end_line": 2,
            }
        ],
    )
    new = _minimal_raw(
        files=[
            {"id": "file:new.py", "path": "new.py", "sha256": "2"},
        ],
        symbols=[
            {
                "id": "sym:new.py:pkg.f",
                "kind": "function",
                "name": "f",
                "qualified_name": "pkg.f",
                "file_id": "file:new.py",
                "line": 1,
                "end_line": 2,
            }
        ],
    )
    d = diff_raw_dicts(old, new)
    high = d["remap"]["symbols"]["high"]
    assert len(high) == 1
    assert high[0]["confidence"] == "high"
    assert high[0]["from_id"] == "sym:old.py:pkg.f"
    assert high[0]["to_id"] == "sym:new.py:pkg.f"


def test_symbol_ambiguous_qualified_name() -> None:
    old = _minimal_raw(
        files=[{"id": "file:a.py", "path": "a.py", "sha256": "1"}],
        symbols=[
            {
                "id": "sym:a.py:pkg.f1",
                "kind": "function",
                "name": "f",
                "qualified_name": "pkg.f",
                "file_id": "file:a.py",
                "line": 1,
                "end_line": 1,
            },
            {
                "id": "sym:a.py:pkg.f2",
                "kind": "function",
                "name": "f",
                "qualified_name": "pkg.f",
                "file_id": "file:a.py",
                "line": 3,
                "end_line": 3,
            },
        ],
    )
    new = _minimal_raw(
        files=[{"id": "file:b.py", "path": "b.py", "sha256": "2"}],
        symbols=[
            {
                "id": "sym:b.py:pkg.f3",
                "kind": "function",
                "name": "f",
                "qualified_name": "pkg.f",
                "file_id": "file:b.py",
                "line": 1,
                "end_line": 1,
            },
            {
                "id": "sym:b.py:pkg.f4",
                "kind": "function",
                "name": "f",
                "qualified_name": "pkg.f",
                "file_id": "file:b.py",
                "line": 3,
                "end_line": 3,
            },
        ],
    )
    d = diff_raw_dicts(old, new)
    assert d["remap"]["symbols"]["high"] == []
    amb = d["remap"]["symbols"]["ambiguous_qualified_name"]
    assert len(amb) == 1
    assert amb[0]["qualified_name"] == "pkg.f"
    assert len(amb[0]["removed_ids"]) == 2
    assert len(amb[0]["added_ids"]) == 2


def test_symbol_medium_kind_name_parent_dir() -> None:
    """Same package directory, moved between modules — qualified_name differs."""
    old = _minimal_raw(
        files=[
            {"id": "file:src/pkg/a.py", "path": "src/pkg/a.py", "sha256": "1"},
            {"id": "file:src/pkg/b.py", "path": "src/pkg/b.py", "sha256": "2"},
        ],
        symbols=[
            {
                "id": "sym:src/pkg/a.py:pkg.a.add",
                "kind": "function",
                "name": "add",
                "qualified_name": "pkg.a.add",
                "file_id": "file:src/pkg/a.py",
                "line": 1,
                "end_line": 2,
            }
        ],
    )
    new = _minimal_raw(
        files=[
            {"id": "file:src/pkg/a.py", "path": "src/pkg/a.py", "sha256": "3"},
            {"id": "file:src/pkg/b.py", "path": "src/pkg/b.py", "sha256": "4"},
        ],
        symbols=[
            {
                "id": "sym:src/pkg/b.py:pkg.b.add",
                "kind": "function",
                "name": "add",
                "qualified_name": "pkg.b.add",
                "file_id": "file:src/pkg/b.py",
                "line": 1,
                "end_line": 2,
            }
        ],
    )
    d = diff_raw_dicts(old, new)
    med = d["remap"]["symbols"]["medium"]
    assert len(med) == 1
    assert med[0]["confidence"] == "medium"
    assert med[0]["parent_dir"] == "src/pkg"
    assert med[0]["from_id"] == "sym:src/pkg/a.py:pkg.a.add"
    assert med[0]["to_id"] == "sym:src/pkg/b.py:pkg.b.add"


def test_file_medium_unique_basename() -> None:
    old = _minimal_raw(
        files=[{"id": "file:src/old/util.py", "path": "src/old/util.py", "sha256": "1"}],
        symbols=[],
    )
    new = _minimal_raw(
        files=[{"id": "file:src/new/util.py", "path": "src/new/util.py", "sha256": "2"}],
        symbols=[],
    )
    d = diff_raw_dicts(old, new)
    fm = d["remap"]["files"]["medium"]
    assert len(fm) == 1
    assert fm[0]["basename"] == "util.py"
    assert fm[0]["from_id"] == "file:src/old/util.py"
    assert fm[0]["to_id"] == "file:src/new/util.py"


def test_build_remap_hints_direct_call() -> None:
    """Smoke: API usable without full diff wrapper."""
    sa = {
        "s1": {
            "id": "s1",
            "kind": "function",
            "name": "f",
            "qualified_name": "m.f",
            "file_id": "file:a.py",
            "line": 1,
            "end_line": 1,
        }
    }
    sb = {
        "s2": {
            "id": "s2",
            "kind": "function",
            "name": "f",
            "qualified_name": "m.f",
            "file_id": "file:b.py",
            "line": 1,
            "end_line": 1,
        }
    }
    old_doc = _minimal_raw(
        files=[{"id": "file:a.py", "path": "a.py", "sha256": "1"}],
        symbols=[sa["s1"]],
    )
    new_doc = _minimal_raw(
        files=[{"id": "file:b.py", "path": "b.py", "sha256": "2"}],
        symbols=[sb["s2"]],
    )
    r = build_remap_hints(
        old_doc,
        new_doc,
        sym_removed=["s1"],
        sym_added=["s2"],
        files_removed=["a.py"],
        files_added=["b.py"],
        sa=sa,
        sb=sb,
    )
    assert len(r["symbols"]["high"]) == 1


def test_golden_no_false_positive_on_identical_index(golden_repo: Path, tmp_path: Path) -> None:
    doc = index_repo(golden_repo)
    p = tmp_path / "x.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    d = diff_raw_dicts(doc, json.loads(p.read_text(encoding="utf-8")))
    assert d["remap"]["symbols"]["high"] == []
    assert d["remap"]["symbols"]["medium"] == []
    assert d["remap"]["symbols"]["ambiguous_qualified_name"] == []
    assert d["remap"]["files"]["medium"] == []


def test_golden_move_function_between_modules(tmp_path: Path) -> None:
    """Real index: move `add` from a.py to b.py under same package dir."""
    src = tmp_path / "proj" / "src" / "mvpkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a.py").write_text(
        "def add():\n    return 40 + 2\n",
        encoding="utf-8",
    )
    (src / "b.py").write_text("# placeholder\n", encoding="utf-8")
    root = tmp_path / "proj"
    before = index_repo(root)

    (src / "a.py").write_text("# moved\n", encoding="utf-8")
    (src / "b.py").write_text(
        "def add():\n    return 40 + 2\n",
        encoding="utf-8",
    )
    after = index_repo(root)
    d = diff_raw_dicts(before, after)
    med = d["remap"]["symbols"]["medium"]
    assert med, "expected medium-confidence remap for same-dir move"
    pair = med[0]
    assert "add" in pair["from_id"] or "add" in pair.get("name", "")
    assert pair["confidence"] == "medium"


def test_diff_cli_includes_remap(tmp_path: Path, golden_repo: Path) -> None:
    from flowcode.diff_raw import diff_raw

    a = index_repo(golden_repo)
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    p1.write_text(json.dumps(a), encoding="utf-8")
    shutil.copy(p1, p2)
    d = diff_raw(p1, p2)
    assert "remap" in d
    assert "note" in d["remap"]
