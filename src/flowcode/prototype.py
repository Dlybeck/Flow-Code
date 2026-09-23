"""Lossless function inventory for the circular-terrain experiment.

Consumes a normal terrain export. Optionally refreshes static relationships from
an execution graph of the EXACT same source snapshot, without recomputing or
substituting embedding scores. This module has no project-specific selectors.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy


def terrain_fixture(document, *, graph=None, title=None):
    view = document["views"]["overview"]
    original = {n["id"]: n for n in view["nodes"]}
    analysis = document["analysis"]
    if len(original) != analysis["function_count"]:
        raise ValueError("Overview must retain every indexed function")
    if graph is not None:
        if (
            not analysis.get("source_digest")
            or graph["analysis"].get("source_digest") != analysis["source_digest"]
        ):
            raise ValueError(
                "Source snapshot changed; rebuild the terrain export first"
            )
        functions = {n["id"]: n for n in graph["nodes"] if n["kind"] == "function"}
        if set(functions) != set(original):
            raise ValueError(
                "Function inventory changed; rebuild the terrain export first"
            )
        raw_edges = graph["edges"]
        entries = (
            document["entries"]
            if analysis.get("entry_selection") == "manual"
            else graph["entrypoints"]
        )
    else:
        functions = original
        raw_edges = view["edges"]
        entries = document["entries"]
    # The legacy adapter fallback means "a starting symbol", not evidence of
    # an entry. Keep its function in the inventory without inventing a summit.
    entries = [
        i
        for i in entries
        if i in original
        and (
            analysis.get("entry_selection") == "manual"
            or functions[i].get("entry_evidence") != ["fallback_first_symbol"]
        )
    ]
    boundaries = {
        i: [] if graph else deepcopy(n.get("boundaries", []))
        for i, n in original.items()
    }
    for records in boundaries.values():
        for record in records:
            record.get("callsite", {}).pop("snippet", None)
    edge_map = {}
    for edge in raw_edges:
        if edge["from"] not in original or edge["kind"] == "contains":
            continue
        site = dict(edge.get("callsite", {}))
        site.pop("snippet", None)
        site.setdefault("path", original[edge["from"]].get("file", ""))
        if edge["to"] not in original:
            if graph:
                boundaries[edge["from"]].append(
                    {
                        "target": site.get("callee_expression")
                        or site.get("callee")
                        or "Unresolved target",
                        "boundary_kind": edge.get("boundary_kind", "unresolved"),
                        "callsite": site,
                    }
                )
            continue
        pair = (edge["from"], edge["to"])
        row = edge_map.setdefault(
            pair,
            {
                "from": pair[0],
                "to": pair[1],
                "primary": False,
                "confidence": "unknown",
                "count": 0,
                "evidence": [],
            },
        )
        evidence = {
            "kind": edge["kind"],
            "confidence": edge["confidence"],
            "reason": edge.get("evidence", "static_call"),
            "callsite": site,
        }
        if evidence not in row["evidence"]:
            row["evidence"].append(evidence)
        row["count"] = len(
            {
                (e["callsite"].get("path"), e["callsite"].get("line"))
                for e in row["evidence"]
            }
        )
        rank = {"resolved": 2, "heuristic": 1, "unknown": 0}
        if rank[edge["confidence"]] > rank[row["confidence"]]:
            row["confidence"] = edge["confidence"]
    nodes = []
    for i, node in sorted(original.items()):
        nodes.append(
            {
                "id": i,
                "label": node.get("displayName") or node["label"],
                "qname": node["qname"],
                "location": node["location"],
                "score": round(
                    0.94 * node["importance"]
                    + 0.06 * node.get("novelty_importance", 0),
                    6,
                ),
                "criticality": node["importance"],
                "novelty": node.get("novelty_importance", 0),
                "language": node["language"],
                "similar": node.get("similar", []),
                "boundaries": boundaries[i],
                "entry_evidence": ["explicit_entry"]
                if analysis.get("entry_selection") == "manual" and i in entries
                else functions[i].get(
                    "entry_evidence", ["export_entry"] if i in entries else []
                ),
                "exits": deepcopy(node.get("exits", [])),
            }
        )
    # Common names such as main, run and __init__ need source context. This is
    # deterministic naming, not generated explanation or importance ranking.
    duplicates = Counter(node["label"] for node in nodes)
    for node in nodes:
        if duplicates[node["label"]] > 1:
            owner = node["qname"].rsplit(".", 1)[0].rsplit(".", 1)[-1]
            node["label"] = f"{owner}.{node['label']}"
    duplicates = Counter(node["label"] for node in nodes)
    for node in nodes:
        if duplicates[node["label"]] > 1:
            node["label"] += (
                f" · {node['location']['path']}:{node['location']['start_line']}"
            )
    return {
        "title": title or document["project"],
        "purpose": analysis.get("purpose", {}).get(
            "text", "Code-only embedding relevance; no project description supplied."
        ),
        "entrypoints": sorted(set(entries)),
        "behaviors": deepcopy(document.get("behaviors", {})),
        "nodes": nodes,
        "edges": [edge_map[k] for k in sorted(edge_map)],
        "coverage": {
            "indexed_functions": len(nodes),
            "included_functions": len(nodes),
            "relationship_source": "refreshed static analysis"
            if graph
            else "stored export",
            "relationship_analyzer": (graph or document)["analysis"].get(
                "analyzer", {}
            ),
            "entry_selection": "manual"
            if analysis.get("entry_selection") == "manual"
            else "detected"
            if graph
            else "export-defined",
            "source_roots": analysis["source_roots"],
            "source_digest": analysis["source_digest"],
            "languages": sorted({n["language"] for n in nodes}),
            "boundary_calls": sum(map(len, boundaries.values())),
            "relationships": dict(Counter(e["confidence"] for e in edge_map.values())),
            "known_limits": (graph or document)["analysis"]["known_limits"],
            "candidate_analysis": (graph or document)["analysis"].get(
                "candidate_analysis", {}
            ),
        },
    }
