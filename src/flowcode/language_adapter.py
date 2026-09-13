"""
Language adapter boundary (SPEC §9.3).

v0 Python stack:
- **Structural index:** `flowcode.index` (stdlib `ast`).
- **Optional type honesty:** `flowcode.diagnostics_pyright` (Pyright / Basedpyright JSON).

The browser adapter uses tree-sitter. Mixed repositories retain both producers
behind this boundary without forking overlay, validation or terrain semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Re-export primary entry for callers that want a single import.
from flowcode.index import index_repo, write_index
from flowcode.sources import BROWSER_EXTENSIONS, source_files

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

    # Detect and index the same selected files, including web code outside src/.
    src_roots = src_roots if src_roots is not None else ['.']
    files = source_files(root_p, src_roots, BROWSER_EXTENSIONS | {'.py'})
    has_ts = any(p.suffix in BROWSER_EXTENSIONS for p in files)
    has_py = any(p.suffix == '.py' for p in files)

    if has_ts and not has_py:
        from flowcode.ts_indexer import index_ts_repo
        return index_ts_repo(root_p, src_roots=src_roots)

    if has_ts and has_py:
        from flowcode.ts_indexer import index_ts_repo
        documents = [index_repo(root_p, src_roots=src_roots), index_ts_repo(root_p, src_roots=src_roots)]
        return {
            "schema_version": 0,
            "indexer": "flowcode.multi_v0",
            "root": str(root_p),
            "documents": documents,
            "files": [f for doc in documents for f in doc["files"]],
            "symbols": [s for doc in documents for s in doc["symbols"]],
            "edges": [e for doc in documents for e in doc["edges"]],
            "index_meta": {"completeness": "partial", "engine": "multiple adapters"},
        }

    return index_repo(root_p, src_roots=src_roots)
