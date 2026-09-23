from flowcode.behaviors import build_behavior_map, extract_exit_sites


def node(node_id, *, score=0.5, exits=None):
    return {
        "id": node_id,
        "label": node_id.rsplit(".", 1)[-1],
        "qname": node_id,
        "language": "python",
        "location": {"path": "app.py", "start_line": 1, "end_line": 20},
        "score": score,
        "exits": exits or [],
    }


def call(source, target, line):
    return {
        "from": source,
        "to": target,
        "kind": "calls",
        "confidence": "resolved",
        "callsite": {"line": line, "path": "app.py"},
    }


def test_python_exits_are_source_grounded_and_nested_functions_are_ignored():
    source = """def run(flag):
    def nested():
        return 'not-run-exit'
    if flag:
        raise ValueError('bad')
    return build_result()
"""
    exits = extract_exit_sites(
        source,
        language="python",
        source_node_id="py:fn:app.run",
        location={"path": "app.py", "start_line": 10, "end_line": 15},
    )
    assert [(row["kind"], row["location"]["start_line"]) for row in exits] == [
        ("raise", 14),
        ("return", 15),
    ]
    assert exits[1]["label"] == "Return Build result"


def test_browser_exits_ignore_returns_from_nested_functions():
    source = """function run(flag) {
  function nested() {
    return 'not-run-exit';
  }
  if (flag) return buildResult();
  throw new Error('bad');
}
"""
    exits = extract_exit_sites(
        source,
        language="javascript",
        source_node_id="ts:fn:app.run",
        location={"path": "app.js", "start_line": 20, "end_line": 26},
    )

    assert [(row["kind"], row["location"]["start_line"]) for row in exits] == [
        ("return", 24),
        ("throw", 25),
    ]


def test_implicit_exit_is_labeled_as_inferred_possibility():
    exits = extract_exit_sites(
        "def store():\n    save()\n",
        language="python",
        source_node_id="py:fn:app.store",
        location={"path": "app.py", "start_line": 4, "end_line": 5},
    )

    assert exits[0]["label"] == "May complete"
    assert exits[0]["inferred"] is True


def test_no_call_helper_is_a_node_not_the_parent_behavior_leaf():
    entry_exit = {
        "id": "exit:entry",
        "kind": "return",
        "label": "Return result",
        "exceptional": False,
        "location": {"path": "app.py", "start_line": 9, "end_line": 9},
    }
    document = build_behavior_map(
        [
            node("py:fn:app.main", exits=[entry_exit]),
            node("py:fn:app.ensure_image"),
        ],
        [call("py:fn:app.main", "py:fn:app.ensure_image", 5)],
        ["py:fn:app.main"],
    )
    layer = document["layers"][document["behaviors"][0]["root_layer_id"]]
    helper = next(row for row in layer["nodes"] if row["label"] == "Ensure image")
    assert helper["kind"] == "node"
    assert layer["leaf_ids"] == ["exit:entry"]
    assert (
        next(row for row in layer["nodes"] if row["id"] == "exit:entry")["source_refs"][
            0
        ]["node_id"]
        == "py:fn:app.main"
    )


def test_seed_points_to_a_focused_child_layer_and_preserves_source_references():
    nodes = [
        node("py:fn:app.main"),
        node("py:fn:app.process"),
        node("py:fn:app.prepare"),
    ]
    document = build_behavior_map(
        nodes,
        [
            call("py:fn:app.main", "py:fn:app.process", 4),
            call("py:fn:app.process", "py:fn:app.prepare", 12),
        ],
        ["py:fn:app.main"],
    )
    parent = document["layers"][document["behaviors"][0]["root_layer_id"]]
    seed = next(row for row in parent["nodes"] if row["kind"] == "seed")
    child = document["layers"][seed["child_layer_id"]]
    assert child["source_node_id"] == "py:fn:app.process"
    assert child["nodes"][0]["kind"] == "root"
    assert seed["source_refs"][0]["node_id"] == "py:fn:app.process"


def test_recursive_call_is_visible_without_an_infinite_seed_dive():
    document = build_behavior_map(
        [node("py:fn:app.walk")],
        [call("py:fn:app.walk", "py:fn:app.walk", 8)],
        ["py:fn:app.walk"],
    )
    layer = next(iter(document["layers"].values()))
    recursive = next(row for row in layer["nodes"] if row.get("recursive"))

    assert recursive["kind"] == "node"
    assert "child_layer_id" not in recursive


def test_duplicate_edge_evidence_at_one_callsite_is_one_visible_call():
    first = call("main", "helper", 4)
    duplicate_evidence = {
        **call("main", "helper", 4),
        "confidence": "heuristic",
        "evidence": "second_analyzer",
    }

    document = build_behavior_map(
        [node("main"), node("helper")],
        [first, duplicate_evidence],
        ["main"],
    )
    layer = document["layers"][document["behaviors"][0]["root_layer_id"]]
    calls = [row for row in layer["nodes"] if row["kind"] in {"node", "seed"}]

    assert len(calls) == 1
    assert calls[0]["label"] == "Helper"
    assert calls[0]["call_count"] == 1
    assert calls[0]["callsites"] == [
        {"path": "app.py", "line": 4, "confidence": "resolved"}
    ]


