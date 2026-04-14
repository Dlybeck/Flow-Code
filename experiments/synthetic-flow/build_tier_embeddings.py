"""Compute tier (execution-based) embeddings for each node in the ground-truth flow.

For each node: embed(source_of(node) + source_of(every descendant)) as one vector.
The resulting hierarchy should, if the hypothesis holds, encode execution structure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from parse_codebase import parse_codebase

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_flow(path: Path) -> tuple[dict, dict[str, list[str]]]:
    doc = json.loads(path.read_text())
    nodes = {n["id"]: n for n in doc["nodes"]}
    children = {n["id"]: list(n["children"]) for n in doc["nodes"]}
    return nodes, children


def descendants(children: dict[str, list[str]], node_id: str) -> list[str]:
    """Return all descendants (transitive children) of node_id, in BFS order."""
    out: list[str] = []
    queue = list(children.get(node_id, []))
    while queue:
        cur = queue.pop(0)
        if cur in out:
            continue
        out.append(cur)
        queue.extend(children.get(cur, []))
    return out


def concat_source(nodes: dict, children: dict, functions: dict, node_id: str) -> tuple[str, list[str]]:
    """Concat node's own source + source of every descendant, in execution order."""
    order = [node_id] + descendants(children, node_id)
    parts: list[str] = []
    for nid in order:
        fname = nodes[nid]["function"]
        parts.append(functions[fname].source)
    return "\n\n".join(parts), order


def main() -> None:
    flow_path = Path("ground_truth_flow.json")
    code_path = Path("test_codebase.py")
    out_path = Path("tier_embeddings.json")

    nodes, children = load_flow(flow_path)
    functions = parse_codebase(code_path)

    # Import lazily so `-h` etc. don't pay the import cost.
    print(f"Loading model {MODEL_NAME}...", flush=True)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)

    texts: list[str] = []
    node_ids: list[str] = []
    descendants_by_node: dict[str, list[str]] = {}
    previews: dict[str, str] = {}

    for nid in nodes:
        text, order = concat_source(nodes, children, functions, nid)
        texts.append(text)
        node_ids.append(nid)
        descendants_by_node[nid] = order[1:]  # exclude self
        previews[nid] = text[:120].replace("\n", " ")

    print(f"Embedding {len(texts)} tier vectors...", flush=True)
    vectors = model.encode(texts, normalize_embeddings=True).tolist()

    payload = {
        "model": MODEL_NAME,
        "nodes": {
            nid: {
                "function": nodes[nid]["function"],
                "descendants": descendants_by_node[nid],
                "source_preview": previews[nid],
                "vector": vec,
            }
            for nid, vec in zip(node_ids, vectors)
        },
    }
    out_path.write_text(json.dumps(payload))
    print(f"wrote {out_path} ({len(node_ids)} vectors, dim={len(vectors[0])})")


if __name__ == "__main__":
    main()
