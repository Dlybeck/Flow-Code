"""Generalized entrypoint detection for the execution IR.

Replaces the hardcoded FastAPI `create_app` heuristic with a multi-signal approach.

Detection tiers (from strongest to weakest signal):
  1. .flowcode.toml config override (exclusive: only matches in config are returned)
  2. Label ends in '.main' or equals 'main'
  3. App factory pattern (label ends in '.create_app', '.create_application', etc.)
  4. Route handler heuristic (no contains parent + outgoing unknown edges to app.* / router.*)
  5. Public package API: top-level functions defined in `__init__.py` files

Tiers 2–5 are **collected cumulatively** so that a project with both a CLI
entrypoint (`cli.main`) and a library API (`generate_graph` in `__init__.py`)
surfaces both. SlowCode's Delegator tier wants to enumerate all use cases, not
just the highest-priority one.

  6. Fallback: first node — only if tiers 2–5 produced nothing.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_flowcode_config(repo_root: Path) -> dict[str, Any]:
    """Load .flowcode.toml from repo root. Returns empty dict if not present."""
    p = repo_root / ".flowcode.toml"
    if not p.is_file():
        return {}
    try:
        with open(p, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _node_in_init_module(node: dict[str, Any]) -> bool:
    """True if the node lives in an `__init__.py` file (Python package init)."""
    loc = node.get("location") or {}
    path = str(loc.get("path", ""))
    return path.endswith("/__init__.py") or path == "__init__.py"


def detect_entrypoints(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """
    Detect entrypoint node IDs from an execution IR node/edge list.

    Args:
        nodes: list of IR node dicts (must have 'id' and 'label' keys; 'location'
               recommended for tier 5).
        edges: list of IR edge dicts.
        config: parsed .flowcode.toml dict (from load_flowcode_config).

    Returns:
        list of node ID strings that are entrypoints. Tiers 2–5 are unioned;
        results are de-duplicated while preserving discovery order.
    """
    if not nodes:
        return []

    cfg = config or {}

    # Tier 1: config override — exclusive. If config specifies entrypoints, use only those.
    ep_cfg = cfg.get("entrypoints", {})
    if isinstance(ep_cfg, dict):
        node_ids_set = {n["id"] for n in nodes if isinstance(n, dict)}
        explicit_ids = [
            ep for ep in ep_cfg.get("ids", [])
            if isinstance(ep, str) and ep in node_ids_set
        ]
        if explicit_ids:
            return explicit_ids

    # Build helper sets
    has_contains_parent: set[str] = set()
    unknown_callee_exprs: dict[str, list[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        if e.get("kind") == "contains" and e.get("confidence") == "resolved":
            child = e.get("to")
            if isinstance(child, str):
                has_contains_parent.add(child)
        if e.get("kind") == "calls" and e.get("confidence") == "unknown":
            fr = e.get("from")
            cs = e.get("callsite") or {}
            expr = cs.get("callee_expression") or cs.get("callee") or ""
            if isinstance(fr, str) and expr:
                unknown_callee_exprs.setdefault(fr, []).append(str(expr))

    real_nodes = [n for n in nodes if isinstance(n, dict) and n.get("id") and n.get("label")]

    collected: list[str] = []
    seen: set[str] = set()

    def _add(ids: list[str]) -> None:
        for nid in ids:
            if nid not in seen:
                seen.add(nid)
                collected.append(nid)

    # Tier 2: label ends in '.main' or equals 'main'
    _add([
        n["id"] for n in real_nodes
        if str(n["label"]).endswith(".main") or str(n["label"]) == "main"
    ])

    # Tier 3: app factory pattern
    factory_suffixes = (".create_app", ".create_application", ".make_app", ".build_app", ".init_app")
    _add([
        n["id"] for n in real_nodes
        if any(str(n["label"]).endswith(s) for s in factory_suffixes)
    ])

    # Tier 4: route handler heuristic — top-level nodes that call app.* / router.*
    route_prefixes = ("app.", "router.", "blueprint.", "api.")
    _add([
        n["id"] for n in real_nodes
        if n["id"] not in has_contains_parent
        and any(
            any(expr.startswith(p) for p in route_prefixes)
            for expr in unknown_callee_exprs.get(n["id"], [])
        )
    ])

    # Tier 5: public package API — top-level functions in __init__.py files
    _add([
        n["id"] for n in real_nodes
        if n["id"] not in has_contains_parent
        and _node_in_init_module(n)
    ])

    if collected:
        return collected

    # Tier 6: fallback — first real node
    return [real_nodes[0]["id"]]
