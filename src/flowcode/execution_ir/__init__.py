"""Language-neutral execution IR: validate, graph ops, layout, Python/TS adapters from RAW."""

from __future__ import annotations

from typing import Any

from flowcode.execution_ir.graph import dead_candidates, maybe_edges, reachable_node_ids
from flowcode.execution_ir.layout import dfs_visit_order
from flowcode.execution_ir.python_from_raw import build_execution_ir_from_raw
from flowcode.execution_ir.validate import (
    EXECUTION_IR_SCHEMA_VERSION,
    validate_execution_ir,
)


def _build_execution_ir(raw_doc: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the correct language adapter based on raw_doc['indexer']."""
    if raw_doc.get("indexer") == "flowcode.multi_v0":
        documents = [_build_execution_ir(doc) for doc in raw_doc["documents"]]
        merged = {
            "schema_version": EXECUTION_IR_SCHEMA_VERSION,
            "repo_root": raw_doc["root"],
            "languages": sorted({lang for doc in documents for lang in doc["languages"]}),
            "entrypoints": sorted({entry for doc in documents for entry in doc["entrypoints"]}),
            "nodes": [n for doc in documents for n in doc["nodes"]],
            "edges": [dict(e, id=f"producer:{i}:{e['id']}") for i, doc in enumerate(documents) for e in doc["edges"]],
            "candidate_analysis": {k: v for doc in documents for k, v in doc.get("candidate_analysis", {}).items()},
            "producers": [p for doc in documents for p in doc.get("producers", [])],
        }
        errors = validate_execution_ir(merged)
        if errors:
            raise ValueError("invalid merged graph: " + "; ".join(errors))
        return merged
    indexer = str(raw_doc.get("indexer", ""))
    if indexer.endswith("_treesitter_v0"):
        from flowcode.execution_ir.treesitter_from_raw import (
            build_execution_ir_from_treesitter_raw,
        )

        return build_execution_ir_from_treesitter_raw(raw_doc)
    if "ts_v0" in indexer or any(
        lang in ("typescript", "javascript")
        for lang in raw_doc.get("languages", [])
    ):
        from flowcode.execution_ir.typescript_from_raw import (
            build_execution_ir_from_ts_raw,
        )
        return build_execution_ir_from_ts_raw(raw_doc)
    return build_execution_ir_from_raw(raw_doc)


def build_execution_ir(raw_doc: dict[str, Any]) -> dict[str, Any]:
    from flowcode.application_edges import attach_application_edges
    graph = _build_execution_ir(raw_doc)
    attach_application_edges(graph, raw_doc)
    errors = validate_execution_ir(graph)
    if errors:
        raise ValueError('invalid application graph: ' + '; '.join(errors))
    return graph


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
