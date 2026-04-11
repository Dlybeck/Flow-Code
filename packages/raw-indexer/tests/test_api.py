"""HTTP API (Phase 3): requires fastapi + httpx (see pyproject [dev])."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raw_indexer.api import app
from raw_indexer.index import index_repo


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    raw = {
        "schema_version": 0,
        "root": str(tmp_path),
        "files": [{"id": "file:a.py", "path": "a.py", "sha256": "x"}],
        "symbols": [{"id": "sym:a:f", "kind": "function", "file_id": "file:a.py"}],
        "edges": [],
    }
    (tmp_path / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "overlay.json").write_text(
        json.dumps(
            {
                "schema_version": 0,
                "by_symbol_id": {"sym:a:f": {"displayName": "f"}},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {},
                "by_flow_node_id": {},
            },
        ),
        encoding="utf-8",
    )
    (tmp_path / "flow.json").write_text(
        json.dumps(
            {
                "schema_version": 0,
                "languages": ["python"],
                "entrypoints": [],
                "nodes": [],
                "edges": [],
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(tmp_path))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_get_raw(client: TestClient) -> None:
    r = client.get("/raw")
    assert r.status_code == 200
    assert r.json()["symbols"][0]["id"] == "sym:a:f"


def test_get_overlay(client: TestClient) -> None:
    r = client.get("/overlay")
    assert r.status_code == 200
    assert r.json()["by_symbol_id"]["sym:a:f"]["displayName"] == "f"


def test_get_flow(client: TestClient) -> None:
    r = client.get("/flow")
    assert r.status_code == 200
    assert r.json()["schema_version"] == 0
    assert r.json()["nodes"] == []


def test_patch_overlay_rejects_orphan(client: TestClient) -> None:
    r = client.patch(
        "/overlay",
        json={
            "schema_version": 0,
            "by_symbol_id": {"sym:missing": {"displayName": "x"}},
            "by_file_id": {},
            "by_directory_id": {},
            "by_root_id": {},
        },
    )
    assert r.status_code == 422


def test_patch_overlay_rejects_orphan_flow(
    golden_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_doc = index_repo(golden_repo)
    (tmp_path / "raw.json").write_text(json.dumps(raw_doc), encoding="utf-8")
    (tmp_path / "overlay.json").write_text("{}", encoding="utf-8")
    (tmp_path / "flow.json").write_text(
        json.dumps({"schema_version": 0, "languages": ["python"], "entrypoints": [], "nodes": [], "edges": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(tmp_path))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)
    with TestClient(app) as c:
        r = c.patch(
            "/overlay",
            json={
                "schema_version": 0,
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {},
                "by_flow_node_id": {"py:flow:does-not-exist": {"displayName": "ghost"}},
            },
        )
    assert r.status_code == 422


def test_patch_overlay_accepts_valid_flow_node(
    golden_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_doc = index_repo(golden_repo)
    (tmp_path / "raw.json").write_text(json.dumps(raw_doc), encoding="utf-8")
    (tmp_path / "overlay.json").write_text("{}", encoding="utf-8")
    (tmp_path / "flow.json").write_text(
        json.dumps({"schema_version": 0, "languages": ["python"], "entrypoints": [], "nodes": [], "edges": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(tmp_path))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)
    with TestClient(app) as c:
        r = c.patch(
            "/overlay",
            json={
                "schema_version": 0,
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {},
                "by_flow_node_id": {
                    "py:boundary:unresolved": {"displayName": "External / unknown calls"},
                },
            },
        )
    assert r.status_code == 200
    data = json.loads((tmp_path / "overlay.json").read_text(encoding="utf-8"))
    assert data["by_flow_node_id"]["py:boundary:unresolved"]["displayName"] == "External / unknown calls"


def test_patch_overlay_rejects_orphan_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {
        "schema_version": 0,
        "root": str(tmp_path),
        "files": [{"id": "file:x.py", "path": "src/x.py", "sha256": "x"}],
        "symbols": [],
        "edges": [],
    }
    (tmp_path / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "overlay.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(tmp_path))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)
    with TestClient(app) as c:
        r = c.patch(
            "/overlay",
            json={
                "schema_version": 0,
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {"dir:ghost": {"displayName": "nope"}},
                "by_root_id": {},
            },
        )
    assert r.status_code == 422


def test_patch_overlay_rejects_bad_root_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {
        "schema_version": 0,
        "root": str(tmp_path),
        "files": [{"id": "file:x.py", "path": "src/x.py", "sha256": "x"}],
        "symbols": [],
        "edges": [],
    }
    (tmp_path / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "overlay.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(tmp_path))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)
    with TestClient(app) as c:
        r = c.patch(
            "/overlay",
            json={
                "schema_version": 0,
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {"not-raw-root": {"displayName": "x"}},
            },
        )
    assert r.status_code == 422


def test_patch_overlay_writes(client: TestClient, tmp_path: Path) -> None:
    r = client.patch(
        "/overlay",
        json={
            "schema_version": 0,
            "by_symbol_id": {"sym:a:f": {"displayName": "renamed"}},
            "by_file_id": {},
            "by_directory_id": {},
            "by_root_id": {},
        },
    )
    assert r.status_code == 200
    data = json.loads((tmp_path / "overlay.json").read_text(encoding="utf-8"))
    assert data["by_symbol_id"]["sym:a:f"]["displayName"] == "renamed"


def test_reindex_writes_raw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    pkg = repo / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text("def hello():\n    pass\n", encoding="utf-8")

    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "raw.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(pub))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)

    with TestClient(app) as c:
        r = c.post("/reindex", json={"repo_root": str(repo)})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["symbol_count"] >= 1
    assert "flow_wrote" in body
    assert Path(body["flow_wrote"]).is_file()
    raw = json.loads((pub / "raw.json").read_text(encoding="utf-8"))
    assert raw.get("symbols")
    flow = json.loads((pub / "flow.json").read_text(encoding="utf-8"))
    assert flow.get("schema_version") == 0
    assert isinstance(flow.get("nodes"), list)


def test_post_apply_bundle_updates_repo_and_raw(
    workspace_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden = workspace_root / "fixtures" / "golden-fastapi"
    dest = tmp_path / "g"
    shutil.copytree(
        golden,
        dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.egg-info"),
    )
    pub = tmp_path / "pub"
    pub.mkdir()
    (pub / "raw.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("BRAINSTORM_GOLDEN_REPO", str(dest))
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(pub))

    patch_text = (
        workspace_root / "packages" / "raw-indexer" / "samples" / "docstring.patch"
    ).read_text(encoding="utf-8")

    with TestClient(app) as c:
        assert c.post("/reindex", json={}).status_code == 200
        r = c.post(
            "/apply-bundle",
            json={
                "schema_version": 0,
                "unified_diff": patch_text,
                "skip_validate": True,
            },
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "patched" in (dest / "src" / "golden_app" / "core.py").read_text(encoding="utf-8")
    raw = json.loads((pub / "raw.json").read_text(encoding="utf-8"))
    assert raw.get("schema_version") == 0
    assert len(raw.get("symbols", [])) >= 1
    assert (pub / "flow.json").is_file()
    flow = json.loads((pub / "flow.json").read_text(encoding="utf-8"))
    assert flow.get("schema_version") == 0
    assert any("greeting_for" in str(n.get("label", "")) for n in flow.get("nodes", []))


def test_post_apply_bundle_invalid_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "x").mkdir(parents=True)
    (repo / "src" / "x" / "__init__.py").write_text("", encoding="utf-8")
    pub = tmp_path / "pub"
    pub.mkdir()
    (pub / "raw.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRAINSTORM_GOLDEN_REPO", str(repo))
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(pub))

    with TestClient(app) as c:
        r = c.post(
            "/apply-bundle",
            json={"schema_version": 99, "unified_diff": "x"},
        )
    assert r.status_code == 422
    assert r.json().get("ok") is False


# ─── Work session tests ───────────────────────────────────────────────────────
# All use WORK_DRY_RUN=1 — no AgentAPI or external services needed.


@pytest.fixture
def work_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client with WORK_DRY_RUN=1 and a minimal public dir."""
    flow = {
        "schema_version": 0,
        "languages": ["python"],
        "entrypoints": ["py:fn:golden_app.core.greeting_for"],
        "nodes": [
            {"id": "py:fn:golden_app.core.greeting_for", "label": "greeting_for", "kind": "function"},
            {"id": "py:fn:golden_app.app.greet", "label": "greet", "kind": "function"},
        ],
        "edges": [
            {"source": "py:fn:golden_app.app.greet", "target": "py:fn:golden_app.core.greeting_for", "kind": "calls"},
        ],
    }
    (tmp_path / "flow.json").write_text(json.dumps(flow), encoding="utf-8")
    (tmp_path / "raw.json").write_text(json.dumps({"schema_version": 0, "files": [], "symbols": [], "edges": []}), encoding="utf-8")
    (tmp_path / "overlay.json").write_text(json.dumps({"schema_version": 0, "by_symbol_id": {}, "by_file_id": {}, "by_directory_id": {}, "by_root_id": {}, "by_flow_node_id": {}}), encoding="utf-8")
    monkeypatch.setenv("BRAINSTORM_PUBLIC_DIR", str(tmp_path))
    monkeypatch.delenv("BRAINSTORM_GOLDEN_REPO", raising=False)
    monkeypatch.setenv("WORK_DRY_RUN", "1")
    return TestClient(app)


