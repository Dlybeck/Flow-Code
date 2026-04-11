"""MCP server exposing the execution graph to AI coding agents (e.g. OpenCode)."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from raw_indexer.update_map import _read_excerpt

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP("execution-graph")


# ─── Path helpers ─────────────────────────────────────────────────────────────


def _public_dir() -> Path:
    env = os.environ.get("BRAINSTORM_PUBLIC_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise RuntimeError(f"BRAINSTORM_PUBLIC_DIR is not a directory: {p}")
        return p
    cwd_pub = Path.cwd() / "poc-brainstorm-ui" / "public"
    if cwd_pub.is_dir():
        return cwd_pub.resolve()
    raise RuntimeError(
        "Set BRAINSTORM_PUBLIC_DIR to poc-brainstorm-ui/public (or run from repo root)."
    )


def _golden_repo() -> Path:
    env = os.environ.get("BRAINSTORM_GOLDEN_REPO", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not p.is_dir():
            raise RuntimeError(f"BRAINSTORM_GOLDEN_REPO is not a directory: {p}")
        return p
    raise RuntimeError(
        "Set BRAINSTORM_GOLDEN_REPO to the repo root to index (e.g. fixtures/golden-fastapi)."
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[return-value]


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_brief() -> dict[str, Any]:
    """
    Return the current work session brief and anchored node details (including source code).
    Call this first to understand what the user wants changed.
    """
    path = _public_dir() / "work_session.json"
    doc = _load_json(path)
    if not doc:
        return {"brief": "", "anchored_nodes": []}

    pub = _public_dir()
    flow = _load_json(pub / "flow.json")
    overlay = _load_json(pub / "overlay.json")
    node_by_id: dict[str, dict[str, Any]] = {
        n.get("id", ""): n for n in flow.get("nodes", []) if n.get("id")
    }

    anchored_nodes: list[dict[str, Any]] = []
    for nid in doc.get("node_ids", []):
        node = node_by_id.get(nid, {})
        loc = node.get("location") or {}
        raw_symbol_id = node.get("raw_symbol_id", "")
        ov_entry: dict[str, Any] = (
            overlay.get("by_flow_node_id", {}).get(nid)
            or overlay.get("by_symbol_id", {}).get(raw_symbol_id)
            or {}
        )
        source = ""
        if loc.get("path"):
            try:
                repo = _golden_repo()
                start = loc.get("start_line") or 1
                end = loc.get("end_line") or start
                source = _read_excerpt(repo, loc["path"], start, end)
            except RuntimeError:
                pass
        anchored_nodes.append({
            "id": nid,
            "label": node.get("label", ""),
            "kind": node.get("kind", ""),
            "location": loc,
            "description": ov_entry.get("userDescription", ""),
            "source": source,
        })

    return {
        "brief": doc.get("brief", ""),
        "anchored_nodes": anchored_nodes,
    }


@mcp.tool()
def get_node(node_id: str) -> dict[str, Any]:
    """
    Return details for a single execution-graph node: label, kind, location,
    overlay description, and a source-code excerpt.
    """
    pub = _public_dir()
    flow = _load_json(pub / "flow.json")
    overlay = _load_json(pub / "overlay.json")

    node: dict[str, Any] = {}
    for n in flow.get("nodes", []):
        if n.get("id") == node_id:
            node = n
            break
    if not node:
        return {"error": f"Node {node_id!r} not found in flow.json"}

    loc = node.get("location") or {}

    # Overlay lookup: by_flow_node_id first, then by_symbol_id
    raw_symbol_id = node.get("raw_symbol_id", "")
    ov_entry: dict[str, Any] = (
        overlay.get("by_flow_node_id", {}).get(node_id)
        or overlay.get("by_symbol_id", {}).get(raw_symbol_id)
        or {}
    )

    # Source excerpt
    source = ""
    if loc.get("path"):
        try:
            repo = _golden_repo()
            start = loc.get("start_line") or 1
            end = loc.get("end_line") or start
            source = _read_excerpt(repo, loc["path"], start, end)
        except RuntimeError:
            pass

    return {
        "id": node_id,
        "label": node.get("label", ""),
        "kind": node.get("kind", ""),
        "location": loc,
        "description": ov_entry.get("userDescription", ""),
        "display_name": ov_entry.get("displayName", ""),
        "source": source,
    }


@mcp.tool()
def get_neighbors(node_id: str) -> dict[str, Any]:
    """
    Return callers (nodes that call this node) and callees (nodes this node calls).
    Each entry includes id, label, location, edge_kind, and confidence.
    """
    pub = _public_dir()
    flow = _load_json(pub / "flow.json")

    node_by_id: dict[str, dict[str, Any]] = {
        n.get("id", ""): n for n in flow.get("nodes", []) if n.get("id")
    }

    callers: list[dict[str, Any]] = []
    callees: list[dict[str, Any]] = []

    for edge in flow.get("edges", []):
        edge_kind = edge.get("kind", "")
        if edge_kind not in ("calls", "contains"):
            continue
        src = edge.get("from", "")
        dst = edge.get("to", "")
        conf = edge.get("confidence", 1.0)

        if dst == node_id and src in node_by_id:
            n = node_by_id[src]
            callers.append({
                "id": src,
                "label": n.get("label", ""),
                "location": n.get("location") or {},
                "edge_kind": edge_kind,
                "confidence": conf,
            })
        if src == node_id and dst in node_by_id:
            n = node_by_id[dst]
            callees.append({
                "id": dst,
                "label": n.get("label", ""),
                "location": n.get("location") or {},
                "edge_kind": edge_kind,
                "confidence": conf,
            })

    return {"callers": callers, "callees": callees}


@mcp.tool()
def get_source(path: str, start_line: int, end_line: int) -> dict[str, Any]:
    """
    Return source code from the project repository for a given file path and line range.
    Path must be relative to the repo root and must not contain '..'.
    """
    if ".." in path:
        return {"error": "Path must not contain '..'"}
    try:
        repo = _golden_repo()
    except RuntimeError as exc:
        return {"error": str(exc)}
    content = _read_excerpt(repo, path, start_line, end_line)
    return {"path": path, "content": content}


@mcp.tool()
def get_entry_points() -> list[dict[str, Any]]:
    """
    Return the execution-graph entry points — the top-level nodes to start exploration from.
    """
    pub = _public_dir()
    flow = _load_json(pub / "flow.json")
    overlay = _load_json(pub / "overlay.json")

    node_by_id: dict[str, dict[str, Any]] = {
        n.get("id", ""): n for n in flow.get("nodes", []) if n.get("id")
    }

    result: list[dict[str, Any]] = []
    for ep in flow.get("entrypoints", []):
        nid = ep if isinstance(ep, str) else ep.get("id", "")
        node = node_by_id.get(nid, {})
        raw_symbol_id = node.get("raw_symbol_id", "")
        ov_entry: dict[str, Any] = (
            overlay.get("by_flow_node_id", {}).get(nid)
            or overlay.get("by_symbol_id", {}).get(raw_symbol_id)
            or {}
        )
        result.append({
            "id": nid,
            "label": node.get("label", ""),
            "location": node.get("location") or {},
            "description": ov_entry.get("userDescription", ""),
        })

    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
