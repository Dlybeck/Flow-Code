"""Developer-only harness: simulates what a real MCP client would see when
calling the Flow-Code tools. Not shipped, not registered in MCP.

Usage:
  .venv/bin/python sidecar/_harness.py pin <qname>
  .venv/bin/python sidecar/_harness.py exercise1       # describe pinned
  .venv/bin/python sidecar/_harness.py exercise2       # neighbors
  .venv/bin/python sidecar/_harness.py exercise3       # walk to entry
  .venv/bin/python sidecar/_harness.py all <qname>     # pin + run all three
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from mcp_server import (  # noqa: E402
    get_selection,
    get_node,
    get_neighbors,
    get_source,
    get_ancestors,
    get_descendants,
    search,
    _edge_index,
    _node_index,
)

SEL = Path("/tmp/flowcode-selection.json")


def _call(tool, *args):
    fn = getattr(tool, "fn", tool)
    return fn(*args)


def pin(qname: str) -> None:
    SEL.write_text(json.dumps({"id": qname}))
    print(f"[pinned] {qname}")


def exercise1() -> None:
    print("=== Ex1: describe pinned ===")
    sel = _call(get_selection)
    print("get_selection ->", json.dumps(sel, indent=2))
    if not sel:
        print("(nothing pinned)")
        return
    src = _call(get_source, sel["qname"])
    if not src:
        print(f"get_source('{sel['qname']}') -> None")
        return
    body = src["body"]
    print(f"get_source('{sel['qname']}') -> {len(body)} bytes at {src['abs_file']}:{src['line_start']}-{src['line_end']}")
    print("--- first 400 chars ---")
    print(body[:400])
    print("--- last 200 chars ---")
    print(body[-200:])


def exercise2() -> None:
    print("=== Ex2: neighbors ===")
    sel = _call(get_selection)
    if not sel:
        print("(nothing pinned)")
        return
    n = _call(get_neighbors, sel["qname"])
    print("get_neighbors ->", json.dumps(n, indent=2))
    # Neighbors now come back with summaries, so no follow-up get_node needed.
    print(f"  -> no follow-up get_node calls needed: summaries inline")


def exercise3() -> None:
    print("=== Ex3: walk up to entry (via get_ancestors) ===")
    sel = _call(get_selection)
    if not sel:
        print("(nothing pinned)")
        return
    anc = _call(get_ancestors, sel["qname"])
    print(f"get_ancestors('{sel['qname']}') -> {len(anc)} nodes")
    for a in anc:
        print(f"  hop {a['hops']}: {a['qname']} ({a['file']}, depth {a['depth']})")
    print("  tools_called: 2 (get_selection + get_ancestors)")


def exercise4() -> None:
    print("=== Ex4: downstream blast (get_descendants) ===")
    sel = _call(get_selection)
    if not sel:
        print("(nothing pinned)")
        return
    desc = _call(get_descendants, sel["qname"], 2)
    print(f"get_descendants('{sel['qname']}', 2) -> {len(desc)} nodes")
    for d in desc[:15]:
        print(f"  hop {d['hops']}: {d['qname']} ({d['file']})")


def exercise5(query: str) -> None:
    print(f"=== Ex5: search '{query}' ===")
    hits = _call(search, query, 5)
    for h in hits:
        print(f"  {h['qname']} ({h['file']}, depth {h['depth']})")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    if cmd == "pin":
        pin(args[1])
    elif cmd == "exercise1":
        exercise1()
    elif cmd == "exercise2":
        exercise2()
    elif cmd == "exercise3":
        exercise3()
    elif cmd == "exercise4":
        exercise4()
    elif cmd == "search":
        exercise5(args[1])
    elif cmd == "all":
        pin(args[1])
        exercise1()
        print()
        exercise2()
        print()
        exercise3()
        print()
        exercise4()
    else:
        print(f"unknown cmd: {cmd}")
        sys.exit(1)
