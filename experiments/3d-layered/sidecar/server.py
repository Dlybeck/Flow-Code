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

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VIZ_ROOT = Path(__file__).resolve().parent.parent
SELECTION_FILE = Path("/tmp/flowcode-selection.json")

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


# Static files LAST so the API routes above take precedence.
# html=True makes `/` serve index.html.
app.mount("/", StaticFiles(directory=str(VIZ_ROOT), html=True), name="static")
