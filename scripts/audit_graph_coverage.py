"""Count static reachability without executing source or exporting code snippets.

Run with either analyzer checkout on PYTHONPATH to compare the same source:
    python scripts/audit_graph_coverage.py REPO --src-root src -o receipt.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from flowcode import generate_graph


def coverage(graph):
    functions = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
    edges = [
        edge
        for edge in graph["edges"]
        if edge["kind"] != "contains"
        and edge["from"] in functions
        and edge["to"] in functions
    ]
    reached = set(graph["entrypoints"]) & functions
    while True:
        added = {edge["to"] for edge in edges if edge["from"] in reached} - reached
        if not added:
            break
        reached.update(added)
    return {
        "functions": len(functions),
        "entries": len(set(graph["entrypoints"]) & functions),
        "internal_pairs": len({(edge["from"], edge["to"]) for edge in edges}),
        "reachable": len(reached),
        "confidence": dict(Counter(edge["confidence"] for edge in edges)),
        "source_digest": graph["analysis"]["source_digest"],
        "candidate_analysis": graph["analysis"].get("candidate_analysis", {}),
        "analyzer": graph["analysis"].get("analyzer", {}),
        "note": "Static may-reachability from adapter entries, including legacy fallbacks. Not runtime coverage or dead-code detection.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--src-root", action="append", dest="src_roots")
    parser.add_argument("-o", "--out", type=Path, required=True)
    args = parser.parse_args()
    result = coverage(
        generate_graph(args.repo, src_roots=args.src_roots, include_overlay=False)
    )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
