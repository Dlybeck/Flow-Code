"""CLI: index | execution-ir | diff | orphans | overlay-migrate"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flowcode.diagnostics_pyright import attach_diagnostics_to_raw
from flowcode.diff_raw import diff_raw, format_diff_report
from flowcode.execution_ir import build_execution_ir_from_raw
from flowcode.index import index_repo, write_index
from flowcode.overlay import report_orphans
from flowcode.overlay_migrate import migrate_overlay_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flowcode", description="Graph generation for Python and TypeScript repos")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Emit RAW JSON for a repo")
    p_index.add_argument("path", type=Path, help="Repository root")
    p_index.add_argument("-o", "--out", type=Path, default=None, help="Write JSON to file (default: stdout)")
    p_index.add_argument(
        "--src-root",
        action="append",
        dest="src_roots",
        default=None,
        help="Relative source root (repeatable), default: src/ if present else .",
    )
    p_index.add_argument(
        "--diagnostics",
        action="store_true",
        help="Attach Pyright/Basedpyright JSON diagnostics if on PATH (optional honesty layer)",
    )

    p_ir = sub.add_parser(
        "execution-ir",
        help="Index repo and emit execution IR (flow) JSON",
    )
    p_ir.add_argument("path", type=Path, help="Repository root")
    p_ir.add_argument("-o", "--out", type=Path, default=None, help="Write JSON to file (default: stdout)")
    p_ir.add_argument(
        "--src-root",
        action="append",
        dest="src_roots",
        default=None,
        help="Relative source root (repeatable), default: src/ if present else .",
    )
    p_ir.add_argument(
        "--diagnostics",
        action="store_true",
        help="Attach Pyright/Basedpyright JSON diagnostics to RAW before building IR",
    )

    p_diff = sub.add_parser("diff", help="Diff two RAW JSON files")
    p_diff.add_argument("old_json", type=Path)
    p_diff.add_argument("new_json", type=Path)
    p_diff.add_argument("-o", "--out", type=Path, default=None)

    p_orphans = sub.add_parser(
        "orphans",
        help="List overlay keys (by_symbol_id / by_file_id) missing from RAW JSON",
    )
    p_orphans.add_argument("raw_json", type=Path)
    p_orphans.add_argument("overlay_json", type=Path)
    p_orphans.add_argument("-o", "--out", type=Path, default=None)

    p_mig = sub.add_parser(
        "overlay-migrate",
        help="Rewrite overlay keys from diff.remap between two RAW JSON snapshots",
    )
    p_mig.add_argument("old_raw", type=Path, help="RAW JSON before refactor")
    p_mig.add_argument("new_raw", type=Path, help="RAW JSON after refactor")
    p_mig.add_argument("overlay_in", type=Path, help="Current overlay.json")
    p_mig.add_argument("-o", "--out", type=Path, default=None, help="Write migrated overlay (required unless --dry-run)")
    p_mig.add_argument(
        "--dry-run",
        action="store_true",
        help="Print migration report JSON only; do not write overlay",
    )
    p_mig.add_argument(
        "--include-medium",
        action="store_true",
        help="Also apply medium-confidence symbol remaps (same kind+name+parent dir)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "index":
        doc = index_repo(args.path, src_roots=args.src_roots)
        if getattr(args, "diagnostics", False):
            doc = attach_diagnostics_to_raw(doc, args.path.resolve())
        write_index(doc, args.out)
        return 0

    if args.cmd == "execution-ir":
        doc = index_repo(args.path, src_roots=args.src_roots)
        if getattr(args, "diagnostics", False):
            doc = attach_diagnostics_to_raw(doc, args.path.resolve())
        ir_doc = build_execution_ir_from_raw(doc)
        text = json.dumps(ir_doc, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    if args.cmd == "diff":
        report = diff_raw(args.old_json, args.new_json)
        text = format_diff_report(report)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    if args.cmd == "orphans":
        rep = report_orphans(args.overlay_json, args.raw_json)
        text = json.dumps(rep, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 1 if rep.get("orphan_count", 0) > 0 else 0

    if args.cmd == "overlay-migrate":
        new_ov, _diff, rep = migrate_overlay_files(
            args.old_raw,
            args.new_raw,
            args.overlay_in,
            include_medium=args.include_medium,
        )
        text = json.dumps({"schema_version": 0, "report": rep, "overlay": new_ov}, indent=2, sort_keys=True) + "\n"
        if args.dry_run:
            print(text, end="")
            return 0
        if not args.out:
            sys.stderr.write("overlay-migrate: use -o OUT or --dry-run\n")
            return 1
        args.out.write_text(json.dumps(new_ov, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sys.stderr.write(json.dumps(rep, indent=2, sort_keys=True) + "\n")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
