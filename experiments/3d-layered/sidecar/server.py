"""Flow-Code sidecar — serves the viz and records the current selection.

Two jobs:
  1. Static-serve the viz files (index.html, app.js, graph.json).
  2. Accept selection updates from the browser at POST /api/selection and
     persist them to /tmp/flowcode-selection.json so the MCP server
     (a separate process) can read the current pinned node.

Decoupling via a file means the browser never has to know the MCP server
exists, and MCP clients never have to know the browser exists.

Run:
  uvicorn sidecar.server:app --host 0.0.0.0 --port 8792
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VIZ_ROOT = Path(__file__).resolve().parent.parent
SELECTION_FILE = Path("/tmp/flowcode-selection.json")
GRAPH_PATH = VIZ_ROOT / "graph.json"
import os


def _graph_source_root() -> Path:
    """Resolve the absolute source root for graph.json. build_graph.py stamps
    the ingested path as graph["root"]; an env var FLOWCODE_SOURCE_ROOT
    overrides for edge cases (e.g., the codebase moved)."""
    if "FLOWCODE_SOURCE_ROOT" in os.environ:
        return Path(os.environ["FLOWCODE_SOURCE_ROOT"])
    try:
        g = json.loads(GRAPH_PATH.read_text())
        r = g.get("root")
        if r:
            return Path(r)
    except Exception:
        pass
    return VIZ_ROOT / "httpie-src" / "httpie"

# Make label_graph importable (lives alongside server.py's parent, not in this package).
sys.path.insert(0, str(VIZ_ROOT))
from label_graph import label_subset  # noqa: E402

app = FastAPI(title="Flow-Code sidecar")


class Selection(BaseModel):
    id: str | None


class LabelRequest(BaseModel):
    ref: str
    scope: Literal["node", "branch", "flow"] = "node"
    # Optional endpoints for scope="flow"
    from_ref: str | None = None
    to_ref: str | None = None


def _strip_prefix(ref: str) -> str:
    return ref.removeprefix("@flowcode:") if ref else ref


def _resolve_scope(graph: dict, ref: str, scope: str, from_ref: str | None, to_ref: str | None) -> list[str]:
    """Return the list of qnames to label for a given scope."""
    ref = _strip_prefix(ref)
    qnames_by_id = {n["id"]: n["qname"] for n in graph["nodes"]}
    qnames_by_qn = {n["qname"]: n["qname"] for n in graph["nodes"]}
    # Accept either id or qname as the incoming ref
    resolved = qnames_by_qn.get(ref) or qnames_by_id.get(ref)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"unknown ref: {ref}")

    if scope == "node":
        return [resolved]

    if scope == "branch":
        # Primary-tree descendants (BFS over is_primary edges).
        qname_from_id = lambda nid: qnames_by_id.get(nid)
        id_from_qname = {n["qname"]: n["id"] for n in graph["nodes"]}
        root_id = id_from_qname.get(resolved)
        children: dict[str, list[str]] = {n["id"]: [] for n in graph["nodes"]}
        for e in graph.get("edges", []):
            if e.get("is_primary"):
                children.setdefault(e["from"], []).append(e["to"])
        seen = {root_id}
        queue = [root_id]
        while queue:
            cur = queue.pop(0)
            for c in children.get(cur, []):
                if c not in seen:
                    seen.add(c)
                    queue.append(c)
        return [qname_from_id(i) for i in seen if qname_from_id(i)]

    if scope == "flow":
        if not from_ref or not to_ref:
            raise HTTPException(status_code=400, detail="scope=flow requires from_ref and to_ref")
        id_from_qname = {n["qname"]: n["id"] for n in graph["nodes"]}
        a = id_from_qname.get(_strip_prefix(from_ref)) or _strip_prefix(from_ref)
        b = id_from_qname.get(_strip_prefix(to_ref)) or _strip_prefix(to_ref)
        # BFS over any edges to find shortest path a→b.
        adj: dict[str, list[str]] = {n["id"]: [] for n in graph["nodes"]}
        for e in graph.get("edges", []):
            adj.setdefault(e["from"], []).append(e["to"])
        prev: dict[str, str] = {}
        queue = [a]
        seen = {a}
        while queue:
            cur = queue.pop(0)
            if cur == b:
                break
            for nxt in adj.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    prev[nxt] = cur
                    queue.append(nxt)
        if b not in seen:
            raise HTTPException(status_code=404, detail=f"no path from {from_ref} to {to_ref}")
        path = [b]
        while path[-1] != a:
            path.append(prev[path[-1]])
        path.reverse()
        return [qnames_by_id[i] for i in path if qnames_by_id.get(i)]

    raise HTTPException(status_code=400, detail=f"unknown scope: {scope}")


@app.post("/api/selection")
def post_selection(sel: Selection) -> dict:
    SELECTION_FILE.write_text(json.dumps({"id": sel.id}))
    return {"ok": True, "id": sel.id}


@app.get("/api/selection")
def get_selection() -> dict:
    if not SELECTION_FILE.exists():
        return {"id": None}
    return json.loads(SELECTION_FILE.read_text())


@app.post("/api/label")
def post_label(req: LabelRequest) -> dict:
    graph = json.loads(GRAPH_PATH.read_text())
    qnames = _resolve_scope(graph, req.ref, req.scope, req.from_ref, req.to_ref)
    # Root-first: if labeling more than one node and the primary-tree root
    # (peak) isn't in the set yet AND has no displayName, prepend it so the
    # LLM has the root's framing context in the same prompt.
    if len(qnames) > 1:
        peaks = graph.get("peaks") or []
        peak_qnames = [n["qname"] for n in graph["nodes"] if n["id"] in peaks]
        for p in peak_qnames:
            if p in qnames:
                continue
            node = next((n for n in graph["nodes"] if n["qname"] == p), None)
            if node and not node.get("displayName"):
                qnames.insert(0, p)
                break  # one root is enough
    try:
        result = label_subset(GRAPH_PATH, _graph_source_root(), qnames)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"label failed: {e}") from e
    return result


# Static files LAST so the API routes above take precedence.
# html=True makes `/` serve index.html.
app.mount("/", StaticFiles(directory=str(VIZ_ROOT), html=True), name="static")
