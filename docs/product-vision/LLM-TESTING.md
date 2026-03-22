# Live LLM testing (Update map / DeepSeek)

**Mocked tests** (`test_update_map_mock_llm_merges`) stay fast and deterministic: they patch `_chat_completion_json` and assert merge/orphan behavior.

**Live tests** call the **real** DeepSeek API end-to-end through `run_update_map`. This is **required** for the default `pytest` run in this repo when a key is configured.

---

## Requirements

1. **`DEEPSEEK_API_KEY`** in the environment **or** in **repo-root** `.env` (loaded automatically before tests — see `packages/raw-indexer/tests/conftest.py`).
2. **Network** allowed during `pytest` for the live test.
3. **`UPDATE_MAP_DRY_RUN`** must **not** be set to `1` when you expect the live test to call the API.

---

## Escape hatch

- **`SKIP_LIVE_LLM=1`** — skips the live DeepSeek test only (e.g. air-gapped machine, forks without secrets).

---

## Commands

From **`packages/raw-indexer`** (with repo-root `.env` present):

```bash
uv run pytest tests/test_update_map_live.py -v
# or full suite (includes live test):
uv run pytest tests/ -v
```

From repo root, adjust paths or `cd packages/raw-indexer` first.

---

## CI

- Set **`DEEPSEEK_API_KEY`** as a **secret** in the pipeline so the live test runs on every push/PR.
- Alternatively set **`SKIP_LIVE_LLM=1`** in CI if you intentionally run without a key (not recommended for validating Update map).

---

## Changelog

| Date | Note |
|------|------|
| 2026-03-22 | Live `test_update_map_live_deepseek_real_api`; repo-root `.env` autoload; `SKIP_LIVE_LLM` escape. |
