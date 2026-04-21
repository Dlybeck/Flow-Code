# Flow-Code MCP — loop-1 findings (2026-04-20 → 2026-04-21)

Autonomous testing pass that drove the MCP surface from the 4-tool skeleton to
an 11-tool, bidirectional, LLM-ergonomic set. All changes are already applied
in `sidecar/mcp_server.py`, `app.js`, and `parse_calls.py`.

## Final tool surface (11 tools)

```
get_selection       — read the currently pinned node (or None)
set_selection(ref)  — AI → viz: pin a node; viz polls and picks it up
get_node(ref)       — full metadata (incl. abs_file)
get_neighbors(ref)  — 1-hop summaries; each carries is_primary
get_source(ref)     — {body, line_start, line_end, abs_file}
get_ancestors       — BFS up; each entry has hops; 100-result cap
get_descendants     — BFS down; same shape
search(query)       — substring match across qname/file
grep_source(regex)  — regex across every in-graph function body
list_nodes          — all node summaries (aggregation queries)
reload_graph        — drop caches after rebuilding graph.json
```

Every `ref` argument also accepts the UI's clipboard format
(`@flowcode:<qname>`) — so you can paste what the "Copy ref" button produced
directly into chat without stripping the prefix.

## Key deltas from the skeleton

| Change | Why |
|--------|-----|
| `get_neighbors` returns summaries inline with `is_primary` | "List callers of X" was N+1 calls; now 1. Primary vs cross-edge visibility matters for reasoning about spines. |
| Added `get_ancestors` / `get_descendants` | Walking the call tree was O(depth) calls; now 1. Each entry has a `hops` field. |
| Added `search` / `grep_source` | Chat-first workflow; cross-cutting ("which fns write to disk"): 1 call, not 1+N. |
| Added `set_selection` + viz polling | Reverse direction: AI can direct the user's attention. Viz polls every 1.5s; flashes a cue when pinned remotely. |
| Added `list_nodes` | Aggregation ("top files by function count") in one call. |
| Added `reload_graph` | User rebuilds graph.json; MCP caches forever otherwise. |
| `get_source` now returns `{body, line_start, line_end, abs_file}` | AI can feed the file/range straight into its own Read/Edit tools. |
| All ref args accept `@flowcode:` prefix | UI's clipboard output just works. |
| `get_selection` tolerates corrupt/empty JSON | Bad selection files previously crashed. |
| `grep_source` scoped to graph nodes only, handles bad regex, missing source root | Noise + crashes. |
| 100-result BFS cap | `get_descendants('main', 6)` would otherwise dump the entire reachable subgraph. |
| `parse_calls.FuncInfo` carries `lineno`/`end_lineno` | Needed for `get_source`'s location field. Non-breaking. |

## Tool-call economy (same user intents, before → after)

| User ask                                         | Before | After |
|--------------------------------------------------|-------:|------:|
| "Explain pinned node"                            |    2   |   2   |
| "Who calls this with full context?"              |  1+N   |   1   |
| "Walk me up to the entry point"                  |  N×2+1 |   2   |
| "What does this fan out to?"                     |  N×2+1 |   2   |
| "Which graph nodes write to disk / ..."          |  1+N   |   1   |
| "Which file has the most functions?"             |  N     |   1   |
| "Look at Parser.parse with me" (AI → user)       |   N/A  |   1   |
| Full describe (what, who, what-it-calls)         |  2+N+N |   4   |

## Verified over real MCP stdio

`sidecar/_stdio_client.py` spawns the server, speaks JSON-RPC, exercises all
11 tools including list returns (multiple TextContent blocks), structured
returns (reload_graph), None returns (unknown refs), and the `@flowcode:`
prefix path. No protocol bugs.

## Stress test

| Load                                      | Total   | Per call |
|-------------------------------------------|--------:|---------:|
| 50× get_neighbors                         |  138 ms |   2.8 ms |
| 20× get_source (5 KB payload)             |  126 ms |   6.3 ms |
| 20× grep_source (regex across 46 bodies)  |  234 ms |  11.7 ms |
| 20 concurrent get_ancestors               |  100 ms |        — |
| 7 different tools in parallel             |   38 ms |        — |

## Bidirectional loop visually verified

1. User clicks node in viz → POST /api/selection → MCP `get_selection` returns it.
2. AI calls `set_selection('_load')` → viz polls, pins `_load`, shows "AI pinned this" cue (3s fade), family tree highlighted.
3. AI calls `set_selection(None)` → viz unpins, panel back to empty state.

## Full-graph sweep

`_sweep.py` runs the core tool chain against every node (46 of them) to catch
node-specific bugs. Result: 0 missing sources, 0 missing abs_files, 0 non-entry
nodes with 0 ancestors, 0 missing line ranges. 27/46 have empty descriptions
(docstring absent in source, not a tool bug).

## Known remaining gaps (not fixed this pass)

- No cluster/flow abstractions yet. The v2 thesis calls for AI-labeled
  clusters and flows; that requires new fields in graph.json and a
  community-detection pass. Separate plan.
- No `paths(from, to)` tool. Callable via composing ancestors/descendants,
  not worth its own surface until a real use case surfaces.
- MCP over HTTP/SSE for mobile clients. Tracked via
  `feedback_mobile_first.md`.
- `get_source` body for very large functions (>15KB) isn't sliced. No such
  function exists in the demo graph; add `get_source(ref, start=, end=)` when
  it matters.

## Dev harness (all `_`-prefixed, not registered as MCP tools)

- `_harness.py` — direct-import smoke tests (fast iteration).
- `_stdio_client.py` — real JSON-RPC roundtrip (catches serialization bugs).
- `_stress.py` — throughput + concurrency.
- `_sweep.py` — full-graph regression (every node, all tools).
