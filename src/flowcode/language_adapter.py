"""
Language adapter boundary (SPEC §9.3).

v0 Python stack:
- **Structural index:** `flowcode.index` (stdlib `ast`).
- **Optional type honesty:** `flowcode.diagnostics_pyright` (Pyright / Basedpyright JSON).

Future adapters (e.g. richer static analysis, TypeScript) should hang off the same
boundary without forking overlay / bundle / validate semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Re-export primary entry for callers that want a single import.
from flowcode.index import index_repo, write_index

__all__ = ["index_repo", "index_repo_auto", "write_index"]


def index_repo_auto(
    root: Path | str,
    *,
    src_roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Auto-detect language(s) present in the repo and dispatch to the appropriate indexer.

    Currently detects Python (always available) and TypeScript/JavaScript (requires
    `pip install flowcode[ts]`). If both are present, returns a merged RAW document.
    """
    root_p = Path(root).resolve()

    has_ts = any(
        p.suffix in {".ts", ".tsx", ".js", ".mjs", ".jsx"}
        for p in root_p.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.parts)
    )
    has_py = any(p.suffix == ".py" for p in root_p.rglob("*.py") if p.is_file())

    if has_ts and not has_py:
        from flowcode.ts_indexer import index_ts_repo
        return index_ts_repo(root_p, src_roots=src_roots)

    if has_ts and has_py:
        # Both present — Python index is primary for now; TS support can be layered later.
        return index_repo(root_p, src_roots=src_roots)

    return index_repo(root_p, src_roots=src_roots)
