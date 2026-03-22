from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from raw_indexer.index import index_repo
from raw_indexer.overlay import ROOT_OVERLAY_ID, valid_directory_ids
from raw_indexer.update_map import (
    DIR_SYSTEM,
    FILE_SYSTEM,
    FLOW_SYSTEM,
    ROOT_SYSTEM,
    SYM_SYSTEM,
    _build_flow_overlay_user_message,
    run_update_map,
)


@pytest.fixture
def golden_repo(workspace_root: Path) -> Path:
    return workspace_root / "fixtures" / "golden-fastapi"


def test_update_map_dry_run_writes_overlay(
    golden_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPDATE_MAP_DRY_RUN", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    raw_doc = index_repo(golden_repo)
    ov = tmp_path / "overlay.json"
    res = run_update_map(golden_repo, ov, raw_doc)
    assert res["ok"] is True
    assert res.get("dry_run") is True
    assert ov.is_file()
    data = json.loads(ov.read_text(encoding="utf-8"))
    assert data.get("by_symbol_id")
    assert data.get("by_directory_id")
    assert data.get("by_root_id", {}).get(ROOT_OVERLAY_ID)
    assert data.get("by_flow_node_id", {}).get("py:boundary:unresolved")


def test_flow_overlay_prompt_lists_callers(golden_repo: Path) -> None:
    from raw_indexer.execution_ir.python_from_raw import build_execution_ir_from_raw

    raw_doc = index_repo(golden_repo)
    ir = build_execution_ir_from_raw(raw_doc)
    msg = _build_flow_overlay_user_message(ir)
    assert "py:boundary:unresolved" in msg
    assert "callers_to_this_node" in msg
    assert "unresolved_call_sink" in msg
    assert "caller_label_short" in msg
    assert "unresolved_callsites" in msg
    assert "FastAPI" in msg
    assert "fastapi.FastAPI" in msg


def test_update_map_missing_key(golden_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPDATE_MAP_DRY_RUN", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    raw_doc = index_repo(golden_repo)
    res = run_update_map(golden_repo, tmp_path / "overlay.json", raw_doc)
    assert res["ok"] is False
    assert any("DEEPSEEK_API_KEY" in e for e in res.get("errors", []))


def test_update_map_mock_llm_merges(
    golden_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPDATE_MAP_DRY_RUN", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    raw_doc = index_repo(golden_repo)
    sym_ids = [str(s["id"]) for s in raw_doc.get("symbols", []) if s.get("id")]
    file_ids = [str(f["id"]) for f in raw_doc.get("files", []) if f.get("id")]

    dir_ids = sorted(valid_directory_ids(raw_doc))

    def fake_chat(*, api_key: str, base_url: str, model: str, system: str, user: str, timeout: float = 120.0):
        assert api_key == "sk-test"
        if system == SYM_SYSTEM:
            return {
                "by_symbol_id": {
                    sid: {"displayName": f"T-{sid[-8:]}", "userDescription": f"D for {sid}"} for sid in sym_ids
                },
            }
        if system == FILE_SYSTEM:
            return {
                "by_file_id": {
                    fid: {"displayName": f"F-{fid[-8:]}", "userDescription": f"FD for {fid}"} for fid in file_ids
                },
            }
        if system == DIR_SYSTEM:
            return {
                "by_directory_id": {
                    did: {"displayName": f"Z-{did[-12:]}", "userDescription": f"ZD for {did}"} for did in dir_ids
                },
            }
        if system == ROOT_SYSTEM:
            return {
                "by_root_id": {
                    ROOT_OVERLAY_ID: {
                        "displayName": "Root stub",
                        "userDescription": "Root summary for tests.",
                    },
                },
            }
        if system == FLOW_SYSTEM:
            from raw_indexer.execution_ir.python_from_raw import build_execution_ir_from_raw

            ir = build_execution_ir_from_raw(raw_doc)
            fids = [
                str(n["id"])
                for n in ir.get("nodes", [])
                if isinstance(n, dict) and n.get("id") and not n.get("raw_symbol_id")
            ]
            return {
                "by_flow_node_id": {
                    fid: {"displayName": f"Flow-{fid[-12:]}", "userDescription": f"Flow D {fid}"}
                    for fid in fids
                },
            }
        raise AssertionError(f"unexpected system prompt: {system[:40]}")

    ov = tmp_path / "overlay.json"
    with patch("raw_indexer.update_map._chat_completion_json", side_effect=fake_chat):
        res = run_update_map(golden_repo, ov, raw_doc)
    assert res["ok"] is True
    assert res["symbols_updated"] == len(sym_ids)
    assert res["files_updated"] == len(file_ids)
    assert res.get("directories_updated") == len(dir_ids)
    assert res.get("root_updated") == 1
    assert res.get("flow_nodes_updated", 0) >= 1
    out = json.loads(ov.read_text(encoding="utf-8"))
    assert len(out["by_symbol_id"]) >= len(sym_ids)
    assert len(out.get("by_directory_id", {})) >= len(dir_ids)
    assert out.get("by_root_id", {}).get(ROOT_OVERLAY_ID, {}).get("displayName") == "Root stub"
    assert out.get("by_flow_node_id", {}).get("py:boundary:unresolved", {}).get("displayName")


def test_post_update_map_dry_run_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    workspace_root: Path,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from raw_indexer.api import app

    golden = workspace_root / "fixtures" / "golden-fastapi"
    pub = tmp_path / "pub"
    pub.mkdir()
    (pub / "raw.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("BRAINSTORM_GOLDEN_REPO", str(golden))
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(pub))
    monkeypatch.setenv("UPDATE_MAP_DRY_RUN", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with TestClient(app) as c:
        r = c.post("/update-map")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert (pub / "raw.json").is_file()
    assert (pub / "overlay.json").is_file()
