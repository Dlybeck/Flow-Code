"""Golden proofs for each language before mixed-language expansion."""

from __future__ import annotations

from pathlib import Path

import pytest

from flowcode import generate_graph
from flowcode.execution_ir import validate_execution_ir
from flowcode.sources import source_files

CASES = [
    (
        "javascript",
        "golden-js",
        "ts:fn:index.main",
        "ts:fn:index.formatGreeting",
        "Dynamic imports and require()",
    ),
    (
        "typescript",
        "golden-ts",
        "ts:fn:index.main",
        "ts:fn:utils.formatGreeting",
        "Dynamic imports and require()",
    ),
    (
        "java",
        "golden-java",
        "java:fn:demo.App.main",
        "java:fn:demo.App.calculate",
        "Overload resolution",
    ),
    (
        "c",
        "golden-c",
        "c:fn:main.main",
        "c:fn:main.calculate",
        "Function pointers",
    ),
    (
        "csharp",
        "golden-csharp",
        "csharp:fn:Demo.App.Main",
        "csharp:fn:Demo.App.Calculate",
        "delegates",
    ),
    (
        "haskell",
        "golden-haskell",
        "haskell:fn:Main.main",
        "haskell:fn:Main.calculate",
        "Higher-order calls",
    ),
]


@pytest.mark.parametrize(
    ("language", "fixture", "caller", "callee", "known_limit"), CASES
)
def test_single_language_graph(
    workspace_root: Path,
    language: str,
    fixture: str,
    caller: str,
    callee: str,
    known_limit: str,
) -> None:
    graph = generate_graph(
        workspace_root / "fixtures" / fixture,
        include_overlay=False,
        use_llm=False,
    )
    assert graph["languages"] == [language]
    assert validate_execution_ir(graph) == []
    assert caller in graph["entrypoints"]
    assert any(
        known_limit in limit for limit in graph["analysis"]["known_limits"]
    )
    assert any(
        edge["from"] == caller
        and edge["to"] == callee
        and edge["kind"] == "calls"
        and edge["confidence"] == "resolved"
        for edge in graph["edges"]
    )
    assert graph == generate_graph(
        workspace_root / "fixtures" / fixture,
        include_overlay=False,
        use_llm=False,
    )


def test_new_language_mix_is_explicitly_deferred(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main():\n    return 1\n")
    (tmp_path / "Main.java").write_text("class Main { static int main() { return 1; } }")
    with pytest.raises(ValueError, match="Mixed-language analysis.*later phase"):
        generate_graph(tmp_path, include_overlay=False, use_llm=False)


def test_generated_language_directories_are_skipped_case_insensitively(
    tmp_path: Path,
) -> None:
    (tmp_path / "Assets").mkdir()
    (tmp_path / "Assets/Game.cs").write_text("class Game {}")
    for directory in ("Library", "bin", "obj", "target"):
        generated = tmp_path / directory
        generated.mkdir()
        (generated / "Generated.cs").write_text("class Generated {}")
    first_party = tmp_path / "packages" / "game"
    first_party.mkdir(parents=True)
    (first_party / "GamePackage.cs").write_text("class GamePackage {}")

    selected = source_files(tmp_path, ["."], {".cs"})
    assert [path.relative_to(tmp_path).as_posix() for path in selected] == [
        "Assets/Game.cs",
        "packages/game/GamePackage.cs",
    ]
    explicitly_selected = source_files(tmp_path, ["Library"], {".cs"})
    assert [path.relative_to(tmp_path).as_posix() for path in explicitly_selected] == [
        "Library/Generated.cs"
    ]


@pytest.mark.parametrize(
    ("extension", "source"),
    [
        (
            ".java",
            """package demo;
class App {
  static int choose(int value) { return value; }
  static String choose(String value) { return value; }
  static void main() { choose(1); }
}
""",
        ),
        (
            ".cs",
            """namespace Demo;
class App {
  static int Choose(int value) { return value; }
  static string Choose(string value) { return value; }
  static void Main() { Choose(1); }
}
""",
        ),
    ],
)
def test_overloaded_call_remains_ambiguous(
    tmp_path: Path, extension: str, source: str
) -> None:
    (tmp_path / f"App{extension}").write_text(source)
    graph = generate_graph(tmp_path, include_overlay=False)
    main = next(node["id"] for node in graph["nodes"] if node["label"].endswith(".main") or node["label"].endswith(".Main"))
    calls = [edge for edge in graph["edges"] if edge["from"] == main]
    assert any(
        edge["confidence"] == "unknown"
        and edge["callsite"]["reason"] == "ambiguous"
        for edge in calls
    )
    assert not any(edge["confidence"] == "resolved" for edge in calls)


def test_java_ids_use_declared_package_in_maven_layout(tmp_path: Path) -> None:
    source = tmp_path / "src/main/java/com/acme/App.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        "package com.acme; class App { static void main() {} }"
    )
    graph = generate_graph(tmp_path, include_overlay=False)
    assert "java:fn:com.acme.App.main" in {
        node["id"] for node in graph["nodes"]
    }
    assert not any("main.java" in node["id"] for node in graph["nodes"])


