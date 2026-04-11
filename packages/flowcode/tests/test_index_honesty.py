"""Phase 4: index_meta and per-file analysis (parse failures)."""

from __future__ import annotations

from pathlib import Path

from flowcode.index import index_repo


def test_index_meta_present(golden_repo: Path) -> None:
    doc = index_repo(golden_repo)
    meta = doc.get("index_meta")
    assert isinstance(meta, dict)
    assert meta.get("completeness") == "partial"
    assert meta.get("engine") == "ast"
    assert isinstance(meta.get("known_limits"), list)
    assert len(meta["known_limits"]) >= 1


def test_files_have_analysis(golden_repo: Path) -> None:
    doc = index_repo(golden_repo)
    for f in doc["files"]:
        a = f.get("analysis")
        assert isinstance(a, dict)
        assert a.get("completeness") in ("complete", "failed")
        assert a.get("parse_ok") is (a.get("completeness") == "complete")


def test_syntax_error_file_recorded(tmp_path: Path) -> None:
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "bad.py").write_text("def x(\n", encoding="utf-8")

    doc = index_repo(tmp_path)
    bad = next(f for f in doc["files"] if f["path"].endswith("bad.py"))
    assert bad["analysis"]["completeness"] == "failed"
    assert bad["analysis"]["parse_ok"] is False
    assert "error" in bad["analysis"]
    assert not any(s["file_id"] == bad["id"] for s in doc["symbols"])
