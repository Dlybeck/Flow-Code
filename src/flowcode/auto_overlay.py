"""Auto-generate overlay use cases from an execution IR document.

Steps:
  1. Group nodes by entrypoint reachability (pure graph — no LLM).
  2. Assign structural names from entrypoint labels (mechanical fallback).
  3. Optionally enrich with LLM names. Provider selection:
       - DEEPSEEK_API_KEY → DeepSeek (deepseek-chat, OpenAI-compatible)
       - ANTHROPIC_API_KEY → Anthropic (claude-haiku)
     DeepSeek is preferred if both are set.

Returns an overlay dict with `by_flow_node_id` populated, compatible with the
existing overlay schema (schema_version 0).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from flowcode.execution_ir.graph import reachable_node_ids

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _structural_name(entrypoint_label: str) -> str:
    """Derive a 2-4 word display name from an entrypoint label.

    Handles snake_case (load_numbers → Load Numbers), camelCase (loadNumbers →
    Load Numbers), PascalCase (LoadNumbers → Load Numbers), and acronyms
    (HTTPServer → HTTP Server).
    """
    leaf = entrypoint_label.rsplit(".", 1)[-1]
    with_spaces = leaf.replace("_", " ")
    split_camel = _CAMEL_BOUNDARY.sub(" ", with_spaces)
    return " ".join(w.capitalize() if w.islower() else w for w in split_camel.split())


def _group_nodes_by_entrypoint(
    entrypoints: list[str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Return {entrypoint_id: set_of_reachable_node_ids}."""
    groups: dict[str, set[str]] = {}
    for ep in entrypoints:
        groups[ep] = reachable_node_ids([ep], edges)
    return groups


def _build_prompt(entrypoint_label: str, reachable_labels: list[str]) -> str:
    return (
        f"You are naming a software use case.\n\n"
        f"Entrypoint function: {entrypoint_label}\n"
        f"Functions it calls: {', '.join(reachable_labels[:20])}\n\n"
        f"Respond with a JSON object with exactly two keys:\n"
        f'  "displayName": a 2-6 word title for this use case (title case)\n'
        f'  "userDescription": 2-4 sentences describing what this use case does for users\n\n'
        f"Respond with only the JSON object, no other text."
    )


def _parse_llm_json(text: str) -> dict[str, str] | None:
    """Parse LLM response text into {displayName, userDescription} or None."""
    text = text.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(result, dict):
        return None
    if "displayName" in result and "userDescription" in result:
        return {
            "displayName": str(result["displayName"]),
            "userDescription": str(result["userDescription"]),
        }
    return None


def _call_deepseek(
    entrypoint_label: str,
    reachable_labels: list[str],
    api_key: str,
) -> dict[str, str] | None:
    """Call DeepSeek chat completions (OpenAI-compatible) via stdlib urllib."""
    prompt = _build_prompt(entrypoint_label, reachable_labels)
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        return _parse_llm_json(text)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, OSError):
        return None


def _call_claude_haiku(
    entrypoint_label: str,
    reachable_labels: list[str],
    api_key: str,
) -> dict[str, str] | None:
    """Call Claude Haiku via Anthropic API using stdlib urllib."""
    prompt = _build_prompt(entrypoint_label, reachable_labels)
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = body["content"][0]["text"]
        return _parse_llm_json(text)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, OSError):
        return None


def _resolve_llm_provider() -> tuple[str, str] | None:
    """Return (provider_name, api_key) for the first available provider, or None."""
    ds = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if ds:
        return ("deepseek", ds)
    an = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if an:
        return ("anthropic", an)
    return None


def _call_llm(
    provider: str,
    api_key: str,
    entrypoint_label: str,
    reachable_labels: list[str],
) -> dict[str, str] | None:
    if provider == "deepseek":
        return _call_deepseek(entrypoint_label, reachable_labels, api_key)
    if provider == "anthropic":
        return _call_claude_haiku(entrypoint_label, reachable_labels, api_key)
    return None


def generate_auto_overlay(
    ir_doc: dict[str, Any],
    *,
    repo_root: Path | None = None,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    """
    Generate an overlay document from an execution IR.

    Args:
        ir_doc: Execution IR dict (output of build_execution_ir_from_raw / build_execution_ir).
        repo_root: Unused (reserved for future file-path enrichment).
        use_llm: If None, auto-detect via DEEPSEEK_API_KEY or ANTHROPIC_API_KEY env var.
                 If True, require LLM (raises if no key found).
                 If False, skip LLM entirely.

    Returns:
        Overlay dict with schema_version, by_flow_node_id, and optional by_symbol_id.
    """
    entrypoints = ir_doc.get("entrypoints") or []
    nodes = ir_doc.get("nodes") or []
    edges = ir_doc.get("edges") or []

    node_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in nodes if isinstance(n, dict)}

    groups = _group_nodes_by_entrypoint(entrypoints, nodes, edges)

    provider_info = _resolve_llm_provider()
    should_use_llm: bool
    if use_llm is True:
        if provider_info is None:
            raise ValueError("use_llm=True but neither DEEPSEEK_API_KEY nor ANTHROPIC_API_KEY is set")
        should_use_llm = True
    elif use_llm is False:
        should_use_llm = False
    else:
        should_use_llm = provider_info is not None

    by_flow_node_id: dict[str, dict[str, Any]] = {}

    for ep_id, reachable in groups.items():
        ep_node = node_by_id.get(ep_id)
        if not ep_node:
            continue
        ep_label = str(ep_node.get("label", ep_id))
        reachable_labels = [
            str(node_by_id[nid]["label"])
            for nid in sorted(reachable)
            if nid in node_by_id and nid != ep_id
        ]

        entry: dict[str, Any] = {
            "displayName": _structural_name(ep_label),
            "use_case": True,
            "reachable_node_count": len(reachable),
        }

        if should_use_llm and provider_info is not None:
            provider, api_key = provider_info
            llm_result = _call_llm(provider, api_key, ep_label, reachable_labels)
            if llm_result:
                entry["displayName"] = llm_result["displayName"]
                entry["userDescription"] = llm_result["userDescription"]
                entry["llm_provider"] = provider

        by_flow_node_id[ep_id] = entry

        # Tag reachable non-entrypoint nodes as part of this use case
        for nid in reachable:
            if nid == ep_id or nid in entrypoints:
                continue
            if nid not in by_flow_node_id:
                n = node_by_id.get(nid)
                if n:
                    by_flow_node_id[nid] = {
                        "displayName": _structural_name(str(n.get("label", nid))),
                    }

    return {
        "schema_version": 0,
        "by_flow_node_id": by_flow_node_id,
        "by_symbol_id": {},
        "by_file_id": {},
        "by_directory_id": {},
    }
