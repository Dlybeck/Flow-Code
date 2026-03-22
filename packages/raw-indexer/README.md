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

# Phase 5 — JSON bundle: unified diff (string) ± overlay merge, then validate (same guarantees as apply-verify path)
# Build bundle JSON with "unified_diff" set to the text of a patch file (or use overlay-only: empty diff + "overlay").
python -m raw_indexer apply-bundle /tmp/golden-copy /tmp/bundle.json --pytest-only
python -m raw_indexer apply-bundle /tmp/golden-copy /tmp/bundle.json --overlay-path /tmp/overlay.json --pytest-only
python -m raw_indexer apply-bundle /tmp/golden-copy /tmp/bundle.json --dry-run   # patch dry-run only (no overlay in bundle)
python -m raw_indexer apply-bundle /tmp/golden-copy /tmp/bundle.json --skip-validate -o /tmp/result.json
```

Paths are relative to **`packages/raw-indexer`** in the examples above; use absolute paths in CI.

### `apply-bundle` (Phase 5)

**`schema_version`:** `0`

- **`unified_diff`** (string): contents of a **unified diff** for `patch -p1` from the repo root (same as **`apply`**). May be empty only if **`overlay`** is present (**overlay-only** bundle: merge overlay against current index, no file patch).
- **`overlay`** (optional): fragment with **`by_symbol_id`** / **`by_file_id`** (and optional **`schema_version`**) merged into the file at **`--overlay-path`** (required when `overlay` is set). After any patch, overlay is validated against a **fresh** `index_repo` — **orphan keys fail** the run (no partial write).

Prints a **JSON result** to stdout (`ok`, `apply_exit_code`, `validate_exit_code`, counts, `errors`). Exit code **1** if not `ok`.

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
- **`GET /flow`** — execution IR JSON (**`flow.json`**) — **404** until **`POST /reindex`** or **`index:golden`** has created it  
- **`GET /overlay`** — overlay JSON (empty maps if file missing)  
- **`PATCH /overlay`** — replace overlay body; **422** if any keys are not in current RAW  
- **`POST /reindex`** — body `{"repo_root": "/path"}` optional; else **`BRAINSTORM_GOLDEN_REPO`**; writes **`raw.json`** and **`flow.json`** under **`BRAINSTORM_PUBLIC_DIR`** (response includes **`flow_wrote`**)  
- **`POST /apply-bundle`** — JSON body: same fields as CLI bundle (**`schema_version`**, **`unified_diff`**, optional **`overlay`**, optional **`dry_run`**, **`skip_validate`**, **`pytest_only`**). Applies to **`BRAINSTORM_GOLDEN_REPO`**. On success, refreshes **`raw.json`** and **`flow.json`**. **`422`** + result JSON if apply/validate/orphans fail.
- **`POST /update-map`** — **Update map**: reindexes into **`raw.json`**, refreshes **`flow.json`**, then calls **DeepSeek** to fill **`overlay.json`**. Requires **`DEEPSEEK_API_KEY`** unless **`UPDATE_MAP_DRY_RUN=1`**. **`503`** + JSON if misconfigured or the model pass fails.

**Secrets:** copy **`.env.example`** → **`.env`** in the repo root (gitignored). **`scripts/brainstorm-api.sh`** sources **`.env`** automatically when present.

## JSON shape (schema_version 0)

- `index_meta`: **Phase 4 honesty** — `completeness` (`partial` for AST v0), `engine` (`ast`), `known_limits[]` (what the index does *not* claim)  
- `root`: absolute repo path  
- `files[]`: `id` (`file:…`), `path`, `sha256`, optional `analysis`: `completeness` (`complete` | `failed`), `parse_ok`, `error?` (e.g. `SyntaxError`)  
- `symbols[]`: `id` (`sym:path:qualified.name`), `kind`, `qualified_name`, `file_id`, `line`, `end_line`  
- `edges[]`: `import` / `import_from` with `from_file`, `module`, etc.
- `diagnostics` (optional): Pyright-shaped payload from **`index --diagnostics`** — `by_path`, `summary`, `partial: true`, `engine`

**Overlay file (presentation, not indexed):** optional `by_symbol_id` and `by_file_id` maps of RAW id → `{ "displayName"?, "userDescription"? }`. The POC and `orphans` command validate keys against the current `raw.json`.

**Bundle file (Phase 5 apply):** `schema_version` `0`, **`unified_diff`** string (or empty with **`overlay`** present), optional **`overlay`** object (same shape as overlay maps above for merge into `--overlay-path`).

## Development

```bash
pytest
ruff check src tests
```

**Update map — live DeepSeek test:** `tests/test_update_map_live.py` calls the **real** API. Put **`DEEPSEEK_API_KEY`** in **repo-root** `.env` (it is loaded automatically before tests) or export it. Without a key, that test **fails** on purpose. Air-gapped: **`SKIP_LIVE_LLM=1`**. See **[`docs/product-vision/LLM-TESTING.md`](../../docs/product-vision/LLM-TESTING.md)**.
