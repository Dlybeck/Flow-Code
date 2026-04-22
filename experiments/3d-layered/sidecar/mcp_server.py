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

MCP_INSTRUCTIONS = """\
FlowCode exposes a 3D call-graph viz of the project's source code. Labels
(displayName + description) are generated automatically at build time by
label_graph.py, branch-by-branch from the primary-tree root.

If the user asks you to refine or rewrite a specific label, use `write_label`.
If they want to find what still needs work, `list_unlabeled` returns nodes
missing a displayName, ranked by importance. Neither happens automatically —
it's invoked by the user, not by polling.
"""

mcp = FastMCP("flowcode", instructions=MCP_INSTRUCTIONS)


_graph_mtime: float = 0.0


def _maybe_reload_graph() -> None:
    """If graph.json has changed on disk since we last loaded it, drop caches.
    Saves the user from having to remember to call reload_graph after
    rebuilding via build_graph.py.
    """
    global _graph_mtime
    try:
        mt = GRAPH_FILE.stat().st_mtime
    except OSError:
        return
    if mt > _graph_mtime:
        if _graph_mtime > 0:
            _graph_cached.cache_clear()
            _node_index.cache_clear()
            _edge_index.cache_clear()
            _primary_lookup.cache_clear()
            _sources.cache_clear()
            _source_lines.cache_clear()
            _embeddings.cache_clear()
        _graph_mtime = mt


@cache
def _graph_cached() -> dict:
    return json.loads(GRAPH_FILE.read_text())


def _graph() -> dict:
    """Public graph accessor. Checks mtime first so a rebuilt graph.json
    auto-reloads without needing reload_graph."""
    _maybe_reload_graph()
    return _graph_cached()


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
def _embeddings() -> tuple[list[str], "object"] | None:
    """Load sibling embeddings.npz if present. Returns (qnames, matrix) or None.

    The matrix is L2-normalised at build time (sentence-transformers
    `normalize_embeddings=True`), so cosine similarity = dot product.
    """
    emb_path = GRAPH_FILE.with_suffix(".embeddings.npz")
    if not emb_path.exists():
        return None
    try:
        import numpy as np
        z = np.load(emb_path, allow_pickle=False)
        qnames = [str(q) for q in z["qnames"].tolist()]
        vectors = z["vectors"]
        return qnames, vectors
    except Exception:
        return None


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
        "importance": n.get("importance", 0.0),
        "n_callees": n.get("n_callees", 0),
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
def get_neighbors(ref: str) -> dict | None:
    """One-hop callers and callees for a node.

    Returns each neighbor as a summary dict (qname, file, depth, description)
    so the caller doesn't need a follow-up get_node per neighbor just to show
    a "callers: [...]" list with context. Each neighbor also has `is_primary`
    indicating whether the edge is a ski-slope spine edge.

    Returns None if `ref` is not in the graph — distinguishes an unknown
    ref from a valid node that genuinely has no neighbors.
    """
    ref = _canon_ref(ref)
    if ref not in _node_index():
        return None
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


def _bfs(ref: str, edge_map: dict[str, list[str]], max_depth: int) -> list[dict] | None:
    idx = _node_index()
    if ref not in idx:
        return None
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
def get_ancestors(ref: str, max_depth: int = 6) -> list[dict] | None:
    """All transitive callers of `ref` up to `max_depth` hops, BFS order.

    Each entry is a node summary plus an `hops` field (1 = direct caller,
    2 = caller's caller, ...). Use this instead of chaining get_neighbors
    when you want the chain to an entry point.

    Returns None if `ref` is unknown; [] if it's a valid node with no
    callers (e.g. the entry point).
    """
    ref = _canon_ref(ref)
    _callees, callers = _edge_index()
    return _bfs(ref, callers, max_depth)


