"""Compare actual vs synthetic flow: render both as ASCII trees and diff edges."""
from __future__ import annotations

import json
from pathlib import Path


def load(name: str) -> dict:
    return json.loads(Path(name).read_text())


def render_tree(flow: dict, title: str) -> str:
    entry = flow["entry"]
    adj: dict[str, list[dict]] = {}
    for e in flow["edges"]:
        adj.setdefault(e["from"], []).append(e)

    out = [f"=== {title} ===", entry]
    seen: set[str] = set()

    def walk(node: str, prefix: str, is_last: bool) -> None:
        children = adj.get(node, [])
        for i, edge in enumerate(children):
            last = i == len(children) - 1
            branch = "└── " if last else "├── "
            conf = f"  ({edge['confidence']:.2f})" if "confidence" in edge else ""
            out.append(f"{prefix}{branch}{edge['to']}{conf}")
            if edge["to"] in seen:
                out.append(f"{prefix}{'    ' if last else '│   '}  ↻ (already visited)")
                continue
            seen.add(edge["to"])
            walk(edge["to"], prefix + ("    " if last else "│   "), last)

    seen.add(entry)
    walk(entry, "", True)
    return "\n".join(out)


def edge_key(e: dict) -> tuple[str, str]:
    return (e["from"], e["to"])


def diff(actual: dict, synthetic: dict) -> None:
    a_edges = {edge_key(e) for e in actual["edges"]}
    s_edges = {edge_key(e) for e in synthetic["edges"]}
    both = a_edges & s_edges
    only_a = a_edges - s_edges
    only_s = s_edges - a_edges

    print("\n=== EDGE DIFF ===")
    print(f"matching edges (read-like-runs): {len(both)}")
    for fr, to in sorted(both):
        print(f"  ✓ {fr} → {to}")
    print(f"\nactual only (reader would miss): {len(only_a)}")
    for fr, to in sorted(only_a):
        print(f"  ! {fr} → {to}")
    print(f"\nsynthetic only (reader would expect, doesn't happen): {len(only_s)}")
    for fr, to in sorted(only_s):
        print(f"  ? {fr} → {to}")

    total = len(a_edges | s_edges)
    if total:
        agreement = len(both) / total
        print(f"\nagreement: {agreement:.0%} ({len(both)}/{total} edges)")


if __name__ == "__main__":
    actual = load("actual_flow.json")
    synthetic = load("synthetic_flow.json")
    print(render_tree(actual, "ACTUAL flow (from static call graph)"))
    print()
    print(render_tree(synthetic, "SYNTHETIC flow (from LLM semantic prediction)"))
    diff(actual, synthetic)
