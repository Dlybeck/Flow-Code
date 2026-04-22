"""Label every node in graph.json with a plain-English name + description.

Runs at build time (called from build_graph.py) so the viz loads with labels
already populated — no runtime LLM calls, no user friction. Pluggable
backend so the user can pick whichever LLM they have a key for, with a
subprocess fallback for users who have `claude` / `opencode` on PATH.

## Backend selection

Explicit override: `FLOWCODE_LABELER=<name>` where name ∈
{anthropic, deepseek, openai, ollama, claude-cli, opencode-cli, noop}.

Otherwise auto-detect:
  1. ANTHROPIC_API_KEY set → anthropic (default model: claude-haiku-4-5)
  2. DEEPSEEK_API_KEY set → deepseek
  3. OPENAI_API_KEY set → openai
  4. `ollama` responds on http://127.0.0.1:11434 → ollama (default qwen2.5-coder:7b)
  5. `claude` on PATH → claude-cli (uses user's Claude Code subscription via `claude -p`)
  6. `opencode` on PATH → opencode-cli
  7. Fall back to noop (skip labeling, log a warning).

## Usage

  python label_graph.py [source-root] [graph.json]

Or, more commonly, call `label_all(graph_path, source_root)` from build_graph.py.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from parse_calls import parse_directory

# ------------ Prompt (shared across every backend) ------------

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

BATCH_SIZE = 40          # functions per LLM call
PARALLEL = 4             # simultaneous LLM calls
HTTP_TIMEOUT = 180.0


# ------------ Helpers ------------

def _strip_fences(s: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    return m.group(1).strip() if m else s.strip()


def _source_hash(src: str) -> str:
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:16]


def _build_user_message(batch: list[tuple[str, str]]) -> str:
    """batch is a list of (qname, source)."""
    lines = ["Functions to label (qname + source):", ""]
    for qname, src in batch:
        if len(src) > 1500:
            src = src[:1500] + "\n# ... (truncated)"
        lines.append(f"## {qname}")
        lines.append("```python")
        lines.append(src)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


# ------------ Backend interface ------------

@dataclass
class Backend:
    name: str
    model: str
    call: Callable[[str], dict]  # user message → {"labels": {qname: {displayName, description}}}

    def label_batch(self, batch: list[tuple[str, str]]) -> dict:
        msg = _build_user_message(batch)
        return self.call(msg)


# ------------ Anthropic (Claude Haiku default) ------------

def _anthropic_call_factory(model: str) -> Callable[[str], dict]:
    key = os.environ["ANTHROPIC_API_KEY"].strip()
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

    def call(user: str) -> dict:
        body = {
            "model": model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=HTTP_TIMEOUT) as c:
            r = c.post(f"{base}/v1/messages", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        text = data["content"][0]["text"]
        return json.loads(_strip_fences(text))

    return call


# ------------ DeepSeek / OpenAI-compatible ------------

def _openai_compatible_call_factory(base_url: str, model: str, key: str, use_response_format: bool) -> Callable[[str], dict]:
    def call(user: str) -> dict:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
        if use_response_format:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=HTTP_TIMEOUT) as c:
            r = c.post(f"{base_url.rstrip('/')}/v1/chat/completions", headers=headers, json=body)
            if r.status_code == 400 and use_response_format:
                body.pop("response_format", None)
                r = c.post(f"{base_url.rstrip('/')}/v1/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        return json.loads(_strip_fences(data["choices"][0]["message"]["content"]))

    return call


# ------------ Ollama (local, OpenAI-compatible at /v1) ------------

def _ollama_reachable() -> bool:
    try:
        base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        with httpx.Client(timeout=1.0) as c:
            return c.get(f"{base}/api/tags").status_code == 200
    except Exception:
        return False


# ------------ Subprocess CLI (Claude Code / OpenCode) ------------

def _subprocess_call_factory(argv_template: list[str]) -> Callable[[str], dict]:
    """argv_template has a '{prompt}' placeholder slot. stdin is used instead,
    so the prompt is piped not injected."""
    def call(user: str) -> dict:
        full_prompt = SYSTEM_PROMPT + "\n\n" + user + "\n\nReturn JSON only."
        proc = subprocess.run(
            argv_template,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=HTTP_TIMEOUT,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"{argv_template[0]} exited {proc.returncode}: {proc.stderr[:200]}")
        out = proc.stdout.strip()
        # CLIs may wrap output in fences, prose preamble, etc. Find the JSON.
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            raise RuntimeError(f"no JSON in {argv_template[0]} output: {out[:200]}")
        return json.loads(m.group(0))

    return call


# ------------ Resolver ------------

def _select_backend() -> Backend | None:
    override = os.environ.get("FLOWCODE_LABELER", "").strip().lower()

    def _anthropic():
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
        return Backend("anthropic", model, _anthropic_call_factory(model))

    def _deepseek():
        key = os.environ["DEEPSEEK_API_KEY"].strip()
        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        return Backend("deepseek", model, _openai_compatible_call_factory(base, model, key, True))

    def _openai():
        key = os.environ["OPENAI_API_KEY"].strip()
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return Backend("openai", model, _openai_compatible_call_factory(base, model, key, True))

    def _ollama():
        base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
        return Backend("ollama", model, _openai_compatible_call_factory(base, model, "ollama", False))

    def _claude_cli():
        return Backend(
            "claude-cli",
            os.environ.get("CLAUDE_MODEL", "haiku"),
            _subprocess_call_factory(["claude", "-p", "--output-format", "json", "--model", os.environ.get("CLAUDE_MODEL", "haiku")]),
        )

    def _opencode_cli():
        return Backend("opencode-cli", "default", _subprocess_call_factory(["opencode", "run"]))

    registry = {
        "anthropic": _anthropic,
        "deepseek": _deepseek,
        "openai": _openai,
        "ollama": _ollama,
        "claude-cli": _claude_cli,
        "opencode-cli": _opencode_cli,
    }

    if override:
        if override == "noop":
            return None
        if override not in registry:
            raise SystemExit(f"Unknown FLOWCODE_LABELER: {override}. Options: {sorted(registry)}")
        return registry[override]()

    # Auto-detect in preference order.
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return _anthropic()
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return _deepseek()
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return _openai()
    if _ollama_reachable():
        return _ollama()
    if shutil.which("claude"):
        return _claude_cli()
    if shutil.which("opencode"):
        return _opencode_cli()
    return None


# ------------ Main labeling entrypoint ------------

def _ordered_work(graph: dict, functions: dict, needs_label: Callable[[dict], bool]) -> list[tuple[str, str]]:
    """Order nodes branch-by-branch starting at the primary-tree root(s).

    Goal: peak first, then each subtree in one contiguous batch so the LLM
    sees a whole branch together. BFS within a subtree so direct descendants
    come before grandchildren — that matters when a batch wraps and the
    first batch carries the most important context.
    """
    id_to_qname = {n["id"]: n["qname"] for n in graph["nodes"]}
    children: dict[str, list[str]] = {}
    has_primary_parent: set[str] = set()
    for e in graph.get("edges", []):
        if not e.get("is_primary"):
            continue
        children.setdefault(e["from"], []).append(e["to"])
        has_primary_parent.add(e["to"])
    roots = [n["id"] for n in graph["nodes"] if n["id"] not in has_primary_parent and not n.get("is_orphan")]
    # If `graph["peaks"]` is explicit, prefer those as the starting set.
    peaks = [p for p in (graph.get("peaks") or []) if p in id_to_qname]
    roots = peaks + [r for r in roots if r not in set(peaks)]

    order: list[str] = []
    seen: set[str] = set()
    for r in roots:
        if r in seen:
            continue
        # BFS this subtree
        queue = [r]
        while queue:
            cur = queue.pop(0)
            if cur in seen:
                continue
            seen.add(cur)
            order.append(cur)
            queue.extend(children.get(cur, []))
    # Orphans last (separate callers)
    for n in graph["nodes"]:
        if n["id"] not in seen:
            order.append(n["id"])
            seen.add(n["id"])

    work: list[tuple[str, str]] = []
    for nid in order:
        qname = id_to_qname.get(nid)
        n = next((x for x in graph["nodes"] if x["id"] == nid), None)
        if not n or not qname:
            continue
        info = functions.get(qname)
        if not info:
            continue
        if needs_label(n):
            work.append((qname, info.source))
    return work


def label_all(graph_path: Path, source_root: Path, force: bool = False) -> dict:
    """Label every node in graph.json that needs labeling.

    Branch-ordered traversal (peak first, then each subtree contiguous).
    Incremental: if a node already has displayName AND source_hash matches
    the current source, skip it. Pass force=True to relabel everything.

    Returns {backend, model, labeled: int, skipped: int, elapsed_ms: int,
             errors: [{qname, error}]}.
    """
    backend = _select_backend()
    graph = json.loads(graph_path.read_text())
    nodes = graph["nodes"]

    if backend is None:
        print("[label] no labeling backend available (no API key, no Ollama, no CLI on PATH) — skipping")
        return {"backend": None, "model": None, "labeled": 0, "skipped": len(nodes), "elapsed_ms": 0, "errors": []}

    functions = parse_directory(source_root)

    def needs_label(n: dict) -> bool:
        qname = n["qname"]
        info = functions.get(qname)
        if not info:
            return False
        if force:
            return True
        has_label = bool(n.get("displayName")) and bool(n.get("description"))
        same_hash = n.get("source_hash") == _source_hash(info.source)
        return not (has_label and same_hash)

    work = _ordered_work(graph, functions, needs_label)

    skipped = len(nodes) - len(work)
    if not work:
        print(f"[label] all {len(nodes)} nodes already labeled with current source — nothing to do")
        return {"backend": backend.name, "model": backend.model, "labeled": 0, "skipped": skipped, "elapsed_ms": 0, "errors": []}

    print(f"[label] {backend.name} ({backend.model}) — labeling {len(work)} function{'s' if len(work) != 1 else ''} branch-by-branch ({skipped} cached)")
    t0 = time.perf_counter()
    # Chunk into batches. Order is preserved so batch 1 is the top of the tree.
    batches = [work[i:i + BATCH_SIZE] for i in range(0, len(work), BATCH_SIZE)]
    all_labels: dict[str, dict] = {}
    errors: list[dict] = []

    def _run_batch(b: list[tuple[str, str]]) -> tuple[dict, list[dict]]:
        try:
            resp = backend.label_batch(b)
            return resp.get("labels", {}), []
        except Exception as e:
            return {}, [{"qname": q, "error": str(e)[:180]} for q, _ in b]

    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        futs = {ex.submit(_run_batch, b): i for i, b in enumerate(batches)}
        done = 0
        for f in concurrent.futures.as_completed(futs):
            labels, errs = f.result()
            all_labels.update(labels)
            errors.extend(errs)
            done += 1
            print(f"[label]   batch {done}/{len(batches)} done ({len(labels)} labels, {len(errs)} errors)", flush=True)

    # Merge back. Update source_hash so incremental works on re-run.
    labeled = 0
    src_by_qname = dict(work)
    for n in nodes:
        qn = n["qname"]
        lbl = all_labels.get(qn)
        if not lbl:
            continue
        disp = (lbl.get("displayName") or "").strip()
        desc = (lbl.get("description") or "").strip()
        if not disp:
            continue
        n["displayName"] = disp
        n["description"] = desc
        if qn in src_by_qname:
            n["source_hash"] = _source_hash(src_by_qname[qn])
        labeled += 1

    graph_path.write_text(json.dumps(graph))
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    print(f"[label] done: {labeled} labeled, {skipped} cached, {len(errors)} errors in {elapsed_ms / 1000:.1f}s")
    if errors[:3]:
        for e in errors[:3]:
            print(f"[label]   error: {e['qname']} — {e['error']}")
    return {"backend": backend.name, "model": backend.model, "labeled": labeled, "skipped": skipped, "elapsed_ms": elapsed_ms, "errors": errors}


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "httpie-src/httpie")
    graph_path = Path(sys.argv[2] if len(sys.argv) > 2 else "graph.json")
    force = "--force" in sys.argv
    label_all(graph_path, root, force=force)


if __name__ == "__main__":
    main()
