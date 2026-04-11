from __future__ import annotations

import json
from pathlib import Path

from flowcode.diff_raw import diff_raw
from flowcode.index import index_repo
from flowcode.overlay import (
    load_overlay,
    overlay_orphan_directory_keys,
    overlay_orphan_file_keys,
    overlay_orphan_keys,
    valid_directory_ids,
)


def test_diff_detects_doc_change(golden_repo: Path, tmp_path: Path) -> None:
    before = index_repo(golden_repo)
    p_before = tmp_path / "a.json"
    p_after = tmp_path / "b.json"
    p_before.write_text(json.dumps(before), encoding="utf-8")
    core = golden_repo / "src" / "golden_app" / "core.py"
    text = core.read_text(encoding="utf-8")
    core.write_text(text.replace("without HTTP.", "without HTTP (edited).", 1), encoding="utf-8")
    try:
        after = index_repo(golden_repo)
        p_after.write_text(json.dumps(after), encoding="utf-8")
        d = diff_raw(p_before, p_after)
        assert d["files"]["changed"]
    finally:
        core.write_text(text, encoding="utf-8")


def test_overlay_orphans(samples_dir: Path, golden_repo: Path, tmp_path: Path) -> None:
    doc = index_repo(golden_repo)
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(doc), encoding="utf-8")
    overlay = load_overlay(samples_dir / "example_overlay.json")
    orphans = overlay_orphan_keys(overlay, doc)
    assert "sym:ghost:missing.symbol" in orphans
    assert "sym:src/golden_app/core.py:golden_app.core.greeting_for" not in orphans
    f_orphans = overlay_orphan_file_keys(overlay, doc)
    assert "file:ghost:missing.py" in f_orphans
    assert "dir:src/golden_app" in valid_directory_ids(doc)
    d_orphans = overlay_orphan_directory_keys(
        {"by_directory_id": {"dir:ghost:nope": {"displayName": "x"}}},
        doc,
    )
    assert "dir:ghost:nope" in d_orphans
