"""Tests for generalized entrypoint detection (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from flowcode.entrypoint_heuristics import detect_entrypoints, load_flowcode_config


def _node(nid: str, label: str, *, path: str | None = None) -> dict:
    n: dict = {"id": nid, "label": label, "kind": "function"}
    if path is not None:
        n["location"] = {"path": path, "start_line": 1, "end_line": 1}
    return n


def _contains(fr: str, to: str) -> dict:
    return {"id": f"e:{fr}-{to}", "from": fr, "to": to, "kind": "contains", "confidence": "resolved"}


def _unknown_call(fr: str, expr: str) -> dict:
    return {
        "id": f"e:{fr}-unk",
        "from": fr,
        "to": "py:boundary:unresolved",
        "kind": "calls",
        "confidence": "unknown",
        "callsite": {"callee_expression": expr},
    }


# ── Priority 2: main node ──────────────────────────────────────────────────


def test_main_label_exact() -> None:
    nodes = [_node("a", "main"), _node("b", "pkg.other")]
    assert detect_entrypoints(nodes, []) == ["a"]


def test_main_label_suffix() -> None:
    nodes = [_node("a", "pkg.main"), _node("b", "pkg.other")]
    assert detect_entrypoints(nodes, []) == ["a"]


def test_main_and_factory_collected_together() -> None:
    """Tiers 2-5 collect cumulatively: a project with both a CLI main and an
    app factory should surface both as entrypoints."""
    nodes = [_node("a", "pkg.main"), _node("b", "pkg.create_app")]
    result = detect_entrypoints(nodes, [])
    assert set(result) == {"a", "b"}


# ── Priority 3: factory pattern ────────────────────────────────────────────


def test_factory_create_app() -> None:
    nodes = [_node("a", "pkg.create_app"), _node("b", "pkg.helper")]
    assert detect_entrypoints(nodes, []) == ["a"]


def test_factory_make_app() -> None:
    nodes = [_node("a", "pkg.make_app"), _node("b", "pkg.helper")]
    assert detect_entrypoints(nodes, []) == ["a"]


def test_factory_build_app() -> None:
    nodes = [_node("a", "pkg.build_app")]
    assert detect_entrypoints(nodes, []) == ["a"]


# ── Priority 4: route handler heuristic ───────────────────────────────────


def test_route_handler_heuristic() -> None:
    nodes = [
        _node("a", "pkg.setup_routes"),
        _node("b", "pkg.helper"),
    ]
    edges = [_unknown_call("a", "app.get")]
    result = detect_entrypoints(nodes, edges)
    assert result == ["a"]


def test_route_handler_skips_nested() -> None:
    """A nested node (has contains parent) should not be detected as route handler."""
    nodes = [
        _node("parent", "pkg.parent"),
        _node("child", "pkg.parent.inner"),
    ]
    edges = [
        _contains("parent", "child"),
        _unknown_call("child", "app.route"),
    ]
    result = detect_entrypoints(nodes, edges)
    # child is nested → falls through to __init__ or fallback
    assert "child" not in result or "parent" in result


# ── Tier 5: __init__ module exports (detected via location.path) ──────────


def test_init_module_via_location_path() -> None:
    """Tier 5 detects functions defined in __init__.py via location.path,
    not via label substring (since module_qualname_from_path strips '__init__'
    from qualified names — labels never contain '__init__')."""
    nodes = [
        _node("a", "pkg.setup", path="src/pkg/__init__.py"),
        _node("b", "pkg.helper.do_thing", path="src/pkg/helper.py"),
    ]
    result = detect_entrypoints(nodes, [])
    assert result == ["a"]


def test_init_module_at_repo_root() -> None:
    nodes = [_node("a", "pkg.api", path="__init__.py")]
    result = detect_entrypoints(nodes, [])
    assert result == ["a"]


def test_main_and_init_export_both_collected() -> None:
    """A project with both a CLI main and a public-API function in __init__.py
    should surface both — covers the flowcode self-hosting case (cli.main +
    flowcode.generate_graph)."""
    nodes = [
        _node("cli", "pkg.cli.main", path="src/pkg/cli.py"),
        _node("api", "pkg.generate_graph", path="src/pkg/__init__.py"),
        _node("internal", "pkg.helper", path="src/pkg/helper.py"),
    ]
    result = detect_entrypoints(nodes, [])
    assert set(result) == {"cli", "api"}


# ── Priority 6: fallback ───────────────────────────────────────────────────


def test_fallback_first_node() -> None:
    nodes = [_node("x", "pkg.arbitrary"), _node("y", "pkg.another")]
    result = detect_entrypoints(nodes, [])
    assert result == ["x"]


def test_empty_nodes_returns_empty() -> None:
    assert detect_entrypoints([], []) == []


# ── Priority 1: config override ───────────────────────────────────────────


def test_config_override_by_id() -> None:
    nodes = [_node("a", "pkg.main"), _node("b", "pkg.other")]
    config = {"entrypoints": {"ids": ["b"]}}
    result = detect_entrypoints(nodes, [], config=config)
    assert result == ["b"]


def test_config_override_ignores_missing_ids() -> None:
    nodes = [_node("a", "pkg.main")]
    config = {"entrypoints": {"ids": ["nonexistent"]}}
    # Falls through to heuristics since no valid id matched
    result = detect_entrypoints(nodes, [], config=config)
    assert result == ["a"]


# ── load_flowcode_config ───────────────────────────────────────────────────


def test_load_config_missing_file(tmp_path: Path) -> None:
    cfg = load_flowcode_config(tmp_path)
    assert cfg == {}


def test_load_config_reads_toml(tmp_path: Path) -> None:
    (tmp_path / ".flowcode.toml").write_text(
        '[entrypoints]\nids = ["py:fn:main"]\n', encoding="utf-8"
    )
    cfg = load_flowcode_config(tmp_path)
    assert cfg["entrypoints"]["ids"] == ["py:fn:main"]


def test_load_config_invalid_toml_returns_empty(tmp_path: Path) -> None:
    (tmp_path / ".flowcode.toml").write_text("not valid toml [[[", encoding="utf-8")
    cfg = load_flowcode_config(tmp_path)
    assert cfg == {}
