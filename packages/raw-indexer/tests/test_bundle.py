from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from raw_indexer.bundle import apply_bundle, load_bundle, merge_overlay_delta, parse_bundle

_PKG_ROOT = Path(__file__).resolve().parents[1]


def test_parse_bundle_requires_diff_or_overlay() -> None:
    with pytest.raises(ValueError, match="unified_diff or a bundle.overlay"):
        parse_bundle({"schema_version": 0})


def test_parse_bundle_rejects_bad_schema() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        parse_bundle({"schema_version": 99, "unified_diff": "x"})


def test_parse_bundle_overlay_types() -> None:
    with pytest.raises(ValueError, match="by_symbol_id"):
        parse_bundle({"schema_version": 0, "unified_diff": "x", "overlay": {"by_symbol_id": []}})

    with pytest.raises(ValueError, match="by_directory_id"):
        parse_bundle({"schema_version": 0, "unified_diff": "x", "overlay": {"by_directory_id": []}})

    with pytest.raises(ValueError, match="by_root_id"):
        parse_bundle({"schema_version": 0, "unified_diff": "x", "overlay": {"by_root_id": []}})

    with pytest.raises(ValueError, match="by_flow_node_id"):
        parse_bundle({"schema_version": 0, "unified_diff": "x", "overlay": {"by_flow_node_id": []}})


def test_merge_overlay_delta_merges_symbol_entry() -> None:
    base = {
        "schema_version": 0,
        "by_symbol_id": {"sym:a": {"displayName": "A"}},
        "by_file_id": {},
        "by_directory_id": {"dir:src": {"displayName": "Src"}},
    }
    delta = {"by_symbol_id": {"sym:a": {"userDescription": "note"}, "sym:b": {"displayName": "B"}}}
    m = merge_overlay_delta(base, delta)
    assert m["by_symbol_id"]["sym:a"] == {"displayName": "A", "userDescription": "note"}
    assert m["by_symbol_id"]["sym:b"] == {"displayName": "B"}
    assert m["by_directory_id"]["dir:src"] == {"displayName": "Src"}


def test_merge_overlay_delta_merges_root_entry() -> None:
    base = {
        "schema_version": 0,
        "by_symbol_id": {},
        "by_file_id": {},
        "by_directory_id": {},
        "by_root_id": {"raw-root": {"displayName": "A"}},
    }
    delta = {"by_root_id": {"raw-root": {"userDescription": "note"}}}
    m = merge_overlay_delta(base, delta)
    assert m["by_root_id"]["raw-root"] == {"displayName": "A", "userDescription": "note"}


def test_merge_overlay_delta_merges_directory_entry() -> None:
    base = {
        "schema_version": 0,
        "by_symbol_id": {},
        "by_file_id": {},
        "by_directory_id": {"dir:a": {"displayName": "A"}},
    }
    delta = {"by_directory_id": {"dir:a": {"userDescription": "note"}, "dir:b": {"displayName": "B"}}}
    m = merge_overlay_delta(base, delta)
    assert m["by_directory_id"]["dir:a"] == {"displayName": "A", "userDescription": "note"}
    assert m["by_directory_id"]["dir:b"] == {"displayName": "B"}


def test_merge_overlay_delta_merges_flow_entry() -> None:
    base = {
        "schema_version": 0,
        "by_symbol_id": {},
        "by_file_id": {},
        "by_directory_id": {},
        "by_root_id": {},
        "by_flow_node_id": {"py:boundary:unresolved": {"displayName": "Unresolved"}},
    }
    delta = {
        "by_flow_node_id": {
            "py:boundary:unresolved": {"userDescription": "Third-party calls land here."},
            "py:fn:other": {"displayName": "Other"},
        },
    }
    m = merge_overlay_delta(base, delta)
    assert m["by_flow_node_id"]["py:boundary:unresolved"] == {
        "displayName": "Unresolved",
        "userDescription": "Third-party calls land here.",
    }
    assert m["by_flow_node_id"]["py:fn:other"] == {"displayName": "Other"}


def test_apply_bundle_patch_skip_validate(
    golden_repo: Path,
    samples_dir: Path,
    tmp_path: Path,
) -> None:
    dest = tmp_path / "g"
    shutil.copytree(
        golden_repo,
        dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.egg-info"),
    )
    diff = (samples_dir / "docstring.patch").read_text(encoding="utf-8")
    res = apply_bundle(dest, {"schema_version": 0, "unified_diff": diff}, skip_validate=True)
    assert res.ok, res.errors
    assert "patched" in (dest / "src" / "golden_app" / "core.py").read_text(encoding="utf-8")
    assert res.raw_symbol_count is not None and res.raw_symbol_count > 0


def test_apply_bundle_overlay_orphan_fails(golden_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "g"
    shutil.copytree(
        golden_repo,
        dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.egg-info"),
    )
    ov_path = tmp_path / "overlay.json"
    res = apply_bundle(
        dest,
        {
            "schema_version": 0,
            "unified_diff": "",
            "overlay": {
                "by_symbol_id": {"sym:ghost:nope": {"displayName": "x"}},
            },
        },
        overlay_path=ov_path,
        skip_validate=True,
    )
    assert not res.ok
    assert any("orphan" in e.lower() for e in res.errors)
    assert not ov_path.is_file()


def test_apply_bundle_overlay_only_writes_file(golden_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "g"
    shutil.copytree(
        golden_repo,
        dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.egg-info"),
    )
    sym = "sym:src/golden_app/core.py:golden_app.core.greeting_for"
    ov_path = tmp_path / "overlay.json"
    res = apply_bundle(
        dest,
        {
            "schema_version": 0,
            "unified_diff": "",
            "overlay": {"by_symbol_id": {sym: {"displayName": "Hello fn"}}},
        },
        overlay_path=ov_path,
        skip_validate=True,
    )
    assert res.ok, res.errors
    assert res.overlay_written
    doc = json.loads(ov_path.read_text(encoding="utf-8"))
    assert doc["by_symbol_id"][sym]["displayName"] == "Hello fn"


def test_apply_bundle_dry_run_rejects_overlay(tmp_path: Path) -> None:
    res = apply_bundle(
        tmp_path,
        {
            "schema_version": 0,
            "unified_diff": "---\n+++ x\n",
            "overlay": {"by_symbol_id": {}},
        },
        overlay_path=tmp_path / "o.json",
        dry_run=True,
    )
    assert not res.ok
    assert any("dry-run" in e.lower() for e in res.errors)


def test_load_bundle_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    p.write_text(json.dumps({"schema_version": 0, "unified_diff": "ok\n"}), encoding="utf-8")
    b = load_bundle(p)
    assert b["unified_diff"] == "ok\n"


def test_cli_apply_bundle_integration(golden_repo: Path, samples_dir: Path, tmp_path: Path) -> None:
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

    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 0,
                "unified_diff": (samples_dir / "docstring.patch").read_text(encoding="utf-8"),
            },
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            str(py),
            "-m",
            "raw_indexer",
            "apply-bundle",
            str(dest),
            str(bundle_path),
            "--pytest-only",
        ],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout + r.stderr
    assert "patched" in (dest / "src" / "golden_app" / "core.py").read_text(encoding="utf-8")
