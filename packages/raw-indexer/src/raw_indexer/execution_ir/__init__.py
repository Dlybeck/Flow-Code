"""Language-neutral execution IR: validate, graph ops, layout, Python adapter from RAW."""

from __future__ import annotations

from raw_indexer.execution_ir.graph import dead_candidates, maybe_edges, reachable_node_ids
from raw_indexer.execution_ir.layout import dfs_visit_order
from raw_indexer.execution_ir.python_from_raw import build_execution_ir_from_raw
from raw_indexer.execution_ir.validate import EXECUTION_IR_SCHEMA_VERSION, validate_execution_ir

__all__ = [
    "EXECUTION_IR_SCHEMA_VERSION",
    "build_execution_ir_from_raw",
    "dead_candidates",
    "dfs_visit_order",
    "maybe_edges",
    "reachable_node_ids",
    "validate_execution_ir",
]
