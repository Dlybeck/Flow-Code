"""CLI overlay-migrate smoke test."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]


def test_cli_overlay_migrate_dry_run(tmp_path: Path, golden_repo: Path) -> None:
    from raw_indexer.index import index_repo

    before = index_repo(golden_repo)
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    p1.write_text(json.dumps(before), encoding="utf-8")
    p2.write_text(json.dumps(before), encoding="utf-8")
    ov = tmp_path / "o.json"
    ov.write_text(json.dumps({"schema_version": 0, "by_symbol_id": {}, "by_file_id": {}}), encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "raw_indexer",
            "overlay-migrate",
            str(p1),
            str(p2),
            str(ov),
            "--dry-run",
        ],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "report" in out
    assert "overlay" in out
