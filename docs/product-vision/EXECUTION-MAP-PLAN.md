# Execution map (flow-first) — vision, IR, and testable slices

This document captures the **execution-shaped map** direction (Option B): **function-level** “what and when,” with **AI** adding **why** (and optionally **how**) on top. It is **language-specific at the indexer**, **language-neutral** everywhere downstream.

**Relationship to today’s POC:** The current **RAW** graph is **structure-first** (directories → files → symbols). The execution map is a **separate view** (and eventually separate artifact) built from a **shared execution IR**, not a replacement for the filesystem index unless we explicitly merge views later.

---

## 1. Product intent (short)

| Layer | Owner | Role |
|--------|--------|------|
| **Topology** | Static indexers per language | **Which function**, **possible order / branches**, **entrypoints**, **uncertainty** (`resolved` vs `may_call` vs `external`). |
| **Semantics** | LLM (and humans) | **Why** this step matters; **how** it fits the story — grounded in IR, not inventing fake call edges. |
| **Structure map** | Existing RAW pipeline | Optional **“where in repo”** drill-down; links share stable ids where possible. |

**Non-goals for v0 IR:** line-level primary map; claiming one true global execution order; crawling inside third-party or plugin internals (stop at a **named boundary**).

---

## 2. Execution IR — forward-compatible contract

All **language adapters** emit documents conforming to this shape (field names can be frozen in a **JSON Schema** or Pydantic model later). **Consumers** (layout, reachability, UI, AI overlay) **only** read IR — they never parse source.

### 2.1 Document

- `schema_version` (integer, additive evolution preferred).
- `workspace_id` / `repo_root` (optional, for display).
- `languages[]` — list of language ids present (`python`, `typescript`, …).
- `entrypoints[]` — list of **node ids** where flow exploration starts.
- `nodes[]` — graph vertices.
- `edges[]` — graph edges.

### 2.2 Node (minimum)

| Field | Purpose |
|--------|---------|
| `id` | Opaque, stable, **namespaced** per producer (`py:sym:…`, `ts:fn:…`) so merges never collide. |
| `kind` | Extensible: `function`, `method`, `entrypoint`, `external`, `dynamic_callsite`, `module`, … Unknown kinds → generic UI. |
| `language` | `python` \| `typescript` \| … |
| `label` | Short technical label (qualified name, import path) — **not** the AI blurb. |
| `location` | Optional `{ "path", "start_line", "end_line" }` — **function granularity** is enough for v0. |
| `tags` | Optional: `third_party`, `stdlib`, `plugin_boundary`, … |

### 2.3 Edge

| Field | Purpose |
|--------|---------|
| `id` | Optional stable id for overlay / tests. |
| `from`, `to` | Node ids. |
| `kind` | `calls`, `imports`, `contains`, `routes_to`, … |
| `confidence` | **`resolved`** \| **`heuristic`** \| **`unknown`** — **“maybe” calls live here.** |
| `evidence` | Optional: callsite line, reason string. |

### 2.4 Design rules for expansion

1. **Additive changes** between minor schema bumps; breaking changes bump `schema_version`.
2. **Opaque ids** — downstream must not parse path strings out of ids.
3. **Uncertainty is first-class** — never draw a solid “certain” edge when confidence is `unknown`.
4. **External / plugin** — prefer a **single `external` or boundary node** per stop, not silent omission.

---

## 3. How this differs from RAW `raw.json`

| | RAW (structure) | Execution IR |
|--|------------------|--------------|
| Primary question | Where does it live? | What can run, in what rough order / tree? |
| Primary key space | `file:`, `dir:`, `sym:` | IR `id` (namespaced) |
| Edges | Imports, containment | Calls, may-calls, imports, routes |
| AI overlay today | `overlay.json` on RAW ids | Future: `flow-overlay.json` (or merged) keyed by IR `id` |

Interop (later): **cross-links** from an IR node to `sym:…` / `file:…` when the indexer can prove the mapping.

---

## 4. Testable slices (order of work)

Each slice has **clear inputs/outputs**, **automated tests**, and **no dependency** on later slices unless noted.

### Slice 0 — **IR schema + validation**

