"""Authored tours cannot silently invent source paths or change semantic data."""

import copy

import pytest

from flowcode.guides import attach_guide


@pytest.fixture
def source_tour():
    snapshot = {
        "entries": ["a"],
        "analysis": {"embedding": {"model": "test"}},
        "views": {
            "feature": {
                "nodes": [
                    {"id": "a", "qname": "client.start", "importance": 0.4},
                    {"id": "b", "qname": "server.handle", "importance": 0.9},
                ],
                "edges": [
                    {
                        "id": "request",
                        "from": "a",
                        "to": "b",
                        "confidence": "heuristic",
                        "kind": "call",
                        "relation": "http",
                    }
                ],
            }
        },
    }
    guide = {
        "title": "Handle a request",
        "summary": "Follow the browser request to its handler.",
        "stops": [
            {"symbol": "client.start", "title": "Send", "summary": "Send a request."},
            {"symbol": "server.handle", "title": "Handle", "summary": "Return data."},
        ],
    }
    return snapshot, guide


def test_tour_preserves_semantics_and_inferred_evidence(source_tour):
    snapshot, guide = source_tour
    original = copy.deepcopy(snapshot)
    result = attach_guide(snapshot, guide)
    assert snapshot == original
    assert {k: v for k, v in result.items() if k != "guide"} == original
    assert result["guide"]["kind"] == "authored_source_tour"
    assert result["guide"]["stops"][1]["via"] == {
        "edge": "request",
        "confidence": "heuristic",
        "relation": "http",
    }


def test_tour_prefers_resolved_callsite_when_available(source_tour):
    snapshot, guide = source_tour
    edges = snapshot["views"]["feature"]["edges"]
    edges.append(dict(edges[0], id="direct", confidence="resolved"))
    assert attach_guide(snapshot, guide)["guide"]["stops"][1]["via"]["edge"] == "direct"


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "ambiguous",
        "reversed",
        "unknown",
        "duplicate",
        "not-entry",
        "empty",
        "blank",
    ],
)
def test_rejects_unsupported_source_tours(source_tour, failure):
    snapshot, guide = source_tour
    view = snapshot["views"]["feature"]
    if failure == "missing":
        guide["stops"][1]["symbol"] = "server.removed"
    elif failure == "ambiguous":
        view["nodes"].append(dict(view["nodes"][1], id="other"))
    elif failure == "reversed":
        view["edges"][0].update({"from": "b", "to": "a"})
    elif failure == "unknown":
        view["edges"][0]["confidence"] = "unknown"
    elif failure == "duplicate":
        guide["stops"][1] = guide["stops"][0]
    elif failure == "not-entry":
        snapshot["entries"] = ["b"]
    elif failure == "empty":
        guide["stops"] = []
    elif failure == "blank":
        guide["stops"][0]["summary"] = " "
    with pytest.raises(ValueError):
        attach_guide(snapshot, guide)
