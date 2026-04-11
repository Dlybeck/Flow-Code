"""Phase 4: TypeScript execution IR golden fixture tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from flowcode.execution_ir import build_execution_ir, validate_execution_ir
from flowcode.execution_ir.typescript_from_raw import (
    BOUNDARY_UNRESOLVED_ID,
    build_execution_ir_from_ts_raw,
)
from flowcode.ts_indexer import index_ts_repo

try:
    import tree_sitter  # noqa: F401
    import tree_sitter_typescript  # noqa: F401
    _HAS_TS = True
except ImportError:
    _HAS_TS = False

pytestmark = pytest.mark.skipif(not _HAS_TS, reason="flowcode[ts] not installed")


@pytest.fixture
def golden_ts(workspace_root: Path) -> Path:
    return workspace_root / "fixtures" / "golden-ts"


def test_ts_indexer_golden_schema(golden_ts: Path) -> None:
    doc = index_ts_repo(golden_ts)
    assert doc["schema_version"] == 0
    assert doc["indexer"] == "flowcode.ts_v0"
    paths = {f["path"] for f in doc["files"]}
    assert "src/index.ts" in paths
    assert "src/utils.ts" in paths
    sym_q = {s["qualified_name"] for s in doc["symbols"]}
    assert "index.main" in sym_q
    assert "utils.formatGreeting" in sym_q
    assert "utils.validateName" in sym_q


def test_ts_ir_golden(golden_ts: Path) -> None:
    raw_doc = index_ts_repo(golden_ts)
    ir = build_execution_ir_from_ts_raw(raw_doc)
    assert validate_execution_ir(ir) == []

    labels = {n["label"] for n in ir["nodes"]}
    assert "index.main" in labels
    assert "index.greet" in labels
    assert "utils.formatGreeting" in labels
    assert "utils.validateName" in labels


def test_ts_ir_entrypoint_is_main(golden_ts: Path) -> None:
    raw_doc = index_ts_repo(golden_ts)
    ir = build_execution_ir_from_ts_raw(raw_doc)
    assert ir["entrypoints"] == ["ts:fn:index.main"]


def test_ts_ir_cross_module_calls_resolved(golden_ts: Path) -> None:
    raw_doc = index_ts_repo(golden_ts)
    ir = build_execution_ir_from_ts_raw(raw_doc)
    call_edges = [e for e in ir["edges"] if e["kind"] == "calls" and e["confidence"] == "resolved"]

    # main -> validateName (cross-module, resolved via import map)
    assert any(
        e["from"] == "ts:fn:index.main" and e["to"] == "ts:fn:utils.validateName"
        for e in call_edges
    )
    # main -> formatGreeting
    assert any(
        e["from"] == "ts:fn:index.main" and e["to"] == "ts:fn:utils.formatGreeting"
        for e in call_edges
    )
    # greet -> buildMessage (same-module call)
    assert any(
        e["from"] == "ts:fn:index.greet" and e["to"] == "ts:fn:index.buildMessage"
        for e in call_edges
    )


def test_ts_ir_third_party_to_boundary(golden_ts: Path) -> None:
    raw_doc = index_ts_repo(golden_ts)
    ir = build_execution_ir_from_ts_raw(raw_doc)
    unknown_edges = [e for e in ir["edges"] if e["confidence"] == "unknown"]
    assert any(e["to"] == BOUNDARY_UNRESOLVED_ID for e in unknown_edges)


def test_build_execution_ir_dispatches_ts(golden_ts: Path) -> None:
    """build_execution_ir() should auto-dispatch to TS adapter for ts_v0 indexer."""
    raw_doc = index_ts_repo(golden_ts)
    ir = build_execution_ir(raw_doc)
    assert ir["languages"] == ["typescript"]
    assert "ts:fn:index.main" in {n["id"] for n in ir["nodes"]}
