"""
Update map — AI fills overlay displayName / userDescription (product-language copy).

Uses DeepSeek's OpenAI-compatible API. Configure with env (see repo .env.example).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from raw_indexer.bundle import merge_overlay_delta
from raw_indexer.overlay import (
    ROOT_OVERLAY_ID,
    load_overlay,
    overlay_orphan_directory_keys,
    overlay_orphan_file_keys,
    overlay_orphan_flow_keys,
    overlay_orphan_keys,
    overlay_orphan_root_keys,
    valid_directory_ids,
)

DEFAULT_DEEPSEEK_BASE = "https://api.deepseek.com"
# deepseek-chat tracks DeepSeek-V3.2 (non-thinking) per DeepSeek API docs.
DEFAULT_MODEL = "deepseek-chat"

# Shared voice: exec briefing for someone who does not build software.
_OVERLAY_DESC_RULES = """Voice (every node type):

Audience: executives and PMs. They do not know frameworks, HTTP verbs, or repo layout. Write like a 30-second spoken brief, not docs.

userDescription:
- Exactly 2–4 short sentences. Each sentence should be plain enough to read aloud to a non-technical board member.
- Say what changes for a person or for the business: outcomes, safeguards, handoffs ("names go in, friendly hellos come out"). Never narrate the code structure.
- Do not name or imply stack or transport unless unavoidable in one plain phrase. Banned in userDescription (and avoid in displayName): HTTP, GET, POST, REST, endpoint, route, URL path, /…, FastAPI, Flask, Django, middleware, JSON (as format), status code, factory, wiring, module, package init, dependency, deployment, metadata, version string, "pure logic", "layer", "processor", initializes, defines, establishes, configures, implements, returns, invokes, registers, "request-response".
- Forbidden openers: "This file", "This folder", "The application", "This component", "This function", "This class", "Here", "Contains", "Responsible for", "Used to", "When called".
- displayName: 2–6 words, human phrase (e.g. "Friendly hello by name", "Quick health pulse"). Not job titles from engineering ("Factory", "Entry point", "Processor", "Core").

Good (tone only): "Someone gives a name and gets a short welcome line back." / "Offers a quick yes/no on whether the live service is responding." / "Keeps the runnable demo app in one place."
Bad (never): "GET /greet/{name}…", "FastAPI application factory", "request-response cycle", "defines package metadata"."""

# Flow-only: describe **what the grouped calls are**, not how the canvas is drawn (no dashed/solid
# lectures—that belongs in the app UI, not overlay blurbs).
_FLOW_MAP_RULES = """Voice — labels for the **shared “outside / not boxed” bucket** on the execution map:

Audience: someone who wants to know **what kind of work** those calls represent, not how the graph is styled.

When the prompt includes **unresolved_callsites** (caller, line, optional import_ref / callee / callee_expression, snippet):
- Ground the copy in those rows: **what** is being invoked or set up (e.g. creating the web app object, registering a route handler) using plain English.
- You may name a library or product (e.g. FastAPI) when **import_ref** or **snippet** supports it.

displayName (3–7 words):
- Summarize the **theme** of what lands in this bucket (e.g. "Library setup & route hooks").
- Avoid: "sink", "unresolved", "boundary node", "collector", "indexer".

userDescription — **exactly 2 sentences**, substance only (under **340** characters if callsites exist, else **260**).
- **Sentence 1:** This is **not** runnable code by itself; it is a **grouping** for calls from your functions toward targets this index does **not** show as their own function boxes (outside packages, decorators, chained calls, etc.).
- **Sentence 2:** Give **one or two concrete examples** from unresolved_callsites—what that call is doing in product terms. Do **not** talk about line styles, colors, dashed lines, solid lines, or “the map” / “the diagram” / “arrows”.

Banned in userDescription: dashed, solid, diagram, picture, canvas, map (as in drawing), arrow, line style, indexer, callee, sink, static analysis, resolve/resolution, JSON, confidence, v0.

