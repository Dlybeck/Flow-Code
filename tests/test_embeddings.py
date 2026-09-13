"""Cache identity is part of correctness: stale vectors must never masquerade as fresh."""

import hashlib
import json

import pytest

from flowcode.embeddings import RECIPE, CodeEmbedder


def cached_record(cache, source):
    source_sha = hashlib.sha256(source.encode()).hexdigest()
    key = hashlib.sha256(
        json.dumps([RECIPE, source_sha], sort_keys=True).encode()
    ).hexdigest()
    record = {
        "key": key,
        "source_sha256": source_sha,
        "tokens": 4,
        "chunks": 1,
        "vector": [1.0] + [0.0] * 767,
    }
    path = cache / (key + ".json")
    path.write_text(json.dumps(record))
    return path, record


def test_content_cache_reuses_vectors_without_loading_model(tmp_path, monkeypatch):
    cached_record(tmp_path, "source")
    encoder = CodeEmbedder(tmp_path)
    monkeypatch.setattr(encoder, "_load", lambda: pytest.fail("Unexpected model load"))
    vectors, receipts = encoder.encode({"renamed-id": "source"})
    assert len(vectors["renamed-id"]) == 768
    assert receipts["renamed-id"]["vector_sha256"]
    assert "vector" not in receipts["renamed-id"]


def test_changed_source_cannot_reuse_old_vector(tmp_path, monkeypatch):
    cached_record(tmp_path, "before")
    encoder = CodeEmbedder(tmp_path)

    def cold_load():
        raise RuntimeError("new embedding required")

    monkeypatch.setattr(encoder, "_load", cold_load)
    with pytest.raises(RuntimeError, match="new embedding required"):
        encoder.encode({"same-id": "after"})


@pytest.mark.parametrize(
    "corruption", ["zero", "nan", "wrong-source", "wrong-dimension"]
)
def test_invalid_vectors_fail_instead_of_faking_a_map(tmp_path, corruption):
    path, record = cached_record(tmp_path, "source")
    if corruption == "zero":
        record["vector"] = [0.0] * 768
    elif corruption == "nan":
        record["vector"][0] = float("nan")
    elif corruption == "wrong-source":
        record["source_sha256"] = "old"
    else:
        record["vector"] = [1.0]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Invalid embedding receipt"):
        CodeEmbedder(tmp_path).encode({"function": "source"})
