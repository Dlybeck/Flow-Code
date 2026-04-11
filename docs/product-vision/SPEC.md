# Product specification — consolidated brainstorming (living)

**Status:** Consolidated from extended planning (2025-03-21). **Source of nuance:** `docs/planning/brainstorming.md` (§8–§10, §9.10–§9.19).

---

## 0. Coherent vision (single spine)

Everything below must agree with these **invariants**; if something drifts, fix the doc or reject the feature.

1. **You steer; the AI implements.** Default story: **no** user-authored source—**goals, approvals, check-ins, tests, and the visual map** drive work.
2. **Two layers, one repo.** **RAW** = deterministic index from code (symbols, refs, use sites). **Overlay** = friendly **names + descriptions + grouping**, keyed by **RAW ids**. **Code bytes** live in normal files; **labels never replace ids.**
3. **Map for understanding, disk for hygiene.** The UI may **explode** reuse (many **appearances**, one **definition**); **`src/`** stays **DRY** and **tool-friendly**. **Anchors** document every link between map and paths.
4. **Truth is enforced, not hoped.** **Orphans, drift, and bundles** are handled with **logic + validation** (and **normal** linters/tests)—not model guesses for correctness.
5. **Agent acts through tools** (MCP-style): **scoped** reads/writes, **bundled** applies, **reparsed** RAW + **patched** overlay when code changes.

---

## 1. One-paragraph summary

A **self-hosted**, **graph-first** environment for building apps with **AI-authored code** and **human steering** (goals, approvals, check-ins, tests). **v1 is Python-native** (see §9); additional languages ship as **adapters** on the same pipeline. A **deterministic indexer** builds a **RAW** technical graph (symbols, references, use sites) from the repo; a separate **overlay** holds **friendly names and descriptions** for non-technical understanding. The **user-facing** map can **explode** reuse (one **appearance** per use site) while **disk** stays **DRY**. **MCP-style tools** let the agent **read/write** under **bundles + validation**; **orphans and drift** are handled with **logic**, not model guesses. **Reparsing + diff** updates RAW; **delta** curation refreshes overlay when needed.

---

## 2. Audience & interaction

- **Primary user (v1):** You — after-work side projects; **low ceremony**.
- **User does not author code** by default: **AI implements**; user **steers** via node-attached goals, **diffs**, **approvals**, **check-ins**, **tests**, **layout** (pan/zoom, auto-layout — visualization only).
- **No directory tree** as the primary UI; **nodes only** as the shell (no parallel “notes” layer — **nodes** are the primitive).
- **Topology:** user does **not** draw graph structure by hand; **structural** changes flow through **agent + approval** (and derived analysis). **At most one conceptual edge** between a pair of nodes where a link exists.

---

## 3. Two artifacts (never conflate)

| Artifact | Contents | Authority |
|----------|----------|-----------|
| **RAW** | Files, symbols, refs, calls (best-effort), **use-site** rows, **stable technical ids** | **Truth from code** (recomputable index) |
| **Overlay** | `displayName`, `userDescription`, grouping / capsules, hide, sort — **all keyed by RAW ids** | **Presentation**; **ids are never replaced by labels** |

**Orphan handling:** **Deterministic** — after reparse, `overlay_keys − valid_raw_ids` → prune or quarantine; **no** AI required for correctness. Optional AI only for **human-readable summary** of structured diffs.

---

## 4. Pipeline (core loop)

1. **Index (RAW)** — Parsers + **LSP** / per-language adapters → workspace graph (see §9.16).
2. **Store** — SQLite / JSON / SCIP-like; **version** or content-hash per file.
3. **Curation (overlay)** — AI **tree-walk** (small context: node + children + snippets), **cheap** model OK; output **validated** ⊆ RAW ids. Fields include **descriptions** for user understanding.
4. **On code change** — **Reparse** → **RAW diff** → **deterministic** overlay patch (orphans, optional **remap**); **delta** curation on affected subtrees only.
5. **Agent edits** — **Bundled** file + overlay (+ graph rules) applies; **§10.11**-style validation before “done.”

---

## 5. User graph vs disk (`src/`)

