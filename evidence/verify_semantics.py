"""Audit baked maps against source and cached model output, independently of rendering."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--maps", type=Path, required=True)
parser.add_argument("--cache", type=Path, required=True)
parser.add_argument("--portfolio", type=Path, required=True)
parser.add_argument("--scribblescan", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
roots = {"flowcode": Path(__file__).resolve().parents[1],
         "portfolio": args.portfolio, "scribblescan": args.scribblescan}
report = {}
for project, root in roots.items():
    path = args.maps / (project + ".json")
    document = json.loads(path.read_text())
    nodes = document["views"]["overview"]["nodes"]
    by_id = {node["id"]: node for node in nodes}
    vectors = []
    for file in document["analysis"]["files"]:
        assert hashlib.sha256((root / file["path"]).read_bytes()).hexdigest() == file["sha256"]
    for node in nodes:
        loc = node["location"]
        source = "".join((root / loc["path"]).read_text().splitlines(keepends=True)[loc["start_line"]-1:loc["end_line"]])
        receipt = node["embedding"]
        assert hashlib.sha256(source.encode()).hexdigest() == receipt["source_sha256"]
        cached = json.loads((args.cache / (receipt["key"] + ".json")).read_text())
        vector = np.asarray(cached["vector"], dtype="<f4")
        assert vector.shape == (768,) and np.isfinite(vector).all()
        assert np.isclose(np.linalg.norm(vector), 1, atol=1e-4)
        assert hashlib.sha256(vector.tobytes()).hexdigest() == receipt["vector_sha256"]
        vectors.append(vector)
    matrix = np.asarray(vectors, dtype=float)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    sims = matrix @ matrix.T
    purpose = document["analysis"]["purpose"]
    purpose_cached = json.loads((args.cache / (purpose["embedding"]["key"] + ".json")).read_text())
    assert hashlib.sha256(purpose["text"].encode()).hexdigest() == purpose_cached["source_sha256"]
    purpose_vector = np.asarray(purpose_cached["vector"], dtype=float)
    purpose_vector /= np.linalg.norm(purpose_vector)
    for i, node in enumerate(nodes):
        assert abs(node["purpose_similarity"] - max(0, float(matrix[i] @ purpose_vector))) < 1e-6
        expected = sorted((j for j in range(len(nodes)) if j != i), key=lambda j: (-sims[i, j], nodes[j]["id"]))[:3]
        # Float32 export precision can swap exact ties; compare score instead.
        for match, j in zip(node["similar"], expected):
            assert abs(match["cosine"] - sims[i, j]) < 1e-6
            k = next(k for k, candidate in enumerate(nodes) if candidate["id"] == match["id"])
            assert abs(match["cosine"] - sims[i, k]) < 1e-6
    for node in document["views"]["feature"]["nodes"]:
        for field in ["importance", "semantic_density", "semantic_height", "x_umap", "y_umap", "embedding"]:
            assert node[field] == by_id[node["id"]][field]
    ordered = sorted(nodes, key=lambda n: n["importance"])
    assert all(a["semantic_height"] <= b["semantic_height"] for a, b in zip(ordered, ordered[1:]))
    report[project] = {
        "functions_verified": len(nodes), "source_digest": document["analysis"]["source_digest"],
        "map_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model": document["analysis"]["embedding"],
        "multi_chunk_functions": sum(n["embedding"]["chunks"] > 1 for n in nodes),
        "importance_quantiles": np.quantile([n["importance"] for n in nodes], [0, .25, .5, .75, 1]).tolist(),
        "highest_estimates": [{"function": n["qname"], "importance": n["importance"],
                               "nearest": by_id[n["similar"][0]["id"]]["qname"]} for n in ordered[-8:][::-1]],
    }
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v["functions_verified"] for k, v in report.items()}))
