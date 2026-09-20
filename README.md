# Flow-Code

Flow-Code turns a codebase into an explorable 3D terrain for someone who has
never seen the source before. Each point is a function. Nearby points contain
similar code, call edges show how work connects, and higher ground highlights
code that is distinctive, substantive, and central to the selected project.

The map is a familiarization surface rather than a literal explanation or a
runtime trace. Readers can start at an entry point, follow connections, switch
between call-path and code-similarity layouts, or browse any function. Static
analysis limits remain visible in the map.

## Core boundary

Map generation is deterministic code plus local vectorization. It does not call
a generative model, read API credentials, or send repository source to a hosted
inference service. The pinned Jina code-embedding model runs locally during the
bake; generated snapshots are static JSON and the browser only loads local
assets.

A human may supply a short project purpose. Flow-Code embeds that text locally
and uses it as an additional importance signal. Portfolio pages and other hosts
may add their own prose without changing the map generator.

A future release may support an optional, one-time generative summary artifact.
That would be a separate enrichment pass over a completed map. It must remain
optional, reviewable, persisted for reuse, and outside normal re-indexing.

## Current language phase

Flow-Code currently proves these languages as independent, single-language
maps:

| Language | Parser | Current static-analysis boundary |
|---|---|---|
| Python | standard-library AST | Dynamic imports, reflection, and metaprogramming can remain unresolved. |
| JavaScript | tree-sitter TypeScript grammar | Dynamic imports, `require()`, and some callback shapes are partial. |
| TypeScript / TSX | tree-sitter TypeScript grammar | Type-only imports and type-aware dispatch are not resolved. |
| Java | tree-sitter Java | Overloads and dynamic dispatch are not type-aware. |
| C | tree-sitter C | Function pointers, macros, and conditional compilation are not resolved. |
| C# | tree-sitter C# | Delegates, LINQ lowering, overloads, and framework wiring are partial. |
| Haskell | tree-sitter Haskell | Higher-order calls, operators, typeclass dispatch, and Template Haskell are not resolved. |

Python plus browser code retains an earlier mixed-project path. General
cross-language linking is the next architectural phase, after the individual
adapters are trustworthy. Java, C, C#, and Haskell therefore reject mixed input
and ask for a single `--src-root` instead of silently producing a misleading
combined graph.

## Install for development

Python 3.11 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev,languages,terrain]"
```

The first semantic bake may download the pinned embedding weights. Set
`HF_HOME` and `FLOWCODE_EMBEDDING_CACHE` to choose their cache locations. With
the weights cached, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` makes the local
boundary explicit.

## Build and view a map

Export one selected language. `--src-root` accepts a file or directory and may
be repeated for roots in the same language.

```bash
flowcode export /path/to/repo \
  --project example \
  --src-root src \
  -o example.json
```

An optional human-written purpose can guide the height metric:

```bash
flowcode export /path/to/repo \
  --project scribblescan \
  --purpose "Turn handwritten pages into editable text" \
  --src-root src \
  -o scribblescan.json
```

Build the viewer once, package the snapshot as an independent static site, and
serve it with any HTTP server:

```bash
cd experiments/3d-layered
npm ci
npm run build
cd ../..

flowcode site example.json -o /tmp/flowcode-example
python -m http.server --directory /tmp/flowcode-example 8000
```

Open `http://127.0.0.1:8000`. The output directory contains everything needed
at runtime and has no Portfolio dependency. `scripts/export_portfolio.py` is a
separate host adapter that installs the same viewer and precomputed maps into
the Portfolio project.

## What height means

Without a purpose hint, Flow-Code computes:

```text
normalize(novelty × code substance × bounded graph centrality)
```

Novelty comes from local code vectors, substance discounts tiny wrappers, and
centrality modestly rewards functions that connect meaningful upstream and
downstream work. The graph term is bounded so generic dispatch code cannot win
on connectedness alone.

With `--purpose`, positive cosine similarity to the human-written purpose is the
primary signal and code importance is a bounded secondary signal. Every map
stores the method, component scores, vector hashes, source hashes, model
revision, and known limits. Heights are estimates relative to the selected
codebase. They are not runtime measurements, complexity scores, or proven
business value.

## CLI

```bash
# Bake the static semantic terrain used by the viewer
flowcode export REPO --project NAME -o MAP.json [--src-root PATH] [--purpose TEXT]

# Package a baked snapshot as a self-contained static site
flowcode site MAP.json -o SITE_DIR

# Emit the deterministic technical symbol index
flowcode index REPO -o raw.json

# Emit the language-neutral execution graph
flowcode execution-ir REPO -o ir.json

# Compare RAW snapshots and maintain authored overlays
flowcode diff before.json after.json
flowcode orphans raw.json overlay.json
flowcode overlay-migrate before.json after.json overlay.json -o overlay-new.json
```

`--entry` on `flowcode export` accepts an exact graph ID or qualified function
name. `--guide guide.json` attaches a human-authored tour after the semantic bake
and validates that adjacent stops have mapped call edges. A guide changes no
vectors, scores, or geometry.

## Library API

```python
from flowcode import generate_graph

graph = generate_graph("/path/to/repo", src_roots=["src"])
print(graph["languages"])
print(graph["entrypoints"])
print(len(graph["nodes"]), len(graph["edges"]))
```

`generate_graph()` produces the technical graph and deterministic structural
labels. Passing `use_llm=True` raises an error because generative enrichment is
outside core map generation.

## Analysis honesty

Resolved calls retain source locations. Recognized inferred links are visibly
distinguished from resolved links. External, ambiguous, and dynamic calls stop
at named boundary nodes instead of becoming invented internal edges. Parse
failures and partial adapters remain explicit in RAW metadata and exported map
notes.

The default scan excludes hidden paths, dependencies, generated build output,
minified files, declaration files, and symlinks. Templates, CSS, SQL, assets,
and unsupported languages are not execution graphs.

See [the product goal](docs/product-vision/goal.md) for the current product
direction and [the specification](docs/product-vision/SPEC.md) for the durable
boundaries.
