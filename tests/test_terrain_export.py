import json

import numpy as np
import pytest

from flowcode.cli import main


@pytest.fixture
def deterministic_embeddings(monkeypatch):
    """Fixed test vectors only; production never substitutes synthetic vectors."""

    def encode(self, sources):
        vectors = {}
        for i, node in enumerate(sorted(sources)):
            vector = np.zeros(768)
            vector[i % 768] = 1
            vectors[node] = vector.tolist()
        return vectors, {node: {"test_fixture": True} for node in sources}

    monkeypatch.setattr("flowcode.embeddings.CodeEmbedder.encode", encode)


def test_export_is_repeatable_and_keeps_cycles_shared_calls_and_unknown_evidence(
    tmp_path,
    deterministic_embeddings,
):
    (tmp_path / "server.py").write_text("""def entry():
    shared()
    external()
def other(): shared()
def shared(): entry()
""")
    output = tmp_path / "map.json"
    args = [
        "export",
        str(tmp_path),
        "--src-root",
        "server.py",
        "--purpose",
        "An example project with functions and shared calls",
        "--project",
        "example",
        "--entry",
        "server.entry",
        "-o",
        str(output),
    ]
    assert main(args) == 0
    first = output.read_bytes()
    assert main(args) == 0
    assert output.read_bytes() == first
    data = json.loads(first)
    overview = data["views"]["overview"]
    assert len(overview["nodes"]) == 3
    assert len(overview["edges"]) == 3
    assert all(
        e["callsite"]["path"] == "server.py" and e["callsite"]["line"] > 0
        for e in overview["edges"]
    )
    assert {n["id"] for n in overview["nodes"]} == {
        "py:fn:server.entry",
        "py:fn:server.other",
        "py:fn:server.shared",
    }
    entry = next(n for n in overview["nodes"] if n["label"] == "entry")
    assert entry["boundaries"][0]["confidence"] == "unknown"
    assert entry["boundaries"][0]["callsite"]["line"] == 3
    assert data["analysis"]["source_digest"]
    assert data["analysis"]["source_roots"] == ["server.py"]
    assert str(tmp_path) not in first.decode()
    assert data["analysis"]["embedding"]["dimensions"] == 768
    assert all("semantic_height" in n and "importance" in n for n in overview["nodes"])


def test_export_refuses_missing_embeddings(tmp_path, monkeypatch):
    from flowcode.terrain import export_terrain

    (tmp_path / "code.py").write_text("def entry(): pass\n")
    monkeypatch.setattr(
        "flowcode.embeddings.CodeEmbedder.encode", lambda *args: ({}, {})
    )
    with pytest.raises(ValueError, match="Missing project purpose embedding"):
        export_terrain(tmp_path, project="missing", purpose="Example")


def test_export_needs_no_readme_or_project_description(
    tmp_path, deterministic_embeddings
):
    from flowcode.terrain import export_terrain

    (tmp_path / "code.py").write_text(
        "def main(): return project_work()\ndef project_work(): return 1\n"
    )
    document = export_terrain(tmp_path, project="independent")
    assert "purpose" not in document["analysis"]
    assert document["analysis"]["terrain"]["method"] == (
        "code novelty x substance with bounded graph centrality"
    )
    assert len(document["views"]["overview"]["nodes"]) == 2


def test_core_overlay_rejects_generative_enrichment(tmp_path):
    from flowcode import generate_graph

    (tmp_path / "code.py").write_text("def main(): return 1\n")
    with pytest.raises(ValueError, match="not part of core map generation"):
        generate_graph(tmp_path, use_llm=True)
    with pytest.raises(ValueError, match="not part of core map generation"):
        generate_graph(tmp_path, include_overlay=False, use_llm=True)


def test_cli_attaches_source_tour_and_preserves_output_on_stale_stop(
    tmp_path, deterministic_embeddings
):
    (tmp_path / "server.py").write_text("def entry(): handle()\ndef handle(): pass\n")
    guide_path = tmp_path / "guide.json"
    guide = {
        "title": "Handle a request",
        "summary": "A source tour.",
        "stops": [
            {
                "symbol": "server.entry",
                "title": "Enter",
                "summary": "Call the handler.",
            },
            {
                "symbol": "server.handle",
                "title": "Handle",
                "summary": "Finish the call.",
            },
        ],
    }
    guide_path.write_text(json.dumps(guide))
    output = tmp_path / "map.json"
    args = [
        "export",
        str(tmp_path),
        "--project",
        "example",
        "--purpose",
        "Handle requests",
        "--src-root",
        "server.py",
        "--entry",
        "server.entry",
        "--guide",
        str(guide_path),
        "-o",
        str(output),
    ]
    assert main(args) == 0
    first = output.read_bytes()
    assert json.loads(first)["guide"]["stops"][1]["via"]["confidence"] == "resolved"
    guide["stops"][1]["symbol"] = "server.removed"
    guide_path.write_text(json.dumps(guide))
    with pytest.raises(ValueError, match="one featured function"):
        main(args)
    assert output.read_bytes() == first


