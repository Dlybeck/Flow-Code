"""Attach an authored source tour only when its stops and links exist in the map.

Descriptions explain selected functions; they never affect vectors or geometry.
This is a path through static source evidence, not a recorded runtime trace.
"""

from __future__ import annotations


def attach_guide(snapshot, guide):
    nodes = snapshot["views"]["feature"]["nodes"]
    edges = snapshot["views"]["feature"]["edges"]
    stops = []
    for step in guide["stops"]:
        matches = [n for n in nodes if step["symbol"] in (n["id"], n["qname"])]
        if len(matches) != 1:
            raise ValueError(
                f"Tour stop must identify one featured function: {step['symbol']}"
            )
        node = matches[0]
        if any(stop["node"] == node["id"] for stop in stops):
            raise ValueError("Tour stops must be distinct")
        stop = {"node": node["id"], "title": step["title"], "summary": step["summary"]}
        if stops:
            links = [
                e
                for e in edges
                if e["from"] == stops[-1]["node"]
                and e["to"] == node["id"]
                and e["confidence"] in ("resolved", "heuristic")
            ]
            if not links:
                raise ValueError(
                    f"No source-supported tour connection to {step['symbol']}"
                )
            # Prefer direct static resolution when several source sites match.
            edge = min(
                links, key=lambda e: (e["confidence"] != "resolved", str(e["id"]))
            )
            stop["via"] = {
                "edge": edge["id"],
                "confidence": edge["confidence"],
                "relation": edge.get("relation", edge["kind"]),
            }
        stops.append(stop)
    if not stops or stops[0]["node"] not in snapshot["entries"]:
        raise ValueError("A source tour must start at a featured entry")
    if any(
        not text.strip()
        for text in [
            guide["title"],
            guide["summary"],
            *(s[k] for s in stops for k in ("title", "summary")),
        ]
    ):
        raise ValueError("Source tour descriptions cannot be empty")
    return dict(
        snapshot,
        guide={
            "title": guide["title"],
            "summary": guide["summary"],
            "kind": "authored_source_tour",
            "stops": stops,
        },
    )
