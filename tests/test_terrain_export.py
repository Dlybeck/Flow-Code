import json

from flowcode.cli import main


def test_export_is_repeatable_and_keeps_cycles_shared_calls_and_unknown_evidence(
    tmp_path,
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
