"""Apply a unified diff with GNU patch; optional apply + validate loop."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def apply_unified_patch(repo: Path, patch_file: Path, *, dry_run: bool = False) -> int:
    """Run `patch` in repo root. Returns patch exit code."""
    repo = repo.resolve()
    patch_file = patch_file.resolve()
    if not shutil.which("patch"):
        sys.stderr.write("raw-indexer apply: `patch` executable not found.\n")
        return 1
    cmd = ["patch", "-d", str(repo), "-p1", "-i", str(patch_file)]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.call(cmd)