def test_go_returns_investigating_phase(work_client: TestClient) -> None:
    r = work_client.post("/go", json={"brief": "fix the greeting", "node_ids": [], "node_labels": []})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    status = work_client.get(f"/status/{sid}").json()
    assert status["phase"] == "investigating"
    assert status["activity_message"]  # non-empty


def test_go_accepts_extra_context(work_client: TestClient) -> None:
    r = work_client.post("/go", json={
        "brief": "fix greeting",
        "node_ids": [],
        "node_labels": [],
        "extra_context": "also fix the goodbye function",
    })
    assert r.status_code == 200
    sid = r.json()["session_id"]
    status = work_client.get(f"/status/{sid}").json()
    assert status["phase"] == "investigating"


def test_full_dryrun_session_reaches_done(work_client: TestClient) -> None:
    r = work_client.post("/go", json={"brief": "fix greeting", "node_ids": [], "node_labels": []})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    # Poll until planning phase, then confirm the plan
    deadline = time.time() + 20
    plan_confirmed = False
    phase = ""
    while time.time() < deadline:
        status = work_client.get(f"/status/{sid}").json()
        phase = status.get("phase", "")
        if phase == "planning" and not plan_confirmed:
            assert status.get("plan_text"), "planning phase must include plan_text"
            work_client.post(f"/status/{sid}/reply", json={"answer": "__confirm__"})
            plan_confirmed = True
        if phase in ("done", "error"):
            break
        time.sleep(0.5)

    assert phase == "done"
    assert status.get("summary")
    assert isinstance(status.get("changed_node_ids"), list)


