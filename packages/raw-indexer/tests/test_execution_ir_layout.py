from __future__ import annotations

from raw_indexer.execution_ir.layout import dfs_visit_order


def test_dfs_visit_order_linear() -> None:
    edges = [
        {"from": "a", "to": "b", "kind": "calls", "confidence": "resolved"},
        {"from": "b", "to": "c", "kind": "calls", "confidence": "resolved"},
    ]
    ev = dfs_visit_order(["a"], edges, max_depth=10, max_children_per_node=10)
    enters = [e.node_id for e in ev if e.action == "enter"]
    assert enters == ["a", "b", "c"]


def test_dfs_respects_max_depth() -> None:
    edges = [
        {"from": "a", "to": "b", "kind": "calls", "confidence": "resolved"},
        {"from": "b", "to": "c", "kind": "calls", "confidence": "resolved"},
    ]
    ev = dfs_visit_order(["a"], edges, max_depth=1, max_children_per_node=10)
    enters = [e.node_id for e in ev if e.action == "enter"]
    assert enters == ["a", "b"]
