# flowcode

## Portable code maps

Python, JavaScript and TypeScript can now coexist in one analysis. The same
exporter powers the three Portfolio maps; it does not execute application code
at runtime. Semantic maps are baked with a local model:

```sh
uv sync --extra dev --extra ts --extra terrain
uv run flowcode export /path/to/repo --project example --purpose "What the project does" --src-root src --src-root static/js --entry package.start -o map.json
uv run pytest tests -q
```

`--src-root` accepts a file or directory and is repeatable. The default scans
supported source trees, excluding hidden paths, dependencies, generated output,
minified files, declarations and symlinks. `--entry` uses an exact qualified
function name or graph ID. Snapshots contain a focused three-step view and all
functions in the selected sources, with source hashes and visible limitations.
**Code similarity** is the default: UMAP projects actual normalized 768-dimensional
Jina code embeddings, and height shows estimated importance. **Call paths** uses
a purpose-relevance score with Flow-Code's original novelty × substance estimate to control the descent along a
primary call tree: important functions stay on ridges. Heights are not runtime
measurements or proven business value. Scores are relative to the selected project. The build embeds a short project
purpose (explicit `--purpose`, or the first 4000 README characters). Positive
purpose cosine, squared and normalized, is the main signal; the original
novelty/substance estimate contributes a bounded 25% multiplier. This avoids
rewarding unusual infrastructure helpers simply for being unusual. The exact
purpose, its embedding receipt, and both component scores are exported.

All model work happens at build time. The pinned Jina weights and implementation
run locally; no repository source is sent to an inference service. Complete
512-token chunks are mean-pooled with token weighting, then normalized. This is
an explicit adaptation of the original function embedding pipeline to avoid
truncating large browser closures. Vectors are cached by model recipe and exact
source content. Set `HF_HOME` and `FLOWCODE_EMBEDDING_CACHE` to choose cache paths.
Weights may download on the first bake; cached builds work offline. Missing or
invalid vectors fail the export; there is no geometry-only fallback.

