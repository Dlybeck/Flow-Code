"""Flow-Code MCP server — exposes the pinned node + graph to an AI client.

Tools:
  get_selection()       → pinned node ref, or None
  get_node(ref)         → full node metadata from graph.json
  get_neighbors(ref)    → {callers: [...], callees: [...]} one hop
  get_source(ref)       → raw function source, re-parsed from disk

Run via stdio (for Claude Code / OpenCode / MCP Inspector):
  mcp dev sidecar/mcp_server.py
or register in .mcp.json.
"""
from __future__ import annotations

import json
import sys
from functools import cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
SELECTION_FILE = Path("/tmp/flowcode-selection.json")
GRAPH_FILE = ROOT / "graph.json"

# Make parse_calls importable (sibling module).
sys.path.insert(0, str(ROOT))
from parse_calls import parse_directory  # noqa: E402

mcp = FastMCP("flowcode")


@cache
def _graph() -> dict:
    return json.loads(GRAPH_FILE.read_text())


@cache
def _node_index() -> dict[str, dict]:
    return {n["id"]: n for n in _graph()["nodes"]}


@cache
def _edge_index() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    callees: dict[str, list[str]] = {}
    callers: dict[str, list[str]] = {}
    for e in _graph()["edges"]:
        callees.setdefault(e["from"], []).append(e["to"])
        callers.setdefault(e["to"], []).append(e["from"])
    return callees, callers


@cache
def _primary_lookup() -> dict[tuple[str, str], bool]:
    """(from, to) -> is_primary for every edge. Primary = ski-slope spine."""
    return {(e["from"], e["to"]): bool(e.get("is_primary")) for e in _graph()["edges"]}


@cache
def _sources() -> dict[str, str]:
    """Re-parse the source tree on demand to get per-function source text.
    graph.json doesn't carry source bodies (keeps it small), so we reparse."""
    src_root = Path(_graph()["root"])
    if not src_root.exists():
        return {}
    return {q: info.source for q, info in parse_directory(src_root).items()}


@cache
def _source_lines() -> dict[str, tuple[int, int]]:
    """qname -> (line_start, line_end) within the function's file."""
    src_root = Path(_graph()["root"])
    if not src_root.exists():
        return {}
    return {
        q: (info.lineno, info.end_lineno)
        for q, info in parse_directory(src_root).items()
    }


def _abs_file(rel: str) -> str:
    """Resolve a node's relative file against the graph's source root."""
    return str(Path(_graph()["root"]) / rel)


REF_PREFIX = "@flowcode:"


def _canon_ref(ref: str | None) -> str | None:
    """Accept both bare qnames (`Parser.parse`) and the UI's clipboard format
    (`@flowcode:Parser.parse`). The latter is what the "Copy ref" button emits."""
    if not ref:
        return ref
    if ref.startswith(REF_PREFIX):
        return ref[len(REF_PREFIX):]
    return ref


def _node_summary(n: dict) -> dict[str, Any]:
    return {
        "id": n["id"],
        "qname": n["qname"],
        "file": n["file"],
        "abs_file": _abs_file(n["file"]),
        "class": n.get("class"),
        "depth": n["depth"],
        "description": n.get("description", ""),
    }


