"""Slice 1 — graph operations on execution IR (language-agnostic)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def reachable_node_ids(
    entrypoints: list[str],
    edges: list[dict[str, Any]],
    *,
    kinds: frozenset[str] | None = None,
) -> set[str]:
    """
    Forward reachability from entrypoints along edges (optionally filter by edge kind).
    """
    if kinds is None:
        kinds = frozenset({"calls", "imports", "contains", "routes_to"})
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if not isinstance(e, dict):
            continue
        if e.get("kind") not in kinds:
            continue
        f, t = e.get("from"), e.get("to")
        if isinstance(f, str) and isinstance(t, str):
            adj[f].append(t)
    seen: set[str] = set()
    stack = [x for x in entrypoints if isinstance(x, str)]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        for t in adj.get(n, ()):
            if t not in seen:
                stack.append(t)
    return seen


def dead_candidates(node_ids: set[str], reachable: set[str]) -> set[str]:
    """Nodes that never appear in reachable (often 'dead' w.r.t. chosen entrypoints)."""
    return set(node_ids) - reachable


def maybe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Edges whose confidence is not 'resolved' (UI: dashed / uncertain)."""
    out: list[dict[str, Any]] = []
    for e in edges:
        if isinstance(e, dict) and e.get("confidence") != "resolved":
            out.append(e)
    return out
