# raw-indexer

**v0** structural **RAW** index for **Python** repos using only the stdlib **`ast`** module.

- **Partial RAW:** captures files (sha256), top-level and nested **functions/classes**, and **import** edges. **No** type-aware call graph; dynamic `import()` and reflection are invisible (aligns with [SPEC.md](../../docs/product-vision/SPEC.md) §7 — mark downstream UI as partial/degraded when you consume this).
- **Optional type honesty:** `index --diagnostics` attaches **`basedpyright` / `pyright`** JSON (`--outputjson`) under **`diagnostics`** when a binary is on `PATH` (orthogonal to the AST graph).

## Install (editable)

```bash
cd packages/raw-indexer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
```

The **`[api]`** extra adds FastAPI + Uvicorn for the Phase 3 HTTP shell (`raw_indexer.api`).

## Commands

From repo root (`Modular Code`), after installing the golden fixture:

```bash
# Index the canonical fixture → stdout (optional: attach type-checker JSON)
python -m raw_indexer index ../fixtures/golden-fastapi -o /tmp/raw.json
python -m raw_indexer index ../fixtures/golden-fastapi -o /tmp/raw-plus.json --diagnostics

# Diff two snapshots (JSON includes `remap` — heuristic symbol/file id mapping hints)
python -m raw_indexer diff /tmp/before.json /tmp/after.json

# Overlay keys not present in RAW (orphans). JSON reports `orphan_symbol_ids`,
# `orphan_file_ids`, `orphan_count`; exit code 1 if count > 0 (CI-friendly).
python -m raw_indexer orphans /tmp/raw.json samples/example_overlay.json

# Validate target repo: pytest + (basedpyright OR pyright on PATH)
python -m raw_indexer validate ../fixtures/golden-fastapi
python -m raw_indexer validate ../fixtures/golden-fastapi --pytest-only

# Apply unified diff (GNU patch -p1)
python -m raw_indexer apply ../fixtures/golden-fastapi samples/docstring.patch

# Apply + pytest/typecheck + optional fresh RAW dump
python -m raw_indexer apply-verify ../fixtures/golden-fastapi samples/docstring.patch --pytest-only --write-raw /tmp/after_raw.json
```

Paths are relative to **`packages/raw-indexer`** in the examples above; use absolute paths in CI.

### `diff` output — `remap` (Phase 4)

Besides `files` / `symbols` add/remove/change lists, each diff includes **`remap`**:

- **`symbols.high`**: one removed + one added symbol share the same **`qualified_name`** (unique pair).
- **`symbols.medium`**: same **`kind`**, **`name`**, and parent directory of file path (unique pair) — e.g. function moved between modules in the same package folder.
- **`ambiguous_*`**: multiple candidates; requires human or smarter logic.
- **`files.medium`**: one removed + one added path share the same **basename** (unique pair) — e.g. file moved between directories.

Use these to **migrate `overlay.json` keys** (`by_symbol_id` / `by_file_id`) after refactors — they are **hints**, not proof the entities are the same.

### `overlay-migrate` (Phase 4)

Applies **`diff.remap`** heuristics to an overlay file (after you have **before** and **after** RAW JSON):

```bash
python -m raw_indexer overlay-migrate /tmp/before.json /tmp/after.json /tmp/overlay.json -o /tmp/overlay-new.json
python -m raw_indexer overlay-migrate /tmp/before.json /tmp/after.json /tmp/overlay.json --dry-run   # JSON plan only
# Include medium-confidence symbol pairs (same kind+name+parent dir):
python -m raw_indexer overlay-migrate /tmp/before.json /tmp/after.json /tmp/overlay.json -o /tmp/out.json --include-medium
```

Writes the **migrated overlay** to **`-o`** and prints a **report** on stderr. Then run **`orphans`** against **`after`** RAW + new overlay.

### Language adapter (SPEC §9.3)

**`raw_indexer.language_adapter`** documents the v0 boundary: AST index + optional **`diagnostics_pyright`**. Future Python analysis should extend here without forking overlay semantics.

## HTTP API (Phase 3)

Serves **`raw.json`** and **`overlay.json`** from a directory (default: repo `poc-brainstorm-ui/public` via env).

From repo root, after `pip install -e ".[api]"`:

```bash
export BRAINSTORM_PUBLIC_DIR="$(pwd)/poc-brainstorm-ui/public"
export BRAINSTORM_GOLDEN_REPO="$(pwd)/fixtures/golden-fastapi"   # for POST /reindex
uvicorn raw_indexer.api:app --host 127.0.0.1 --port 8000
```

Or run **`scripts/brainstorm-api.sh`** from the monorepo root (uses the same defaults).

- **`GET /health`** — liveness  
- **`GET /raw`** — full RAW document  
- **`GET /overlay`** — overlay JSON (empty maps if file missing)  
- **`PATCH /overlay`** — replace overlay body; **422** if any keys are not in current RAW  
- **`POST /reindex`** — body `{"repo_root": "/path"}` optional; else **`BRAINSTORM_GOLDEN_REPO`**; writes **`raw.json`** under **`BRAINSTORM_PUBLIC_DIR`**

## JSON shape (schema_version 0)

- `index_meta`: **Phase 4 honesty** — `completeness` (`partial` for AST v0), `engine` (`ast`), `known_limits[]` (what the index does *not* claim)  
- `root`: absolute repo path  
- `files[]`: `id` (`file:…`), `path`, `sha256`, optional `analysis`: `completeness` (`complete` | `failed`), `parse_ok`, `error?` (e.g. `SyntaxError`)  
- `symbols[]`: `id` (`sym:path:qualified.name`), `kind`, `qualified_name`, `file_id`, `line`, `end_line`  
- `edges[]`: `import` / `import_from` with `from_file`, `module`, etc.
- `diagnostics` (optional): Pyright-shaped payload from **`index --diagnostics`** — `by_path`, `summary`, `partial: true`, `engine`

**Overlay file (presentation, not indexed):** optional `by_symbol_id` and `by_file_id` maps of RAW id → `{ "displayName"?, "userDescription"? }`. The POC and `orphans` command validate keys against the current `raw.json`.

## Development

```bash
pytest
ruff check src tests
```
