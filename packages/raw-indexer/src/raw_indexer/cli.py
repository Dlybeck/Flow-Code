"""CLI: index | execution-ir | diff | orphans | overlay-migrate | validate | apply | apply-verify | apply-bundle"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from raw_indexer.apply_patch import apply_unified_patch
from raw_indexer.bundle import apply_bundle, load_bundle
from raw_indexer.execution_ir import build_execution_ir_from_raw
from raw_indexer.diagnostics_pyright import attach_diagnostics_to_raw
from raw_indexer.diff_raw import diff_raw, format_diff_report
from raw_indexer.index import index_repo, write_index
from raw_indexer.overlay import report_orphans
from raw_indexer.overlay_migrate import migrate_overlay_files
from raw_indexer.validate import validate_repo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raw-indexer", description="RAW index v0 (AST) for Python repos")
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

    p_val = sub.add_parser("validate", help="Run pytest and basedpyright/pyright in repo")
    p_val.add_argument("path", type=Path)
    p_val.add_argument("--pytest-only", action="store_true")

    p_apply = sub.add_parser("apply", help="Apply unified diff with patch(1)")
    p_apply.add_argument("repo", type=Path)
    p_apply.add_argument("patch", type=Path)
    p_apply.add_argument("--dry-run", action="store_true")

    p_av = sub.add_parser(
        "apply-verify",
        help="Apply patch then run validate (orchestration demo, no LLM)",
    )
    p_av.add_argument("repo", type=Path)
    p_av.add_argument("patch", type=Path)
    p_av.add_argument("--dry-run", action="store_true")
    p_av.add_argument("--pytest-only", action="store_true")
    p_av.add_argument(
        "--write-raw",
        type=Path,
        default=None,
        help="After apply, write fresh RAW JSON to this path (orchestration demo)",
    )

    p_ab = sub.add_parser(
        "apply-bundle",
        help="Apply JSON bundle: unified_diff (optional if overlay-only) + optional overlay merge",
    )
    p_ab.add_argument("repo", type=Path, help="Repository root")
    p_ab.add_argument("bundle_json", type=Path, help="Bundle JSON file (schema_version 0)")
    p_ab.add_argument(
        "--overlay-path",
        type=Path,
        default=None,
        help="Required if bundle includes overlay: path to overlay.json to read/merge/write",
    )
    p_ab.add_argument("--dry-run", action="store_true", help="patch --dry-run only (no overlay bundles)")
    p_ab.add_argument("--skip-validate", action="store_true", help="Skip pytest/typecheck after apply")
    p_ab.add_argument("--pytest-only", action="store_true", help="If validating, pytest only (no typecheck)")
    p_ab.add_argument("-o", "--out", type=Path, default=None, help="Write result JSON to file")

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
        out_obj = {
            "schema_version": 0,
            "report": rep,
            "overlay": new_ov,
        }
        text = json.dumps(out_obj, indent=2, sort_keys=True) + "\n"
        if args.dry_run:
            print(text, end="")
            return 0
        if not args.out:
            sys.stderr.write("overlay-migrate: use -o OUT or --dry-run\n")
            return 1
        args.out.write_text(json.dumps(new_ov, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sys.stderr.write(json.dumps(rep, indent=2, sort_keys=True) + "\n")
        return 0

    if args.cmd == "validate":
        return validate_repo(args.path, pytest_only=args.pytest_only)

    if args.cmd == "apply":
        return apply_unified_patch(args.repo, args.patch, dry_run=args.dry_run)

    if args.cmd == "apply-verify":
        code = apply_unified_patch(args.repo, args.patch, dry_run=args.dry_run)
        if code != 0:
            return code
        if args.dry_run:
            return 0
        if getattr(args, "write_raw", None):
            doc = index_repo(args.repo)
            write_index(doc, args.write_raw)
        return validate_repo(args.repo, pytest_only=args.pytest_only)

    if args.cmd == "apply-bundle":
        bundle_doc = load_bundle(args.bundle_json)
        res = apply_bundle(
            args.repo,
            bundle_doc,
            overlay_path=args.overlay_path,
            dry_run=args.dry_run,
            skip_validate=args.skip_validate,
            pytest_only=args.pytest_only,
        )
        text = json.dumps(res.to_json_dict(), indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0 if res.ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
