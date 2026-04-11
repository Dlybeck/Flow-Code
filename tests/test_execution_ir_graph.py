from __future__ import annotations

from flowcode.execution_ir.graph import dead_candidates, maybe_edges, reachable_node_ids


def test_reachable_follows_calls() -> None:
    edges = [
        {"from": "a", "to": "b", "kind": "calls", "confidence": "resolved"},
        {"from": "b", "to": "c", "kind": "calls", "confidence": "resolved"},
    ]
    r = reachable_node_ids(["a"], edges)
    assert r == {"a", "b", "c"}


def test_reachable_respects_kind_filter() -> None:
    edges = [
        {"from": "a", "to": "b", "kind": "calls", "confidence": "resolved"},
        {"from": "a", "to": "x", "kind": "imports", "confidence": "resolved"},
    ]
    r = reachable_node_ids(["a"], edges, kinds=frozenset({"calls"}))
    assert r == {"a", "b"}


def test_dead_candidates() -> None:
    nodes = {"a", "b", "z"}
    r = {"a", "b"}
    assert dead_candidates(nodes, r) == {"z"}


def test_maybe_edges() -> None:
    edges = [
        {"from": "a", "to": "b", "kind": "calls", "confidence": "resolved"},
        {"from": "a", "to": "c", "kind": "calls", "confidence": "unknown"},
    ]
    m = maybe_edges(edges)
    assert len(m) == 1 and m[0]["to"] == "c"