def test_planning_phase_returns_plan_text(work_client: TestClient) -> None:
    r = work_client.post("/go", json={"brief": "fix greeting", "node_ids": [], "node_labels": []})
    sid = r.json()["session_id"]

    # Wait for planning phase
    deadline = time.time() + 15
    while time.time() < deadline:
        status = work_client.get(f"/status/{sid}").json()
        if status.get("phase") == "planning":
            break
        time.sleep(0.5)

    assert status["phase"] == "planning"
    assert status.get("plan_text"), "plan_text must be non-empty in planning phase"


def test_plan_confirm_transitions_to_writing(work_client: TestClient) -> None:
    r = work_client.post("/go", json={"brief": "fix greeting", "node_ids": [], "node_labels": []})
    sid = r.json()["session_id"]

    # Wait for planning phase
    deadline = time.time() + 15
    while time.time() < deadline:
        status = work_client.get(f"/status/{sid}").json()
        if status.get("phase") == "planning":
            break
        time.sleep(0.5)

    assert status["phase"] == "planning"

    # Confirm plan
    work_client.post(f"/status/{sid}/reply", json={"answer": "__confirm__"})

    # Next poll should be writing or beyond (not planning)
    time.sleep(0.2)
    status = work_client.get(f"/status/{sid}").json()
    assert status["phase"] != "planning"


def test_cancel_session(work_client: TestClient) -> None:
    r = work_client.post("/go", json={"brief": "fix greeting", "node_ids": [], "node_labels": []})
    sid = r.json()["session_id"]

    cancel = work_client.post(f"/status/{sid}/cancel")
    assert cancel.json()["ok"] is True

    # Session should be gone
    assert work_client.get(f"/status/{sid}").status_code == 404


def test_prompt_contains_source_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_node_context injects file path and source snippet for anchored nodes."""
    from raw_indexer.api import _build_node_context

    # Create a source file in the fake repo
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src_file = src_dir / "greet.py"
    src_file.write_text("def greeting_for(name):\n    return f'Hello, {name}'\n", encoding="utf-8")

    flow = {
        "schema_version": 0,
        "nodes": [
            {
                "id": "py:fn:greet.greeting_for",
                "label": "greeting_for",
                "kind": "function",
                "location": {"path": "src/greet.py", "start_line": 1, "end_line": 2},
            },
            {
                "id": "py:fn:greet.caller",
                "label": "caller",
                "kind": "function",
            },
        ],
        "edges": [
            {"source": "py:fn:greet.caller", "target": "py:fn:greet.greeting_for", "kind": "calls"},
        ],
    }
    flow_path = tmp_path / "flow.json"
    flow_path.write_text(json.dumps(flow), encoding="utf-8")

    ctx = _build_node_context(["py:fn:greet.greeting_for"], flow_path, tmp_path)

    assert "greeting_for" in ctx
    assert "src/greet.py" in ctx
    assert "Hello" in ctx  # source snippet injected
    assert "caller" in ctx  # neighbor label included