Good: reads like a short note about **real calls**, not a legend.
Bad: map-visual meta, field names from JSON, three-plus sentences."""

SYM_SYSTEM = f"""You write labels for a product map.

{_OVERLAY_DESC_RULES}

You infer behavior from kind, name, path, and excerpt—but output zero implementation detail. If the code is an API, describe it as what a user or operator gets, not how it is served.

Use only the ids given. Output JSON only.

Output shape: a single JSON object with key "by_symbol_id" mapping each symbol id string to {{"displayName"?, "userDescription"?}}. Include every id from the prompt."""

FILE_SYSTEM = f"""You write labels for file-level map nodes.

{_OVERLAY_DESC_RULES}

You see path, excerpt, and symbol blurbs—use them only to infer the human story. Do not summarize symbols with engineering vocabulary. One file might be "where the live demo is glued together" or "where welcome lines get shaped"; never "where routes are registered".

Use only the ids given. Output JSON only.

Output shape: a single JSON object with key "by_file_id" mapping each file id string to {{"displayName"?, "userDescription"?}}. Include every id from the prompt."""

DIR_SYSTEM = f"""You write labels for folder-level map nodes.

{_OVERLAY_DESC_RULES}

Describe the product area in plain words. Labeling runs bottom-up: nested folders in descendant_directories were already described in earlier steps (deepest paths first in that list). Synthesize this folder from that rollup plus files_in_directory and files_deeper_in_tree—especially for shallow wrappers (e.g. a segment that only groups packages below). One level more general than repeating a single child blurb.

Avoid empty filler when you have no signal; still never use banned jargon.

Use only the ids given. Output JSON only.

Output shape: a single JSON object with key "by_directory_id" mapping each directory id string to {{"displayName"?, "userDescription"?}}. Include every id from the prompt."""

ROOT_SYSTEM = f"""You write the single diagram root node for a repository map. There is exactly one id: {ROOT_OVERLAY_ID!r} (the graph root, not a folder on disk).

{_OVERLAY_DESC_RULES}

You receive the repo folder name plus rollups of top-level directories and root-level files (with display names and blurbs from earlier steps). Summarize what this repository delivers as a whole—one level above any single subfolder.

Output JSON only: one object with key "by_root_id" whose value is a single-entry object. That entry's key must be exactly {ROOT_OVERLAY_ID!r} and its value must be {{"displayName"?, "userDescription"?}}."""

FLOW_SYSTEM = f"""You write labels for **special nodes on a flow diagram** (not file-tree symbols).

{_FLOW_MAP_RULES}

These are stand-ins, not ordinary function boxes. Describe **what the grouped calls represent** in the product/code sense—**not** how the graph looks.

Use only the ids given. Output JSON only.

Output shape: a single JSON object with key "by_flow_node_id" mapping each node id string to {{"displayName"?, "userDescription"?}}. Include every id from the prompt."""


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _deepseek_config() -> tuple[str, str, str]:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE).strip().rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip()
    return key, base, model


def _read_excerpt(repo: Path, rel_path: str, line: int, end_line: int, max_lines: int = 48) -> str:
    path = (repo / rel_path).resolve()
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    lo = max(0, line - 1)
    hi = min(len(lines), max(end_line, line, lo + max_lines))
    chunk = lines[lo:hi]
    return "\n".join(chunk)


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _chat_completion_json(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout: float = 120.0,
) -> dict[str, Any]:
    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.35,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=body)
        if r.status_code == 400:
            body.pop("response_format", None)
            r = client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    raw_content = msg.get("content") or ""
    if not isinstance(raw_content, str):
        raise ValueError("empty model content")
    return _parse_json_object(raw_content)


def _file_by_id(raw_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(f["id"]): f for f in raw_doc.get("files", []) if "id" in f}


