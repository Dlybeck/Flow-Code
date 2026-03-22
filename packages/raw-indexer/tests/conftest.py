from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Load repo-root `.env` into the process so pytest sees DEEPSEEK_API_KEY (never overrides env)."""
    root = Path(__file__).resolve().parents[3]
    env_path = root / ".env"
    if not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


@pytest.fixture
def workspace_root() -> Path:
    """Modular Code workspace (parent of `packages/`)."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def golden_repo(workspace_root: Path) -> Path:
    return workspace_root / "fixtures" / "golden-fastapi"


@pytest.fixture
def samples_dir(workspace_root: Path) -> Path:
    return workspace_root / "packages" / "raw-indexer" / "samples"
