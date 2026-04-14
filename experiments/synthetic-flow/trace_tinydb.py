"""Exercise TinyDB under sys.settrace and capture the real call sequence.

Only captures 'call' events inside tinydb-src/tinydb/. Resolves each frame to
the qualified name (ClassName.method or function_name) that matches our
embedding keys from parse_multi.
"""
from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Make the TinyDB clone importable
ROOT = Path(__file__).parent
TINYDB_SRC = ROOT / "tinydb-src"
sys.path.insert(0, str(TINYDB_SRC))

# Filter: we only care about frames inside this directory
TINYDB_PKG = TINYDB_SRC / "tinydb"
TINYDB_PREFIX = str(TINYDB_PKG.resolve())

_events: list[dict] = []
_depth = 0


def _resolve_qname(frame) -> str | None:
    """Map a frame to a qname like 'Table.insert' or 'touch'. None if outside our scope."""
    path = frame.f_code.co_filename
    try:
        resolved = str(Path(path).resolve())
    except OSError:
        return None
    if not resolved.startswith(TINYDB_PREFIX):
        return None
    qname = getattr(frame.f_code, "co_qualname", frame.f_code.co_name)
    # Strip any leading "ClassName.<locals>.inner" artifacts — keep first and last segments
    # (e.g. "Table.insert.<locals>.updater" → we skip these inner closures; tracer will catch them)
    if ".<locals>." in qname:
        return None
    return qname


def _tracer(frame, event, arg):
    global _depth
    if event == "call":
        q = _resolve_qname(frame)
        if q is not None:
            _events.append({"qname": q, "depth": _depth})
            _depth += 1
            return _tracer
        return None
    if event == "return":
        q = _resolve_qname(frame)
        if q is not None:
            _depth = max(0, _depth - 1)
    return _tracer


def run_session() -> None:
    """Exercise a broad slice of TinyDB."""
    from tinydb import TinyDB, Query

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fp:
        db_path = fp.name

    sys.settrace(_tracer)
    try:
        db = TinyDB(db_path)
        db.insert({"name": "alice", "age": 30})
        db.insert({"name": "bob", "age": 25})
        db.insert_multiple([{"name": "carol", "age": 40}, {"name": "dave", "age": 22}])

        q = Query()
        _ = db.search(q.age > 26)
        _ = db.get(q.name == "alice")
        _ = db.all()
        _ = db.contains(q.name == "bob")

        db.update({"age": 31}, q.name == "alice")
        db.remove(q.name == "dave")
        db.close()
    finally:
        sys.settrace(None)

    Path(db_path).unlink(missing_ok=True)


def main() -> None:
    run_session()
    counts = Counter(e["qname"] for e in _events)

    # Cross-check against our embedding keys
    emb = json.loads((ROOT / "function_embeddings.json").read_text())
    known_qnames = {f["qname"] for f in emb["functions"]}
    in_set = {q: c for q, c in counts.items() if q in known_qnames}
    missing = {q: c for q, c in counts.items() if q not in known_qnames}

    out = {
        "events": _events,
        "visit_counts": dict(counts),
        "in_embedding_set": in_set,
        "outside_embedding_set": missing,
    }
    (ROOT / "real_trace.json").write_text(json.dumps(out, indent=2))
    print(f"captured {len(_events)} call events")
    print(f"  {len(in_set)} distinct qnames mapped to embeddings")
    print(f"  {len(missing)} distinct qnames outside the embedding set:")
    for q, c in sorted(missing.items(), key=lambda x: -x[1])[:10]:
        print(f"    {q} ({c})")


if __name__ == "__main__":
    main()
