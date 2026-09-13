"""Portable, deterministic terrain snapshots from the public execution graph.

Geometry is a navigation aid, never a measurement of runtime or complexity.
Unknown calls remain attached as evidence rather than becoming terrain peaks.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque

from flowcode import generate_graph
from flowcode.sources import SKIP_DIR_NAMES


def _layout(functions, edges, seeds):
    ids = set(functions)
    edges = [e for e in edges if e["from"] in ids and e["to"] in ids]
    children = defaultdict(set)
    incoming = Counter()
    for e in edges:
        children[e["from"]].add(e["to"])
        incoming[e["to"]] += 1
    depth, parents = {}, {}
    peaks = []
    candidates = list(
        dict.fromkeys(
            [*seeds, *sorted(n for n in ids if not incoming[n]), *sorted(ids)]
        )
    )
    for root in candidates:
        if root not in ids or root in depth:
            continue
        peaks.append(root)
        depth[root] = 0
        queue = deque([root])
        while queue:
            node = queue.popleft()
            for child in sorted(children[node]):
                if child not in depth:
                    depth[child] = depth[node] + 1
                    parents[child] = node
                    queue.append(child)
    levels = defaultdict(list)
    for node in sorted(ids):
        levels[depth[node]].append(node)
    files = sorted({n["file"] for n in functions.values()})
    groups = defaultdict(list)
    for node in sorted(ids):
        groups[functions[node]["file"]].append(node)
    nodes = []
    maximum = max(depth.values(), default=0)
    for node in sorted(ids):
        n = dict(functions[node])
        level = levels[depth[node]]
        angle = 2 * math.pi * level.index(node) / len(level) + depth[node] * 0.31
        radius = 3 + depth[node] * 3 + (level.index(node) % 3) * 0.25
        group = groups[n["file"]]
        file_angle = 2 * math.pi * files.index(n["file"]) / max(1, len(files))
        local_angle = 2 * math.pi * group.index(node) / len(group)
        n.update(
            depth=depth[node],
            x_fan=round(radius * math.cos(angle), 6),
            y_fan=round(radius * math.sin(angle), 6),
            height=round(3 + 12 * (1 - depth[node] / max(1, maximum)), 6),
            x_umap=round(12 * math.cos(file_angle) + 2 * math.cos(local_angle), 6),
            y_umap=round(12 * math.sin(file_angle) + 2 * math.sin(local_angle), 6),
            is_orphan=False,
            n_callees=len(children[node]),
        )
        nodes.append(n)
    return {
        "nodes": nodes,
        "edges": [dict(e, is_primary=parents.get(e["to"]) == e["from"]) for e in edges],
        "peaks": peaks,
        "max_depth": maximum,
        "constrained_spines": False,
    }


def export_terrain(repo_path, *, project, src_roots=None, entries=None):
    """Generate both complete selected-source and focused views without model calls."""
    graph = generate_graph(
        repo_path, src_roots=src_roots, include_overlay=False, use_llm=False
    )
    by_id = {n["id"]: n for n in graph["nodes"]}
    functions = {}
    for n in graph["nodes"]:
        if n["kind"] != "function":
            continue
        loc = n["location"]
        functions[n["id"]] = {
            "id": n["id"],
            "qname": n["label"],
            "label": n["label"].split(".")[-1],
            "displayName": f"Callback · line {loc['start_line']}"
            if n["label"].split(".")[-1].startswith("$callback_")
            else n["label"].split(".")[-1],
            "file": loc["path"],
            "location": loc,
            "language": n["language"],
            "source_lines": loc["end_line"] - loc["start_line"] + 1,
            "description": f"{n['language']} function · {loc['path']}:{loc['start_line']}",
            "routes": n.get("routes", []),
            "boundaries": [],
        }
    if not functions:
        raise ValueError("No supported functions found in the selected source roots")
    internal = []
    for e in graph["edges"]:
        if e["from"] not in functions:
            continue
        if e["kind"] == "contains":
            continue
        e = dict(
            e, callsite=dict(e.get("callsite", {}), path=functions[e["from"]]["file"])
        )
        e["callsite"].pop(
            "snippet", None
        )  # Portable evidence needs locations, not source argument values.
        if e["to"] in functions:
            internal.append(e)
        else:
            cs = e["callsite"]
            functions[e["from"]]["boundaries"].append(
                dict(
                    e,
                    target=cs.get("callee_expression")
                    or cs.get("callee")
                    or by_id[e["to"]]["label"],
                )
            )
    seeds = []
    for entry in entries or []:
        matches = [
            n["id"] for n in functions.values() if entry in {n["id"], n["qname"]}
        ]
        if len(matches) != 1:
            raise ValueError(f"Entry must name exactly one function: {entry}")
        seeds.extend(matches)
    if not seeds:
        seeds = [n for n in graph["entrypoints"] if n in functions][:3] or [
            sorted(functions)[0]
        ]
    neighbors = defaultdict(set)
    for e in internal:
        neighbors[e["from"]].add(e["to"])
    focus = set(seeds)
    frontier = set(seeds)
    for _ in range(3):
        frontier = {target for node in frontier for target in neighbors[node]} - focus
        focus.update(frontier)
    analysis = dict(
        graph["analysis"],
        source_roots=src_roots or ["."],
        excluded_directories=sorted(SKIP_DIR_NAMES),
        excluded_patterns=[
            "hidden paths",
            "symlinks",
            "*.min.*",
            "*.d.ts",
            "*.d.mts",
            "*.d.cts",
        ],
        languages=graph["languages"],
        function_count=len(functions),
        edge_confidence=dict(Counter(e["confidence"] for e in graph["edges"])),
    )
    analysis["known_limits"] += [
        "Only selected Python and browser source files are indexed; templates, CSS, SQL and other languages are not execution graphs.",
        "The featured view follows up to three outgoing steps; all selected-source functions remain available in the overview.",
        "External and unresolved calls appear in function evidence. Terrain height encodes traversal depth; By file is not code similarity.",
        "Declared routes may not be mounted at runtime. Constructor and callback links are static hypotheses.",
    ]
    return {
        "schema_version": 1,
        "project": project,
        "analysis": analysis,
        "entries": seeds,
        "views": {
            "feature": _layout(
                {k: v for k, v in functions.items() if k in focus}, internal, seeds
            ),
            "overview": _layout(functions, internal, seeds),
        },
    }
