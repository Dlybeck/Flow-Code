"""Slice 0 — validate execution IR documents (language-neutral)."""

from __future__ import annotations

from typing import Any

EXECUTION_IR_SCHEMA_VERSION = 0

CONFIDENCE = frozenset({"resolved", "heuristic", "unknown"})
EDGE_KINDS = frozenset({"calls", "imports", "contains", "routes_to"})


def validate_execution_ir(doc: Any) -> list[str]:
    """
    Return a list of error strings; empty means valid enough for downstream graph code.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["root must be a JSON object"]
    if doc.get("schema_version") != EXECUTION_IR_SCHEMA_VERSION:
        errs.append(
            f"schema_version must be {EXECUTION_IR_SCHEMA_VERSION}, got {doc.get('schema_version')!r}",
        )
    if "languages" not in doc:
        errs.append("missing languages")
    elif not isinstance(doc["languages"], list):
        errs.append("languages must be an array")
    if "entrypoints" not in doc:
        errs.append("missing entrypoints")
    elif not isinstance(doc["entrypoints"], list):
        errs.append("entrypoints must be an array")
    nodes = doc.get("nodes")
    if not isinstance(nodes, list):
        errs.append("nodes must be an array")
    else:
        seen: set[str] = set()
        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                errs.append(f"nodes[{i}] must be an object")
                continue
            nid = n.get("id")
            if not isinstance(nid, str) or not nid.strip():
                errs.append(f"nodes[{i}].id must be a non-empty string")
            elif nid in seen:
                errs.append(f"duplicate node id: {nid!r}")
            else:
                seen.add(nid)
            for req in ("kind", "language", "label"):
                if req not in n or not isinstance(n.get(req), str) or not str(n.get(req)).strip():
                    errs.append(f"nodes[{i}].{req} must be a non-empty string")
            loc = n.get("location")
            if loc is not None:
                if not isinstance(loc, dict):
                    errs.append(f"nodes[{i}].location must be an object or omitted")
                else:
                    if "path" in loc and not isinstance(loc["path"], str):
                        errs.append(f"nodes[{i}].location.path must be a string")
    edges = doc.get("edges")
    if not isinstance(edges, list):
        errs.append("edges must be an array")
    else:
        node_ids = {n["id"] for n in nodes} if isinstance(nodes, list) else set()
        for i, e in enumerate(edges):
            if not isinstance(e, dict):
                errs.append(f"edges[{i}] must be an object")
                continue
            for req in ("from", "to", "kind", "confidence"):
                if req not in e:
                    errs.append(f"edges[{i}] missing {req!r}")
                    continue
                if req != "confidence" and (not isinstance(e[req], str) or not e[req].strip()):
                    errs.append(f"edges[{i}].{req} must be a non-empty string")
            if e.get("kind") not in EDGE_KINDS:
                errs.append(f"edges[{i}].kind must be one of {sorted(EDGE_KINDS)}")
            if e.get("confidence") not in CONFIDENCE:
                errs.append(f"edges[{i}].confidence must be one of {sorted(CONFIDENCE)}")
            if node_ids:
                if e.get("from") not in node_ids:
                    errs.append(f"edges[{i}].from unknown node: {e.get('from')!r}")
                if e.get("to") not in node_ids:
                    errs.append(f"edges[{i}].to unknown node: {e.get('to')!r}")
    if isinstance(doc.get("entrypoints"), list) and isinstance(nodes, list):
        node_ids_ep = {n["id"] for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)}
        for i, ep in enumerate(doc["entrypoints"]):
            if not isinstance(ep, str):
                errs.append(f"entrypoints[{i}] must be a string")
            elif node_ids_ep and ep not in node_ids_ep:
                errs.append(f"entrypoints[{i}] unknown node: {ep!r}")
    return errs