def test_csharp_block_namespaces_are_scoped_per_declaration(tmp_path: Path) -> None:
    (tmp_path / "App.cs").write_text(
        """namespace Alpha { class App { static void Main() {} } }
namespace Beta { class Worker { static void Run() {} } }
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False)
    node_ids = {node["id"] for node in graph["nodes"]}
    assert "csharp:fn:Alpha.App.Main" in node_ids
    assert "csharp:fn:Beta.Worker.Run" in node_ids


def test_haskell_equations_form_one_function_with_resolved_calls(tmp_path: Path) -> None:
    (tmp_path / "Main.hs").write_text(
        """module Main where
choose 0 = 0
choose n = choose (n - 1)
main = print (choose 2)
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False)
    choose_id = "haskell:fn:Main.choose"
    assert [node["id"] for node in graph["nodes"]].count(choose_id) == 1
    resolved = {
        (edge["from"], edge["to"])
        for edge in graph["edges"]
        if edge["confidence"] == "resolved"
    }
    assert ("haskell:fn:Main.main", choose_id) in resolved
    assert (choose_id, choose_id) in resolved


def test_java_explicit_receiver_and_overload_arity(tmp_path):
    (tmp_path / 'App.java').write_text('''
class Worker {
    void work() { work(1); }
    void work(int value) { }
}
class App {
    static void main(String[] args) {
        Worker item = new Worker();
        item.work();
    }
    void unknown(External item) { item.work(); }
}
''')
    graph = generate_graph(tmp_path, include_overlay=False)
    edges = [e for e in graph['edges'] if e['confidence'] != 'unknown']
    call = next(e for e in edges if e['from'].endswith('App.main'))
    assert call['to'].endswith('Worker.work')
    assert call['confidence'] == 'heuristic'
    assert call['evidence'] == 'declared_receiver_type_and_arity'
    assert any(e['from'].endswith('Worker.work') and e['to'].endswith('Worker.work$overload_2') for e in edges)
    assert not any(e['from'].endswith('App.unknown') for e in edges)


def test_java_missing_this_or_implicit_member_is_not_unrelated_method(tmp_path):
    (tmp_path / 'App.java').write_text('''
class App extends External {
    void main() { this.save(); save(); }
}
class Unrelated { void save() {} }
''')
    graph = generate_graph(tmp_path, include_overlay=False)
    assert not [e for e in graph['edges'] if e['to'].endswith('Unrelated.save')]
    assert len([e for e in graph['edges'] if e['confidence'] == 'unknown']) == 2


def test_java_local_type_from_another_block_does_not_bind_a_field(tmp_path):
    (tmp_path / 'App.java').write_text('''
class Worker { void run() {} }
class App {
    External item;
    void main() {
        { Worker item = new Worker(); }
        item.run();
    }
}
''')
    graph = generate_graph(tmp_path, include_overlay=False)
    assert not [e for e in graph['edges'] if e['to'].endswith('Worker.run')]
