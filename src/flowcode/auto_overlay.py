"""Deterministic presentation labels derived from execution IR labels.

Core graph generation never calls a generative model or reads provider
credentials. A future one-time enrichment tool can consume the portable output
without becoming part of this module or the update path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flowcode.execution_ir.graph import reachable_node_ids

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _structural_name(label: str) -> str:
    leaf = label.rsplit(".", 1)[-1]
    return " ".join(
        word.capitalize() if word.islower() else word
        for word in _CAMEL_BOUNDARY.sub(" ", leaf.replace("_", " ")).split()
    )


def generate_auto_overlay(
    ir_doc: dict[str, Any],
    *,
    repo_root: Path | None = None,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    """Build stable mechanical labels; generative enrichment is out of core."""
    del repo_root
    if use_llm:
        raise ValueError(
            "Generative enrichment is not part of core map generation; "
            "use a separate optional one-time artifact when one is implemented"
        )
    entrypoints = ir_doc.get("entrypoints") or []
    nodes = ir_doc.get("nodes") or []
    edges = ir_doc.get("edges") or []
    node_by_id = {node["id"]: node for node in nodes if isinstance(node, dict)}
    overlay: dict[str, dict[str, Any]] = {}
    for entrypoint in entrypoints:
        node = node_by_id.get(entrypoint)
        if node is None:
            continue
        reachable = reachable_node_ids([entrypoint], edges)
        overlay[entrypoint] = {
            "displayName": _structural_name(str(node.get("label", entrypoint))),
            "use_case": True,
            "reachable_node_count": len(reachable),
        }
        for node_id in reachable:
            if node_id in overlay or node_id not in node_by_id:
                continue
            overlay[node_id] = {
                "displayName": _structural_name(
                    str(node_by_id[node_id].get("label", node_id))
                )
            }
    return {
        "schema_version": 0,
        "by_flow_node_id": overlay,
        "by_symbol_id": {},
        "by_file_id": {},
        "by_directory_id": {},
    }
