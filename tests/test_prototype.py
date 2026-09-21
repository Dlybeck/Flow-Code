from copy import deepcopy

import pytest

from flowcode import generate_graph
from flowcode.prototype import terrain_fixture


def snapshot(graph):
    nodes = [n for n in graph["nodes"] if n["kind"] == "function"]
    return {
        "project": "independent",
        "entries": graph["entrypoints"],
        "analysis": dict(
            graph["analysis"], function_count=len(nodes), source_roots=["."]
        ),
        "views": {
            "overview": {
                "nodes": [
                    dict(
                        n, qname=n["label"], importance=0.5, file=n["location"]["path"]
                    )
                    for n in nodes
                ],
                "edges": graph["edges"],
            }
        },
    }


def test_complete_inventory_and_bridge_evidence(tmp_path):
    (tmp_path / "code.py").write_text("""
class Worker:
    def run(self): external()
def bridge(): return Worker().run()
def main(): return bridge()
def isolated(): pass
""")
    graph = generate_graph(tmp_path, include_overlay=False)
    doc = snapshot(graph)
    fixture = terrain_fixture(doc, graph=graph)
    assert len(fixture["nodes"]) == fixture["coverage"]["indexed_functions"] == 4
    assert fixture["entrypoints"] == ["py:fn:code.main"]
    edges = {(e["from"], e["to"]): e for e in fixture["edges"]}
    bridge = edges["py:fn:code.bridge", "py:fn:code.Worker.run"]
    assert bridge["confidence"] == "heuristic"
    assert bridge["evidence"][0]["callsite"] == {"line": 4, "path": "code.py"}
    worker = next(n for n in fixture["nodes"] if n["id"] == "py:fn:code.Worker.run")
    assert worker["boundaries"][0]["target"] == "external"
    assert any(n["id"] == "py:fn:code.isolated" for n in fixture["nodes"])
    assert fixture == terrain_fixture(doc, graph=graph)
    assert doc == snapshot(graph), "conversion must not mutate its input"


def test_refresh_refuses_stale_sources_or_missing_functions(tmp_path):
    (tmp_path / "code.py").write_text("def main(): pass\n")
    graph = generate_graph(tmp_path, include_overlay=False)
    doc = snapshot(graph)
    stale = deepcopy(graph)
    stale["analysis"]["source_digest"] = "stale"
    with pytest.raises(ValueError, match="Source snapshot changed"):
        terrain_fixture(doc, graph=stale)
    stale = deepcopy(graph)
    stale["nodes"] = []
    with pytest.raises(ValueError, match="Function inventory changed"):
        terrain_fixture(doc, graph=stale)
    doc["views"]["overview"]["nodes"] = []
    with pytest.raises(ValueError, match="retain every"):
        terrain_fixture(doc)


def test_no_entry_evidence_does_not_turn_first_function_into_entry(tmp_path):
    (tmp_path / "code.py").write_text("def helper(): pass\n")
    graph = generate_graph(tmp_path, include_overlay=False)
    fixture = terrain_fixture(snapshot(graph), graph=graph)
    assert fixture["nodes"] and fixture["entrypoints"] == []


def test_refresh_preserves_explicit_entry_selection(tmp_path):
    (tmp_path / "code.py").write_text("def main(): pass\ndef api(): pass\n")
    graph = generate_graph(tmp_path, include_overlay=False)
    doc = snapshot(graph)
    doc["analysis"]["entry_selection"] = "manual"
    doc["entries"] = ["py:fn:code.api"]
    fixture = terrain_fixture(doc, graph=graph)
    assert fixture["entrypoints"] == ["py:fn:code.api"]
    assert fixture["coverage"]["entry_selection"] == "manual"