def test_same_named_candidate_targets_are_one_honest_call_event():
    left = node("module.Left.save")
    right = node("module.Right.save")

    document = build_behavior_map(
        [node("main"), left, right],
        [call("main", left["id"], 7), call("main", right["id"], 7)],
        ["main"],
    )
    layer = document["layers"][document["behaviors"][0]["root_layer_id"]]
    calls = [row for row in layer["nodes"] if row["kind"] in {"node", "seed"}]

    assert len(calls) == 1
    assert calls[0]["label"] == "Save"
    assert calls[0]["candidate_count"] == 2
    assert calls[0]["target_candidates"] == sorted([left["id"], right["id"]])
    assert len(calls[0]["source_refs"]) == 2
    assert "child_layer_id" not in calls[0]


def test_repeated_calls_are_compacted_without_hiding_the_count():
    document = build_behavior_map(
        [node("main"), node("helper"), node("between")],
        [
            call("main", "helper", 4),
            call("main", "between", 5),
            call("main", "helper", 6),
        ],
        ["main"],
    )
    layer = document["layers"][document["behaviors"][0]["root_layer_id"]]
    calls = [row for row in layer["nodes"] if row["kind"] in {"node", "seed"}]

    assert len(calls) == 2
    helper = next(row for row in calls if row["label"] == "Helper")
    assert helper["call_count"] == 2
    assert [site["line"] for site in helper["callsites"]] == [4, 6]


def test_distinct_same_named_functions_get_source_context():
    left = node("module.Left.save")
    right = node("module.Right.save")

    document = build_behavior_map(
        [node("main"), left, right],
        [call("main", left["id"], 4), call("main", right["id"], 5)],
        ["main"],
    )
    layer = document["layers"][document["behaviors"][0]["root_layer_id"]]
    labels = {row["label"] for row in layer["nodes"] if row["kind"] in {"node", "seed"}}

    assert labels == {"Left · Save", "Right · Save"}


def test_duplicate_qualified_names_use_their_source_line():
    first = node("first")
    first["qname"] = "scope.rehash"
    first["label"] = "rehash"
    first["location"]["start_line"] = 10
    second = node("second")
    second["qname"] = "scope.rehash"
    second["label"] = "rehash"
    second["location"]["start_line"] = 20

    document = build_behavior_map(
        [node("main"), first, second],
        [call("main", "first", 4), call("main", "second", 5)],
        ["main"],
    )
    layer = document["layers"][document["behaviors"][0]["root_layer_id"]]
    labels = {row["label"] for row in layer["nodes"] if row["kind"] in {"node", "seed"}}

    assert labels == {"Scope · Rehash · line 10", "Scope · Rehash · line 20"}


def test_leaf_orders_retain_both_project_and_local_strategies():
    exits = [
        {
            "id": "exit:project",
            "kind": "return",
            "label": "Project relevant",
            "exceptional": False,
            "location": {"path": "app.py", "start_line": 8, "end_line": 8},
            "project_similarity": 0.95,
            "local_similarity": 0.2,
        },
        {
            "id": "exit:local",
            "kind": "return",
            "label": "Locally relevant",
            "exceptional": False,
            "location": {"path": "app.py", "start_line": 9, "end_line": 9},
            "project_similarity": 0.1,
            "local_similarity": 0.98,
        },
    ]
    document = build_behavior_map([node("main", exits=exits)], [], ["main"])
    layer = next(iter(document["layers"].values()))
    assert layer["leaf_orders"]["project"][0] == "exit:project"
    assert layer["leaf_orders"]["local"][0] == "exit:local"
    assert layer["leaf_orders"]["hybrid"][0] == "exit:local"


def test_every_function_has_a_layer_and_unreachable_functions_are_explicit():
    document = build_behavior_map(
        [node("main", score=1), node("called"), node("unused")],
        [call("main", "called", 2)],
        ["main"],
    )
    assert document["coverage"]["functions_with_layers"] == 3
    assert document["coverage"]["unplaced_function_ids"] == ["unused"]
    assert set(document["coverage"]["accounted_function_ids"]) == {
        "main",
        "called",
        "unused",
    }


def test_primary_behaviors_prefer_declared_routes_over_generic_callbacks():
    route = node("route", score=0.4)
    route["entry_evidence"] = ["declared_route"]
    callback = node("callback", score=0.6)
    callback["label"] = "Callback · line 12"
    callback["entry_evidence"] = ["event_listener_callback"]
    document = build_behavior_map([route, callback], [], ["callback", "route"])
    assert document["behaviors"][0]["root_node_id"] == "route"
    assert document["behaviors"][0]["rank_signals"]["entry_evidence"] > 0


def test_primary_behaviors_use_exported_importance_and_hide_generic_callbacks():
    named = node("named", score=0.1)
    named["importance"] = 0.4
    named["label"] = "main"
    named["entry_evidence"] = ["conventional_main"]
    callback = node("callback", score=0.9)
    callback["importance"] = 1.0
    callback["label"] = "Callback · line 12"
    callback["entry_evidence"] = ["event_listener_callback"]

    document = build_behavior_map([callback, named], [], ["callback", "named"])

    by_root = {behavior["root_node_id"]: behavior for behavior in document["behaviors"]}
    assert by_root["callback"]["score"] == 1.0
    assert by_root["named"]["score"] == 0.4
    assert document["primary_behavior_ids"] == [by_root["named"]["id"]]


def test_generic_route_names_use_the_source_backed_method_and_path():
    route = node("route")
    route["label"] = "test"
    route["routes"] = [{"method": "GET", "path": "/projects/programs"}]

    document = build_behavior_map([route], [], ["route"])

    assert document["behaviors"][0]["label"] == "Projects › Programs"