def _build_symbol_user_message(raw_doc: dict[str, Any], repo: Path) -> str:
    files = _file_by_id(raw_doc)
    blocks: list[str] = []
    for sym in raw_doc.get("symbols", []):
        sid = str(sym.get("id", ""))
        if not sid:
            continue
        fid = str(sym.get("file_id", ""))
        frow = files.get(fid, {})
        rel = str(frow.get("path", ""))
        line = int(sym.get("line") or 1)
        end_line = int(sym.get("end_line") or line)
        excerpt = _read_excerpt(repo, rel, line, end_line) if rel else ""
        blocks.append(
            json.dumps(
                {
                    "id": sid,
                    "kind": sym.get("kind"),
                    "qualified_name": sym.get("qualified_name"),
                    "file_path": rel,
                    "code_excerpt": excerpt[:8000],
                },
                indent=2,
            ),
        )
    return (
        "Symbols — output by_symbol_id for each id. "
        "Plain-English only: no HTTP, routes, FastAPI, GET/POST, 'endpoint', 'factory', or code-structure narration.\n\n"
        + "\n\n---\n\n".join(blocks)
    )


def _build_file_user_message(
    raw_doc: dict[str, Any],
    repo: Path,
    symbol_overlay: dict[str, Any],
) -> str:
    files = raw_doc.get("files", [])
    symbols = raw_doc.get("symbols", [])
    by_sym = symbol_overlay.get("by_symbol_id") or {}
    blocks: list[str] = []
    for f in files:
        fid = str(f.get("id", ""))
        rel = str(f.get("path", ""))
        if not fid or not rel:
            continue
        children: list[dict[str, Any]] = []
        for sym in symbols:
            if str(sym.get("file_id")) != fid:
                continue
            sid = str(sym.get("id", ""))
            if not sid:
                continue
            meta = by_sym.get(sid) or {}
            children.append(
                {
                    "symbol_id": sid,
                    "qualified_name": sym.get("qualified_name"),
                    "displayName": meta.get("displayName"),
                    "userDescription": meta.get("userDescription"),
                },
            )
        head = _read_excerpt(repo, rel, 1, 1, max_lines=30)[:4000]
        blocks.append(
            json.dumps(
                {
                    "id": fid,
                    "path": rel,
                    "file_head_excerpt": head,
                    "symbols_in_file": children,
                },
                indent=2,
            ),
        )
    return (
        "Files — output by_file_id for each id. "
        "Brief a non-engineer: outcomes and handoffs only; ban API/HTTP jargon.\n\n"
        + "\n\n---\n\n".join(blocks)
    )


def _dir_path_from_id(did: str) -> str:
    if did.startswith("dir:"):
        return did[4:]
    return did


def _directory_tiers(valid_dirs: set[str]) -> list[list[str]]:
    if not valid_dirs:
        return []
    by_depth: dict[int, list[str]] = {}
    for did in valid_dirs:
        depth = _dir_path_from_id(did).count("/")
        by_depth.setdefault(depth, []).append(did)
    max_d = max(by_depth)
    return [sorted(by_depth[d]) for d in range(max_d, -1, -1)]


def _files_under_dir_prefix(raw_doc: dict[str, Any], dpath: str) -> list[dict[str, Any]]:
    """Indexed files at or under posix directory dpath (dpath '' = repo root)."""
    rows = raw_doc.get("files", [])
    if not dpath:
        return [f for f in rows if isinstance(f, dict)]
    prefix = dpath + "/"
    out: list[dict[str, Any]] = []
    for f in rows:
        if not isinstance(f, dict):
            continue
        rel = str(f.get("path", ""))
        if not rel:
            continue
        if rel == dpath or rel.startswith(prefix):
            out.append(f)
    return sorted(out, key=lambda x: str(x.get("path", "")))


