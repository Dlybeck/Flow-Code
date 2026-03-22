from __future__ import annotations

from pathlib import Path

import pytest


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
