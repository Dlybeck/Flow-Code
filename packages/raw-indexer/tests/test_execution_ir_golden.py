from __future__ import annotations

from pathlib import Path

from raw_indexer.execution_ir import (
    build_execution_ir_from_raw,
    dead_candidates,
    dfs_visit_order,
    reachable_node_ids,
    validate_execution_ir,
)
from raw_indexer.index import index_repo


def test_golden_fastapi_execution_ir(
    golden_repo: Path,
) -> None:
    raw_doc = index_repo(golden_repo)
    ir = build_execution_ir_from_raw(raw_doc)
    assert validate_execution_ir(ir) == []

    quals = {n["label"] for n in ir["nodes"]}
    assert "golden_app.core.greeting_for" in quals
    assert "golden_app.app.create_app.greet" in quals

    greet_id = "py:fn:golden_app.app.create_app.greet"
    greet_to_id = "py:fn:golden_app.core.greeting_for"
    call_edges = [e for e in ir["edges"] if e["kind"] == "calls"]
    assert any(e["from"] == greet_id and e["to"] == greet_to_id for e in call_edges)

    eps = ir["entrypoints"]
    assert eps and all(x.startswith("py:fn:") for x in eps)
    reach = reachable_node_ids(eps, ir["edges"])
    assert greet_to_id in reach

    dead = dead_candidates({n["id"] for n in ir["nodes"]}, reach)
    assert greet_to_id not in dead

    order = dfs_visit_order(eps, ir["edges"], max_depth=8, max_children_per_node=16)
    assert any(e.node_id == greet_to_id and e.action == "enter" for e in order)