def _descendant_directories_roll_up(
    dpath: str,
    current_did: str,
    all_valid: set[str],
    by_dir: dict[str, Any],
    *,
    cap: int = 60,
) -> list[dict[str, Any]]:
    """
    Every directory id strictly under dpath (any depth), with overlay blurbs.
    Deepest paths first — matches bottom-up labeling order so parents see full subtree context.
    """
    candidates: list[tuple[int, str, str]] = []
    for vid in all_valid:
        if vid == current_did:
            continue
        vp = _dir_path_from_id(vid)
        if not vp:
            continue
        if dpath:
            if not vp.startswith(dpath + "/"):
                continue
        candidates.append((-vp.count("/"), vp, vid))
    candidates.sort()
    out: list[dict[str, Any]] = []
    for _, vp, vid in candidates[:cap]:
        dm = by_dir.get(vid) or {}
        ud = dm.get("userDescription")
        if isinstance(ud, str) and len(ud) > 200:
            ud = ud[:200].rstrip() + "…"
        out.append(
            {
                "id": vid,
                "path": vp,
                "displayName": dm.get("displayName"),
                "userDescription": ud,
            },
        )
    return out


def _build_directory_user_message(
    raw_doc: dict[str, Any],
    overlay: dict[str, Any],
    dir_ids: list[str],
    all_valid: set[str],
) -> str:
    by_fil = overlay.get("by_file_id") or {}
    by_dir = overlay.get("by_directory_id") or {}
    blocks: list[str] = []
    for did in dir_ids:
        dpath = _dir_path_from_id(did)
        files_in: list[dict[str, Any]] = []
        for f in raw_doc.get("files", []):
            rel = str(f.get("path", ""))
            if not rel:
                continue
            parent = "/".join(rel.split("/")[:-1]) if "/" in rel else ""
            if parent != dpath:
                continue
            fid = str(f.get("id", ""))
            if not fid:
                continue
            fm = by_fil.get(fid) or {}
            files_in.append(
                {
                    "file_id": fid,
                    "path": rel,
                    "displayName": fm.get("displayName"),
                    "userDescription": fm.get("userDescription"),
                },
            )
        descendant_dirs = _descendant_directories_roll_up(
            dpath,
            did,
            all_valid,
            by_dir,
        )
        segment = dpath.split("/")[-1] if dpath else ""
        deeper: list[dict[str, Any]] = []
        if not files_in:
            for f in _files_under_dir_prefix(raw_doc, dpath)[:40]:
                fid = str(f.get("id", ""))
                rel = str(f.get("path", ""))
                if not fid:
                    continue
                fm = by_fil.get(fid) or {}
                ud = fm.get("userDescription")
                if isinstance(ud, str) and len(ud) > 200:
                    ud = ud[:200].rstrip() + "…"
                deeper.append(
                    {
                        "path": rel,
                        "displayName": fm.get("displayName"),
                        "userDescription": ud,
                    },
                )
        blocks.append(
            json.dumps(
                {
                    "id": did,
                    "path": dpath,
                    "folder_segment_name": segment,
                    "files_in_directory": files_in,
                    "files_deeper_in_tree": deeper,
                    "descendant_directories": descendant_dirs,
                },
                indent=2,
            ),
        )
    header = (
        "Folders — output by_directory_id for each id. "
        "Passes are bottom-up (deepest dirs labeled first). "
        "descendant_directories is every nested folder under this path, deepest listed first, "
        "with blurbs from earlier passes—use them plus files to summarize this folder. "
        "No 'source tree', HTTP, or framework names.\n\n"
    )
    return header + "\n\n---\n\n".join(blocks)


