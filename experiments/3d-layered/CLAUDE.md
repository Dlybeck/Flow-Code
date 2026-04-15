# CLAUDE.md — experiments/3d-layered/

## MANDATORY WORKFLOW for any change to app.js / index.html / graph.json

Every change to rendered output follows this exact sequence:

1. Edit the code.
2. If `graph.json` or `build_graph.py` changed, rebuild it:
   `CUDA_VISIBLE_DEVICES="" .venv/bin/python build_graph.py httpie-src/httpie graph.json main`
3. Load chrome tools via ToolSearch if not loaded:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_console_messages,mcp__claude-in-chrome__javascript_tool`
4. `mcp__claude-in-chrome__navigate` to `http://127.0.0.1:8792/?v=<timestamp>`
5. Wait 2-3 seconds with `computer action=wait duration=3`
6. `computer action=screenshot` — LOOK AT THE SCREENSHOT
7. `read_console_messages pattern=".*"` — LOOK AT THE ERRORS
8. If the screenshot shows the intended result AND no relevant errors: respond to user with the screenshot as evidence.
9. If not: fix the code, go to step 1. Do NOT respond to the user with "please reload and check".

## Forbidden responses

Never send the user any of:
- "reload and tell me what you see"
- "check on your browser"
- "paste what you see on your end"
- "my sandbox can't / environmental issue"

If my chrome actually cannot render something (proven by data-probe that shows getContext returns null across webgl / webgl2 / experimental-webgl), state it once with the proof and propose a concrete alternative (e.g. Canvas2D fallback). Do not pivot to asking the user to verify.

## Why

The user has repeatedly called out this pattern. Repeated violation destroys trust. The chrome extension IS my verification surface. Use it every single time.
