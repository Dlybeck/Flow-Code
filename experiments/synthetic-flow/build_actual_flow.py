"""Build the ACTUAL flow graph from static AST call edges (ground truth)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from parse_codebase import parse_codebase


def build_actual_flow(path: Path, entry: str) -> dict:
    functions = parse_codebase(path)
    if entry not in functions:
        raise SystemExit(f"entry point {entry!r} not found in {path}")

    nodes: list[str] = []
    edges: list[dict] = []
    visited: set[str] = set()

    def walk(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        nodes.append(name)
        for callee in functions[name].calls:
            edges.append({"from": name, "to": callee})
            walk(callee)

    walk(entry)
    return {"entry": entry, "nodes": nodes, "edges": edges}


if __name__ == "__main__":
    codebase = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("test_codebase.py")
    entry = sys.argv[2] if len(sys.argv) > 2 else "handle_signup"
    result = build_actual_flow(codebase, entry)
    out = Path("actual_flow.json")
    out.write_text(json.dumps(result, indent=2))
    print(f"wrote {out} ({len(result['nodes'])} nodes, {len(result['edges'])} edges)")
