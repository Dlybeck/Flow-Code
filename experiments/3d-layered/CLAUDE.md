# CLAUDE.md — experiments/3d-layered/

## MANDATORY WORKFLOW for any change to app.js / index.html / graph.json

Every change to rendered output follows this exact sequence:

1. Edit the code.
2. If `graph.json` or `build_graph.py` changed, rebuild it:
   `CUDA_VISIBLE_DEVICES="" .venv/bin/python build_graph.py httpie-src/httpie graph.json main`
3. Make sure the sidecar server is running (see below). If it isn't:
   `.venv/bin/uvicorn sidecar.server:app --host 0.0.0.0 --port 8792 &`
4. Load chrome tools via ToolSearch if not loaded:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_console_messages,mcp__claude-in-chrome__javascript_tool`
5. `mcp__claude-in-chrome__navigate` to `http://100.79.140.119:8792/?v=<timestamp>`
6. Wait 2-3 seconds with `computer action=wait duration=3`
7. `computer action=screenshot` — LOOK AT THE SCREENSHOT
8. `read_console_messages pattern=".*"` — LOOK AT THE ERRORS
9. If the screenshot shows the intended result AND no relevant errors: respond to user with the screenshot as evidence.
10. If not: fix the code, go to step 1. Do NOT respond to the user with "please reload and check".

## Sidecar + MCP

The viz is served by `sidecar/server.py` (FastAPI). It also accepts selection
updates at `POST /api/selection` from the browser and mirrors them to
`/tmp/flowcode-selection.json`.

The MCP server is `sidecar/mcp_server.py` (stdio, via `FastMCP`). It exposes
11 tools documented in `sidecar/NOTES.md`; the loop is bidirectional —
`set_selection(ref)` pins a node in the viz (which polls `/api/selection`
every 1.5s), while user clicks in the viz POST to the same endpoint for
`get_selection` to read.

All `ref` args accept both bare qnames and the UI's clipboard format
(`@flowcode:<qname>`).

Registered in project-root `.mcp.json`. Launch MCP inspector for manual
testing: `.venv/bin/mcp dev sidecar/mcp_server.py`.

Dev harnesses (`sidecar/_*.py`) verify tools directly, over stdio, and under
load — see NOTES.md for how to run each.

## Forbidden responses

Never send the user any of:
- "reload and tell me what you see"
- "check on your browser"
- "paste what you see on your end"
- "my sandbox can't / environmental issue"

If my chrome actually cannot render something (proven by data-probe that shows getContext returns null across webgl / webgl2 / experimental-webgl), state it once with the proof and propose a concrete alternative (e.g. Canvas2D fallback). Do not pivot to asking the user to verify.

## Why

The user has repeatedly called out this pattern. Repeated violation destroys trust. The chrome extension IS my verification surface. Use it every single time.
