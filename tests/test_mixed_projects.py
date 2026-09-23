from pathlib import Path

from flowcode import generate_graph
from flowcode.execution_ir import validate_execution_ir
from flowcode.language_adapter import index_repo_auto
from flowcode.cli import main
import json


def test_one_graph_preserves_both_halves_of_a_web_application(tmp_path: Path):
    (tmp_path / "server.py").write_text(
        'def format_result():\n    return "done"\n\nasync def digitize():\n    return format_result()\n'
    )
    (tmp_path / "client.js").write_text(
        'function renderResult() { return "done"; }\nasync function submitDocument() { renderResult(); }\n'
    )

    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)

    assert validate_execution_ir(graph) == []
    assert set(graph["languages"]) == {"python", "javascript"}
    functions = {n["label"]: n for n in graph["nodes"] if n["kind"] == "function"}
    assert set(functions) == {
        "server.format_result",
        "server.digitize",
        "client.renderResult",
        "client.submitDocument",
    }
    calls = {
        (e["from"], e["to"]) for e in graph["edges"] if e["confidence"] == "resolved"
    }
    assert (
        functions["server.digitize"]["id"],
        functions["server.format_result"]["id"],
    ) in calls
    assert (
        functions["client.submitDocument"]["id"],
        functions["client.renderResult"]["id"],
    ) in calls
    assert len({e["id"] for e in graph["edges"]}) == len(graph["edges"])
    assert generate_graph(tmp_path, include_overlay=False, use_llm=False) == graph


def test_source_selection_excludes_dependencies_and_works_under_hidden_parent(
    tmp_path: Path,
):
    root = tmp_path / ".private-checkout"
    for rel, text in {
        "server/api.py": "def endpoint(): pass",
        "browser/view.js": "function render() {}",
        "browser/node_modules/package/index.js": "function dependency() {}",
        "browser/dist/app.js": "function compiled() {}",
        "browser/vendor/library.js": "function vendor() {}",
        "browser/library.min.js": "function minified() {}",
        "unselected/example.ts": "function unrelated() {}",
    }.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    raw = index_repo_auto(root, src_roots=["server", "browser", "browser"])
    assert {f["path"] for f in raw["files"]} == {"server/api.py", "browser/view.js"}
    assert len(raw["files"]) == 2
    graph = generate_graph(
        root, src_roots=["server", "browser"], include_overlay=False, use_llm=False
    )
    assert set(graph["languages"]) == {"python", "javascript"}
    assert {n["label"] for n in graph["nodes"]} == {
        "server.api.endpoint",
        "browser.view.render",
    }


def test_command_line_exports_the_same_mixed_graph(tmp_path: Path):
    (tmp_path / "server.py").write_text("def endpoint(): pass")
    (tmp_path / "view.js").write_text("function openPage() {}")
    output = tmp_path / "flow.json"
    assert main(["execution-ir", str(tmp_path), "-o", str(output)]) == 0
    graph = json.loads(output.read_text())
    assert set(graph["languages"]) == {"python", "javascript"}
    assert {n["label"] for n in graph["nodes"]} == {"server.endpoint", "view.openPage"}


def test_browser_closures_and_callback_bodies_have_their_own_source_context(
    tmp_path: Path,
):
    (tmp_path / "view.js").write_text("""(function () {
  function renderResult() { return "done"; }
  const openPage = async () => { renderResult(); };
  document.addEventListener('click', () => { openPage(); });
})();
""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    functions = [n for n in graph["nodes"] if n["kind"] == "function"]
    render = next(n for n in functions if n["label"].endswith(".renderResult"))
    opened = next(n for n in functions if n["label"].endswith(".openPage"))
    callback = next(n for n in functions if n["location"]["start_line"] == 4)
    calls = {
        (e["from"], e["to"]) for e in graph["edges"] if e["confidence"] == "resolved"
    }
    assert (opened["id"], render["id"]) in calls
    assert (callback["id"], opened["id"]) in calls
    assert all(n["location"]["path"] == "view.js" for n in functions)
    assert len({n["id"] for n in functions}) == len(functions)


def test_reused_browser_function_names_remain_distinct_and_resolve_by_block(
    tmp_path: Path,
):
    (tmp_path / "view.js").write_text("""function render(flag) {
  if (flag) {
    function finish() { return 'first'; }
    finish();
  }
  if (!flag) {
    function finish() { return 'second'; }
    finish();
  }
}
""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    finishes = [n for n in graph["nodes"] if n["label"] == "view.render.finish"]
    assert len(finishes) == 2
    assert len({n["id"] for n in finishes}) == 2
    calls = {
        (e["from"], e["to"], e.get("callsite", {}).get("line"))
        for e in graph["edges"]
        if e["confidence"] == "resolved"
    }
    render_id = "ts:fn:view.render"
    first = next(n for n in finishes if n["location"]["start_line"] == 3)
    second = next(n for n in finishes if n["location"]["start_line"] == 7)
    assert (render_id, first["id"], 4) in calls
    assert (render_id, second["id"], 8) in calls


def test_reused_python_route_names_remain_distinct_functions(tmp_path: Path):
    (tmp_path / "routes.py").write_text("""def first_result(): pass
def second_result(): pass
@router.get('/first')
def page(): return first_result()
@router.get('/second')
def page(): return second_result()
""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    pages = [
        n for n in graph["nodes"] if n.get("location", {}).get("start_line") in {4, 6}
    ]
    assert len(pages) == 2
    assert len({n["id"] for n in pages}) == 2
    assert {n["label"] for n in pages} == {"routes.page"}
    edges = {
        (e["from"], e["to"]) for e in graph["edges"] if e["confidence"] == "resolved"
    }
    assert (pages[0]["id"], "py:fn:routes.first_result") in edges
    assert (pages[1]["id"], "py:fn:routes.second_result") in edges


def test_imports_resolve_the_named_module_without_guessing_by_function_name(
    tmp_path: Path,
):
    (tmp_path / "chosen.ts").write_text("export function format() {}")
    (tmp_path / "other.ts").write_text("export function format() {}")
    (tmp_path / "main.ts").write_text(
        'import {format} from "./chosen";\nexport function main() { format(); }'
    )
    (tmp_path / "external.ts").write_text(
        'import {format} from "chosen";\nexport function request() { format(); }'
    )
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    resolved = {
        (e["from"], e["to"]) for e in graph["edges"] if e["confidence"] == "resolved"
    }
    assert ("ts:fn:main.main", "ts:fn:chosen.format") in resolved
    assert not any(fr == "ts:fn:external.request" for fr, _ in resolved)
    assert any(
        e["from"] == "ts:fn:external.request" and e["confidence"] == "unknown"
        for e in graph["edges"]
    )


def test_jsx_component_body_is_analyzed_with_its_actual_grammar(tmp_path: Path):
    (tmp_path / "screen.jsx").write_text(
        'function title() { return "Demo"; }\nexport function Screen() { return <h1>{title()}</h1>; }'
    )
    raw = index_repo_auto(tmp_path)
    assert raw["files"][0]["analysis"]["parse_ok"] is True
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    assert any(
        e["from"] == "ts:fn:screen.Screen"
        and e["to"] == "ts:fn:screen.title"
        and e["confidence"] == "resolved"
        for e in graph["edges"]
    )
