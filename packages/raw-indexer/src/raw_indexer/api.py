"""Phase 3: small HTTP shell for RAW + overlay (FastAPI)."""

from __future__ import annotations

import datetime
import json
import logging
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

_log = logging.getLogger("brainstorm.api")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from raw_indexer.bundle import apply_bundle
from raw_indexer.execution_ir import build_execution_ir_from_raw
from raw_indexer.index import index_repo, write_index
from raw_indexer.overlay import (
    overlay_orphan_directory_keys,
    overlay_orphan_file_keys,
    overlay_orphan_flow_keys,
    overlay_orphan_keys,
    overlay_orphan_root_keys,
)
from raw_indexer.update_map import _chat_completion_json, _read_excerpt, run_update_map


class ReindexBody(BaseModel):
    """Optional override for POST /reindex (defaults from env)."""

    repo_root: str | None = Field(
        default=None,
        description="Repository root to index; else BRAINSTORM_GOLDEN_REPO",
    )


class CommentIn(BaseModel):
    """A map comment posted from the UI."""

    id: str
    node_ids: list[str]
    node_labels: list[str]
    body: str
    timestamp: str
    pending: bool = True


class CommentPatch(BaseModel):
    """Fields that can be updated on an existing comment."""

    pending: bool | None = None


class ApplyBundleBody(BaseModel):
    """
    Change package for POST /apply-bundle (Phase 5).

    Repo root is **BRAINSTORM_GOLDEN_REPO** (Option A — one deployment per project).
    If ``overlay`` is set, it is merged into ``BRAINSTORM_PUBLIC_DIR/overlay.json`` after
    the patch, validated against a fresh index of the repo.
    """

    schema_version: int = Field(default=0, description="Must be 0")
    unified_diff: str = Field(
        default="",
        description="Unified diff for patch -p1 from repo root; may be empty if overlay-only",
    )
    overlay: dict[str, Any] | None = Field(
        default=None,
        description="Optional overlay fragment (by_symbol_id / by_file_id / by_directory_id) to merge",
    )
    dry_run: bool = Field(
        default=False, description="patch --dry-run only; disallowed if overlay set"
    )
    skip_validate: bool = Field(default=False, description="Skip pytest/typecheck after apply")
    pytest_only: bool = Field(
        default=False,
        description="If validating, pytest only (no typecheck)",
    )


def _bundle_dict_from_body(body: ApplyBundleBody) -> dict[str, Any]:
    d: dict[str, Any] = {"schema_version": body.schema_version, "unified_diff": body.unified_diff}
    if body.overlay is not None:
        d["overlay"] = body.overlay
    return d


def _public_dir() -> Path:
    env = os.environ.get("BRAINSTORM_PUBLIC_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise HTTPException(
                status_code=500,
                detail=f"BRAINSTORM_PUBLIC_DIR is not a directory: {p}",
            )
        return p
    cwd_pub = Path.cwd() / "poc-brainstorm-ui" / "public"
    if cwd_pub.is_dir():
        return cwd_pub.resolve()
    raise HTTPException(
        status_code=500,
        detail="Set BRAINSTORM_PUBLIC_DIR to poc-brainstorm-ui/public (or run uvicorn from repo root).",
    )


def _raw_path() -> Path:
    return _public_dir() / "raw.json"


def _overlay_path() -> Path:
    return _public_dir() / "overlay.json"


def _flow_path() -> Path:
    return _public_dir() / "flow.json"


def _comments_path() -> Path:
    return _public_dir() / "comments.json"