- **Deliverable:** JSON Schema (or Pydantic) + validator CLI or unit tests.
- **Tests:** Golden **valid** / **invalid** fixtures (missing `id`, bad `confidence`, unknown `schema_version` handling).
- **Exit:** CI fails on invalid IR; valid fixtures parse clean.

### Slice 1 — **Graph library (language-agnostic)**

Pure functions over IR:

- `reachable(entrypoints, edges, direction)` → set of node ids.
- `dead_candidates(nodes, reachable_set)` → nodes never reached from any entry.
- `maybe_edges(edges)` → filter `confidence != resolved`.

**Tests:** Tiny synthetic graphs (5–20 nodes) with **expected** reachable / dead sets — **no filesystem, no Python parser**.

### Slice 2 — **Layout / visit order (presentation-only)**

- **Input:** IR + entrypoints + limits (`max_depth`, `max_branching`).
- **Output:** Ordered list of **visit events** (e.g. DFS with backtracking) or ranked layers — **for UI only**, not semantic truth.

**Tests:** Fixed graph → **exact** expected visit sequence; limit tests truncate predictably.

### Slice 3 — **Python adapter v0 — resolved calls only**

- **Input:** Existing index or AST pass for **one** repo shape (e.g. golden-fastapi).
- **Output:** IR with `calls` edges only where callee **resolves** to another indexed function.
- **Tests:** Golden repo → snapshot IR (or subset) compared to expected **node count**, **edge count**, and **spot-check ids**; regression when golden changes.

### Slice 4 — **Entrypoint discovery (Python)**

- Heuristics: `__main__`, ASGI app factory, `uvicorn` target patterns, explicit config list.
- **Tests:** Each heuristic fixture file → expected `entrypoints[]`.

### Slice 5 — **Uncertainty + boundaries**

- Unresolved calls → `confidence: unknown` or `dynamic_callsite` node.
- Third-party / stdlib imports → `external` node, **no** internal crawl.

**Tests:** Fixtures with `getattr`, dynamic import, `requests.get` → expected **unknown** / **external** shapes.

### Slice 6 — **Merge multiple producers (future)**

- **Input:** two IR docs (e.g. Python + TypeScript).
- **Output:** merged IR with id namespaces preserved.

**Tests:** Two minimal JSON blobs → merged graph invariants (no duplicate ids, edges valid).

### Slice 7 — **UI: flow view (read-only)**

- Load `flow.json` (or API route) + render second **tab** or mode: nodes/edges from IR only.
- **Tests:** Playwright or Vitest + mocked IR (optional for POC); minimum: **storybook-less** unit test on layout reducer.

### Slice 8 — **AI overlay on flow nodes**

- Parallel to Update map: prompt takes **IR neighborhood** (successors, labels, confidence); writes **displayName** / **userDescription** keyed by IR `id`.
- **Tests:** Mock LLM in unit tests; **live provider** test when API key is configured (same pattern as **[LLM-TESTING.md](./LLM-TESTING.md)** / `test_update_map_live.py`).

---

## 5. Suggested sequencing

```text
0 (schema) → 1 (graph ops) → 2 (layout)
        ↘ 3 (Python v0) → 4 (entries) → 5 (uncertainty)
        ↘ 7 (UI) when 2 + 3 are enough for a demo
        ↘ 8 (AI) after 7 or with mocked UI
6 when monorepo / second language matters
```

**First vertical demo:** Slices **0–3 + 4** produce a real IR from one Python repo; **2** gives visit order; **7** shows it. **5** hardens honesty about unknowns. **8** adds the “why.”

---

## 6. Risks (keep visible)

- **Soundness:** Static call graphs **over-approximate** or **under-approximate**; UI must show **confidence**.
- **Cost:** Large graphs need **pruning** and **summarization** for AI context windows.
- **Maintenance:** Each new language is a **new adapter**; IR stability is what keeps the rest of the product from fracturing.

---

## 7. Next doc steps (when ready)

- Add **`flow.schema.json`** (or `packages/flow-ir/schema/`) and **fixture directory** `fixtures/flow-ir/*.json`.
- Link from **SPEC.md** / **ARCHITECTURE.md** once execution map is an agreed v1 track.

---

## Changelog

| Date | Note |
|------|------|
| 2026-03-22 | Initial plan: IR contract, Option B scope, testable slices 0–8, sequencing. |
