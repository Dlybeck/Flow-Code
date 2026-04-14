"""Embed every function/method in a codebase individually (no concat).

This is the 'per-function base embedding' path. Output becomes the raw material
for terrain projection + trace overlay.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from parse_multi import parse_directory

MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "tinydb-src/tinydb")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "function_embeddings.json")

    print(f"Parsing {root}...", flush=True)
    functions = parse_directory(root)
    print(f"  {len(functions)} functions/methods", flush=True)

    qnames = sorted(functions.keys())
    texts = [functions[q].source for q in qnames]

    print(f"Loading {MODEL_NAME}...", flush=True)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)

    print(f"Embedding {len(texts)} functions...", flush=True)
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True).tolist()

    payload = {
        "model": MODEL_NAME,
        "root": str(root),
        "functions": [
            {
                "qname": q,
                "file": functions[q].file,
                "docstring_head": (functions[q].docstring.split("\n", 1)[0] if functions[q].docstring else ""),
                "source_lines": functions[q].source.count("\n") + 1,
                "vector": v,
            }
            for q, v in zip(qnames, vectors)
        ],
    }
    out.write_text(json.dumps(payload))
    print(f"wrote {out} ({len(qnames)} vectors, dim={len(vectors[0])})")


if __name__ == "__main__":
    main()