- **`src/`** may follow **functional** / tooling-friendly layout (imports, tests, CI).
- **Graph** (RAW + overlay) reflects **product** understanding; shapes may **differ**; **anchors** document every link (§9.13).
- **Leaf-only code (behavior):** implementation lives under **leaves**; inner nodes are **grouping / orchestration** (§8.2.1).
- **Exploded UX (§8.2.3):** **One** function on disk → **many appearance nodes** in the UI (every important use site). **`definitionId`** ties them together.
- **Shared implementation (§8.2.2):** one file, many **linked** use-site leaves; validators catch **copy-paste** dupes vs intentional link.

---

## 6. Agent, MCP, validation

- **MCP-like** (or equivalent) **tool protocol**: traverse graph, **resolve** anchors, **read/write** in **scoped** bundles (§9.9, §9.14).
- **Platform-agnostic surface:** Prefer **one** tool implementation behind **HTTP** and a **thin MCP server**; **IDE / CLI / chat hosts** attach via **MCP** or **HTTP** without duplicating indexer logic — operational detail in **[ROADMAP.md](./ROADMAP.md)** (*AI and tool hosts*).
- **Do not** rely on the model alone to **discover** the repo — **indexer** supplies RAW; agent **curates** and **edits** with tools.
- **Validation stack (§10.11):** prompts/skills + scoped context + **linters/types** + **graph invariants** + tests + human gates + rollback.
- **Graph validation** guarantees **structural** honesty for the agent; **normal CI** still needed for **code quality** inside files (§9.12).

---

## 7. ID stability & incomplete RAW

- **IDs:** prefer **tool-stable** symbol ids where possible; avoid **line-only** keys as sole identity. **RAW diff events** + **remap** (auto when high-confidence, else suggest) + **subtree re-curation** (§9.19).
- **Incomplete RAW:** dynamic dispatch, macros, unseen codegen → **gaps**. **Mark** regions **degraded / partial** so users don’t assume a **complete** call graph (§9.19).

---

## 8. Scale

- **Cost** is mostly **indexer + storage + UI payload**, not only curation API. Use **filters**, **incremental** index, **lazy** expansion in UI (§9.19).

---

## 9. Language strategy

### 9.1 Product lane (v1)

- **Python-native v1:** indexing, **default validation** recipes, docs, and examples assume a **normal Python repo**. The **core pipeline** (RAW store, diff, overlay, bundles, API, UI patterns) stays **language-agnostic**; **semantic depth** lands **Python-first**.
- **Canonical MVP vertical (make the loop solid here first):** one **installable package** with **`src/` layout** (e.g. `src/myapp/`), **`pyproject.toml`**, **`tests/`** (pytest), and a **Python web service** surface—**FastAPI** (or similar ASGI: Starlette, etc.) as the **reference** app shape. This is **not** a permanent limit; it **bounds** v1 so the path **index → map → goal → bundle → validate → reindex/diff/orphans** is **proven** before **widening** layouts.
- **Widen after the loop is boring:** monorepos, multiple top-level packages, scripts-only trees, heavy C extensions, notebooks—**explicitly later** unless trivially identical to the canonical adapter inputs.

### 9.2 Adjacent stacks (sequencing)

- **Python web frameworks** (FastAPI, Starlette, Django patterns): **in v1 scope** as **variants** of the same canonical shape—**tuning** the Python adapter and templates, **not** a new core.
- **CLI-only or library packages** (no HTTP surface): still **in scope** if they match the same **`src/` + `pyproject.toml` + pytest** shape; the **reference** template stays **FastAPI-style** for docs and dogfooding.

### 9.3 Adapter boundary (easy expansion later)

Implement **language-specific** work behind a narrow boundary (name illustrative: **`LanguageAdapter`**):

| Responsibility | Belongs in adapter | Belongs in core (language-neutral) |
|----------------|-------------------|-------------------------------------|
| Project roots, config discovery (`pyproject.toml`, envs) | ✓ | |
| Structure parse, symbols, refs, use sites, **stable ids** | ✓ | |
| RAW **schema** kinds, storage, **diff**, overlay rules | | ✓ |
| **Validation recipes** (invoke `pytest`, `basedpyright` / pyright, ruff, …) | **Recipe** per stack | ✓ orchestrates |
| Bundle apply, MCP tools, graph UI | | ✓ |

- **Python:** prefer **Pyright / basedpyright-class** semantics for **types + symbols** where possible; **Tree-sitter** or equivalent for **structure** where helpful; mark **dynamic** `import()`, reflection, metaprogramming as **degraded / partial** (§7).
- **New language (e.g. TypeScript):** new **adapter** + **validation recipes**; **avoid** embedding TS- or Python-only assumptions in **shared RAW node shapes**—use **generic** node/edge kinds and **optional adapter-specific payloads** when needed.

