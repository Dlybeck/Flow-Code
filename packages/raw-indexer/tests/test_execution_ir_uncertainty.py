from __future__ import annotations

from pathlib import Path

from raw_indexer.execution_ir import build_execution_ir_from_raw, validate_execution_ir
from raw_indexer.execution_ir.python_from_raw import BOUNDARY_UNRESOLVED_ID
from raw_indexer.index import index_repo


def test_unresolved_name_emits_unknown_edge_to_boundary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    pkg = repo / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "m.py").write_text(
        "def foo():\n    bar()\n",
        encoding="utf-8",
    )

    raw_doc = index_repo(repo)
    ir = build_execution_ir_from_raw(raw_doc)
    assert validate_execution_ir(ir) == []

    assert any(n["id"] == BOUNDARY_UNRESOLVED_ID for n in ir["nodes"])
    foo_id = "py:fn:pkg.m.foo"
    unk = [
        e
        for e in ir["edges"]
        if e["kind"] == "calls"
        and e["confidence"] == "unknown"
        and e["to"] == BOUNDARY_UNRESOLVED_ID
    ]
    assert any(e["from"] == foo_id for e in unk)


def test_golden_has_third_party_unresolved_call(golden_repo: Path) -> None:
    """create_app() constructs FastAPI(...); callee is not in the index → unknown edge."""
    raw_doc = index_repo(golden_repo)
    ir = build_execution_ir_from_raw(raw_doc)
    create_id = "py:fn:golden_app.app.create_app"
    assert any(
        e["from"] == create_id
        and e["to"] == BOUNDARY_UNRESOLVED_ID
        and e["confidence"] == "unknown"
        for e in ir["edges"]
    )
