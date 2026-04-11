from __future__ import annotations

import json
from pathlib import Path

import pytest

from flowcode.bundle import load_bundle, merge_overlay_delta, parse_bundle


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


def test_load_bundle_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    p.write_text(json.dumps({"schema_version": 0, "unified_diff": "ok\n"}), encoding="utf-8")
    b = load_bundle(p)
    assert b["unified_diff"] == "ok\n"
