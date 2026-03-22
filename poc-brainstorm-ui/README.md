# Brainstorm POC — visual node map (temporary)

Disposable UI for planning: **no file tree**, **graph navigation**, **double-click to drill**. Includes:

- **Mock** mode — data from `src/mockGraph.ts` (original POC).
- **RAW** mode — loads **`public/raw.json`** produced by [`packages/raw-indexer`](../packages/raw-indexer) from the [golden FastAPI fixture](../fixtures/golden-fastapi).

### Interactions (POC)

- **Box-select:** drag on empty canvas; **Shift+click** to add to selection; drag one selected node to move the group.
- **Pan:** middle- or right-drag, or **Space + drag**.
- **Auto-layout open:** top-left — **dagre** on tree edges (dashed import edges skipped for layout).
- **RAW mode:** double-click a **directory** to expand/collapse its subtree; double-click a **file** to show/hide **symbols** under that file. Dashed edges = resolved **internal** imports (`import_from` target maps to another indexed file).
- **Test** button: **Mock** = recursive mock report from `mockTests.ts`. **RAW** = shows node id / subtitle (real tests = `raw-indexer validate`).

## Run

```bash
cd poc-brainstorm-ui
npm install
npm run dev
```

Open the printed local URL (e.g. `http://localhost:5173`). If **`public/raw.json`** exists, the app starts in **RAW** mode; otherwise use **Mock** or **Load RAW file**.

### Phase 3 — load via API (optional)

Two terminals from **repo root**:

1. **`npm run api`** from repo root (runs `scripts/brainstorm-api.sh`; needs `pip install -e ".[api]"` in `packages/raw-indexer`).
2. **`npm run dev:api`** (or `cd poc-brainstorm-ui && npm run dev:api`).

The UI then fetches **`/api/brainstorm/raw`** and **`/overlay`** (Vite proxies to Uvicorn on port 8000). With the API, the side panel includes **Apply change package** — **`POST /apply-bundle`** with a unified diff (dev/POC until AI proposes the same payload). Production build still defaults to static files unless you set **`VITE_BRAINSTORM_API`** at build time.

**Regenerate the golden index** (from this directory):

```bash
npm run index:golden
```

After refactors, migrate **`overlay.json`** keys using **`raw-indexer overlay-migrate`** (see **`packages/raw-indexer/README.md`**). Optional: **`python -m raw_indexer index … --diagnostics`** to embed Pyright JSON for the POC **Type checker** side panel.

Uses `packages/raw-indexer/.venv/bin/python` when present, else `python3` (install the package editable first).

**Explainer (disk vs graph vs shared code):** [http://localhost:5173/repo-model.html](http://localhost:5173/repo-model.html)

## Change the “product”

- **Mock:** edit **`src/mockGraph.ts`** (`CHILDREN`, `META`, `EXTRA_EDGES`).
- **RAW graph mapping:** **`src/rawGraph.ts`** + types in **`src/rawTypes.ts`**.

Presentation: `src/App.css`, `src/CustomNodes.tsx`. Layout: `src/layoutGraph.ts`.

## Delete when done

This folder is not the final platform—remove it when the brainstorm moves on.
