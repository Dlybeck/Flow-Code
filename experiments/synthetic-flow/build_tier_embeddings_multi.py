"""Multi-file tier embedding builder for the TinyDB experiment.

Reads a ground-truth flow JSON that specifies a codebase_root and per-node
qnames. For each node: concatenate its source + all descendants' source, embed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from parse_multi import parse_directory

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def descendants(children: dict[str, list[str]], node_id: str) -> list[str]:
    out: list[str] = []
    queue = list(children.get(node_id, []))
    while queue:
        cur = queue.pop(0)
        if cur in out:
            continue
        out.append(cur)
        queue.extend(children.get(cur, []))
    return out


def main() -> None:
    flow_path = Path(sys.argv[1] if len(sys.argv) > 1 else "tinydb_insert_flow.json")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "tier_embeddings.json")

    flow = json.loads(flow_path.read_text())
    root_dir = Path(flow["codebase_root"])
    nodes_list = flow["nodes"]
    nodes = {n["id"]: n for n in nodes_list}
    children = {n["id"]: list(n["children"]) for n in nodes_list}

    print(f"Parsing {root_dir}...", flush=True)
    functions = parse_directory(root_dir)
    print(f"  found {len(functions)} functions/methods in codebase", flush=True)

    # Verify every qname in the ground truth exists
    missing = [n["qname"] for n in nodes_list if n["qname"] not in functions]
    if missing:
        raise SystemExit(f"qnames missing from parsed codebase: {missing}")

    print(f"Loading model {MODEL_NAME}...", flush=True)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)

    ids: list[str] = []
    texts: list[str] = []
    descendants_by_node: dict[str, list[str]] = {}
    previews: dict[str, str] = {}

    for nid, node in nodes.items():
        desc_ids = descendants(children, nid)
        # Deduplicate while preserving order (in case a DAG shares descendants)
        seen: set[str] = set()
        ordered = []
        for x in [nid] + desc_ids:
            if x not in seen:
                seen.add(x)
                ordered.append(x)
        parts = [functions[nodes[x]["qname"]].source for x in ordered]
        text = "\n\n".join(parts)
        ids.append(nid)
        texts.append(text)
        descendants_by_node[nid] = desc_ids
        previews[nid] = text[:140].replace("\n", " ")

    print(f"Embedding {len(texts)} tier vectors...", flush=True)
    vectors = model.encode(texts, normalize_embeddings=True).tolist()

    payload = {
        "model": MODEL_NAME,
        "source": flow_path.name,
        "nodes": {
            nid: {
                "qname": nodes[nid]["qname"],
                "file": functions[nodes[nid]["qname"]].file,
                "descendants": descendants_by_node[nid],
                "source_preview": previews[nid],
                "vector": vec,
            }
            for nid, vec in zip(ids, vectors)
        },
    }
    out_path.write_text(json.dumps(payload))
    print(f"wrote {out_path} ({len(ids)} vectors, dim={len(vectors[0])})")


if __name__ == "__main__":
    main()
