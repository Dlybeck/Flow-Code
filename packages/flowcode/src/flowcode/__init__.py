"""flowcode — static analysis graph generation for Python and TypeScript codebases."""

from __future__ import annotations

from pathlib import Path
from typing import Any

__version__ = "0.1.0"


def generate_graph(
    repo_path: str | Path,
    *,
    src_roots: list[str] | None = None,
    include_overlay: bool = True,
    overlay_path: str | Path | None = None,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    """
    Index a repository and return its execution graph.

    Chains: index_repo_auto → build_execution_ir → generate_auto_overlay → merge.

    Args:
        repo_path: Path to the repository root.
        src_roots: Relative source roots (e.g. ["src"]). Auto-detected if None.
        include_overlay: If True (default), attach auto-generated use-case overlay.
        overlay_path: Optional path to an existing overlay.json to merge instead of
                      auto-generating one.
        use_llm: Passed to generate_auto_overlay. None = auto-detect via ANTHROPIC_API_KEY.

    Returns:
        dict with keys: schema_version, repo_root, languages, entrypoints,
        nodes, edges, and (if include_overlay) use_cases.
    """
    from flowcode.auto_overlay import generate_auto_overlay
    from flowcode.execution_ir import build_execution_ir
    from flowcode.language_adapter import index_repo_auto

    root = Path(repo_path).resolve()
    raw_doc = index_repo_auto(root, src_roots=src_roots)
    ir_doc = build_execution_ir(raw_doc)

    result: dict[str, Any] = {
        "schema_version": ir_doc["schema_version"],
        "repo_root": ir_doc["repo_root"],
        "languages": ir_doc["languages"],
        "entrypoints": ir_doc["entrypoints"],
        "nodes": ir_doc["nodes"],
        "edges": ir_doc["edges"],
    }

    if include_overlay:
        if overlay_path is not None:
            import json
            ov = json.loads(Path(overlay_path).read_text(encoding="utf-8"))
        else:
            ov = generate_auto_overlay(ir_doc, repo_root=root, use_llm=use_llm)
        result["use_cases"] = ov.get("by_flow_node_id", {})

    return result


__all__ = ["__version__", "generate_graph"]
