"""Optional Pyright JSON → diagnostics payload."""

from __future__ import annotations

import json
from pathlib import Path

from raw_indexer.diagnostics_pyright import diagnostics_payload_for_raw


def test_diagnostics_payload_normalizes_paths(samples_dir: Path) -> None:
    sample = samples_dir / "pyright-output-sample.json"
    data = json.loads(sample.read_text(encoding="utf-8"))
    repo = Path("/abs/repo")
    payload = diagnostics_payload_for_raw(repo, data)
    assert payload["schema_version"] == 0
    assert payload["partial"] is True
    assert "src/pkg/mod.py" in payload["by_path"]
    issues = payload["by_path"]["src/pkg/mod.py"]
    assert len(issues) == 1
    assert issues[0]["line"] == 3
    assert issues[0]["severity"] == "error"
    assert issues[0]["rule"] == "reportUndefinedVariable"