def _load_comments_doc() -> dict[str, Any]:
    p = _comments_path()
    if not p.is_file():
        return {"schema_version": 0, "comments": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_comments_doc(doc: dict[str, Any]) -> None:
    _comments_path().write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _plan_path() -> Path:
    return _public_dir() / "plan.json"


def _load_plan_doc() -> dict[str, Any]:
    p = _plan_path()
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_plan_doc(doc: dict[str, Any]) -> None:
    _plan_path().write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _delete_plan_doc() -> None:
    p = _plan_path()
    if p.is_file():
        p.unlink()


def _write_flow_json(raw_doc: dict[str, Any]) -> Path:
    """Derive execution IR from RAW and write next to raw.json (POC main graph)."""
    path = _flow_path()
    ir_doc = build_execution_ir_from_raw(raw_doc)
    path.write_text(json.dumps(ir_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _golden_repo() -> Path:
    env = os.environ.get("BRAINSTORM_GOLDEN_REPO", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise HTTPException(
                status_code=500,
                detail=f"BRAINSTORM_GOLDEN_REPO is not a directory: {p}",
            )
        return p
    raise HTTPException(
        status_code=500,
        detail="Set BRAINSTORM_GOLDEN_REPO to the repo root to index (e.g. fixtures/golden-fastapi).",
    )


def _opencode_url() -> str:
    return os.environ.get("OPENCODE_URL", "http://localhost:4096").rstrip("/")


def _agentapi_cmd() -> str:
    return os.environ.get("AGENTAPI_CMD", "agentapi")


def _agent_argv() -> list[str]:
    """Return the agent command + args to pass after '--' to agentapi server.

    Starts Aider in 'ask' mode (no file writes) for the investigation phase.
    The monitor switches to 'code' mode via /code before executing.
    Override AGENT_CMD for a different agent (e.g. 'opencode').
    Override AGENT_MODEL to change the model.
    """
    cmd = os.environ.get("AGENT_CMD", "aider")
    model = os.environ.get("AGENT_MODEL", "deepseek/deepseek-chat")
    if cmd == "aider":
        return [cmd, "--model", model, "--chat-mode", "ask", "--yes-always", "--no-pretty"]
    return [cmd]


def _free_port() -> int:
    """Find a free TCP port by binding to port 0 and reading the assigned port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _work_session_path() -> Path:
    return _public_dir() / "work_session.json"


def _save_work_session(body: "GoBody") -> None:
    doc = {
        "schema_version": 0,
        "brief": body.brief,
        "node_ids": body.node_ids,
        "node_labels": body.node_labels,
        "extra_context": body.extra_context,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _work_session_path().write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _build_file_to_nodes_map() -> dict[str, list[str]]:
    """Map relative file path → list of node IDs (from flow.json)."""
    fp = _flow_path()
    if not fp.is_file():
        return {}
    flow_doc = json.loads(fp.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for node in flow_doc.get("nodes", []):
        loc = node.get("location") or {}
        rel = loc.get("path", "")
        nid = node.get("id", "")
        if rel and nid:
            result.setdefault(rel, []).append(nid)
    return result


_MAX_SESSION_SECONDS = 20 * 60  # 20 minutes


def _cleanup_old_sessions() -> None:
    """Remove sessions older than 2 hours and terminate their subprocesses."""
    cutoff = time.time() - 7200
    stale = [sid for sid, s in list(_WORK_SESSIONS.items()) if s.get("start", 0) < cutoff]
    for sid in stale:
        proc = _WORK_SESSIONS[sid].get("agentapi_proc")
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        _WORK_SESSIONS.pop(sid, None)


def _build_node_context(
    node_ids: list[str], flow_path: Path, repo_root: Path | None
) -> str:
    """Build source context for anchored nodes from flow.json + actual source files.

    Returns a formatted string describing each anchored node (label, file, source snippet,
    direct neighbors) suitable for injection into the OpenCode initial prompt.
    """
    if not node_ids or not flow_path.is_file():
        return ""
    try:
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    id_to_node = {n["id"]: n for n in flow.get("nodes", [])}

    # Build neighbor labels per anchored node from edges (handles both from/to and source/target formats)
    neighbor_labels: dict[str, list[str]] = {}
    for edge in flow.get("edges", []):
        src = edge.get("from") or edge.get("source", "")
        tgt = edge.get("to") or edge.get("target", "")
        if not (src and tgt):
            continue
        src_node = id_to_node.get(src)
        tgt_node = id_to_node.get(tgt)
        if src in node_ids and tgt_node:
            neighbor_labels.setdefault(src, []).append(tgt_node.get("label", tgt))
        if tgt in node_ids and src_node:
            neighbor_labels.setdefault(tgt, []).append(src_node.get("label", src))

    parts: list[str] = []
    for nid in node_ids:
        node = id_to_node.get(nid)
        if not node:
            continue
        label = node.get("label", nid)
        loc = node.get("location") or {}
        file_rel = loc.get("path", "")
        start_line = loc.get("start_line")
        end_line = loc.get("end_line")

        source_snippet = ""
        if file_rel and repo_root and start_line is not None and end_line is not None:
            try:
                lines = (repo_root / file_rel).read_text(encoding="utf-8").splitlines()
                source_snippet = "\n".join(lines[start_line - 1 : end_line])
            except Exception:
                pass

        nbrs = neighbor_labels.get(nid, [])
        nbr_str = f"\n  Neighbors: {', '.join(nbrs[:4])}" if nbrs else ""

        if source_snippet and file_rel:
            abs_path = str(repo_root / file_rel) if repo_root else file_rel
            parts.append(
                f'Starting point — "{label}" ({abs_path}, lines {start_line}–{end_line}):\n'
                f"```\n{source_snippet}\n```{nbr_str}"
            )
        elif file_rel:
            abs_path = str(repo_root / file_rel) if repo_root else file_rel
            parts.append(f'Starting point — "{label}" in {abs_path}{nbr_str}')
        else:
            parts.append(f'Starting point — "{label}"{nbr_str}')

    return "\n\n".join(parts)


def _spawn_agentapi(
    session_id: str,
    brief: str,
    node_ids: list[str],
    node_labels: list[str],
    extra_context: str = "",
) -> None:
    """Start an AgentAPI subprocess wrapping openclaude, send investigation prompt."""
    import httpx

    session = _WORK_SESSIONS.get(session_id)
    if not session:
        return

    merged_brief = brief
    if extra_context:
        merged_brief = f"{brief}\n\nAdditional context from user: {extra_context}"

    try:
        repo_root = _golden_repo()
        repo_path = str(repo_root)
    except Exception:
        repo_root = None
        repo_path = ""

    node_context = _build_node_context(node_ids, _flow_path(), repo_root)
    if not node_context and node_labels:
        node_context = f"Starting area: {', '.join(node_labels)}."

    port = _free_port()
    _log.info("spawn_agentapi: session=%s port=%d brief=%r", session_id, port, merged_brief[:60])

    try:
        proc = subprocess.Popen(
            [_agentapi_cmd(), "server", "--port", str(port), "--", *_agent_argv()],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        session["agentapi_proc"] = proc
        session["agentapi_port"] = port

        base_url = f"http://localhost:{port}"

        # Wait for AgentAPI + agent to be ready and idle ("stable") — up to 60s
        deadline = time.monotonic() + 60
        with httpx.Client(timeout=5) as client:
            while time.monotonic() < deadline:
                try:
                    r = client.get(f"{base_url}/status")
                    if r.status_code == 200 and r.json().get("status") == "stable":
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("AgentAPI agent did not reach stable state within 60s")

        t = threading.Thread(
            target=_monitor_agentapi, args=(session_id, port), daemon=True
        )
        t.start()

        context_block = f"\n\n{node_context}" if node_context else ""
        repo_line = f"\n\nRepo: {repo_path}" if repo_path else ""
        test_cmd = f'cd "{repo_path}" && python -m pytest' if repo_path else "python -m pytest"
        investigation_prompt = f"""\
Task: {merged_brief}{context_block}{repo_line}

## Phase 1 — Investigate and Plan

Explore the codebase starting from the files and functions shown above.
Produce a clear, numbered implementation plan describing the changes needed.
**Do NOT create, edit, or delete any files in this phase.**
End your response with the numbered plan only — no preamble or summary.
"""
        with httpx.Client(timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10)) as client:
            try:
                client.post(f"{base_url}/message", json={"type": "user", "content": investigation_prompt}).raise_for_status()
            except httpx.TimeoutException:
                _log.info("spawn_agentapi: message POST timed out (expected) — monitor is running")

    except Exception as exc:
        _log.exception("spawn_agentapi: failed session=%s", session_id)
        # Clean up subprocess if it was started
        proc = session.get("agentapi_proc")
        if proc:
            proc.terminate()
        s = _WORK_SESSIONS.get(session_id)
        if s:
            s.update(
                {
                    "phase": "error",
                    "error": str(exc),
                    "activity_message": "Could not start AgentAPI. Is it installed?",
                }
            )



def _wait_for_stable(base_url: str, poll_interval: float = 2.0, timeout: float = 1200.0) -> bool:
    """Poll AgentAPI GET /status until status is 'stable'. Returns True on stable, False on timeout."""
    import httpx

    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=10) as client:
        while time.monotonic() < deadline:
            try:
                r = client.get(f"{base_url}/status")
                if r.status_code == 200:
                    data = r.json()
                    # AgentAPI returns {"status": "stable"} or {"status": "running"}
                    status = data.get("status") if isinstance(data, dict) else data
                    if status == "stable":
                        return True
            except Exception:
                pass
            time.sleep(poll_interval)
    return False


def _extract_last_assistant_text(messages_data: Any) -> str:
    """Extract the last assistant message text from AgentAPI GET /messages response.

    Strips terminal prompt echoes (e.g. 'ask> ...') that Aider prepends to
    its output when running in non-default chat modes.
    """
    import re

    msgs: list[Any] = []
    if isinstance(messages_data, dict):
        msgs = messages_data.get("messages", [])
    elif isinstance(messages_data, list):
        msgs = messages_data

    for msg in reversed(msgs):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role in ("assistant", "agent"):
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle content blocks: [{"type": "text", "text": "..."}]
                    texts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ]
                    content = "\n".join(texts)
                if not isinstance(content, str):
                    continue
                # Strip leading terminal prompt-echo lines (e.g. "ask> ...", "code> ...")
                lines = content.split("\n")
                cleaned: list[str] = []
                stripping_prompt = True
                for line in lines:
                    if stripping_prompt and re.match(r"^\w+>\s*", line.rstrip()):
                        continue
                    stripping_prompt = False
                    cleaned.append(line.rstrip())
                return "\n".join(cleaned).strip()
    return ""


def _snapshot_repo_mtimes(repo_root: Path) -> dict[str, float]:
    """Snapshot file mtimes in the golden repo."""
    try:
        return {
            str(p.relative_to(repo_root)): p.stat().st_mtime
            for p in repo_root.rglob("*")
            if p.is_file() and not any(
                part.startswith(".") or part == "__pycache__"
                for part in p.parts
            )
        }
    except Exception:
        return {}


def _changed_node_ids_from_mtimes(before: dict[str, float], repo_root: Path) -> list[str]:
    """Compare mtime snapshots to find which flow.json nodes changed."""
    try:
        after = _snapshot_repo_mtimes(repo_root)
        file_map = _build_file_to_nodes_map()
        changed_files = [rel for rel, mtime in after.items() if before.get(rel) != mtime]
        _log.info("monitor: mtime-diff changed_files=%r", changed_files)
        node_ids: list[str] = []
        for rel in changed_files:
            node_ids.extend(file_map.get(rel, []))
        return list(set(node_ids))
    except Exception:
        _log.exception("monitor: mtime-diff error")
        return []


def _monitor_agentapi(session_id: str, port: int) -> None:
    """Background thread: drive AgentAPI through investigate→plan→confirm→execute→done."""
    import httpx

    session = _WORK_SESSIONS.get(session_id)
    if not session:
        return

    base_url = f"http://localhost:{port}"
    session_start = time.monotonic()

    try:
        # ── Phase 1: Wait for investigation to complete ──────────────────────
        session.update({"phase": "investigating", "activity_message": "Investigating the codebase…"})
        stable = _wait_for_stable(base_url, timeout=_MAX_SESSION_SECONDS)
        if not stable or time.monotonic() - session_start > _MAX_SESSION_SECONDS:
            _log.warning("monitor_agentapi: investigation timed out session=%s", session_id)
            session.update({"phase": "error", "activity_message": "Timed out during investigation.", "error": "Investigation exceeded time limit."})
            return
        if not _WORK_SESSIONS.get(session_id):
            return  # cancelled

        # Ask agent for a clean numbered plan (avoids repo-scan noise in the raw response)
        with httpx.Client(timeout=httpx.Timeout(connect=10, read=60, write=10, pool=10)) as client:
            try:
                client.post(
                    f"{base_url}/message",
                    json={"type": "user", "content":
                        "Based on your investigation, output ONLY a clean numbered implementation plan. "
                        "5-10 concrete steps maximum. No file scan output, no statistics, no preamble. "
                        "Just the numbered list of what to implement."},
                )
            except Exception:
                pass
        _wait_for_stable(base_url, timeout=60)
        with httpx.Client(timeout=15) as client:
            msgs_resp = client.get(f"{base_url}/messages")
            msgs_data = msgs_resp.json() if msgs_resp.status_code == 200 else []
        plan_text = _extract_last_assistant_text(msgs_data)
        _log.info("monitor_agentapi: plan extracted len=%d session=%s", len(plan_text), session_id)

        session.update({
            "phase": "planning",
            "activity_message": "Review the plan below and confirm to execute.",
            "plan_text": plan_text,
        })

        # ── Wait for user to confirm the plan ────────────────────────────────
        plan_deadline = time.monotonic() + 600  # 10 min to review
        while time.monotonic() < plan_deadline:
            s = _WORK_SESSIONS.get(session_id)
            if not s:
                return  # cancelled
            if s.get("plan_confirmed"):
                break
            time.sleep(0.5)
        else:
            session.update({"phase": "error", "activity_message": "Timed out waiting for plan confirmation.", "error": "Plan not confirmed within 10 minutes."})
            return

        # ── Phase 2: Switch to code mode and execute ──────────────────────────
        session.update({"phase": "writing", "activity_message": "Writing changes…"})

        try:
            repo_root = _golden_repo()
        except Exception:
            repo_root = None

        mtime_before: dict[str, float] = _snapshot_repo_mtimes(repo_root) if repo_root else {}

        repo_path = str(repo_root) if repo_root else ""
        test_cmd = f'cd "{repo_path}" && python -m pytest' if repo_path else "python -m pytest"

        # Switch Aider from ask → code mode (same session, context preserved)
        with httpx.Client(timeout=15) as client:
            try:
                client.post(f"{base_url}/message", json={"type": "user", "content": "/code"}).raise_for_status()
            except Exception:
                pass
        _wait_for_stable(base_url, timeout=30)

        execute_msg = (
            f"Implement the plan we just discussed. Use absolute file paths.\n"
            f"After making all changes, run: {test_cmd}\n"
            f"If tests fail, fix and retry up to 3 times.\n"
            f"End with a 2-3 sentence plain-language summary of what changed."
        )
        with httpx.Client(timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10)) as client:
            try:
                client.post(f"{base_url}/message", json={"type": "user", "content": execute_msg}).raise_for_status()
            except httpx.TimeoutException:
                pass  # expected — agent is working

        stable = _wait_for_stable(base_url, timeout=_MAX_SESSION_SECONDS)
        if not stable:
            session.update({"phase": "error", "activity_message": "Timed out during execution.", "error": "Execution exceeded time limit."})
            return

        session["phase"] = "checking"
        time.sleep(1)

        # Extract changed nodes and summary
        if repo_root:
            changed_ids = _changed_node_ids_from_mtimes(mtime_before, repo_root)
            session["changed_node_ids"] = changed_ids
            _log.info("monitor_agentapi: changed_node_ids=%r", changed_ids)

        # Ask for a plain-language summary of what changed
        summary = "Done."
        with httpx.Client(timeout=httpx.Timeout(connect=10, read=60, write=10, pool=10)) as client:
            try:
                client.post(
                    f"{base_url}/message",
                    json={"type": "user", "content": "In 2-3 plain sentences, summarize what you just changed and why. No code, no file names, no jargon."},
                ).raise_for_status()
            except httpx.TimeoutException:
                pass
        _wait_for_stable(base_url, timeout=60)
        with httpx.Client(timeout=15) as client:
            msgs_resp = client.get(f"{base_url}/messages")
            msgs_data = msgs_resp.json() if msgs_resp.status_code == 200 else []
        summary_text = _extract_last_assistant_text(msgs_data)
        if summary_text:
            summary = summary_text

        session.update({"phase": "done", "activity_message": "Done.", "summary": summary})
        _log.info("monitor_agentapi: done session=%s summary=%r", session_id, summary[:80])

    except Exception:
        _log.exception("monitor_agentapi: error session=%s", session_id)
        import traceback
        s = _WORK_SESSIONS.get(session_id)
        if s:
            s.update({"phase": "error", "error": traceback.format_exc(), "activity_message": "Something went wrong."})
    finally:
        proc = (_WORK_SESSIONS.get(session_id) or {}).get("agentapi_proc")
        if proc:
            proc.terminate()


def _normalize_overlay(body: dict[str, Any]) -> dict[str, Any]:
    by_sym = body.get("by_symbol_id")
    by_file = body.get("by_file_id")
    by_dir = body.get("by_directory_id")
    by_root = body.get("by_root_id")
    by_flow = body.get("by_flow_node_id")
    if by_sym is not None and not isinstance(by_sym, dict):
        raise HTTPException(status_code=422, detail="by_symbol_id must be an object")
    if by_file is not None and not isinstance(by_file, dict):
        raise HTTPException(status_code=422, detail="by_file_id must be an object")
    if by_dir is not None and not isinstance(by_dir, dict):
        raise HTTPException(status_code=422, detail="by_directory_id must be an object")
    if by_root is not None and not isinstance(by_root, dict):
        raise HTTPException(status_code=422, detail="by_root_id must be an object")
    if by_flow is not None and not isinstance(by_flow, dict):
        raise HTTPException(status_code=422, detail="by_flow_node_id must be an object")
    sv = body.get("schema_version")
    if sv is not None and not isinstance(sv, int):
        raise HTTPException(status_code=422, detail="schema_version must be an integer")
    return {
        "schema_version": int(sv) if isinstance(sv, int) else 0,
        "by_symbol_id": dict(by_sym) if isinstance(by_sym, dict) else {},
        "by_file_id": dict(by_file) if isinstance(by_file, dict) else {},
        "by_directory_id": dict(by_dir) if isinstance(by_dir, dict) else {},
        "by_root_id": dict(by_root) if isinstance(by_root, dict) else {},
        "by_flow_node_id": dict(by_flow) if isinstance(by_flow, dict) else {},
    }


app = FastAPI(
    title="Brainstorm API",
    description="RAW + execution IR (flow.json) + overlay for the brainstorm POC.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/raw")
def get_raw() -> JSONResponse:
    path = _raw_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@app.get("/flow")
def get_flow() -> JSONResponse:
    path = _flow_path()
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Missing {path} — run POST /reindex or index:golden"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


def _no_store_json(data: dict[str, Any]) -> JSONResponse:
    return JSONResponse(content=data, headers={"Cache-Control": "no-store"})


@app.get("/overlay")
def get_overlay() -> JSONResponse:
    path = _overlay_path()
    if not path.is_file():
        return _no_store_json(
            {
                "schema_version": 0,
                "by_symbol_id": {},
                "by_file_id": {},
                "by_directory_id": {},
                "by_root_id": {},
                "by_flow_node_id": {},
            },
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return _no_store_json(data)


@app.patch("/overlay")
def patch_overlay(body: dict[str, Any]) -> JSONResponse:
    raw_path = _raw_path()
    if not raw_path.is_file():
        raise HTTPException(status_code=400, detail="raw.json must exist before patching overlay")
    raw_doc = json.loads(raw_path.read_text(encoding="utf-8"))
    overlay = _normalize_overlay(body)
    sym_orphans = overlay_orphan_keys(overlay, raw_doc)
    file_orphans = overlay_orphan_file_keys(overlay, raw_doc)
    dir_orphans = overlay_orphan_directory_keys(overlay, raw_doc)
    root_orphans = overlay_orphan_root_keys(overlay)
    flow_orphans = overlay_orphan_flow_keys(overlay, raw_doc)
    if sym_orphans or file_orphans or dir_orphans or root_orphans or flow_orphans:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Overlay contains keys not present in RAW / flow IR",
                "orphan_symbol_ids": sym_orphans,
                "orphan_file_ids": file_orphans,
                "orphan_directory_ids": dir_orphans,
                "orphan_root_ids": root_orphans,
                "orphan_flow_node_ids": flow_orphans,
            },
        )
    out = _overlay_path()
    out.write_text(json.dumps(overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return JSONResponse(content=overlay)


@app.get("/comments")
def get_comments() -> JSONResponse:
    return _no_store_json(_load_comments_doc())


@app.post("/comments")
def add_comment(comment: CommentIn) -> dict[str, Any]:
    doc = _load_comments_doc()
    doc["comments"].append(comment.model_dump())
    _save_comments_doc(doc)
    return {"ok": True, "id": comment.id}


@app.patch("/comments/{comment_id}")
def patch_comment(comment_id: str, patch: CommentPatch) -> dict[str, Any]:
    doc = _load_comments_doc()
    for c in doc["comments"]:
        if c["id"] == comment_id:
            if patch.pending is not None:
                c["pending"] = patch.pending
            _save_comments_doc(doc)
            return {"ok": True}
    raise HTTPException(status_code=404, detail=f"Comment {comment_id!r} not found")


@app.delete("/comments/{comment_id}")
def delete_comment(comment_id: str) -> dict[str, Any]:
    doc = _load_comments_doc()
    before = len(doc["comments"])
    doc["comments"] = [c for c in doc["comments"] if c["id"] != comment_id]
    if len(doc["comments"]) == before:
        raise HTTPException(status_code=404, detail=f"Comment {comment_id!r} not found")
    _save_comments_doc(doc)
    return {"ok": True}


_ORCHESTRATOR_SYSTEM_PROMPT = """\
You receive user notes tied to execution-map node anchors. Each note includes node IDs, human-readable labels, and the file paths those nodes live in.

First: group notes that touch the same logical concern or the same area of code into one chunk.

Second: check each chunk pair for conflicts — shared edit sites, call-chain dependencies, or ordering constraints. Chunks must be independently executable or explicitly ordered.

Third: if two chunks cannot be made independent, assign an explicit order and explain why in order_note. If order is genuinely unclear, say so — do not invent a sequence.

Do not write patches, diffs, or solutions here. Output the plan only.

Output ONLY a JSON object with this exact shape:
{
  "schema_version": 0,
  "chunks": [
    {
      "id": "chunk-1",
      "summary": "Short plain-English description of the change",
      "comment_ids": ["<uuid>"],
      "node_ids": ["<flow_node_id>"],
      "depends_on": [],
      "order_note": ""
    }
  ]
}
Rules: depends_on lists chunk ids this chunk must come after (empty if independent). order_note is blank when truly independent; otherwise a one-sentence explanation. Do not add extra keys.\
"""


@app.get("/plan")
def get_plan() -> JSONResponse:
    return _no_store_json(_load_plan_doc())


@app.post("/plan")
def save_plan(body: dict[str, Any]) -> dict[str, Any]:
    _save_plan_doc(body)
    return {"ok": True}


@app.delete("/plan")
def delete_plan() -> dict[str, Any]:
    _delete_plan_doc()
    return {"ok": True}


@app.post("/orchestrate")
def orchestrate() -> JSONResponse:
    """
    Slice B: read all pending comments + flow context, call orchestrator AI
    (or return a deterministic stub when ORCHESTRATE_DRY_RUN=1).
    """
    comments_doc = _load_comments_doc()
    pending = [c for c in comments_doc.get("comments", []) if c.get("pending")]
    if not pending:
        raise HTTPException(status_code=400, detail="No pending comments to orchestrate.")

    # Build node context from flow.json (id → file path).
    node_file: dict[str, str] = {}
    flow_p = _flow_path()
    if flow_p.is_file():
        flow_doc = json.loads(flow_p.read_text(encoding="utf-8"))
        for node in flow_doc.get("nodes", []):
            nid = node.get("id", "")
            path = (node.get("location") or {}).get("path") or ""
            if nid:
                node_file[nid] = path

    # Collect unique node IDs referenced by pending comments.
    all_node_ids: list[str] = []
    seen: set[str] = set()
    for c in pending:
        for nid in c.get("node_ids", []):
            if nid not in seen:
                seen.add(nid)
                all_node_ids.append(nid)

    node_context = [{"id": nid, "file_path": node_file.get(nid, "")} for nid in all_node_ids]

    dry_run = os.environ.get("ORCHESTRATE_DRY_RUN", "0").strip() == "1"

    if dry_run:
        # v0 stub: one chunk per pending comment, all independent.
        chunks = [
            {
                "id": f"chunk-{i + 1}",
                "summary": f"[Stub] {c['body'][:80]}{'…' if len(c['body']) > 80 else ''}",
                "comment_ids": [c["id"]],
                "node_ids": c.get("node_ids", []),
                "depends_on": [],
                "order_note": "",
            }
            for i, c in enumerate(pending)
        ]
        plan: dict[str, Any] = {"schema_version": 0, "chunks": chunks}
    else:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="DEEPSEEK_API_KEY not set. Set ORCHESTRATE_DRY_RUN=1 for stub mode.",
            )
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()

        user_payload = {
            "comments": [
                {
                    "id": c["id"],
                    "node_ids": c.get("node_ids", []),
                    "node_labels": c.get("node_labels", []),
                    "body": c["body"],
                }
                for c in pending
            ],
            "node_context": node_context,
        }
        try:
            plan = _chat_completion_json(
                api_key=api_key,
                base_url=base_url,
                model=model,
                system=_ORCHESTRATOR_SYSTEM_PROMPT,
                user=json.dumps(user_payload),
                timeout=60.0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Orchestrator LLM call failed: {exc}",
            ) from exc

        if "chunks" not in plan:
            raise HTTPException(
                status_code=503,
                detail=f"Orchestrator returned unexpected shape: {str(plan)[:200]}",
            )

    _save_plan_doc(plan)
    return _no_store_json(plan)


_EXECUTE_SYSTEM_PROMPT = """\
You are a software developer. You receive a task description, the user comments that motivated it, and the current source code for the relevant files. Produce a unified diff (patch -p1 format, paths relative to repo root) that implements exactly what the task describes.

Output ONLY a JSON object with this exact shape:
{"unified_diff": "<the full unified diff as a single string>"}

Rules:
- The diff must be valid patch -p1 format (--- a/path, +++ b/path, @@ hunks).
- Make the minimal change that satisfies the task. Do not add comments, logging, or unrequested changes.
- Do not include any explanation outside the JSON.\
"""

# Canned diff used when EXECUTE_DRY_RUN=1 so the UI can be wired without a live LLM key.
_STUB_UNIFIED_DIFF = """\
--- a/src/golden_app/core.py
+++ b/src/golden_app/core.py
@@ -4,4 +4,8 @@
 def greeting_for(name: str) -> str:
     \"\"\"Return a short greeting string.\"\"\"
-    cleaned = name.strip() or "world"
+    if not name or not name.strip():
+        # Handle empty strings, None, or whitespace-only strings gracefully
+        cleaned = "friend"
+    else:
+        cleaned = name.strip()
     return f"Hello, {cleaned}!"
"""


class ExecuteChunkBody(BaseModel):
    chunk_id: str


class ChunkPatch(BaseModel):
    executed: bool | None = None


@app.get("/source")
def get_source(path: str, start: int = 1, end: int = 0) -> JSONResponse:
    """Return a source code excerpt from BRAINSTORM_GOLDEN_REPO for developer AI context."""
    if ".." in path:
        raise HTTPException(status_code=400, detail="Path must not contain '..'")
    repo = _golden_repo()
    effective_end = end if end >= start else start
    content = _read_excerpt(repo, path, start, effective_end)
    if not content and not (repo / path).is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return JSONResponse(content={"content": content})


@app.post("/execute-chunk")
def execute_chunk(body: ExecuteChunkBody) -> JSONResponse:
    """
    Slice C: for one approved chunk, generate a unified diff via the developer AI.
    Does NOT apply the diff — returns it for preview.
    """
    plan = _load_plan_doc()
    chunks = plan.get("chunks", [])
    chunk = next((c for c in chunks if c.get("id") == body.chunk_id), None)
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Chunk {body.chunk_id!r} not found in plan")

    # Build node → file location map from flow.json.
    node_location: dict[str, dict[str, Any]] = {}
    flow_p = _flow_path()
    if flow_p.is_file():
        flow_doc = json.loads(flow_p.read_text(encoding="utf-8"))
        for node in flow_doc.get("nodes", []):
            nid = node.get("id", "")
            loc = node.get("location") or {}
            if nid and loc.get("path"):
                node_location[nid] = loc

    # Load linked comments.
    comments_doc = _load_comments_doc()
    comment_ids = set(chunk.get("comment_ids", []))
    linked = [c for c in comments_doc.get("comments", []) if c.get("id") in comment_ids]

    # Collect unique file paths and read excerpts.
    repo = _golden_repo()
    seen_paths: set[str] = set()
    code_context: list[dict[str, Any]] = []
    for nid in chunk.get("node_ids", []):
        loc = node_location.get(nid)
        if not loc:
            continue
        fpath = loc.get("path", "")
        if not fpath or fpath in seen_paths:
            continue
        seen_paths.add(fpath)
        start_line = loc.get("start_line") or 1
        end_line = loc.get("end_line") or start_line
        content = _read_excerpt(repo, fpath, start_line, end_line)
        code_context.append(
            {
                "path": fpath,
                "start_line": start_line,
                "end_line": end_line,
                "content": content,
            }
        )

    dry_run = os.environ.get("EXECUTE_DRY_RUN", "0").strip() == "1"

    if dry_run:
        return JSONResponse(content={"chunk_id": body.chunk_id, "unified_diff": _STUB_UNIFIED_DIFF})

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="DEEPSEEK_API_KEY not set. Set EXECUTE_DRY_RUN=1 for stub mode.",
        )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()

    user_payload = {
        "chunk_id": chunk["id"],
        "summary": chunk.get("summary", ""),
        "comments": [
            {"id": c["id"], "body": c["body"], "node_labels": c.get("node_labels", [])}
            for c in linked
        ],
        "code_context": code_context,
    }

    try:
        result = _chat_completion_json(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system=_EXECUTE_SYSTEM_PROMPT,
            user=json.dumps(user_payload),
            timeout=120.0,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Developer AI call failed: {exc}",
        ) from exc

    unified_diff = result.get("unified_diff")
    if not isinstance(unified_diff, str) or not unified_diff.strip():
        raise HTTPException(
            status_code=503,
            detail=f"Developer AI returned unexpected shape: {str(result)[:200]}",
        )

    return JSONResponse(content={"chunk_id": body.chunk_id, "unified_diff": unified_diff})


@app.patch("/plan/chunk/{chunk_id}")
def patch_plan_chunk(chunk_id: str, patch: ChunkPatch) -> dict[str, Any]:
    plan = _load_plan_doc()
    chunks = plan.get("chunks", [])
    for c in chunks:
        if c.get("id") == chunk_id:
            if patch.executed is not None:
                c["executed"] = patch.executed
            _save_plan_doc(plan)
            return {"ok": True}
    raise HTTPException(status_code=404, detail=f"Chunk {chunk_id!r} not found in plan")


# ─── Work session (PM-to-developer flow) ─────────────────────────────────────

# In-process session store. Sessions are ephemeral — restart clears them.
_WORK_SESSIONS: dict[str, dict[str, Any]] = {}

_STUB_PHASES = [
    (3.0, "investigating", "Investigating the codebase starting from your annotation…"),
    (7.0, "planning", "Review the plan below and confirm to execute."),
    (12.0, "writing", "Writing changes…"),
    (14.0, "checking", "Running checks…"),
]
_STUB_CHECK_IN_AT = 4.5  # show check-in once, mid-investigating
_STUB_PLAN_TEXT = """\
1. Add input validation to the `parse_config()` function in config.py to reject malformed inputs early.
2. Update `load_settings()` to propagate the new `ValidationError` to callers.
3. Add unit tests in test_config.py covering the new error path and the happy path.
4. Run the full test suite to confirm no regressions."""


@app.get("/debug/sessions")
def debug_sessions() -> JSONResponse:
    """Developer endpoint: full state of all active work sessions."""
    out = {}
    for sid, s in _WORK_SESSIONS.items():
        out[sid] = {
            "phase": s.get("phase"),
            "activity_message": s.get("activity_message"),
            "error": s.get("error"),
            "oc_session_id": s.get("oc_session_id"),
            "brief": s.get("brief", "")[:80],
            "accumulated_text_len": len(s.get("accumulated_text", "")),
            "changed_node_ids": s.get("changed_node_ids", []),
            "event_log": s.get("event_log", []),
            "elapsed": round(time.time() - s.get("start", time.time()), 1),
        }
    return JSONResponse(content=out)


class GoBody(BaseModel):
    brief: str
    node_ids: list[str] = []
    node_labels: list[str] = []
    extra_context: str = ""


class ReplyBody(BaseModel):
    answer: str


@app.post("/go")
def go(body: GoBody) -> JSONResponse:
    """Start a work session. Returns session_id immediately in investigating phase."""
    _cleanup_old_sessions()
    _save_work_session(body)
    session_id = str(uuid4())

    _WORK_SESSIONS[session_id] = {
        "start": time.time(),
        "brief": body.brief,
        "node_ids": body.node_ids,
        "node_labels": body.node_labels,
        "extra_context": body.extra_context,
        "phase": "investigating",
        "activity_message": "Investigating the codebase…",
        "check_in_answered": False,
        "plan_text": None,
        "plan_confirmed": False,
        "agentapi_proc": None,
        "agentapi_port": None,
        "changed_node_ids": [],
    }

    dry_run = os.environ.get("WORK_DRY_RUN", "0").strip() == "1"
    if dry_run:
        return JSONResponse(content={"session_id": session_id})

    # Real mode: spawn AgentAPI immediately
    _log.info("go: session=%s brief=%r nodes=%r", session_id, body.brief[:60], body.node_ids)
    t = threading.Thread(
        target=_spawn_agentapi,
        args=(session_id, body.brief, body.node_ids, body.node_labels, body.extra_context),
        daemon=True,
    )
    t.start()

    return JSONResponse(content={"session_id": session_id})


@app.get("/status/{session_id}")
def get_status(session_id: str) -> JSONResponse:
    """Poll work session status."""
    session = _WORK_SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    dry_run = os.environ.get("WORK_DRY_RUN", "0").strip() == "1"
    if not dry_run:
        return JSONResponse(
            content={
                "phase": session.get("phase", "investigating"),
                "activity_message": session.get("activity_message", "Starting up…"),
                "check_in": None,
                "plan_text": session.get("plan_text"),
                "summary": session.get("summary"),
                "note": None,
                "changed_node_ids": session.get("changed_node_ids", []),
                "error": session.get("error"),
            }
        )

    elapsed = time.time() - session["start"]
    brief: str = session["brief"]
    node_ids: list[str] = session.get("node_ids", [])
    check_in_answered: bool = session.get("check_in_answered", False)

    # Find current phase from elapsed time since session start
    phase, activity_message = "investigating", "Investigating…"
    for threshold, ph, msg in _STUB_PHASES:
        if elapsed >= threshold:
            phase, activity_message = ph, msg

    plan_confirmed: bool = session.get("plan_confirmed", False)

    # Planning phase: freeze here until user confirms — no auto-advance
    if phase == "planning" and not plan_confirmed:
        session["phase"] = "planning"  # write back so reply handler sees correct phase
        return JSONResponse(
            content={
                "phase": "planning",
                "activity_message": activity_message,
                "check_in": None,
                "plan_text": _STUB_PLAN_TEXT,
                "summary": None,
                "changed_node_ids": [],
                "error": None,
            }
        )

    # Post-planning phases: base elapsed on time since plan was confirmed
    if plan_confirmed:
        plan_confirm_time: float = session.get("plan_confirm_time", time.time())
        post_plan_elapsed = time.time() - plan_confirm_time
        # Re-map to post-planning phases only (writing, checking, done)
        post_phases = [(ph, msg) for (_, ph, msg) in _STUB_PHASES if ph not in ("investigating", "planning")]
        post_thresholds = [2.0, 4.0]  # writing at 2s, checking at 4s, done at 6s
        post_done_at = 6.0
        phase, activity_message = "writing", "Writing changes…"
        for thresh, (ph, msg) in zip(post_thresholds, post_phases):
            if post_plan_elapsed >= thresh:
                phase, activity_message = ph, msg

        if post_plan_elapsed >= post_done_at:
            short_brief = brief[:60] + ("…" if len(brief) > 60 else "")
            summary = (
                f'I looked into the issue you described ("{short_brief}"). '
                "The logic now handles edge cases more gracefully — the problematic path "
                "falls back to a safe default instead of raising an unhandled error. "
                "Related call sites were updated to stay consistent."
            )
            return JSONResponse(
                content={
                    "phase": "done",
                    "activity_message": "Done.",
                    "plan_text": None,
                    "summary": summary,
                    "note": "One edge case was left intentionally untouched — it looked out of scope. Worth a follow-up if you see issues there.",
                    "changed_node_ids": node_ids[:2] if node_ids else [],
                }
            )
        return JSONResponse(content={"phase": phase, "activity_message": activity_message, "plan_text": None})

    # Check-in mid-investigating (once, if not answered)
    if elapsed >= _STUB_CHECK_IN_AT and phase == "investigating" and not check_in_answered:
        return JSONResponse(
            content={
                "phase": phase,
                "activity_message": "Found a few related areas…",
                "plan_text": None,
                "check_in": {
                    "question": "Should the fix apply broadly to all similar cases, or only to the area you pointed at?",
                    "options": ["Broadly — fix all similar cases", "Just the area I pointed at"],
                },
            }
        )

    return JSONResponse(content={"phase": phase, "activity_message": activity_message, "plan_text": None})


@app.post("/status/{session_id}/reply")
def reply_check_in(session_id: str, body: ReplyBody) -> dict[str, Any]:
    """Submit a reply — either plan confirmation/feedback or a check-in answer."""
    session = _WORK_SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("phase") == "planning":
        # Reply in planning phase confirms the plan; non-confirm answer is stored as feedback
        if body.answer and body.answer != "__confirm__":
            session["plan_feedback"] = body.answer
        session["plan_confirmed"] = True
        session["plan_confirm_time"] = time.time()
        _log.info("reply_check_in: plan confirmed session=%s", session_id)
        return {"ok": True}

    _log.info("reply_check_in: phase=%s answer=%r session=%s", session.get("phase"), body.answer, session_id)

    # Check-in reply (post-align phases)
    session["check_in_answered"] = True
    return {"ok": True}


@app.post("/status/{session_id}/cancel")
def cancel_session(session_id: str) -> dict[str, Any]:
    """Cancel an in-flight work session."""
    _WORK_SESSIONS.pop(session_id, None)
    return {"ok": True}


@app.post("/status/{session_id}/undo")
def undo_session(session_id: str) -> dict[str, Any]:
    """Stub: undo not yet implemented (OpenCode revert planned)."""
    _WORK_SESSIONS.pop(session_id, None)
    return {"ok": True, "note": "Undo not yet implemented — no changes were reverted."}


@app.post("/reindex")
def reindex(body: ReindexBody | None = None) -> dict[str, Any]:
    root = (
        Path(body.repo_root).expanduser().resolve() if body and body.repo_root else _golden_repo()
    )
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    doc = index_repo(root)
    raw_out = _raw_path()
    write_index(doc, raw_out)
    flow_out = _write_flow_json(doc)
    return {
        "ok": True,
        "wrote": str(raw_out),
        "flow_wrote": str(flow_out),
        "symbol_count": len(doc.get("symbols", [])),
        "file_count": len(doc.get("files", [])),
    }


@app.post("/apply-bundle")
def apply_bundle_http(body: ApplyBundleBody) -> JSONResponse:
    """
    Apply a change package to **BRAINSTORM_GOLDEN_REPO**, then refresh **public/raw.json**
    so GET /raw matches the repo after success.
    """
    root = _golden_repo()
    bundle_dict = _bundle_dict_from_body(body)
    overlay_path = _overlay_path() if body.overlay is not None else None
    res = apply_bundle(
        root,
        bundle_dict,
        overlay_path=overlay_path,
        dry_run=body.dry_run,
        skip_validate=body.skip_validate,
        pytest_only=body.pytest_only,
    )
    if res.ok and not body.dry_run:
        doc = index_repo(root)
        write_index(doc, _raw_path())
        _write_flow_json(doc)
    payload = res.to_json_dict()
    if not res.ok:
        return JSONResponse(status_code=422, content=payload)
    return JSONResponse(content=payload)


@app.post("/update-map")
def update_map() -> JSONResponse:
    """
    **Update map** — AI (DeepSeek) fills ``displayName`` / ``userDescription`` in
    ``overlay.json``. Requires ``DEEPSEEK_API_KEY`` unless ``UPDATE_MAP_DRY_RUN=1``.

    Refreshes ``raw.json`` from ``BRAINSTORM_GOLDEN_REPO`` first.
    """
    root = _golden_repo()
    doc = index_repo(root)
    write_index(doc, _raw_path())
    _write_flow_json(doc)
    result = run_update_map(root, _overlay_path(), doc)
    if not result.get("ok"):
        return JSONResponse(status_code=503, content=result)
    return JSONResponse(content=result)
