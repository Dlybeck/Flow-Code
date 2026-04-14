"""Build a SYNTHETIC flow graph using an LLM to predict next steps from semantics.

For each function we visit, we show the LLM:
  - the function's source
  - ALL other functions as candidates (name + docstring only, no call info)
And ask: which candidate(s) are the most natural next step in execution?

The LLM never sees the static call graph. If the synthetic flow matches the
actual flow, the code "reads like it runs" — readable. Divergences are surprises.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

from parse_codebase import FuncInfo, parse_codebase

CONFIDENCE_THRESHOLD = 0.55
MAX_DEPTH = 10
MAX_BRANCHES_PER_NODE = 2

DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """You are analyzing a small Python codebase to predict what function naturally runs next in execution after a given function, based only on semantics (names, docstrings, source).

You return STRICT JSON of the form:
{
  "candidates": [
    {"name": "<function_name>", "confidence": 0.0-1.0, "reason": "<one short sentence>"}
  ]
}

Rules:
- Return at most 2 candidates.
- Only include candidates with confidence >= 0.4.
- If none of the candidates look like a natural next step (e.g. this function terminates), return an empty list.
- The "name" must be one of the candidate names given. Do not invent names.
"""


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def call_llm(system: str, user: str) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set. Export it and retry.")
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=60.0) as client:
        r = client.post(f"{DEEPSEEK_BASE}/v1/chat/completions", headers=headers, json=body)
        if r.status_code == 400:
            body.pop("response_format", None)
            r = client.post(f"{DEEPSEEK_BASE}/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return json.loads(_strip_fences(content))


def build_user_message(current: FuncInfo, candidates: list[FuncInfo]) -> str:
    lines = [f"Current function: {current.name}", "", "Source:", "```python", current.source, "```", ""]
    lines.append("Candidate next steps (other functions in this codebase):")
    for c in candidates:
        doc = c.docstring.strip().split("\n")[0] if c.docstring else "(no docstring)"
        lines.append(f"- {c.name}: {doc}")
    lines += [
        "",
        "Which 1–2 of these candidates is the most natural next step in execution "
        "after the current function runs? Use only the semantics you can read.",
    ]
    return "\n".join(lines)


def build_synthetic_flow(path: Path, entry: str) -> dict:
    functions = parse_codebase(path)
    if entry not in functions:
        raise SystemExit(f"entry point {entry!r} not found")

    nodes: list[str] = []
    edges: list[dict] = []
    visited: set[str] = set()

    def walk(name: str, depth: int) -> None:
        if name in visited or depth >= MAX_DEPTH:
            return
        visited.add(name)
        nodes.append(name)

        current = functions[name]
        candidates = [f for n, f in functions.items() if n != name]
        if not candidates:
            return

        user_msg = build_user_message(current, candidates)
        print(f"  [llm] predicting next after {name!r}...", flush=True)
        try:
            resp = call_llm(SYSTEM_PROMPT, user_msg)
        except Exception as e:
            print(f"  [llm] failed at {name!r}: {e}", flush=True)
            return

        picks = resp.get("candidates", [])[:MAX_BRANCHES_PER_NODE]
        for p in picks:
            cname = p.get("name")
            conf = float(p.get("confidence", 0.0))
            reason = p.get("reason", "")
            if cname not in functions or conf < CONFIDENCE_THRESHOLD:
                continue
            edges.append({"from": name, "to": cname, "confidence": conf, "reason": reason})
            walk(cname, depth + 1)

    walk(entry, 0)
    return {"entry": entry, "nodes": nodes, "edges": edges}


if __name__ == "__main__":
    codebase = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("test_codebase.py")
    entry = sys.argv[2] if len(sys.argv) > 2 else "handle_signup"
    result = build_synthetic_flow(codebase, entry)
    out = Path("synthetic_flow.json")
    out.write_text(json.dumps(result, indent=2))
    print(f"wrote {out} ({len(result['nodes'])} nodes, {len(result['edges'])} edges)")
