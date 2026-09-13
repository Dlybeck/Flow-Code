"""Portable, deterministic terrain snapshots from the public execution graph.

Geometry is a navigation aid, never a measurement of runtime or complexity.
Unknown calls remain attached as evidence rather than becoming terrain peaks.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

from flowcode import generate_graph
from flowcode.sources import SKIP_DIR_NAMES


def _semantic_signals(functions, vectors, purpose_vector=None):
    """Score all selected sources together, before taking a featured subset."""
    from types import SimpleNamespace

    import numpy as np

    from flowcode.semantic_layout import compute_importance, compute_semantic_density

    ids = sorted(functions)
    values = np.asarray([vectors[node] for node in ids], dtype=float)
    if (
        values.ndim != 2
        or not np.isfinite(values).all()
        or (np.linalg.norm(values, axis=1) == 0).any()
    ):
        raise ValueError("Every function requires a finite, nonzero code embedding")
    values /= np.linalg.norm(values, axis=1, keepdims=True)
    similarities = values @ values.T
    density = compute_semantic_density(ids, vectors)
    importance = compute_importance(
        ids,
        {},
        {node: SimpleNamespace(source=functions[node]["_source"]) for node in ids},
        density,
    )
    novelty_importance = dict(importance)
    relevance = {node: 0.0 for node in ids}
    if purpose_vector is not None:
        purpose = np.asarray(purpose_vector, dtype=float)
        if not np.isfinite(purpose).all() or np.linalg.norm(purpose) == 0:
            raise ValueError("Project purpose requires a valid embedding")
        purpose /= np.linalg.norm(purpose)
        relevance = {
            node: max(0.0, float(values[i] @ purpose)) for i, node in enumerate(ids)
        }
        maximum = max(relevance.values()) or 1
        # Purpose relevance dominates; the original novelty/substance estimate
        # is a bounded secondary signal, so unusual utilities cannot dominate.
        raw = {
            node: (relevance[node] / maximum) ** 2 * (0.75 + 0.25 * importance[node])
            for node in ids
        }
        peak = max(raw.values()) or 1
        importance = {node: score / peak for node, score in raw.items()}
    if len(ids) > 3:
        import umap

        coords = umap.UMAP(
            n_components=2,
            n_neighbors=min(15, len(ids) - 1),
            min_dist=0.15,
            metric="cosine",
            random_state=42,
            n_jobs=1,
            init="random",
        ).fit_transform(values)
    else:
        # UMAP has no useful neighbor graph at this size. Exact centered SVD
        # still derives positions from embeddings, never file names or depth.
        centered = values - values.mean(axis=0)
        u, singular, _ = np.linalg.svd(centered, full_matrices=False)
        coords = np.zeros((len(ids), 2))
        width = min(2, len(singular))
        coords[:, :width] = u[:, :width] * singular[:width]
    for i, node in enumerate(ids):
        neighbors = sorted(
            (j for j in range(len(ids)) if j != i),
            key=lambda j: (-similarities[i, j], ids[j]),
        )
        functions[node].update(
            importance=importance[node],
            novelty_importance=novelty_importance[node],
            purpose_similarity=relevance[node],
            semantic_density=density[node],
            x_umap=float(coords[i, 0]),
            y_umap=float(coords[i, 1]),
            # Monotonic contrast expansion; raw importance is retained above.
            semantic_height=2 + 18 * math.sqrt(importance[node]),
            similar=[
                {"id": ids[j], "cosine": float(similarities[i, j])}
                for j in neighbors[:3]
            ],
        )


def _layout(functions, edges, seeds, vectors):
    from flowcode.semantic_layout import radial_fan_layout

    ids = sorted(functions)
    edges = [e for e in edges if e["from"] in functions and e["to"] in functions]
    children, callers = {n: set() for n in ids}, {n: set() for n in ids}
    for edge in edges:
        children[edge["from"]].add(edge["to"])
        callers[edge["to"]].add(edge["from"])
    positions, raw_heights, peaks, primary = radial_fan_layout(
        ids,
        {n: sorted(v) for n, v in children.items()},
        {n: sorted(v) for n, v in callers.items()},
        vectors,
        {n: functions[n]["semantic_density"] for n in ids},
        {n: functions[n]["importance"] for n in ids},
    )
    # One positive affine transform makes the original relative-descent terrain
    # fit the same display range. It cannot change order or manufacture ridges.
    low, high = min(raw_heights.values()), max(raw_heights.values())
    scale = 18 / (high - low) if high > low else 1
    primary_children = defaultdict(list)
    for parent, child in sorted(primary):
        primary_children[parent].append(child)
    depth = {n: 0 for n in ids if not any(child == n for _, child in primary)}
    queue = deque(depth)
    while queue:
        parent = queue.popleft()
        for child in primary_children[parent]:
            depth[child] = depth[parent] + 1
            queue.append(child)
    nodes = []
    for node in ids:
        n = {k: v for k, v in functions[node].items() if k != "_source"}
        n.update(
            depth=depth[node],
            x_fan=positions[node][0],
            y_fan=positions[node][1],
            height=2 + (raw_heights[node] - low) * scale,
            raw_height=raw_heights[node],
            is_orphan=False,
            n_callees=len(children[node]),
        )
        nodes.append(n)
    return {
        "nodes": nodes,
        "edges": [dict(e, is_primary=(e["from"], e["to"]) in primary) for e in edges],
        "peaks": peaks,
        "max_depth": max(depth.values(), default=0),
        "constrained_spines": False,
        "height_scale": {"offset": 2, "factor": scale, "raw_min": low},
    }


def export_terrain(
    repo_path, *, project, src_roots=None, entries=None, embedder=None, purpose=None
):
    """Bake source embeddings and both views locally; export only static data."""
    if not purpose:
        readme = next(
            (
                Path(repo_path) / name
                for name in ("README.md", "readme.md", "README.rst")
                if (Path(repo_path) / name).is_file()
            ),
            None,
        )
        purpose = readme.read_text()[:4000].strip() if readme else ""
    if not purpose or not purpose.strip():
        raise ValueError(
            "Provide --purpose describing what this project does, or a README"
        )
    graph = generate_graph(
        repo_path, src_roots=src_roots, include_overlay=False, use_llm=False
    )
    by_id = {n["id"]: n for n in graph["nodes"]}
    source_files = {}
    for file in graph["analysis"]["files"]:
        content = (Path(repo_path) / file["path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != file["sha256"]:
            raise ValueError(f"Source changed during export: {file['path']}")
        source_files[file["path"]] = content.decode("utf-8").splitlines(keepends=True)
    functions = {}
    for n in graph["nodes"]:
        if n["kind"] != "function":
            continue
        loc = n["location"]
        functions[n["id"]] = {
            "_source": "".join(
                source_files[loc["path"]][loc["start_line"] - 1 : loc["end_line"]]
            ),
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
    from flowcode.embeddings import RECIPE, CodeEmbedder

    vectors, receipts = (embedder or CodeEmbedder()).encode(
        {
            **{n: f["_source"] for n, f in functions.items()},
            "__project_purpose__": purpose,
        }
    )
    purpose_vector = vectors.pop("__project_purpose__", None)
    purpose_receipt = receipts.pop("__project_purpose__", None)
    if purpose_vector is None or purpose_receipt is None:
        raise ValueError("Missing project purpose embedding")
    if set(vectors) != set(functions) or set(receipts) != set(functions):
        raise ValueError(
            "Missing code embeddings; no geometry-only fallback is allowed"
        )
    _semantic_signals(functions, vectors, purpose_vector)
    for node, function in functions.items():
        function["embedding"] = receipts[node]
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
            min(functions)
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
        embedding=dict(RECIPE),
        purpose={"text": purpose, "embedding": purpose_receipt},
        terrain={
            "method": "purpose relevance with original novelty x substance / relative descent",
            "importance": "normalize((positive purpose cosine / max cosine)^2 * (0.75 + 0.25 * novelty_importance))",
            "projection": "UMAP cosine, seed 42; exact SVD for <=3 functions",
            "semantic_height": "2 + 18 * sqrt(importance); monotonic visual contrast",
            "scoring_scope": "all selected-source functions before featured filtering",
        },
        edge_confidence=dict(Counter(e["confidence"] for e in graph["edges"])),
    )
    analysis["known_limits"] += [
        "Only selected Python and browser source files are indexed; templates, CSS, SQL and other languages are not execution graphs.",
        "The featured view follows up to three outgoing steps; all selected-source functions remain available in the overview.",
        "External and unresolved calls appear in function evidence. Semantic height shows estimated importance, not runtime or proven business value. Similarity positions are an approximate projection. Call-path heights also depend on the primary call tree.",
        "Declared routes may not be mounted at runtime. Constructor and callback links are static hypotheses.",
    ]
    return {
        "schema_version": 2,
        "project": project,
        "analysis": analysis,
        "entries": seeds,
        "views": {
            "feature": _layout(
                {k: v for k, v in functions.items() if k in focus},
                internal,
                seeds,
                vectors,
            ),
            "overview": _layout(functions, internal, seeds, vectors),
        },
    }
