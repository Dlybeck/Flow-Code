# Next steps — uncertainty, UI, scale, AI

Living plan for the execution-map POC and the path to a shippable product story. **Update this file** as slices land.

## Principles

1. **Trust before features** — The map must not look more certain than the engine is.
2. **One primary story** — Execution flow first; structure (RAW) and dev tools second.
3. **Ground AI in the graph** — Short UI labels + a tiny system prompt beats either one alone.

---

## Phase A — Uncertainty (in progress)

**Goal:** Users can tell “sure” vs “we stopped / not traced” without reading code.

| Step | Deliverable |
|------|-------------|
| A1 | Internal one-pager: which cases are *resolved*, *unknown*, *boundary* in v1. |
| A2 | IR + producer: emit `confidence: unknown` calls and a **boundary** node when calls aren’t resolved. **Done (v0):** unresolved non-builtin `Name` → `py:boundary:unresolved`; builtins skipped. **Next:** method / attribute calls, richer evidence strings. |
| A3 | UI: **solid vs dashed** (and/or color) for call edges; legend + tooltip copy in plain language. **Done (v0):** amber dashed “uncertain” calls + boundary node styling + sidebar copy. |
| A4 | Fixtures / tests: small repos that **must** produce expected uncertain shapes. **Done (v0):** `test_execution_ir_uncertainty.py` + golden asserts. |

**Exit:** A stakeholder can answer “what are we sure about?” from the map alone.

---

## Phase B — UI cleanup (sidebar & chrome)

**Goal:** Canvas is the hero; noise moves behind **Advanced** / **Developer**.

| Step | Deliverable |
|------|-------------|
| B1 | Short hero line: execution map first; RAW = structure drill-down. **Partial:** shorter header + “Map” explainer. |
| B2 | Collapse **mock cards**, **refresh recipes**, **JSON file pickers** under `<details>`. **Done:** details for imports, index/diagnostics, POC placeholders. |
| B3 | API-only actions (Update map, Apply bundle) under **Developer** (when API mode on). **Done.** |
| B4 | Keep **legend** and one **refresh** action visible. **Partial:** Reload stays in header; refresh text in collapsible section. |

**Exit:** New user sees map + legend + one obvious action without scrolling past POC cruft.

---

## Phase C — Facelift

**Goal:** Looks like one product, not three tools glued together.

| Step | Deliverable |
|------|-------------|
| C1 | Typography + spacing hierarchy (entry vs function vs boundary). |
| C2 | Toolbar / minimap density tuned for small screens. |
| C3 | Empty and error states: one message + **one** recommended command. |

---

## Phase D — Scale (after A–C)

- Default **depth** and **entrypoint-scoped** subgraph; expand on demand.
- Summarize or group hot spots (many callees) without losing honesty.

---

## Phase E — AI on the flow map

- Flow-scoped overlay or prompts keyed by **IR id** / `raw_symbol_id`.
- **Grounding:** use graph + excerpts; mark speculation when edges are uncertain.
- Experiment: anchor on **lowest confident node**, explain parent + uncertain child with code context.

---

## Phase F — Scenario lock-in

Name 4–6 scenarios (dynamic call, third-party boundary, nested handler, two entrypoints, …). For each: **expected map shape** + **what AI may say**. Use as release bar for the next milestone.

---

## Suggested order

1. **A2–A3** (data + canvas + legend)  
2. **B** (sidebar / story)  
3. **C** (visual polish)  
4. **D** → **E** → **F** as needed  

**A4** can run in parallel with A2.