def test_semantic_neighbors_and_heights_follow_vectors_not_call_depth():
    from flowcode.terrain import _semantic_signals

    functions = {
        n: {"_source": "def function():\n    return 1\n", "depth": 0}
        for n in ["a", "b", "distinct"]
    }
    vectors = {"a": [1, 0, 0], "b": [0.99, 0.01, 0], "distinct": [0, 0, 1]}
    _semantic_signals(functions, vectors)
    assert functions["a"]["similar"][0]["id"] == "b"
    assert functions["distinct"]["importance"] > functions["a"]["importance"]
    assert functions["distinct"]["semantic_height"] > functions["a"]["semantic_height"]
    before = functions["a"]["similar"][0]["cosine"]
    vectors["b"] = [0, 0, 1]
    _semantic_signals(functions, vectors)
    assert functions["distinct"]["similar"][0]["id"] == "b"
    assert functions["a"]["similar"][0]["cosine"] < before


def test_equal_vectors_do_not_manufacture_importance_differences():
    from flowcode.terrain import _semantic_signals

    functions = {n: {"_source": "same"} for n in ["a", "b", "c"]}
    _semantic_signals(functions, {n: [1, 0] for n in functions})
    assert len({f["importance"] for f in functions.values()}) == 1
    assert len({f["semantic_height"] for f in functions.values()}) == 1


def test_graph_centrality_is_bounded_secondary_context():
    from flowcode.terrain import _semantic_signals

    functions = {
        "entry": {"_source": "short"},
        "project_work": {"_source": "substantive project work " * 20},
        "helper": {"_source": "short"},
    }
    vectors = {
        "entry": [1, 0, 0],
        "project_work": [0, 1, 0],
        "helper": [0.99, 0.01, 0],
    }
    edges = [
        {"from": "entry", "to": "project_work"},
        {"from": "project_work", "to": "helper"},
    ]
    _semantic_signals(functions, vectors, call_edges=edges)
    assert functions["project_work"]["graph_centrality"] == 1
    assert functions["project_work"]["importance"] > functions["helper"]["importance"]


def test_purpose_relevance_prevents_novel_utility_from_dominating():
    from flowcode.terrain import _semantic_signals

    functions = {n: {"_source": "same size"} for n in ["idea", "related", "utility"]}
    vectors = {"idea": [1, 0, 0], "related": [0.99, 0.01, 0], "utility": [0, 0, 1]}
    _semantic_signals(functions, vectors, purpose_vector=[1, 0, 0])
    assert (
        functions["utility"]["novelty_importance"]
        > functions["idea"]["novelty_importance"]
    )
    assert functions["idea"]["importance"] > functions["utility"]["importance"]
    assert (
        functions["idea"]["semantic_height"] > functions["utility"]["semantic_height"]
    )


def test_real_umap_projection_runs_and_repeats_with_pinned_dependencies():
    from flowcode.terrain import _semantic_signals

    functions = {str(i): {"_source": "same size"} for i in range(6)}
    vectors = {str(i): [1, i / 5, (i % 2) / 2] for i in range(6)}
    _semantic_signals(functions, vectors)
    first = [(f["x_umap"], f["y_umap"]) for f in functions.values()]
    _semantic_signals(functions, vectors)
    assert first == [(f["x_umap"], f["y_umap"]) for f in functions.values()]
    assert np.isfinite(first).all()
    assert len(set(first)) > 1


def test_call_path_importance_controls_descent_and_scale_preserves_order():
    from flowcode.terrain import _layout

    functions = {
        n: {"file": "example.py", "semantic_density": 0.5, "importance": value}
        for n, value in [("root", 1), ("idea", 1), ("helper", 0)]
    }
    view = _layout(
        functions,
        [{"from": "root", "to": child} for child in ["idea", "helper"]],
        ["root"],
        {n: [1, 0] for n in functions},
    )
    nodes = (
        {n["id"]: n for n in view["nodes"]}
        if "id" in view["nodes"][0]
        else dict(zip(sorted(functions), view["nodes"]))
    )
    assert nodes["root"]["height"] > nodes["idea"]["height"] > nodes["helper"]["height"]
    assert (
        nodes["root"]["raw_height"]
        > nodes["idea"]["raw_height"]
        > nodes["helper"]["raw_height"]
    )


def test_call_path_sibling_order_keeps_embedding_similarity():
    from flowcode.semantic_layout import radial_fan_layout

    ids = ["root", "a", "b", "c"]
    children = {"root": ["a", "b", "c"]}
    callers = {n: ["root"] for n in ["a", "b", "c"]}
    vectors = {"root": [1, 0], "a": [1, 0], "b": [0.9, 0.1], "c": [0, 1]}
    first = radial_fan_layout(ids, children, callers, vectors, {})[0]
    vectors["a"], vectors["c"] = vectors["c"], vectors["a"]
    second = radial_fan_layout(ids, children, callers, vectors, {})[0]
    assert first["a"] != second["a"]
    assert first["root"] == second["root"]


def test_feature_keeps_project_wide_semantic_scores(tmp_path, deterministic_embeddings):
    from flowcode.terrain import export_terrain

    (tmp_path / "code.py").write_text(
        "def entry(): helper()\ndef helper(): pass\ndef separate(): pass\n"
    )
    document = export_terrain(
        tmp_path, project="scope", entries=["code.entry"], purpose="Example functions"
    )
    overview = {n["id"]: n for n in document["views"]["overview"]["nodes"]}
    for node in document["views"]["feature"]["nodes"]:
        for key in [
            "importance",
            "semantic_density",
            "semantic_height",
            "x_umap",
            "y_umap",
        ]:
            assert node[key] == overview[node["id"]][key]
