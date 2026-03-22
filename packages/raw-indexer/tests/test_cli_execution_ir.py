from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]


def test_cli_execution_ir_writes_json(golden_repo: Path, tmp_path: Path) -> None:
    out = tmp_path / "flow.json"
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "raw_indexer",
            "execution-ir",
            str(golden_repo),
            "-o",
            str(out),
        ],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 0
    labels = {n["label"] for n in doc["nodes"]}
    assert "golden_app.core.greeting_for" in labels