@mcp.tool()
def get_selection() -> dict | None:
    """Return the node currently pinned in the viz, or None if nothing is pinned."""
    if not SELECTION_FILE.exists():
        return None
    try:
        data = json.loads(SELECTION_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable selection file — treat as "nothing pinned".
        return None
    node_id = data.get("id") if isinstance(data, dict) else None
    if not node_id:
        return None
    n = _node_index().get(node_id)
    return _node_summary(n) if n else None


@mcp.tool()
def get_node(ref: str) -> dict | None:
    """Full metadata for a node, looked up by qname/id.

    Accepts bare qname (`Parser.parse`) or the UI clipboard format
    (`@flowcode:Parser.parse`).
    """
    ref = _canon_ref(ref)
    n = _node_index().get(ref)
    if not n:
        return None
    out = {k: v for k, v in n.items() if k not in ("x_fan", "y_fan", "x_umap", "y_umap", "height")}
    out["abs_file"] = _abs_file(n["file"])
    return out


@mcp.tool()
def get_neighbors(ref: str) -> dict:
    """One-hop callers and callees for a node.

    Returns each neighbor as a summary dict (qname, file, depth, description)
    so the caller doesn't need a follow-up get_node per neighbor just to show
    a "callers: [...]" list with context. Each neighbor also has `is_primary`
    indicating whether the edge is a ski-slope spine edge.
    """
    ref = _canon_ref(ref)
    callees, callers = _edge_index()
    idx = _node_index()
    pl = _primary_lookup()

    def _resolve(ref_list: list[str], direction: str) -> list[dict]:
        out = []
        for r in ref_list:
            n = idx.get(r)
            entry = _node_summary(n) if n else {"id": r, "qname": r}
            # Primary edges run from caller → callee. For a callee list
            # (direction=callees) the edge is (ref, r). For callers, (r, ref).
            edge = (ref, r) if direction == "callees" else (r, ref)
            entry["is_primary"] = pl.get(edge, False)
            out.append(entry)
        return out

    return {
        "callers": _resolve(callers.get(ref, []), "callers"),
        "callees": _resolve(callees.get(ref, []), "callees"),
    }


@mcp.tool()
def get_source(ref: str) -> dict | None:
    """Raw source of the function plus its location in the file.

    Returns {body, line_start, line_end, abs_file} so the caller can feed
    the location into its own Read/Edit tools. None if ref is unknown.
    """
    ref = _canon_ref(ref)
    body = _sources().get(ref)
    if body is None:
        return None
    line_start, line_end = _source_lines().get(ref, (0, 0))
    n = _node_index().get(ref)
    abs_file = _abs_file(n["file"]) if n else None
    return {
        "body": body,
        "line_start": line_start,
        "line_end": line_end,
        "abs_file": abs_file,
    }


_BFS_MAX_RESULTS = 100  # hard cap so a depth=6 fan-out doesn't flood the AI's context


def _bfs(ref: str, edge_map: dict[str, list[str]], max_depth: int) -> list[dict]:
    idx = _node_index()
    if ref not in idx:
        return []
    seen = {ref}
    frontier = [ref]
    out: list[dict] = []
    hop = 0
    while frontier and hop < max_depth and len(out) < _BFS_MAX_RESULTS:
        hop += 1
        next_frontier: list[str] = []
        for cur in frontier:
            for nb in edge_map.get(cur, []):
                if nb in seen:
                    continue
                seen.add(nb)
                n = idx.get(nb)
                if n:
                    summary = _node_summary(n)
                    summary["hops"] = hop
                    out.append(summary)
                    if len(out) >= _BFS_MAX_RESULTS:
                        break
                next_frontier.append(nb)
            if len(out) >= _BFS_MAX_RESULTS:
                break
        frontier = next_frontier
    return out


@mcp.tool()
def get_ancestors(ref: str, max_depth: int = 6) -> list[dict]:
    """All transitive callers of `ref` up to `max_depth` hops, BFS order.

    Each entry is a node summary plus an `hops` field (1 = direct caller,
    2 = caller's caller, ...). Use this instead of chaining get_neighbors
    when you want the chain to an entry point.
    """
    ref = _canon_ref(ref)
    _callees, callers = _edge_index()
    return _bfs(ref, callers, max_depth)


@mcp.tool()
def get_descendants(ref: str, max_depth: int = 3) -> list[dict]:
    """All transitive callees of `ref` up to `max_depth` hops, BFS order.

    Default depth is smaller than get_ancestors because call trees fan out
    fast. Each entry includes an `hops` field.
    """
    ref = _canon_ref(ref)
    callees, _callers = _edge_index()
    return _bfs(ref, callees, max_depth)


@mcp.tool()
def grep_source(pattern: str, limit: int = 30, ignore_case: bool = True) -> list[dict]:
    """Regex search across every function's source. Returns one entry per
    matching function with the first matched line and its local line number.

    Collapses N get_source + client-side regex calls into one server call.
    Good for 'which functions write to disk / spawn processes / use asyncio'.
    """
    import re

    if not pattern.strip():
        return []
    flags = re.IGNORECASE if ignore_case else 0
    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        return [{"error": f"bad regex: {e}"}]
    # Restrict to nodes that are actually in the graph — parse_directory picks
    # up every function in the source tree, but the selection surface is the
    # graph, so results that can't be pinned are just noise.
    idx = _node_index()
    sources = _sources()
    out: list[dict] = []
    for qname, n in idx.items():
        src = sources.get(qname)
        if not src:
            continue
        for i, line in enumerate(src.splitlines(), start=1):
            if rx.search(line):
                out.append({
                    "qname": qname,
                    "file": n["file"],
                    "line": i,
                    "match": line.strip()[:160],
                })
                break
        if len(out) >= limit:
            break
    return out


@mcp.tool()
def search(query: str, limit: int = 10) -> list[dict]:
    """Find nodes whose qname or file contains `query` (case-insensitive).

    Useful when the user names a function in chat instead of pinning it.
    Returns up to `limit` node summaries. Empty query returns [].
    """
    q = query.strip().lower()
    if not q:
        return []
    out: list[dict] = []
    for n in _node_index().values():
        hay = (n["qname"] + " " + n["file"]).lower()
        if q in hay:
            out.append(_node_summary(n))
            if len(out) >= limit:
                break
    return out


@mcp.tool()
def set_selection(ref: str | None) -> dict:
    """Pin `ref` in the viz (AI → user direction).

    Use this when you want to direct the user's attention to a specific node:
    "let's look at Parser.parse together". The viz polls the selection file
    and updates its pinned node within a couple of seconds. Pass None to
    unpin. Returns {ok, id, known} — `known` is False when `ref` isn't in
    the graph.
    """
    ref = _canon_ref(ref)
    if ref is not None and ref not in _node_index():
        return {"ok": False, "id": None, "known": False}
    SELECTION_FILE.write_text(json.dumps({"id": ref}))
    return {"ok": True, "id": ref, "known": ref is not None}


@mcp.tool()
def list_nodes(limit: int = 200) -> list[dict]:
    """Every node in the graph as a summary dict, capped at `limit`.

    For aggregation questions (top-N by callers, group-by-file, etc.) that
    the client can answer with a single fetch instead of chained calls.
    """
    return [_node_summary(n) for n in list(_node_index().values())[:limit]]


@mcp.tool()
def reload_graph() -> dict:
    """Drop cached graph.json and source-parse state.

    Call this after rebuilding graph.json via build_graph.py so the next tool
    call reads the fresh data. Returns the new node count.
    """
    _graph.cache_clear()
    _node_index.cache_clear()
    _edge_index.cache_clear()
    _primary_lookup.cache_clear()
    _sources.cache_clear()
    _source_lines.cache_clear()
    g = _graph()
    return {"reloaded": True, "n_nodes": g["n_nodes"], "n_edges": g["n_edges"]}


if __name__ == "__main__":
    mcp.run()