def _build_root_user_message(raw_doc: dict[str, Any], overlay: dict[str, Any]) -> str:
    root_path = str(raw_doc.get("root", ""))
    folder_name = Path(root_path).name if root_path else "Project"
    by_fil = overlay.get("by_file_id") or {}
    by_dir = overlay.get("by_directory_id") or {}
    top_dirs: list[dict[str, Any]] = []
    for did in sorted(valid_directory_ids(raw_doc)):
        p = _dir_path_from_id(did)
        if "/" in p:
            continue
        dm = by_dir.get(did) or {}
        ud = dm.get("userDescription")
        if isinstance(ud, str) and len(ud) > 200:
            ud = ud[:200].rstrip() + "…"
        top_dirs.append(
            {
                "id": did,
                "path": p,
                "displayName": dm.get("displayName"),
                "userDescription": ud,
            },
        )
    root_files: list[dict[str, Any]] = []
    for f in raw_doc.get("files", []):
        rel = str(f.get("path", ""))
        if not rel or "/" in rel:
            continue
        fid = str(f.get("id", ""))
        if not fid:
            continue
        fm = by_fil.get(fid) or {}
        ud = fm.get("userDescription")
        if isinstance(ud, str) and len(ud) > 200:
            ud = ud[:200].rstrip() + "…"
        root_files.append(
            {
                "id": fid,
                "path": rel,
                "displayName": fm.get("displayName"),
                "userDescription": ud,
            },
        )
    payload = {
        "diagram_root_id": ROOT_OVERLAY_ID,
        "repo_folder_name": folder_name,
        "top_level_directories": top_dirs,
        "files_at_repo_root": root_files,
    }
    return (
        f'Project root — output by_root_id with a single key "{ROOT_OVERLAY_ID}" only.\n\n'
        + json.dumps(payload, indent=2)
    )


def _filter_root_delta(resp: dict[str, Any]) -> dict[str, Any]:
    br = resp.get("by_root_id")
    if not isinstance(br, dict):
        return {}
    ent = br.get(ROOT_OVERLAY_ID)
    if not isinstance(ent, dict):
        return {}
    cleaned = {
        k: v
        for k, v in ent.items()
        if k in ("displayName", "userDescription") and isinstance(v, str)
    }
    if not cleaned:
        return {}
    return {ROOT_OVERLAY_ID: cleaned}


