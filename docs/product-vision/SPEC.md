# Flow-Code product specification

**Status:** Living specification for the 2026-09-20 familiarization direction.
Read [goal.md](./goal.md) first.

## 1. Product invariants

1. **A newcomer can explore without prior code knowledge.** The main surface is
   the map, with source locations available for deeper inspection.
2. **Terrain stays central.** Height carries contextual importance; horizontal
   position carries code similarity or call-path structure.
3. **Technical structure is reproducible.** Source parsing, IR construction,
   vectorization, scoring, layout, and export do not require generative AI.
4. **Static uncertainty remains visible.** Unresolved, inferred, external, and
   partial analysis cannot be presented as recorded runtime truth.
5. **Flow-Code is independently usable.** A host can style or introduce a map,
   but source-to-viewer operation cannot require that host.
6. **Language adapters meet one shared contract.** Language-specific syntax
   stops at RAW; execution IR, terrain, export, and viewer stay language-neutral.
7. **Mixed-language behavior is explicit.** Unsupported combinations fail with
   guidance instead of silently omitting or inventing cross-language edges.

## 2. Audience and interaction

The primary reader is unfamiliar with the repository. They explore functions,
call neighborhoods, entry points, and similar code in any order. An authored
tour can suggest a path but is never required.

Each function detail exposes its language, source location, callers, callees,
similar functions, and boundary evidence. URLs preserve project, view, layout,
and selection so another person can open the same perspective.

## 3. Artifacts

| Artifact | Contents | Authority |
|---|---|---|
| RAW | Parsed files, symbols, call sites, hashes, adapter limits | Recomputable evidence from selected source |
| Execution IR | Language-neutral nodes, entry points, calls, confidence, boundaries | Technical graph consumed downstream |
| Terrain snapshot | Local vector receipts, scores, layouts, selected source metadata, guide | Portable static map data |
| Structural overlay | Deterministic human-readable labels keyed to technical IDs | Presentation; cannot replace IDs |
| Authored guide | Optional validated sequence of mapped functions and human prose | Human context; cannot alter geometry |
| Standalone site | Viewer assets plus one terrain snapshot | Publishable runtime artifact after owner review |

An optional future generated summary would be another artifact. It cannot be an
implicit pipeline stage or an authority for graph structure.

## 4. Pipeline

```text
selected source
  → language adapter and RAW
  → execution IR with confidence and boundary nodes
  → local code embeddings
  → deterministic importance and layouts
  → static terrain snapshot
  → standalone viewer or optional host adapter
```

Source hashes are checked again while exporting so a snapshot cannot combine an
old graph with changed source. Invalid or missing vectors fail the export;
geometry-only fallback is not allowed.

## 5. Importance and geometry

The default importance formula is normalized code novelty × substance with a
bounded graph-centrality multiplier. Graph centrality considers reachable
upstream and downstream functions. The multiplier is limited so topology alone
cannot make generic infrastructure the tallest code.

When a human supplies `--purpose`, positive local vector similarity to that text
becomes the main signal and code importance becomes a bounded secondary signal.
The purpose text and vector receipt are stored in the snapshot.

The similarity layout uses cosine-distance code vectors projected by seeded
UMAP, with exact SVD for three or fewer functions. The call-path layout derives
from mapped calls and the primary call tree. Visual height transforms are
monotonic and preserve score order.

## 6. Language adapter contract

An adapter owns source extensions, parsing, symbols, qualified names, direct
call evidence, and language-specific limitations. It emits the shared RAW
shape. The IR layer owns confidence, unresolved boundary nodes, entrypoint
detection, validation, and downstream IDs.

| Language | Status | Adapter |
|---|---|---|
| Python | Independent baseline | stdlib `ast` |
| JavaScript | Independent proof | tree-sitter TypeScript grammar |
| TypeScript / TSX | Independent proof | tree-sitter TypeScript grammar |
| Java | Independent proof | tree-sitter Java |
| C | Independent proof | tree-sitter C |
| C# | Independent proof | tree-sitter C# |
| Haskell | Independent proof | tree-sitter Haskell |

The Java, C, C#, and Haskell adapter is intentionally conservative: it resolves
only direct calls when there is one unambiguous selected target. Type-aware,
dynamic, generated, macro, higher-order, and framework dispatch remains a
boundary or a documented limitation.

Python plus browser code retains a legacy mixed adapter. It proves that multiple
producer documents can coexist, but it is not the general mixed-language
design. New adapters remain single-language until cross-language calls have an
explicit evidence model.

## 7. Core generative-AI boundary

Core commands must not inspect generative-provider environment variables or
make provider requests. Deterministic structural labels are the default.
`generate_graph(use_llm=True)` fails clearly instead of silently changing the
pipeline.

Any future summary pass must have its own command, input and output artifact,
provider receipt, review step, and cache/reuse behavior. Ordinary indexing and
map updates must never invoke it.

## 8. Host boundary

The standalone viewer consumes a terrain snapshot from a relative local URL.
`flowcode site` packages the snapshot and built assets without Portfolio.

A host adapter may replace viewer configuration, supply theme packs, add
navigation, and select multiple reviewed snapshots. It cannot change code
vectors or importance during page load. Deriving a snapshot from a private
repository is not permission to publish it.

## 9. Validation gates

A language proof requires:

- a representative fixture or real repository example;
- deterministic RAW and execution IR on repeated runs;
- a resolved entry point and at least one resolved internal call;
- a locally vectorized terrain snapshot with hashes and known limits;
- successful 3D rendering plus the 2D fallback;
- no runtime request to a model or third-party asset host.

Whole-project changes also require the Python test suite, lint checks, viewer
bundle build, browser acceptance, and a review of the final diff.

## 10. Current non-goals

- literal runtime tracing or a claim of complete program execution;
- automatic prose explanation as a condition of using a map;
- continuous generative summaries on repository updates;
- editing code or graph topology in the terrain;
- replacing source control, IDEs, tests, or language tooling;
- claiming general mixed-language support from simple graph concatenation;
- making MCP or an agent client part of the core runtime.

## 11. Next phase

Use the seven independent language proofs to define cross-language evidence:
imports, FFI boundaries, process or HTTP calls, generated bindings, and build
configuration. Only links with inspectable evidence should become edges. Kotlin
and Go follow when a real project needs them.

## Changelog

| Date | Change |
|---|---|
| 2025-03-21 | Initial graph-first and RAW/overlay specification. |
| 2026-04-19 | AI shared-pointing surface became the primary product framing. |
| 2026-09-20 | Reframed Flow-Code as an independent newcomer familiarization tool; made terrain and deterministic local analysis the core; moved generative summaries and agent integration outside normal map generation. |
