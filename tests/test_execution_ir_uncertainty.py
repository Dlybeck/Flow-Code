from __future__ import annotations

from pathlib import Path

from flowcode.execution_ir import build_execution_ir_from_raw, validate_execution_ir
from flowcode.execution_ir.python_from_raw import BOUNDARY_UNRESOLVED_ID
from flowcode.index import index_repo


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
    bar_edges = [e for e in unk if e["from"] == foo_id]
    assert len(bar_edges) == 1, f"expected exactly 1 unknown edge from foo, got {len(bar_edges)}"
    assert bar_edges[0].get("callsite", {}).get("callee") == "bar"


def test_unknown_edges_not_multiplied_by_function_count(tmp_path: Path) -> None:
    """Regression: a file with multiple functions must not record the same
    unknown call multiple times. Pre-fix, python_from_raw iterated `for s in
    symbols:` and re-walked each file once per function in it, multiplying
    unknown_records by function count. Resolved edges were deduped via a set,
    so the bug was invisible to existing `assert any(...)` tests on goldens.
    """
    repo = tmp_path / "repo"
    pkg = repo / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "m.py").write_text(
        "def needs_thirdparty():\n"
        "    third_party_call()\n"
        "\n"
        "def helper_a():\n"
        "    return 1\n"
        "\n"
        "def helper_b():\n"
        "    return 2\n",
        encoding="utf-8",
    )

    raw_doc = index_repo(repo)
    ir = build_execution_ir_from_raw(raw_doc)
    needs_id = "py:fn:pkg.m.needs_thirdparty"
    unk = [
        e
        for e in ir["edges"]
        if e["kind"] == "calls"
        and e["confidence"] == "unknown"
        and e["from"] == needs_id
    ]
    assert len(unk) == 1, (
        f"expected exactly 1 unknown edge for one third_party_call() in source, "
        f"got {len(unk)} (would be 3 pre-fix because m.py has 3 functions)"
    )
    assert unk[0]["callsite"]["callee"] == "third_party_call"


def test_golden_has_third_party_unresolved_call(golden_repo: Path) -> None:
    """create_app() constructs FastAPI(...); callee is not in the index → unknown edge.

    Asserts exact count: pre-fix this would have been 4 (file had 4 functions).
    """
    raw_doc = index_repo(golden_repo)
    ir = build_execution_ir_from_raw(raw_doc)
    create_id = "py:fn:golden_app.app.create_app"
    to_b = [
        e
        for e in ir["edges"]
        if e["from"] == create_id
        and e["to"] == BOUNDARY_UNRESOLVED_ID
        and e["confidence"] == "unknown"
    ]
    fastapi_edges = [
        e for e in to_b if (e.get("callsite") or {}).get("callee") == "FastAPI"
    ]
    assert len(fastapi_edges) == 1, (
        f"create_app() calls FastAPI(...) exactly once; got {len(fastapi_edges)} edges"
    )
    assert fastapi_edges[0]["callsite"]["import_ref"] == "fastapi.FastAPI"