Similarity heights use `2 + 18 * sqrt(importance)` to expand visible differences
without changing score order. Call-path heights use one positive linear scale.
Raw scores, source and vector hashes, model revisions, and nearest-neighbor
cosines remain in the snapshot. Featured views retain project-wide scores. The
browser and FastAPI app only serve JSON and assets; neither imports the model.
The source model is [Jina's code embedding model](https://huggingface.co/jinaai/jina-embeddings-v2-base-code).

Resolved calls retain their source line. HTTP route matches, event registrations
and module-bound service dispatch are explicitly inferred. Imported targets
outside selected modules and recognized browser APIs are marked external;
remaining dynamic calls stay unresolved. These distinctions describe static
evidence, not observed runtime behavior. Source argument snippets are omitted
from portable exports.

An optional `--guide guide.json` adds a short, authored source tour after the
semantic bake. It never changes vectors, scores, or geometry. The JSON contains
`title`, `summary`, and ordered `stops`, each with `symbol` (qualified function
name or ID), `title`, and `summary`. The first stop must be a featured entry;
each following stop must have a mapped call from its predecessor. Missing,
ambiguous, disconnected, or unknown-confidence stops fail before writing output.
The viewer labels inferred links and keeps source details available. These are
explanations of static source, not recordings of a running application.

The three reference tours live in `scripts/portfolio_guides.json`: Portfolio
theme switching, ScribbleScan's saved demo, and Flow-Code's semantic map builder.
The ScribbleScan demo replays saved HTML and timing records; it does not run OCR.

Build the viewer in `experiments/3d-layered` with `npm ci` and `npm run build`, then:

```sh
uv run python scripts/export_portfolio.py --portfolio /path/to/Portfolio --scribblescan /path/to/ScribbleScan
```

This installs that same viewer, its template, and three snapshots into Portfolio.
The Original ScribbleScan checkout is a read-only input. Local snapshots derived
from private repositories are **not publication approval**. Review selected scope
before publishing. The preserved comparison graph remains available in the
standalone viewer with `?example=saved`; its original renderer is `original.html`.

The Portfolio page is `/how-it-works?project=portfolio`; it also accepts `flowcode`
and `scribblescan`. Selection, layout, view scope, theme and return context stay
in the URL. Controls and 3D terrain consume Portfolio's validated Theme Packs.
The viewer falls back to a selectable 2D map when WebGL is unavailable.

**A visualization layer that sits alongside your AI coding assistant** (Claude Code, OpenCode, Cursor — anything that speaks MCP). It shows your codebase as a 3D execution terrain: peak at the entry point, height encoding architectural importance, ridges tracing the substantive call spine. You and the AI share the map as a pointing surface — select a branch and ask a question, and the AI gets both your functional intent and the underlying source; when the AI references something back, it highlights the region for you. You stay in functionality-space instead of translating every question into file paths.

Under the hood, flowcode is a Python + TypeScript static analysis pipeline that produces an **execution IR** — a call graph of functions as nodes and calls/contains as edges — using only the standard library (Python) or tree-sitter (TypeScript). No language server required.

**Status:** library + indexer are working and tested. 3D mountain viz is active iteration. MCP server is the next milestone.

See [`docs/product-vision/goal.md`](docs/product-vision/goal.md) for the full framing.

## Installation

```bash
# Python support only (stdlib, no extra dependencies)
pip install flowcode

# Python + TypeScript/JavaScript support
pip install "flowcode[ts]"

# Development
pip install "flowcode[dev]"
```

## Quick start

```python
from flowcode import generate_graph

graph = generate_graph("/path/to/repo")
# Returns: schema_version, repo_root, languages, entrypoints, nodes, edges, use_cases
print(len(graph["nodes"]), "functions")
print(len(graph["edges"]), "edges")
print(graph["entrypoints"])
```

## CLI

```bash
# Emit RAW JSON (symbol index)
flowcode index /path/to/repo -o raw.json

# Emit execution IR (call graph)
flowcode execution-ir /path/to/repo -o ir.json

# Diff two RAW snapshots
flowcode diff before.json after.json

# List orphaned overlay keys
flowcode orphans raw.json overlay.json

# Migrate overlay keys after a refactor
flowcode overlay-migrate before.json after.json overlay.json -o overlay-new.json
```

## Output schema

### RAW JSON (index)

```json
{
  "schema_version": 0,
  "indexer": "flowcode.ast_v0",
  "root": "/abs/path/to/repo",
  "files": [{ "id": "file:src/app.py", "path": "src/app.py", "sha256": "...", "analysis": {...} }],
  "symbols": [{ "id": "sym:src/app.py:app.main", "kind": "function", "qualified_name": "app.main", ... }],
  "edges": [{ "kind": "import_from", "module": "fastapi", ... }]
}
```

### Execution IR

```json
{
  "schema_version": 1,
  "languages": ["python"],
  "entrypoints": ["py:fn:app.main"],
  "nodes": [{ "id": "py:fn:app.main", "kind": "function", "label": "app.main", "location": {...} }],
  "edges": [
    { "id": "e:0", "from": "py:fn:app.main", "to": "py:fn:utils.helper", "kind": "calls", "confidence": "resolved" },
    { "id": "e:1", "from": "py:fn:app.main", "to": "py:boundary:unresolved", "kind": "calls", "confidence": "unknown", "callsite": {...} }
  ]
}
```

## Entrypoint detection

flowcode auto-detects entrypoints using a priority cascade:

1. **`.flowcode.toml` config** — explicit node ID list
2. **`main` label** — function named `main` or `*.main`
3. **App factory pattern** — `create_app`, `make_app`, `build_app`, `init_app`
4. **Route handler heuristic** — top-level functions that call `app.*` / `router.*`
5. **`__init__` module exports** — top-level functions in `__init__` files
6. **Fallback** — first node

### `.flowcode.toml` config

```toml
[entrypoints]
ids = ["py:fn:myapp.server.create_app"]
```

## Optional diagnostics (Python)

If `basedpyright` or `pyright` is on `PATH`, attach type diagnostics to the RAW output:

```bash
flowcode index /path/to/repo --diagnostics -o raw.json
```

## Optional LLM overlay enrichment

Set `DEEPSEEK_API_KEY` (preferred — cheaper) or `ANTHROPIC_API_KEY` and `generate_graph()` will call the LLM to generate `displayName` and `userDescription` for each entrypoint. Without a key, structural names are derived mechanically from entrypoint labels (e.g. `loadNumbers` → `"Load Numbers"`). DeepSeek is checked first; Anthropic is the fallback.

```python
import os
os.environ["DEEPSEEK_API_KEY"] = "sk-..."

graph = generate_graph("/path/to/repo")
# graph["use_cases"]["py:fn:app.main"]["displayName"] == "Statistical Report Generator"
# graph["use_cases"]["py:fn:app.main"]["userDescription"] == "..."
# graph["use_cases"]["py:fn:app.main"]["llm_provider"] == "deepseek"
```

## When to call `generate_graph()`

Flowcode is designed for **batch consumption at well-defined events**, not as a live linter inside hot loops. Pure compute (`use_llm=False`) is fast and free; LLM enrichment is the only thing that costs money.

Recommended call sites for tools building on flowcode:

- **Authority pass-offs** — when a component delegates a scope to another and the receiver needs to understand the codebase shape. Run with enrichment.
- **Periodic check-ins** — to compare the current graph against a baseline (`flowcode diff`) and detect drift. Compute-only is enough here.
- **Context reconstruction** — when a long-running session needs to rebuild its mental model after dropping state.
- **Initial onboarding** — once at project entry, with `use_llm=True`, to get human-friendly use case names. Persist the resulting overlay JSON.

**Avoid** calling `generate_graph(use_llm=True)` inside an inner loop (e.g. after every code edit). The overlay system + `overlay-migrate` lets you call the LLM once, persist the overlay, and migrate it across refactors instead of regenerating. For agent loops that re-index after every change, pass `use_llm=False` and reuse a persisted overlay.

## Language support

| Language | Indexer | Execution IR |
|----------|---------|--------------|
| Python 3.8+ | `flowcode.ast_v0` (stdlib `ast`) | `flowcode.execution_ir.python_from_raw` |
| TypeScript / TSX | `flowcode.ts_v0` (tree-sitter) | `flowcode.execution_ir.typescript_from_raw` |
| JavaScript / JSX / MJS | `flowcode.ts_v0` (tree-sitter) | `flowcode.execution_ir.typescript_from_raw` |

### Known limits

**Python:** Dynamic `import()`, reflection, and metaprogramming are marked `confidence: unknown`. Unresolved third-party calls go to a `py:boundary:unresolved` node.

**TypeScript:** Dynamic imports and `require()` are not traced. Type-only imports are not distinguished from value imports. Arrow functions in object literals are not indexed.

## Overlay system

The RAW index is purely technical (stable IDs from code). The overlay adds human-friendly presentation keyed by those IDs:

```json
{
  "schema_version": 0,
  "by_flow_node_id": {
    "py:fn:app.create_app": { "displayName": "App Factory", "userDescription": "Wires up FastAPI routes." }
  },
  "by_symbol_id": { "sym:src/app.py:app.main": { "displayName": "Entry Point" } },
  "by_file_id": {},
  "by_directory_id": {}
}
```

After a refactor, migrate overlay keys automatically:

```bash
flowcode overlay-migrate before.json after.json overlay.json -o overlay-migrated.json
# Or dry-run to see what would change:
flowcode overlay-migrate before.json after.json overlay.json --dry-run
```
