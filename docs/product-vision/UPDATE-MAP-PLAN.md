# Plan — “Update map” (AI overlay / user-facing labels)

**Status:** Draft for implementation. **User-facing name:** **Update map**. Internally: overlay curation against **RAW ids**.

**Reads with:** **[goal.md](./goal.md)**, **[v1-strategy.md](./v1-strategy.md)**, **[ORCHESTRATOR-POC-PLAN.md](./ORCHESTRATOR-POC-PLAN.md)** (separate track).

---

## 1. Purpose

Use an **LLM** to fill **`displayName`** and **`userDescription`** on the **user map** — copy that is **functionality- and product-oriented**, not a code lecture. Technical truth stays in **RAW**; overlay stays **keyed by RAW ids** and **validated** so keys always exist.

**First target:** **`fixtures/golden-fastapi`** (or whatever **`BRAINSTORM_GOLDEN_REPO`** points at), writing through the same **`BRAINSTORM_PUBLIC_DIR/overlay.json`** path the POC already uses.

**Not in v1 of this plan:** map-anchored comments, orchestrator, delta-from-diff (add as **slice D**), directory pseudo-nodes in overlay (POC **dir:** ids are UI-only today — v1 curates **files + symbols** from RAW only).

---

## 2. Copy rules (non-negotiable for prompts)

- **Audience:** Someone who uses the product but **does not** read the repo.
- **Titles (`displayName`):** Short, outcome- or role-oriented (plain language).
- **Descriptions (`userDescription`):** **One focused paragraph** when useful — what this **does** in the system, what it’s **for**, how it **fits** neighbors — **not** “returns X / calls Y / implements Z” unless unavoidable.
- **No** stuffing raw code blocks into descriptions; snippets in the **model input** are fine, not in the **user-facing** paragraph.

---

## 3. Token strategy (bottom-up)

Aligned with your design:

1. **Leaf pass (symbols first)**  
   For each **symbol** (or small batches per request — see slices): send **id, kind, qualified name, path, tight excerpt** (lines from file). **No** whole-repo context. **Parallel** calls are allowed; **merge all overlay fragments in memory**, then **one write** to `overlay.json`.

2. **Parent pass (files)**  
   For each **file**: send **file id, path, optional file-level excerpt**, plus **only** the **`displayName` / `userDescription`** produced for **child symbols in that file** — **not** full child source again.

3. **Order:** Finish **all symbols** → then **files**. Ensures parents see **final** child labels.

4. **Concurrency:** Start **sequential or low concurrency** in slice A to debug; increase parallelism in slice B with **rate-limit** awareness (DeepSeek limits).

**v1 scope note:** **Directory** nodes in the React graph are not RAW-backed overlay keys yet; skip **dir:** curation until the data model has stable ids for them.

---

## 4. Provider — DeepSeek

- **Key:** Server only — e.g. env **`DEEPSEEK_API_KEY`** (or a neutral **`BRAINSTORM_LLM_API_KEY`** + config for base URL).
- **Client:** HTTP from **`raw_indexer`** using **OpenAI-compatible** chat/completions API (DeepSeek documents this pattern). **No key in browser.**
- **Model:** Configurable via env (e.g. **`DEEPSEEK_MODEL`**), default to a documented chat model.

---

## 5. Safety & merge

- **Output:** Strict **JSON** object: maps of **`by_symbol_id`** / **`by_file_id`** → `{ "displayName"?, "userDescription"? }` (only ids the model was asked to fill).
- **Validate:** Every key must exist in **current RAW** (`index_repo` or loaded `raw.json`). Drop or reject unknown ids; never write orphans.
- **Merge:** **Deep merge** into existing overlay: new AI fields **fill empty** or **overwrite** per policy — **v1:** overwrite **only keys touched** in this run; preserve unrelated keys. (Optional later: “refresh only empty fields.”)
- **Write:** Same file as **`PATCH /overlay`** uses (`_overlay_path()`), after validation.

---

## 6. Implementation slices

### Slice A — Core path (small, synchronous)

- Add **`httpx`** (or stdlib) client module under **`packages/raw-indexer`** (e.g. **`map_update/`** or **`curate_map.py`**) with env-based config.
- **`POST /update-map`** on FastAPI (name TBD in code — user string is “Update map”):
  - Resolve **`BRAINSTORM_GOLDEN_REPO`**, run **`index_repo`**, optionally reload existing overlay.
  - Run **symbol** pass (sequential, single batch for golden’s tiny symbol count OK).
  - Run **file** pass.
  - Validate + merge + write **`overlay.json`**.
  - Return JSON: `{ "ok", "symbols_updated", "files_updated", "errors"? }`.
- **Tests:** Mock LLM HTTP response or stub provider interface so CI does not call the network.

### Slice B — Parallel symbol pass + batching

- Batch multiple symbols per request **or** `asyncio.gather` with semaphore (max N concurrent).
- Config env: **`UPDATE_MAP_MAX_CONCURRENT`**, **`UPDATE_MAP_SYMBOLS_PER_REQUEST`**.

### Slice C — POC UI

- In **`poc-brainstorm-ui`**, when API mode: button **Update map** → `POST /update-map` → show result → **Reload RAW + overlay**.

### Slice D — Later (not v1)

- **Delta mode:** body lists **symbol/file ids** (from **diff** / manual selection); only those ids are sent to the model.
- **Directory nodes** when RAW/UI expose stable **`dir:`** overlay keys.

---

## 7. Open decisions (before coding)

| Question | Proposal |
|----------|----------|
| Env var for key | **`DEEPSEEK_API_KEY`** in repo-root **`.env`** (see **`.env.example`**); `brainstorm-api.sh` sources `.env` |
| Route path | `POST /update-map` (matches user language) |
| Merge policy v1 | Overwrite AI-provided keys for touched ids only |
| Stub in dev | `UPDATE_MAP_DRY_RUN=1` returns fake overlay for UI wiring without key |

---

## 8. Changelog

| Date | Note |
|------|------|
| 2026-03-22 | Initial plan: Update map, DeepSeek, bottom-up symbol→file, product-facing copy rules, API + POC button slices. |
