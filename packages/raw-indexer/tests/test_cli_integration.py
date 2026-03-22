from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[1]


def _golden_app_importable() -> bool:
    return importlib.util.find_spec("golden_app") is not None


@pytest.mark.skipif(not _golden_app_importable(), reason="pip install -e fixtures/golden-fastapi[dev]")
def test_validate_golden_pytest_only(golden_repo: Path) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "raw_indexer", "validate", str(golden_repo), "--pytest-only"],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout


def test_apply_verify_sample_patch(golden_repo: Path, samples_dir: Path, tmp_path: Path) -> None:
    """Isolated venv: install golden copy + raw-indexer, then apply-verify."""
    dest = tmp_path / "golden-copy"
    shutil.copytree(
        golden_repo,
        dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.egg-info"),
    )
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    py = venv / "bin" / "python"
    pip = venv / "bin" / "pip"
    subprocess.run([str(pip), "install", "-q", "--upgrade", "pip"], check=True)
    subprocess.run([str(pip), "install", "-q", "-e", f"{dest}[dev]"], check=True)
    subprocess.run([str(pip), "install", "-q", "-e", str(_PKG_ROOT)], check=True)
    patch = samples_dir / "docstring.patch"
    r = subprocess.run(
        [
            str(py),
            "-m",
            "raw_indexer",
            "apply-verify",
            str(dest),
            str(patch),
            "--pytest-only",
            "--write-raw",
            str(tmp_path / "out.json"),
        ],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    core = dest / "src" / "golden_app" / "core.py"
    assert "patched" in core.read_text(encoding="utf-8")
    assert (tmp_path / "out.json").is_file()
