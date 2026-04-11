"""Optional Pyright / Basedpyright JSON diagnostics → RAW attachment (Phase 4)."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def resolve_typechecker() -> str | None:
    for cmd in ("basedpyright", "pyright"):
        if shutil.which(cmd):
            return cmd
    return None


def _pyright_argv_attempts(cmd: str, repo: Path) -> list[list[str]]:
    r = str(repo.resolve())
    if cmd == "basedpyright":
        return [
            [cmd, "analyze", r, "--outputjson"],
            [cmd, r, "--outputjson"],
        ]
    return [[cmd, r, "--outputjson"]]


def run_pyright_json(repo: Path) -> dict[str, Any] | None:
    """
    Run type checker with --outputjson. Returns parsed dict or None if unavailable / failure.
    """
    cmd = resolve_typechecker()
    if not cmd:
        return None
    repo = repo.resolve()
    for argv in _pyright_argv_attempts(cmd, repo):
        try:
            proc = subprocess.run(
                argv,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        raw_out = (proc.stdout or "").strip()
        if not raw_out:
            continue
        try:
            return json.loads(raw_out)
        except json.JSONDecodeError:
            continue
    return None


def _rel_key_for_diagnostic_file(repo: Path, file_path: str) -> str | None:
    """Map absolute diagnostic path to repo-relative posix path for RAW file keys."""
    try:
        p = Path(file_path).resolve()
        rel = p.relative_to(repo.resolve())
        return rel.as_posix()
    except ValueError:
        return None


def diagnostics_payload_for_raw(
    repo: Path,
    pyright_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize pyright --outputjson into a compact structure keyed by path (posix, relative to repo).
    """
    repo = repo.resolve()
    by_path: dict[str, list[dict[str, Any]]] = {}
    for d in pyright_result.get("generalDiagnostics") or []:
        fp = d.get("file")
        if not fp:
            continue
        rel = _rel_key_for_diagnostic_file(repo, str(fp))
        if not rel:
            continue
        rng = d.get("range") or {}
        start = rng.get("start") or {}
        line = int(start.get("line", 0)) + 1  # 1-based for humans / RAW lines
        entry = {
            "line": line,
            "severity": d.get("severity", "information"),
            "message": d.get("message", ""),
        }
        rule = d.get("rule")
        if rule:
            entry["rule"] = rule
        by_path.setdefault(rel, []).append(entry)

    summary = pyright_result.get("summary") or {}
    return {
        "schema_version": 0,
        "partial": True,
        "note": (
            "Type checker output is orthogonal to the AST index — use for honesty / CI, "
            "not as a complete symbol graph."
        ),
        "summary": {
            "errorCount": int(summary.get("errorCount", 0)),
            "warningCount": int(summary.get("warningCount", 0)),
            "informationCount": int(summary.get("informationCount", 0)),
            "filesAnalyzed": int(summary.get("filesAnalyzed", 0)),
        },
        "by_path": {k: sorted(v, key=lambda x: (x["line"], x.get("message", ""))) for k, v in sorted(by_path.items())},
    }


def attach_diagnostics_to_raw(doc: dict[str, Any], repo: Path) -> dict[str, Any]:
    """
    If pyright/basedpyright is on PATH, merge diagnostics into a deep copy of doc.
    Otherwise return doc unchanged (same object).
    """
    cmd = resolve_typechecker()
    if not cmd:
        return doc
    data = run_pyright_json(repo)
    if not data:
        return doc
    out = copy.deepcopy(doc)
    payload = diagnostics_payload_for_raw(repo, data)
    payload["engine"] = cmd
    out["diagnostics"] = payload
    meta = dict(out.get("index_meta") or {})
    lim = list(meta.get("known_limits") or [])
    extra = f"Optional type diagnostics attached (`{cmd}`) — see top-level `diagnostics`."
    if extra not in lim:
        lim.append(extra)
    meta["known_limits"] = lim
    out["index_meta"] = meta
    return out
