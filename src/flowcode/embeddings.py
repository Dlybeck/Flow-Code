"""Build-time code embeddings. Nothing in this module runs on the web server.

Jina's original code model, pinned weights and implementation, local inference.
Long functions use token-weighted mean pooling over complete 512-token chunks;
no source is silently truncated. Content-addressed vectors make rebuilds cheap.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

MODEL = "jinaai/jina-embeddings-v2-base-code"
REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
CODE_REVISION = "3baf9e3ac750e76e8edd3019170176884695fb94"
RECIPE = {
    "model": MODEL,
    "revision": REVISION,
    "code_revision": CODE_REVISION,
    "pooling": "token-weighted mean of complete 512-token chunks; L2 normalized",
    "chunk_tokens": 512,
    "dimensions": 768,
}


class CodeEmbedder:
    def __init__(self, cache_dir=None):
        self.cache = Path(
            cache_dir
            or os.environ.get(
                "FLOWCODE_EMBEDDING_CACHE", Path.home() / ".cache/flowcode/embeddings"
            )
        )
        self.tokenizer = self.model = None

    def _load(self):
        import torch
        from transformers import AutoModel, AutoTokenizer

        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = AutoModel.from_pretrained(
            MODEL,
            revision=REVISION,
            code_revision=CODE_REVISION,
            trust_remote_code=True,
            use_safetensors=True,
        ).eval()

    def encode(self, sources):
        """Return actual vectors plus per-function input receipts, keyed by ID."""
        import numpy as np

        self.cache.mkdir(parents=True, exist_ok=True)
        vectors, receipts = {}, {}
        for index, (node, source) in enumerate(sorted(sources.items())):
            source_sha = hashlib.sha256(source.encode()).hexdigest()
            key = hashlib.sha256(
                json.dumps([RECIPE, source_sha], sort_keys=True).encode()
            ).hexdigest()
            path = self.cache / (key + ".json")
            if path.exists():
                record = json.loads(path.read_text())
                if record["key"] != key:
                    raise ValueError("Embedding cache identity mismatch")
            else:
                if self.model is None:
                    self._load()
                import torch

                tokens = self.tokenizer.encode(source, add_special_tokens=False)
                width = (
                    RECIPE["chunk_tokens"] - self.tokenizer.num_special_tokens_to_add()
                )
                chunks = [
                    tokens[i : i + width] for i in range(0, len(tokens), width)
                ] or [[]]
                total = None
                weight = 0
                with torch.inference_mode():
                    for chunk in chunks:
                        inputs = self.tokenizer.prepare_for_model(
                            chunk, return_tensors="pt", return_attention_mask=True
                        )
                        inputs = {k: v.unsqueeze(0) for k, v in inputs.items()}
                        output = self.model(**inputs).last_hidden_state
                        mask = inputs["attention_mask"].unsqueeze(-1)
                        mean = (output * mask).sum(dim=1) / mask.sum(dim=1)
                        count = max(1, len(chunk))
                        total = mean * count if total is None else total + mean * count
                        weight += count
                vector = torch.nn.functional.normalize(total / weight, dim=1)[
                    0
                ].tolist()
                record = {
                    "key": key,
                    "source_sha256": source_sha,
                    "tokens": len(tokens),
                    "chunks": len(chunks),
                    "vector": vector,
                }
                temporary = path.with_suffix(f".{os.getpid()}.tmp")
                temporary.write_text(json.dumps(record, sort_keys=True))
                temporary.replace(path)
            vector = np.asarray(record["vector"], dtype=float)
            if (
                vector.shape != (RECIPE["dimensions"],)
                or not np.isfinite(vector).all()
                or not np.isclose(np.linalg.norm(vector), 1, atol=1e-4)
                or record["source_sha256"] != source_sha
            ):
                raise ValueError(f"Invalid embedding receipt for {node}")
            vectors[node] = vector.tolist()
            receipts[node] = {k: v for k, v in record.items() if k != "vector"}
            receipts[node]["vector_sha256"] = hashlib.sha256(
                np.asarray(vector, dtype="<f4").tobytes()
            ).hexdigest()
            if (index + 1) % 25 == 0 or index + 1 == len(sources):
                print(
                    f"Embedded/cached {index + 1}/{len(sources)} functions", flush=True
                )
        return vectors, receipts
