from __future__ import annotations

from pathlib import Path

from flowcode.index import index_repo


def test_index_golden_schema(golden_repo: Path) -> None:
    doc = index_repo(golden_repo)
    assert doc["schema_version"] == 0
    assert doc["indexer"] == "flowcode.ast_v0"
    paths = {f["path"] for f in doc["files"]}
    assert "src/golden_app/core.py" in paths
    assert "src/golden_app/app.py" in paths
    sym_q = {s["qualified_name"] for s in doc["symbols"]}
    assert "golden_app.core.greeting_for" in sym_q
    assert "golden_app.app.create_app" in sym_q


def test_nested_route_function_symbol(golden_repo: Path) -> None:
    doc = index_repo(golden_repo)
    inner = [s for s in doc["symbols"] if "health" in s["name"] and "create_app" in s["qualified_name"]]
    assert inner, "expected nested handler under create_app"


def test_import_edges(golden_repo: Path) -> None:
    doc = index_repo(golden_repo)
    imports = [e for e in doc["edges"] if e["kind"] == "import_from"]
    modules = {e["module"] for e in imports if e.get("module")}
    assert "fastapi" in modules or any("fastapi" in str(e) for e in imports)
