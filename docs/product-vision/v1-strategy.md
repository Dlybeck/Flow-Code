# v1 strategy — in-house shell first, shared brain, optional IDE later

**Status:** Architectural decision + actionable next steps (2026-03-21). Aligns with **[goal.md](./goal.md)** (bridge human ↔ AI via map + ids) and **[ROADMAP.md](./ROADMAP.md)** Phases **5–7**.

---

## Decision (what we’re doing)

1. **Single Python spine** — Indexing, overlay rules, bundle apply, reindex, and validation live in **one** implementation (`packages/raw-indexer` + API). **No second indexer** for “another client.”

2. **Primary v1 user surface** — A **minimal in-house** experience (extend or replace the brainstorm POC over time) that is **graph-first**: map, **node-scoped** intent, **review** of proposed changes, **Approve / Reject**, then the spine runs **apply → reindex → validate**. Chat/agent polish is **narrow**: few tools, one model provider, good enough UX—not parity with OpenCode / Claude Code on day one.

3. **Secondary surface (later)** — **OpenCode extension**, **MCP**, or other IDE bridges are **thin adapters** over the **same** HTTP/API capabilities **after** the loop is proven end-to-end in the in-house shell. They are **leverage**, not the foundation.

**Why:** The wedge is **shared references** (friendly map + stable anchors). That requires **owning the steering UX**. Piggybacking on a generic agent host first trades away coherence and increases **map ↔ repo drift** unless you add heavy detection everywhere—still needed, but easier when the **default** path is yours.

---

## Map ↔ code sync (non-negotiable)

Drift can happen whenever files change **outside** the blessed pipeline. Robustness is **mechanical**:

- **Blessed path:** land work through **bundle apply** (or equivalent) that **writes** and then **reindexes** (and runs validation).
- **Detection:** `orphans`, optional CI comparing fresh index to committed artifacts, overlay checks.
- **Recovery:** existing **`diff` → `remap` → `overlay-migrate`** story after refactors.

Document these invariants in runbooks as they land; do not rely on the model to “follow the strategy.”

---

## Next steps (do in order)

### Step 1 — Formalize the bundle (Phase 5 core) — **started**

- **Done (baseline):** **`schema_version` 0** bundle JSON in **`raw_indexer.bundle`**: **`unified_diff`** (optional empty if **`overlay`** only) + optional **`overlay`** merge to **`--overlay-path`** (validated vs fresh **`index_repo`** after patch). Library **`apply_bundle`**, CLI **`apply-bundle`**, tests in **`tests/test_bundle.py`**. See **`packages/raw-indexer/README.md`** (`apply-bundle`).
- **Done (baseline):** **`POST /apply-bundle`** on **`raw_indexer.api`** — JSON body = change package; repo from **`BRAINSTORM_GOLDEN_REPO`**; optional flags mirror CLI; success refreshes **`public/raw.json`**.
- **Still to do:** Optional **`repo_root` in body** (Option B) when one server serves many repos; richer bundle ops only if needed.

### Step 2 — Expose the spine over HTTP

- Add FastAPI routes (or extend [`raw_indexer.api`](../../packages/raw-indexer/src/raw_indexer/api.py)) for: **get raw (or subgraph)**, **get/patch overlay** (existing where applicable), **post apply_bundle**, **post reindex**, **post validate** — all backed by the **same** functions as the CLI.
- Document env vars and a **single-repo** dev flow on **`fixtures/golden-fastapi`**.

### Step 3 — Minimal in-house steering UI — **started (POC)**

- **Done (baseline):** API mode shows **Apply change package** in the side panel: paste unified diff, **Dry-run patch** or **Apply** → **`POST /apply-bundle`**; response JSON shown; on success **Reload RAW + overlay** runs so the graph updates (`poc-brainstorm-ui` + `ApplyBundlePanel.tsx`).
- **Still to do:** Node-scoped **goal** field, **Propose** from model, structured **Approve / Reject** on a generated change package (no hand-pasted diff).

### Step 4 — Model integration (still “narrow loop”)

- One server-side integration (provider TBD) that uses **structured tool calls** against the spine—not a full chat product.
- Tracing/logging sufficient to debug **bad subgraphs** vs model mistakes.

### Step 5 — Optional second door (Phase 6, reordered)

- Implement **MCP** and/or IDE extension **only** as adapters to the **same** routes/functions used in Step 2–3.
- Exit: script or external host can complete a **small** task **using the same bundle contract**; **in-house** path remains the reference UX.

### Step 6 — Phase 7 polish

- Goals on nodes, check-ins stub, retry on validation failure—still **behind** the same gates.

---

## Relationship to roadmap

| Roadmap phase | This strategy |
|---------------|----------------|
| **5** | **Do first** — bundle schema + apply + reindex + validate as **the** productized path. |
| **6** | **Capability layer first** on the server; **MCP second** after Step 3 exit. |
| **7** | Orchestration + approvals **defaults to in-house**; external agents optional. |

If this file and **ROADMAP** disagree on ordering, **update ROADMAP** and note the change in its changelog.

---

## Changelog

| Date | Note |
|------|------|
| 2026-03-21 | Initial **v1 client strategy**: in-house graph shell first, shared spine, MCP/IDE optional; ordered next steps. |
