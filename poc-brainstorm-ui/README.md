# Brainstorm POC — visual node map (temporary)

Disposable UI for planning: **no file tree**, **graph navigation**, **double-click to drill**. Includes:

- **Flow** mode (default when present) — **`public/flow.json`**: execution IR (function **contains** + **calls**) from `raw-indexer execution-ir`, same golden fixture. **Entrypoints** use the route-style node; blue edges = calls.
- **RAW** mode — **`public/raw.json`**: filesystem / symbol index from the indexer.
- **Mock** mode — `src/mockGraph.ts` (original POC).

### Interactions (POC)

- **Box-select:** drag on empty canvas; **Shift+click** to add to selection; drag one selected node to move the group.
- **Pan:** middle- or right-drag, or **Space + drag**.
- **Auto-layout open:** top-left — **dagre** on tree edges (dashed import edges skipped for layout).
- **Flow mode:** static execution map (no drill-down). **Test** shows qualified name / IR id. Overlay **displayName** applies when a node has **`raw_symbol_id`** matching `overlay.json`.
- **RAW mode:** double-click a **directory** to expand/collapse its subtree; double-click a **file** to show/hide **symbols** under that file. Dashed edges = resolved **internal** imports (`import_from` target maps to another indexed file).
- **Test** button: **Mock** = recursive mock report from `mockTests.ts`. **RAW** = shows node id / subtitle (real tests = `raw-indexer validate`).

## Run

**One command from monorepo root** (indexes golden fixture, starts API + Vite; Ctrl+C stops both):

```bash
cd /path/to/Modular\ Code   # repo root
npm install                  # once, installs `concurrently` at root
npm run dev:studio
```

Open **http://localhost:5173/**. In **development**, flow/raw/overlay refetch about every **4s** when the tab is visible, so after `index:golden` or `POST /reindex` the map updates without clicking Reload.

### Lighter options

```bash
cd poc-brainstorm-ui
npm install
npm run dev
```

Static only: uses **`public/flow.json`** + **`raw.json`** if present (no FastAPI).

### Phase 3 — API + UI in two terminals (optional)

1. **`npm run api`** from repo root.
2. **`npm run dev:api`** from repo root or `poc-brainstorm-ui`.

The UI fetches **`/flow`**, **`/raw`**, and **`/overlay`** under **`/api/brainstorm/…`** (Vite proxies to Uvicorn). **`POST /reindex`** and **`POST /apply-bundle`** (on success) refresh **`raw.json`** and **`flow.json`** on disk. Side panel: **Update map** (**`POST /update-map`**) and **Apply change package**. Put **`DEEPSEEK_API_KEY`** in repo-root **`.env`**; **`scripts/brainstorm-api.sh`** loads **`.env`**. Use **`UPDATE_MAP_DRY_RUN=1`** to test without a key.

**Regenerate the golden index** (from this directory):

```bash
npm run index:golden
```

Writes **`public/raw.json`** and **`public/flow.json`**. Run **`npm test`** for Vitest (flow graph builder).

After refactors, migrate **`overlay.json`** keys using **`raw-indexer overlay-migrate`** (see **`packages/raw-indexer/README.md`**). Optional: **`python -m raw_indexer index … --diagnostics`** to embed Pyright JSON for the POC **Type checker** side panel.

Uses `packages/raw-indexer/.venv/bin/python` when present, else `python3` (install the package editable first).

**Explainer (disk vs graph vs shared code):** [http://localhost:5173/repo-model.html](http://localhost:5173/repo-model.html)

## Change the “product”

- **Mock:** edit **`src/mockGraph.ts`** (`CHILDREN`, `META`, `EXTRA_EDGES`).
- **RAW graph mapping:** **`src/rawGraph.ts`** + types in **`src/rawTypes.ts`**.

Presentation: `src/App.css`, `src/CustomNodes.tsx`. Layout: `src/layoutGraph.ts`.

## Delete when done

This folder is not the final platform—remove it when the brainstorm moves on.
