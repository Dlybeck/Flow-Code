"""Language-neutral execution IR: validate, graph ops, layout, Python/TS adapters from RAW."""

from __future__ import annotations

from typing import Any

from flowcode.execution_ir.graph import dead_candidates, maybe_edges, reachable_node_ids
from flowcode.execution_ir.layout import dfs_visit_order
from flowcode.execution_ir.python_from_raw import build_execution_ir_from_raw
from flowcode.execution_ir.validate import EXECUTION_IR_SCHEMA_VERSION, validate_execution_ir


def build_execution_ir(raw_doc: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the correct language adapter based on raw_doc['indexer']."""
    indexer = str(raw_doc.get("indexer", ""))
    if "ts_v0" in indexer or any(
        lang in ("typescript", "javascript")
        for lang in raw_doc.get("languages", [])
    ):
        from flowcode.execution_ir.typescript_from_raw import build_execution_ir_from_ts_raw
        return build_execution_ir_from_ts_raw(raw_doc)
    return build_execution_ir_from_raw(raw_doc)


__all__ = [
    "EXECUTION_IR_SCHEMA_VERSION",
    "build_execution_ir",
    "build_execution_ir_from_raw",
    "dead_candidates",
    "dfs_visit_order",
    "maybe_edges",
    "reachable_node_ids",
    "validate_execution_ir",
]
