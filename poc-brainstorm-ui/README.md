# Brainstorm POC — execution map (temporary)

Disposable UI for planning: **no file tree**, **graph navigation** of the AI-derived execution map.

- **Primary:** **`public/flow.json`** — execution IR (function **contains** + **calls**) from `raw-indexer execution-ir`, same golden fixture. **Entrypoints** use the route-style node; blue edges = resolved calls; dashed amber = uncertain when detail is on.
- **Overlay:** **`public/overlay.json`** — friendly **displayName** / descriptions when **`raw_symbol_id`** or flow node id matches.

### Interactions (POC)

- **Double-click** a function that has nested functions (**contains**): collapse or expand that subtree.
- **Box-select:** drag on empty canvas; **Shift+click** to add to selection; drag one selected node to move the group.
- **Pan:** middle- or right-drag, or **Space + drag**.
- **Auto-layout open:** top-left — **dagre** on visible tree edges.
- **Test** on a node shows qualified name, IR id, and overlay text when merged.
- **Show uncertain detail** (header): reveals boundary node and dashed uncertain call edges.

## Run

**One command from monorepo root** (indexes golden fixture, starts API + Vite; Ctrl+C stops both):

```bash
cd /path/to/Modular\ Code   # repo root
npm install                  # once, installs `concurrently` at root
npm run dev:studio
```

Open **http://localhost:5173/**. In **development**, flow + overlay refetch about every **4s** when the tab is visible, so after `index:golden` or `POST /reindex` the map updates without clicking Reload.

### Lighter options

```bash
cd poc-brainstorm-ui
npm install
npm run dev
```

Static only: uses **`public/flow.json`** + **`overlay.json`** if present (no FastAPI).

### Phase 3 — API + UI in two terminals (optional)

1. **`npm run api`** from repo root.
2. **`npm run dev:api`** from repo root or `poc-brainstorm-ui`.

The UI fetches **`/flow`** and **`/overlay`** under **`/api/brainstorm/…`** (Vite proxies to Uvicorn). **`POST /reindex`** and **`POST /apply-bundle`** (on success) refresh index artifacts on disk. Collapsed **API tools** in the sidebar: **Update map** (**`POST /update-map`**) and **Apply change package**. Put **`DEEPSEEK_API_KEY`** in repo-root **`.env`**; **`scripts/brainstorm-api.sh`** loads **`.env`**. Use **`UPDATE_MAP_DRY_RUN=1`** to test without a key.

**Regenerate the golden index** (from this directory):

```bash
npm run index:golden
```

Writes **`public/raw.json`** and **`public/flow.json`**. Run **`npm test`** for Vitest (flow graph builder).

After refactors, migrate **`overlay.json`** keys using **`raw-indexer overlay-migrate`** (see **`packages/raw-indexer/README.md`**).

Uses `packages/raw-indexer/.venv/bin/python` when present, else `python3` (install the package editable first).

**Explainer (disk vs graph vs shared code):** [http://localhost:5173/repo-model.html](http://localhost:5173/repo-model.html)

## Change the “product”

- **Execution map:** pipeline that produces **`flow.json`** (see `packages/raw-indexer`).
- **Types:** **`src/flowTypes.ts`**, **`src/overlayTypes.ts`**.

Presentation: `src/App.css`, `src/CustomNodes.tsx`. Layout: `src/layoutGraph.ts`. Graph build: `src/flowGraph.ts`.

## Delete when done

This folder is not the final platform—remove it when the brainstorm moves on.