def _filter_keys(
    proposed: dict[str, Any],
    valid: set[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in proposed.items():
        if k not in valid:
            continue
        if isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in v.items() if kk in ("displayName", "userDescription")}
    return out


def _build_flow_overlay_user_message(ir_doc: dict[str, Any]) -> str:
    """Prompt for IR nodes that have no raw_symbol_id (synthetic / boundary)."""
    edges = ir_doc.get("edges", [])
    nodes = ir_doc.get("nodes", [])
    id_to_label: dict[str, str] = {}
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        iid = str(n["id"])
        id_to_label[iid] = str(n.get("label", iid))

    blocks: list[str] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("raw_symbol_id"):
            continue
        nid = str(n.get("id", ""))
        if not nid:
            continue
        incoming_all = [e for e in edges if isinstance(e, dict) and str(e.get("to")) == nid]
        incoming = incoming_all[:48]
        callers: list[dict[str, Any]] = []
        seen_from: set[str] = set()
        for x in incoming:
            if str(x.get("kind")) != "calls":
                continue
            fid = str(x.get("from", ""))
            if fid in seen_from:
                continue
            seen_from.add(fid)
            full = id_to_label.get(fid, fid)
            short = full.rsplit(".", 1)[-1] if full else fid
            callers.append(
                {
                    "from_id": fid,
                    "caller_label_short": short,
                    "caller_label_full": full,
                    "confidence": x.get("confidence"),
                    "evidence": x.get("evidence"),
                },
            )
        n_calls_in = sum(1 for e in incoming_all if str(e.get("kind")) == "calls")
        unresolved_callsites: list[dict[str, Any]] = []
        for x in incoming_all:
            if str(x.get("kind")) != "calls" or str(x.get("confidence")) != "unknown":
                continue
            cs = x.get("callsite")
            if not isinstance(cs, dict):
                continue
            fid = str(x.get("from", ""))
            full = id_to_label.get(fid, fid)
            short = full.rsplit(".", 1)[-1] if full else fid
            row: dict[str, Any] = {"caller_function": short}
            for key in ("callee", "import_ref", "callee_expression", "line", "snippet"):
                if key in cs and cs[key] not in (None, ""):
                    row[key] = cs[key]
            unresolved_callsites.append(row)
        unresolved_callsites = unresolved_callsites[:22]
        role = (
            "unresolved_call_sink"
            if nid.endswith("boundary:unresolved") or n.get("kind") == "dynamic_callsite"
            else "synthetic_flow_node"
        )
        payload: dict[str, Any] = {
            "id": nid,
            "kind": n.get("kind"),
            "technical_label": n.get("label"),
            "map_role": role,
            "incoming_call_edge_count": n_calls_in,
            "callers_to_this_node": callers[:12],
            "other_incoming_edges": [
                {
                    "kind": x.get("kind"),
                    "confidence": x.get("confidence"),
                    "from_id": x.get("from"),
                }
                for x in incoming
                if str(x.get("kind")) != "calls"
            ][:8],
        }
        if unresolved_callsites:
            payload["unresolved_callsites"] = unresolved_callsites
        blocks.append(json.dumps(payload, indent=2))
    if not blocks:
        return ""
    return (
        "Flow diagram — synthetic nodes (no symbol id). Context below is for you only; "
        "do not paste field names or jargon into userDescription. "
        "Output by_flow_node_id for every id.\n\n"
        + "\n\n---\n\n".join(blocks)
    )


def _dry_run_flow_overlay(raw_doc: dict[str, Any]) -> dict[str, Any]:
    try:
        from raw_indexer.execution_ir.python_from_raw import build_execution_ir_from_raw

        ir = build_execution_ir_from_raw(raw_doc)
    except Exception:
        return {}
    out: dict[str, Any] = {}
    for n in ir.get("nodes", []):
        if not isinstance(n, dict):
            continue
        if n.get("raw_symbol_id"):
            continue
        nid = str(n.get("id", ""))
        if not nid:
            continue
        tail = str(n.get("label", nid)).split(".")[-1].replace("_", " ").title()
        out[nid] = {
            "displayName": f"{tail} (stub)",
            "userDescription": (
                "Placeholder for a boundary or uncertain map node "
                "(UPDATE_MAP_DRY_RUN)."
            ),
        }
    return out


def _dry_run_overlay(raw_doc: dict[str, Any]) -> dict[str, Any]:
    by_sym: dict[str, Any] = {}
    for sym in raw_doc.get("symbols", []):
        sid = str(sym.get("id", ""))
        if not sid:
            continue
        qn = str(sym.get("qualified_name", "")).split(".")[-1] or sid
        by_sym[sid] = {
            "displayName": qn.replace("_", " ").title(),
            "userDescription": f"Part of the app related to {qn}; labels are stubbed (UPDATE_MAP_DRY_RUN).",
        }
    by_fil: dict[str, Any] = {}
    for f in raw_doc.get("files", []):
        fid = str(f.get("id", ""))
        rel = str(f.get("path", ""))
        if not fid:
            continue
        name = Path(rel).name if rel else fid
        by_fil[fid] = {
            "displayName": f"File: {name}",
            "userDescription": "Stub file summary (UPDATE_MAP_DRY_RUN).",
        }
    by_dir: dict[str, Any] = {}
    for did in valid_directory_ids(raw_doc):
        tail = _dir_path_from_id(did).split("/")[-1]
        by_dir[did] = {
            "displayName": tail.replace("_", " ").replace("-", " ").title(),
            "userDescription": f"Folder area for {tail} (UPDATE_MAP_DRY_RUN stub).",
        }
    root_name = Path(str(raw_doc.get("root", ""))).name or "Project"
    by_root = {
        ROOT_OVERLAY_ID: {
            "displayName": root_name.replace("_", " ").replace("-", " ").title(),
            "userDescription": f"Stub summary for {root_name} (UPDATE_MAP_DRY_RUN).",
        },
    }
    return {
        "schema_version": 0,
        "by_symbol_id": by_sym,
        "by_file_id": by_fil,
        "by_directory_id": by_dir,
        "by_root_id": by_root,
        "by_flow_node_id": _dry_run_flow_overlay(raw_doc),
    }


def run_update_map(
    repo: Path,
    overlay_path: Path,
    raw_doc: dict[str, Any],
) -> dict[str, Any]:
    """
    Refresh overlay using DeepSeek, or stub if UPDATE_MAP_DRY_RUN=1.

    Merges into existing overlay file; validates against raw_doc before write.
    """
    repo = repo.resolve()
    errors: list[str] = []
    existing = load_overlay(overlay_path)

    if _env_flag("UPDATE_MAP_DRY_RUN"):
        stub = _dry_run_overlay(raw_doc)
        merged = dict(existing)
        merged = merge_overlay_delta(merged, {"by_symbol_id": stub["by_symbol_id"]})
        merged = merge_overlay_delta(merged, {"by_file_id": stub["by_file_id"]})
        merged = merge_overlay_delta(merged, {"by_directory_id": stub["by_directory_id"]})
        merged = merge_overlay_delta(merged, {"by_root_id": stub["by_root_id"]})
        merged = merge_overlay_delta(merged, {"by_flow_node_id": stub["by_flow_node_id"]})
        merged["schema_version"] = int(merged.get("schema_version") or 0)
        sym_o = overlay_orphan_keys(merged, raw_doc)
        fil_o = overlay_orphan_file_keys(merged, raw_doc)
        dir_o = overlay_orphan_directory_keys(merged, raw_doc)
        root_o = overlay_orphan_root_keys(merged)
        flow_o = overlay_orphan_flow_keys(merged, raw_doc)
        if sym_o or fil_o or dir_o or root_o or flow_o:
            return {
                "ok": False,
                "dry_run": True,
                "errors": [
                    f"orphans after merge: sym={sym_o}, file={fil_o}, dir={dir_o}, root={root_o}, flow={flow_o}",
                ],
            }
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        overlay_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "ok": True,
            "dry_run": True,
            "symbols_updated": len(stub["by_symbol_id"]),
            "files_updated": len(stub["by_file_id"]),
            "directories_updated": len(stub["by_directory_id"]),
            "root_updated": 1,
            "flow_nodes_updated": len(stub["by_flow_node_id"]),
            "errors": [],
        }

    api_key, base, model = _deepseek_config()
    if not api_key:
        return {
            "ok": False,
            "dry_run": False,
            "errors": [
                "DEEPSEEK_API_KEY is not set. Add it to your environment (see .env.example at repo root).",
            ],
        }

    valid_sym = {str(s["id"]) for s in raw_doc.get("symbols", []) if s.get("id")}
    valid_fil = {str(f["id"]) for f in raw_doc.get("files", []) if f.get("id")}
    valid_dir = valid_directory_ids(raw_doc)

    try:
        sym_user = _build_symbol_user_message(raw_doc, repo)
        sym_resp = _chat_completion_json(
            api_key=api_key,
            base_url=base,
            model=model,
            system=SYM_SYSTEM,
            user=sym_user,
        )
        raw_sym = sym_resp.get("by_symbol_id")
        if not isinstance(raw_sym, dict):
            raise ValueError("model JSON missing by_symbol_id object")
        sym_delta = _filter_keys(raw_sym, valid_sym)
    except Exception as e:
        errors.append(f"symbol pass failed: {e}")
        return {"ok": False, "dry_run": False, "errors": errors}

    working = merge_overlay_delta(dict(existing), {"by_symbol_id": sym_delta})

    try:
        file_user = _build_file_user_message(raw_doc, repo, working)
        file_resp = _chat_completion_json(
            api_key=api_key,
            base_url=base,
            model=model,
            system=FILE_SYSTEM,
            user=file_user,
        )
        raw_fil = file_resp.get("by_file_id")
        if not isinstance(raw_fil, dict):
            raise ValueError("model JSON missing by_file_id object")
        fil_delta = _filter_keys(raw_fil, valid_fil)
    except Exception as e:
        errors.append(f"file pass failed: {e}")
        return {"ok": False, "dry_run": False, "errors": errors}

    merged = merge_overlay_delta(working, {"by_file_id": fil_delta})
    merged["schema_version"] = int(merged.get("schema_version") or 0)

    dir_delta_all: dict[str, Any] = {}
    if valid_dir:
        try:
            working_dirs = merged
            for tier in _directory_tiers(valid_dir):
                if not tier:
                    continue
                dir_user = _build_directory_user_message(
                    raw_doc,
                    working_dirs,
                    tier,
                    valid_dir,
                )
                dir_resp = _chat_completion_json(
                    api_key=api_key,
                    base_url=base,
                    model=model,
                    system=DIR_SYSTEM,
                    user=dir_user,
                )
                raw_d = dir_resp.get("by_directory_id")
                if not isinstance(raw_d, dict):
                    raise ValueError("model JSON missing by_directory_id object")
                d_delta = _filter_keys(raw_d, valid_dir)
                working_dirs = merge_overlay_delta(working_dirs, {"by_directory_id": d_delta})
                dir_delta_all.update(d_delta)
            merged = working_dirs
        except Exception as e:
            errors.append(f"directory pass failed: {e}")
            return {"ok": False, "dry_run": False, "errors": errors}

    root_delta: dict[str, Any] = {}
    try:
        root_user = _build_root_user_message(raw_doc, merged)
        root_resp = _chat_completion_json(
            api_key=api_key,
            base_url=base,
            model=model,
            system=ROOT_SYSTEM,
            user=root_user,
        )
        root_delta = _filter_root_delta(root_resp)
        if root_delta:
            merged = merge_overlay_delta(merged, {"by_root_id": root_delta})
    except Exception as e:
        errors.append(f"root pass failed: {e}")
        return {"ok": False, "dry_run": False, "errors": errors}

    flow_delta: dict[str, Any] = {}
    try:
        from raw_indexer.execution_ir.python_from_raw import build_execution_ir_from_raw

        ir_doc = build_execution_ir_from_raw(raw_doc)
    except Exception:
        ir_doc = None

    if ir_doc is not None:
        flow_user = _build_flow_overlay_user_message(ir_doc)
        if flow_user.strip():
            valid_flow = {
                str(n["id"])
                for n in ir_doc.get("nodes", [])
                if isinstance(n, dict) and n.get("id")
            }
            try:
                flow_resp = _chat_completion_json(
                    api_key=api_key,
                    base_url=base,
                    model=model,
                    system=FLOW_SYSTEM,
                    user=flow_user,
                )
                raw_flow = flow_resp.get("by_flow_node_id")
                if not isinstance(raw_flow, dict):
                    raise ValueError("model JSON missing by_flow_node_id object")
                flow_delta = _filter_keys(raw_flow, valid_flow)
                merged = merge_overlay_delta(merged, {"by_flow_node_id": flow_delta})
            except Exception as e:
                errors.append(f"flow pass failed: {e}")
                return {"ok": False, "dry_run": False, "errors": errors}

    sym_o = overlay_orphan_keys(merged, raw_doc)
    fil_o = overlay_orphan_file_keys(merged, raw_doc)
    dir_o = overlay_orphan_directory_keys(merged, raw_doc)
    root_o = overlay_orphan_root_keys(merged)
    flow_o = overlay_orphan_flow_keys(merged, raw_doc)
    if sym_o or fil_o or dir_o or root_o or flow_o:
        return {
            "ok": False,
            "dry_run": False,
            "errors": [
                f"orphan keys after merge: symbol={sym_o}, file={fil_o}, directory={dir_o}, root={root_o}, flow={flow_o}",
            ],
        }

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "dry_run": False,
        "model": model,
        "symbols_updated": len(sym_delta),
        "files_updated": len(fil_delta),
        "directories_updated": len(dir_delta_all) if valid_dir else 0,
        "root_updated": len(root_delta),
        "flow_nodes_updated": len(flow_delta),
        "errors": [],
    }
