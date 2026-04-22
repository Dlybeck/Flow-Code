"""Ask DeepSeek to label every node in graph.json with a plain-English name + description.

Mirrors update_map.py's voice: non-technical, 1-2 short sentences each, no code jargon.
Batched for efficiency — one LLM call covers all nodes in the graph (reasonable for
the single-flow views the prototype produces, which are 30-200 functions).

Usage:  python label_graph.py [codebase-src-dir] [graph.json]

Requires DEEPSEEK_API_KEY in environment.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

from parse_calls import parse_directory

DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """You are labeling functions in a codebase for a visual map meant for non-technical reviewers.

For each function you're given, produce:
- displayName: a short plain-English phrase (3-6 words) that says WHAT the function does in everyday language. Title case. Not a class name, not code syntax.
- description: 1-2 short sentences explaining the function's purpose in plain English. No jargon. Say it like you'd say it to a product manager.

Voice rules:
- No code: no mentions of HTTP, JSON, FastAPI, decorators, async, etc. Describe effects, not implementation.
- Concrete: "Turns a web address into a request you can send" beats "Builds a URL object".
- No filler: skip "This function…", just say what it does.

Return STRICT JSON of the form:
{
  "labels": {
    "<qname>": {"displayName": "...", "description": "..."},
    ...
  }
}

Every qname in the input must have an entry in the output.
"""


def _strip_fences(s: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    return m.group(1).strip() if m else s.strip()


def call_llm(user: str) -> dict:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=240.0) as c:
        r = c.post(f"{DEEPSEEK_BASE}/v1/chat/completions", headers=headers, json=body)
        if r.status_code == 400:
            body.pop("response_format", None)
            r = c.post(f"{DEEPSEEK_BASE}/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    return json.loads(_strip_fences(data["choices"][0]["message"]["content"]))


def build_user_message(functions: dict, graph_nodes: list[dict]) -> str:
    qnames = [n["qname"] for n in graph_nodes]
    lines = ["Functions to label (qname + source):", ""]
    for q in qnames:
        info = functions.get(q)
        if not info:
            continue
        src = info.source
        if len(src) > 1500:
            src = src[:1500] + "\n# ... (truncated)"
        lines.append(f"## {q}")
        lines.append("```python")
        lines.append(src)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def label_subset(graph_path: Path, source_root: Path, qnames: list[str]) -> dict:
    """Label a specific subset of nodes. Reads graph.json, runs one LLM call
    for the requested qnames, writes the labels back into graph.json, and
    returns {elapsed_ms, labeled: [{ref, displayName, description}]}.

    Shared between the CLI (`label_graph.py`) and the sidecar `/api/label`
    endpoint so both paths produce identical labels with the same prompt.
    """
    import time
    functions = parse_directory(source_root)
    graph = json.loads(graph_path.read_text())
    nodes = graph["nodes"]
    qname_set = {q for q in qnames}
    subset = [n for n in nodes if n["qname"] in qname_set]
    if not subset:
        return {"elapsed_ms": 0, "labeled": []}

    user_msg = build_user_message(functions, subset)
    t0 = time.perf_counter()
    resp = call_llm(user_msg)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    labels = resp.get("labels", {})
    labeled = []
    for n in nodes:
        lbl = labels.get(n["qname"])
        if not lbl:
            continue
        display_name = lbl.get("displayName") or n["qname"].split(".")[-1]
        description = lbl.get("description") or n.get("description", "")
        n["displayName"] = display_name
        n["description"] = description
        labeled.append({"ref": n["qname"], "displayName": display_name, "description": description})

    graph_path.write_text(json.dumps(graph))
    return {"elapsed_ms": elapsed_ms, "labeled": labeled}


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "httpie-src/httpie")
    graph_path = Path(sys.argv[2] if len(sys.argv) > 2 else "graph.json")

    print(f"Parsing {root}...")
    graph = json.loads(graph_path.read_text())
    qnames = [n["qname"] for n in graph["nodes"]]
    print(f"  {len(qnames)} nodes to label")
    approx_tokens = len(build_user_message(parse_directory(root), graph["nodes"])) // 4
    print(f"  ~{approx_tokens} tokens in prompt, calling DeepSeek...", flush=True)

    result = label_subset(graph_path, root, qnames)
    print(f"  labeled {len(result['labeled'])} functions in {result['elapsed_ms']} ms")


if __name__ == "__main__":
    main()
