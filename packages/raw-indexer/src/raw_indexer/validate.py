"""Run pytest and basedpyright/pyright on a target repo (subprocess)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _env_with_src_on_path(repo: Path) -> dict[str, str]:
    """Uninstalled `src/` layout repos: let `pytest` import the package."""
    env = dict(os.environ)
    src = repo / "src"
    if src.is_dir():
        prev = env.get("PYTHONPATH", "")
        prefix = str(src.resolve())
        env["PYTHONPATH"] = prefix + (os.pathsep + prev if prev else "")
    return env


def run_pytest(repo: Path, *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=repo,
        capture_output=capture,
        text=True,
        env=_env_with_src_on_path(repo),
    )


def resolve_typechecker() -> str | None:
    for cmd in ("basedpyright", "pyright"):
        if shutil.which(cmd):
            return cmd
    return None


def run_typecheck(repo: Path, *, capture: bool = True) -> subprocess.CompletedProcess[str] | None:
    cmd = resolve_typechecker()
    if not cmd:
        return None
    # Analyze project from root; pyright/basedpyright accept directory
    return subprocess.run(
        [cmd, str(repo)],
        cwd=repo,
        capture_output=capture,
        text=True,
    )


def validate_repo(repo: Path, *, pytest_only: bool = False) -> int:
    """Run checks; return 0 if all ran OK, non-zero otherwise."""
    repo = repo.resolve()
    pr = run_pytest(repo)
    if pr.returncode != 0:
        sys.stdout.write(pr.stdout or "")
        sys.stderr.write(pr.stderr or "")
        return pr.returncode

    if pytest_only:
        return 0

    tc = run_typecheck(repo)
    if tc is None:
        sys.stderr.write(
            "raw-indexer validate: no `basedpyright` or `pyright` on PATH; "
            "install one or use --pytest-only.\n"
        )
        return 1

    if tc.returncode != 0:
        sys.stdout.write(tc.stdout or "")
        sys.stderr.write(tc.stderr or "")
        return tc.returncode

    return 0