### 9.4 Status

1. ✅ **Python adapter** (`flowcode.ast_v0`) — stdlib `ast`, RAW + execution IR, `diff`, `orphans`, `overlay-migrate`.
2. ✅ **TypeScript/JS adapter** (`flowcode.ts_v0`) — tree-sitter, same RAW + IR schema, cross-module call resolution.
3. ✅ **Generalized entrypoint detection** — config override, `main`, factory, route-handler, `__init__`, fallback.
4. ✅ **Auto overlay generation** — structural naming + optional Claude Haiku enrichment.
5. **Next:** Go / Rust adapters, monorepo multi-root support, incremental index.

---

## 10. Positioning (wedge)

- Raw symbol/index is **commodity** (IDEs, code hosts). This product combines **RAW + overlay for non-dev mental models**, **exploded use-site UX**, **agent + bundles + validators**, and **honesty about analysis limits** — that **bundle** is the differentiator (§9.19).

---

## 11. Non-goals (current)

- Visual dataflow / Blueprint-style **topology editing** as the programming model.
- User **drawing** arbitrary graph wires for routine dev.
- **Replacing** Git or normal language tooling — **complement** them.

---

## 12. Suggested next engineering steps

**Implementation status:** The `flowcode` graph generation package is complete and published at [`packages/flowcode`](../../packages/flowcode).

Delivered:
1. **RAW indexer** — Python (`flowcode.ast_v0`) + TypeScript/JS (`flowcode.ts_v0` via tree-sitter).
2. **Schemas frozen** — RAW node/edge types, overlay record, execution IR schema v1.
3. **RAW diff** + **deterministic** orphan detection + **remap** hooks.
4. **Auto overlay curation** — structural naming + optional Claude Haiku enrichment.
5. **`generate_graph()` API** — one call: index → IR → overlay → merged result.
6. **Architecture diagram:** see **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

---

## 13. Flowcode package (graph generation layer)

The **`flowcode`** package is a standalone PyPI library consumed by SlowCode (and any other tool) as the graph generation dependency.

```python
from flowcode import generate_graph
graph = generate_graph("/path/to/repo")
# nodes, edges, entrypoints, use_cases
```

CLI: `flowcode index | execution-ir | diff | orphans | overlay-migrate`

See [`packages/flowcode/README.md`](../../packages/flowcode/README.md) for full API, schema, and `.flowcode.toml` config reference.

### SPEC changelog

| Date | Change |
|------|--------|
| 2025-03-21 | Initial consolidation from brainstorming threads. |
| 2025-03-21 | **§0** coherent vision spine (invariants). **`docs/planning/how-to-use.md`** rewritten as the **experience** layer aligned to §0 (pass 1). |
| 2025-03-21 | **`docs/planning/idea.md`** filled from SPEC §0–§11 + audience pointers (pass 2 — pitch layer). |
| 2025-03-21 | **`ARCHITECTURE.md`** added — logical diagram + component table (pass 3); §13 step 6 points here. |
| 2026-03-21 | **§9** rewritten: **Python-native v1**, **FastAPI + `src/`** canonical MVP vertical, **adapter boundary** for future languages; **§1** notes Python v1 + adapters. |
| 2026-03-21 | **§9.2:** removed **Electron** from scope narrative; **§9.4** roadmap step 3 generalized (second adapter when justified). |
| 2026-03-22 | **§13:** pointer to **`packages/raw-indexer`** + **`fixtures/golden-fastapi`** (v0 AST indexer landed). |
| 2026-03-22 | **`ROADMAP.md`** — phased full development guide; **§13** links it. |
| 2026-03-22 | **§6:** **Platform-agnostic** MCP + HTTP tool surface; pointer to **ROADMAP** *AI and tool hosts*. |
| 2026-03-22 | **Phase 4 tooling** (implementation): `diff.remap`, **`overlay-migrate`**, optional **`index --diagnostics`**. |
| 2026-04-11 | **`flowcode` package** — refactored from `raw-indexer`: TypeScript adapter, generalized entrypoint detection, `auto_overlay`, `generate_graph()` API. §9.4 updated to status. §12–§14 rewritten to reflect delivered state. |