@mcp.tool()
def get_descendants(ref: str, max_depth: int = 3) -> list[dict] | None:
    """All transitive callees of `ref` up to `max_depth` hops, BFS order.

    Default depth is smaller than get_ancestors because call trees fan out
    fast. Each entry includes an `hops` field.

    Returns None if `ref` is unknown; [] if it's a valid leaf.
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
        raise ValueError(f"invalid regex: {e}") from e
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
def similar(ref: str, limit: int = 5) -> list[dict] | None:
    """Semantically similar nodes to `ref` by embedding cosine similarity.

    Uses the Jina code-embedding vectors computed at build time — this is
    *conceptual* closeness, not name/file match (for that, see `search`).
    Good for "what else looks like this?" or "find alternatives."

    Returns list of summaries ordered by similarity (highest first), each
    with a `similarity` field in [-1, 1]. Excludes `ref` itself.

    Returns None if `ref` is unknown OR if embeddings.npz is missing
    (rebuild with the updated build_graph.py to generate it).
    """
    ref = _canon_ref(ref)
    if ref not in _node_index():
        return None
    emb = _embeddings()
    if emb is None:
        return None
    qnames, vectors = emb
    if ref not in qnames:
        return None
    import numpy as np
    idx = qnames.index(ref)
    query = vectors[idx]
    # vectors are L2-normalised → cosine = dot product
    sims = vectors @ query
    order = np.argsort(-sims)
    out: list[dict] = []
    idx_lookup = _node_index()
    for i in order:
        if int(i) == idx:
            continue
        q = qnames[int(i)]
        n = idx_lookup.get(q)
        if not n:
            continue  # in embedding set but not in current graph (e.g. filtered)
        s = _node_summary(n)
        s["similarity"] = float(sims[int(i)])
        out.append(s)
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
def write_label(ref: str, display_name: str, description: str) -> dict:
    """Persist a plain-English name + description for a node.

    This is the core labeling tool. YOU compose the label (no remote LLM
    is called); FlowCode just stores it and pushes it into the viz.

    Voice rules (from SYSTEM prompt in label_graph.py):
      - displayName: 3-6 words, title case, no code jargon
      - description: 1-2 short sentences, plain English, no "This function…"
        filler, describe EFFECT not implementation

    Refs accept bare qnames or @flowcode:qname. Returns {ok, ref}. The viz
    refreshes the pinned panel and tooltip within ~2s.
    """
    ref = _canon_ref(ref)
    if ref is None:
        return {"ok": False, "error": "empty ref"}
    graph = _graph()
    target = next((n for n in graph["nodes"] if n["qname"] == ref or n["id"] == ref), None)
    if not target:
        return {"ok": False, "error": f"unknown ref: {ref}"}
    target["displayName"] = display_name
    target["description"] = description
    GRAPH_FILE.write_text(json.dumps(graph))
    _graph_cached.cache_clear()
    _node_index.cache_clear()
    return {"ok": True, "ref": ref}


@mcp.tool()
def list_unlabeled(limit: int = 50) -> list[dict]:
    """Nodes missing a displayName, ranked by importance.

    Useful for "sweep the map" sessions: the user asks "label what's missing"
    and you iterate on this list calling write_label for each. Each item is
    a compact summary (qname, file, depth, importance, n_callees) so you can
    decide prioritization without a get_node per item.
    """
    nodes = list(_node_index().values())
    unlabeled = [n for n in nodes if not n.get("displayName")]
    unlabeled.sort(key=lambda n: n.get("importance", 0), reverse=True)
    return [{
        "ref": n["qname"],
        "id": n.get("id"),
        "file": n.get("file"),
        "depth": n.get("depth"),
        "importance": n.get("importance"),
        "n_callees": n.get("n_callees"),
    } for n in unlabeled[:limit]]


@mcp.tool()
def reload_graph() -> dict:
    """Drop cached graph.json and source-parse state.

    Call this after rebuilding graph.json via build_graph.py so the next tool
    call reads the fresh data. Returns the new node count.
    """
    _graph_cached.cache_clear()
    _node_index.cache_clear()
    _edge_index.cache_clear()
    _primary_lookup.cache_clear()
    _sources.cache_clear()
    _source_lines.cache_clear()
    _embeddings.cache_clear()
    g = _graph()
    return {"reloaded": True, "n_nodes": g["n_nodes"], "n_edges": g["n_edges"]}


if __name__ == "__main__":
    mcp.run()
