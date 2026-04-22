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
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VIZ_ROOT = Path(__file__).resolve().parent.parent
SELECTION_FILE = Path("/tmp/flowcode-selection.json")
LABEL_QUEUE_FILE = Path("/tmp/flowcode-label-queue.json")
GRAPH_PATH = VIZ_ROOT / "graph.json"
import time
import uuid

app = FastAPI(title="Flow-Code sidecar")


class Selection(BaseModel):
    id: str | None


class QueueLabelRequest(BaseModel):
    ref: str
    scope: Literal["node", "branch", "flow"] = "node"
    from_ref: str | None = None
    to_ref: str | None = None


def _read_queue() -> list[dict]:
    if not LABEL_QUEUE_FILE.exists():
        return []
    try:
        return json.loads(LABEL_QUEUE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _write_queue(items: list[dict]) -> None:
    LABEL_QUEUE_FILE.write_text(json.dumps(items))


class LabelWrite(BaseModel):
    ref: str
    displayName: str
    description: str


@app.post("/api/selection")
def post_selection(sel: Selection) -> dict:
    SELECTION_FILE.write_text(json.dumps({"id": sel.id}))
    return {"ok": True, "id": sel.id}


@app.get("/api/selection")
def get_selection() -> dict:
    if not SELECTION_FILE.exists():
        return {"id": None}
    return json.loads(SELECTION_FILE.read_text())


@app.get("/api/label-queue")
def get_label_queue() -> dict:
    """Return the current labeling request queue.

    The browser polls this to show pending/in-progress state per pin.
    MCP clients (agents) call the equivalent pending_label_requests tool.
    """
    return {"items": _read_queue()}


@app.post("/api/label-queue")
def enqueue_label_request(req: QueueLabelRequest) -> dict:
    """Enqueue a labeling request from the browser. The connected AI agent
    will pick it up via MCP and process it on its next turn.
    """
    items = _read_queue()
    # De-dupe: if the same ref+scope is already queued, return its existing id.
    for it in items:
        if it.get("ref") == req.ref and it.get("scope") == req.scope:
            return {"ok": True, "id": it["id"], "dedup": True}
    new = {
        "id": uuid.uuid4().hex[:12],
        "ref": req.ref,
        "scope": req.scope,
        "from_ref": req.from_ref,
        "to_ref": req.to_ref,
        "queued_at": time.time(),
        "status": "pending",
    }
    items.append(new)
    _write_queue(items)
    return {"ok": True, "id": new["id"], "dedup": False}


@app.delete("/api/label-queue/{req_id}")
def complete_label_request(req_id: str) -> dict:
    """Remove a queue entry (called after the agent has written labels)."""
    items = _read_queue()
    kept = [it for it in items if it.get("id") != req_id]
    _write_queue(kept)
    return {"ok": True, "removed": len(items) - len(kept)}


@app.post("/api/label-write")
def label_write(req: LabelWrite) -> dict:
    """Write a single {displayName, description} onto a node in graph.json.

    Called by the MCP write_label tool; also available to anyone who can
    reach the sidecar. The viz picks up the change via its poll.
    """
    graph = json.loads(GRAPH_PATH.read_text())
    target = next((n for n in graph["nodes"] if n["qname"] == req.ref or n["id"] == req.ref), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"unknown ref: {req.ref}")
    target["displayName"] = req.displayName
    target["description"] = req.description
    GRAPH_PATH.write_text(json.dumps(graph))
    return {"ok": True, "ref": req.ref}


# Static files LAST so the API routes above take precedence.
# html=True makes `/` serve index.html.
app.mount("/", StaticFiles(directory=str(VIZ_ROOT), html=True), name="static")
