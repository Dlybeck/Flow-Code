from __future__ import annotations

import json
from pathlib import Path

from raw_indexer.execution_ir.validate import validate_execution_ir


def _fixture(name: str) -> dict:
    p = Path(__file__).resolve().parent / "fixtures" / name
    return json.loads(p.read_text(encoding="utf-8"))


def test_validate_min_fixture_ok() -> None:
    doc = _fixture("flow_ir_valid_min.json")
    assert validate_execution_ir(doc) == []


def test_validate_rejects_bad_confidence() -> None:
    doc = _fixture("flow_ir_invalid_confidence.json")
    errs = validate_execution_ir(doc)
    assert any("confidence" in e.lower() for e in errs)


def test_validate_rejects_unknown_entrypoint() -> None:
    doc = _fixture("flow_ir_valid_min.json")
    doc = dict(doc)
    doc["entrypoints"] = ["py:fn:missing"]
    errs = validate_execution_ir(doc)
    assert any("unknown node" in e for e in errs)
