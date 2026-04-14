"""Ask DeepSeek to predict which functions would fire for a TinyDB session.

Candidates constrained to the 117 qnames we have embeddings for (no hallucinations).
Simulates the same driver session as trace_tinydb.py so the real vs predicted
comparison is apples-to-apples.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

from parse_multi import parse_directory

DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SESSION_DESCRIPTION = """A TinyDB session that does the following operations in order:
1. TinyDB(db_path)  — open a JSON file as a DB
2. db.insert({"name": "alice", "age": 30})
3. db.insert({"name": "bob", "age": 25})
4. db.insert_multiple([{"name": "carol", "age": 40}, {"name": "dave", "age": 22}])
5. db.search(Query().age > 26)
6. db.get(Query().name == "alice")
7. db.all()
8. db.contains(Query().name == "bob")
9. db.update({"age": 31}, Query().name == "alice")
10. db.remove(Query().name == "dave")
11. db.close()
"""

SYSTEM_PROMPT = """You are a Python expert familiar with TinyDB's internals. You are predicting
which internal functions/methods would fire during a given session.

Return STRICT JSON:
{
  "functions_expected_to_fire": [
    {"qname": "...", "approx_calls": <int>, "reason": "<short>"}
  ]
}

Rules:
- `qname` must be from the provided candidate list. Do not invent names.
- `approx_calls` is a rough estimate of how many times this function runs during the session.
- Include every candidate you believe fires at least once.
- Return only a JSON object.
"""


def _strip_fences(s: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    return m.group(1).strip() if m else s.strip()


def call_llm(user: str) -> dict:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY not set")
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=180.0) as c:
        r = c.post(f"{DEEPSEEK_BASE}/v1/chat/completions", headers=headers, json=body)
        if r.status_code == 400:
            body.pop("response_format", None)
            r = c.post(f"{DEEPSEEK_BASE}/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    return json.loads(_strip_fences(data["choices"][0]["message"]["content"]))


def build_user_message(functions: dict) -> str:
    lines = ["Candidate functions (qname: first-line docstring):", ""]
    for qname in sorted(functions.keys()):
        info = functions[qname]
        doc = info.docstring.strip().split("\n", 1)[0] if info.docstring else "(no docstring)"
        lines.append(f"- {qname}: {doc}")
    lines += ["", "Session:", SESSION_DESCRIPTION, "", "Which functions fire, and roughly how many times each?"]
    return "\n".join(lines)


def main() -> None:
    root = Path("tinydb-src/tinydb")
    functions = parse_directory(root)
    emb = json.loads(Path("function_embeddings.json").read_text())
    known = {f["qname"] for f in emb["functions"]}
    functions = {q: f for q, f in functions.items() if q in known}
    print(f"{len(functions)} candidate qnames")

    user_msg = build_user_message(functions)
    print("calling DeepSeek...", flush=True)
    resp = call_llm(user_msg)

    predicted = resp.get("functions_expected_to_fire", [])
    kept: list[dict] = []
    dropped: list[str] = []
    for item in predicted:
        q = item.get("qname")
        c = int(item.get("approx_calls", 0) or 0)
        if q in known and c > 0:
            kept.append({"qname": q, "approx_calls": c, "reason": item.get("reason", "")})
        else:
            dropped.append(q or "")

    visit_counts = {k["qname"]: k["approx_calls"] for k in kept}
    out = {
        "session": SESSION_DESCRIPTION,
        "predictions": kept,
        "visit_counts": visit_counts,
        "dropped_unknown": dropped,
    }
    Path("predicted_trace.json").write_text(json.dumps(out, indent=2))
    print(f"predicted {len(kept)} firing functions ({sum(visit_counts.values())} total calls)")
    if dropped:
        print(f"dropped {len(dropped)} unknown/invalid: {dropped[:5]}")


if __name__ == "__main__":
    main()
