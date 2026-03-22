"""
Language adapter boundary (SPEC §9.3).

v0 Python stack:
- **Structural index:** `raw_indexer.index` (stdlib `ast`).
- **Optional type honesty:** `raw_indexer.diagnostics_pyright` (Pyright / Basedpyright JSON).

Future adapters (e.g. richer static analysis) should hang off the same boundary without
forking overlay / bundle / validate semantics.
"""

from __future__ import annotations

# Re-export primary entry for callers that want a single import.
from raw_indexer.index import index_repo, write_index

__all__ = ["index_repo", "write_index"]
