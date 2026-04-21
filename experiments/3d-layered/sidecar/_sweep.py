"""Run the core tool suite against every node in the graph. Any crash,
inconsistency, or surprise gets reported. Serves as a regression sweep
for the MCP surface."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from mcp_server import (  # noqa: E402
    get_selection, get_node, get_neighbors, get_source,
    get_ancestors, get_descendants, list_nodes, grep_source,
)


def _c(t, *a, **k):
    return getattr(t, "fn", t)(*a, **k)


def main() -> int:
    nodes = _c(list_nodes)
    problems: list[str] = []
    stats = {
        "missing_source": 0,
        "missing_abs_file": 0,
        "empty_description": 0,
        "no_callers_non_entry": 0,
    }

    for n in nodes:
        qn = n["qname"]

        # 1. Every node must resolve via get_node
        full = _c(get_node, qn)
        if not full:
            problems.append(f"{qn}: get_node returned None")
            continue

        # 2. abs_file should exist on disk
        if not os.path.exists(full["abs_file"]):
            stats["missing_abs_file"] += 1
            problems.append(f"{qn}: abs_file does not exist: {full['abs_file']}")

        # 3. get_source should succeed + carry line info
        src = _c(get_source, qn)
        if src is None:
            stats["missing_source"] += 1
        elif src["line_start"] <= 0 or src["line_end"] <= 0:
            problems.append(f"{qn}: source has no line range")

        # 4. Description presence
        if not full.get("description"):
            stats["empty_description"] += 1

        # 5. Neighbors shape correctness (now returns None for unknown ref,
        # dict for known). Since qn is from list_nodes, it's known — expect dict.
        nb = _c(get_neighbors, qn)
        assert nb is not None, f"{qn}: get_neighbors returned None for known ref"
        assert "callers" in nb and "callees" in nb, f"{qn}: neighbors shape"
        for side in ("callers", "callees"):
            for x in nb[side]:
                assert "qname" in x and "file" in x, f"{qn}: neighbor missing keys"

        # 6. Ancestors - for non-entry, should have at least 1
        if full["depth"] > 0:
            anc = _c(get_ancestors, qn)
            if not anc:
                stats["no_callers_non_entry"] += 1
                problems.append(f"{qn}: non-entry (depth {full['depth']}) but 0 ancestors")

        # 7. Descendants shape (None = unknown, list = known)
        desc = _c(get_descendants, qn, 3)
        assert isinstance(desc, list), f"{qn}: descendants not list (got {type(desc).__name__})"

    # 8. Setting selection to every node in turn
    for n in nodes:
        Path("/tmp/flowcode-selection.json").write_text(json.dumps({"id": n["id"]}))
        sel = _c(get_selection)
        assert sel and sel["qname"] == n["qname"], f"selection mismatch for {n['qname']}"

    print(f"swept {len(nodes)} nodes")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if problems:
        print(f"problems: {len(problems)}")
        for p in problems[:20]:
            print(f"  - {p}")
        return 1
    print("no problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
