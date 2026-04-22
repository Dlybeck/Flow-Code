"""Flow-Code sidecar — serves the viz and records the current selection.

Two jobs:
  1. Static-serve the viz files (index.html, app.js, graph.json).
  2. Accept selection updates from the browser at POST /api/selection and
     persist them to /tmp/flowcode-selection.json so the MCP server
     (a separate process) can read the current pinned node.

Decoupling via a file means the browser never has to know the MCP server
exists, and MCP clients never have to know the browser exists.

Labels are baked into graph.json at build time by label_graph.py
(branch-by-branch from the primary-tree root). The sidecar holds no LLM
keys and makes no LLM calls at runtime.

Run:
  uvicorn sidecar.server:app --host 0.0.0.0 --port 8792
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VIZ_ROOT = Path(__file__).resolve().parent.parent
SELECTION_FILE = Path("/tmp/flowcode-selection.json")
GRAPH_PATH = VIZ_ROOT / "graph.json"

app = FastAPI(title="Flow-Code sidecar")


class Selection(BaseModel):
    id: str | None


@app.post("/api/selection")
def post_selection(sel: Selection) -> dict:
    SELECTION_FILE.write_text(json.dumps({"id": sel.id}))
    return {"ok": True, "id": sel.id}


@app.get("/api/selection")
def get_selection() -> dict:
    if not SELECTION_FILE.exists():
        return {"id": None}
    return json.loads(SELECTION_FILE.read_text())


@app.get("/api/freshness")
def freshness() -> dict:
    """Is graph.json stale relative to source?

    Returns {stale, graph_mtime, newest_source_mtime, files_changed,
             source_root, rebuild_cmd}. "files_changed" is a truncated list
     of .py paths newer than graph.json (for the tooltip). Cheap to call
    (stat-only walk); safe to poll every ~30s.
    """
    if not GRAPH_PATH.exists():
        return {"stale": True, "reason": "no graph.json", "files_changed": [], "rebuild_cmd": None}
    try:
        graph = json.loads(GRAPH_PATH.read_text())
    except Exception as e:
        return {"stale": True, "reason": f"couldn't read graph.json: {e}", "files_changed": [], "rebuild_cmd": None}
    root_str = graph.get("root")
    if not root_str:
        return {"stale": False, "reason": "graph has no root field", "files_changed": [], "rebuild_cmd": None}
    root = Path(root_str)
    graph_mtime = GRAPH_PATH.stat().st_mtime
    changed: list[str] = []
    newest = graph_mtime
    if root.exists():
        for p in root.rglob("*.py"):
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            if mt > newest:
                newest = mt
            if mt > graph_mtime:
                try:
                    changed.append(str(p.relative_to(root)))
                except ValueError:
                    changed.append(str(p))
    stale = len(changed) > 0
    return {
        "stale": stale,
        "graph_mtime": graph_mtime,
        "newest_source_mtime": newest,
        "files_changed": changed[:20],
        "files_changed_total": len(changed),
        "source_root": str(root),
        "rebuild_cmd": f"python build_graph.py {root} graph.json",
    }


# Static files LAST so the API routes above take precedence.
# html=True makes `/` serve index.html.
app.mount("/", StaticFiles(directory=str(VIZ_ROOT), html=True), name="static")
