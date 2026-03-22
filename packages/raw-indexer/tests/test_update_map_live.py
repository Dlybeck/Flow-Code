"""
Live DeepSeek integration for Update map.

Calls the real API (many round-trips). Requires DEEPSEEK_API_KEY — use repo-root `.env`
(loaded in conftest) or export the variable.

Air-gapped / no key: SKIP_LIVE_LLM=1
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from raw_indexer.index import index_repo
from raw_indexer.overlay import ROOT_OVERLAY_ID
from raw_indexer.update_map import run_update_map


@pytest.mark.live_llm
def test_update_map_live_deepseek_real_api(
    golden_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.environ.get("SKIP_LIVE_LLM", "").strip().lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_LIVE_LLM=1")

    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        pytest.fail(
            "DEEPSEEK_API_KEY is required for the live Update map test. "
            "Add it to repo-root `.env` (auto-loaded) or export it. "
            "To skip on machines without a key: SKIP_LIVE_LLM=1. "
            "See docs/product-vision/LLM-TESTING.md",
        )

    monkeypatch.delenv("UPDATE_MAP_DRY_RUN", raising=False)

    raw_doc = index_repo(golden_repo)
    ov = tmp_path / "overlay.json"
    res = run_update_map(golden_repo, ov, raw_doc)

    assert res.get("ok") is True, res
    assert res.get("dry_run") is False
    assert ov.is_file()

    data = json.loads(ov.read_text(encoding="utf-8"))
    by_sym = data.get("by_symbol_id") or {}
    by_fil = data.get("by_file_id") or {}
    assert len(by_sym) >= 1, "expected at least one symbol overlay from live run"
    assert len(by_fil) >= 1, "expected at least one file overlay from live run"

    sample = next(iter(by_sym.values()))
    assert isinstance(sample, dict)
    assert sample.get("displayName") or sample.get("userDescription"), (
        "live model should return displayName and/or userDescription for symbols"
    )

    root_ent = (data.get("by_root_id") or {}).get(ROOT_OVERLAY_ID)
    assert isinstance(root_ent, dict), "expected by_root_id.raw-root from live run"
    assert root_ent.get("displayName") or root_ent.get("userDescription")
