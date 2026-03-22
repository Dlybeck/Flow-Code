"""Slice 2 — presentation-only visit order (DFS with limits)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisitEvent:
    """One step in a depth-first walk (backtracking explicit via exit)."""

    action: str  # "enter" | "exit"
    node_id: str
    depth: int


def dfs_visit_order(
    entrypoints: list[str],
    edges: list[dict[str, Any]],
    *,
    max_depth: int = 32,
    max_children_per_node: int = 64,
    kinds: frozenset[str] | None = None,
) -> list[VisitEvent]:
    """
    Deterministic DFS: successors sorted by `to` id; truncated by depth and branching.
    Only follows edges in `kinds` (default: calls + contains).
    """
    if kinds is None:
        kinds = frozenset({"calls", "contains"})
    adj: dict[str, list[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        if e.get("kind") not in kinds:
            continue
        f, t = e.get("from"), e.get("to")
        if not isinstance(f, str) or not isinstance(t, str):
            continue
        adj.setdefault(f, []).append(t)
    for k in adj:
        adj[k] = sorted(set(adj[k]))

    events: list[VisitEvent] = []
    visited_stack: list[str] = []

    def dfs(node: str, depth: int) -> None:
        if depth > max_depth:
            return
        if node in visited_stack:
            return
        visited_stack.append(node)
        events.append(VisitEvent("enter", node, depth))
        children = adj.get(node, [])[:max_children_per_node]
        for c in children:
            dfs(c, depth + 1)
        visited_stack.pop()
        events.append(VisitEvent("exit", node, depth))

    for ep in entrypoints:
        if isinstance(ep, str):
            dfs(ep, 0)
    return events
