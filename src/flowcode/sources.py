"""Deterministic source selection shared by language detection and adapters."""

from __future__ import annotations

import os
from pathlib import Path

BROWSER_EXTENSIONS = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
)
SKIP_DIR_NAMES = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        "bin",
        "out",
        "obj",
        "target",
        "coverage",
        "library",
        "vendor",
        "vendors",
        "third_party",
        "venv",
        "__pycache__",
        "site-packages",
    }
)


def source_files(
    root: Path, roots: list[str], extensions: set[str] | frozenset[str]
) -> list[Path]:
    root = root.resolve()
    selected: set[Path] = set()
    for relative in roots:
        requested = root / relative
        if any(
            p.is_symlink()
            for p in [requested, *requested.parents]
            if p != root and p.is_relative_to(root)
        ):
            continue
        base = (root / relative).resolve()
        if not base.is_relative_to(root):
            raise ValueError(f"Source root must stay within the repository: {relative}")
        walk = (
            [(str(base.parent), [], [base.name])]
            if base.is_file()
            else os.walk(base, followlinks=False)
        )
        for directory, dirs, files in walk:
            dirs[:] = sorted(
                d
                for d in dirs
                if not d.startswith(".")
                and d.casefold() not in SKIP_DIR_NAMES
                and not d.endswith(".egg-info")
            )
            for name in files:
                path = Path(directory) / name
                if (
                    path.is_symlink()
                    or name.startswith(".")
                    or path.suffix not in extensions
                ):
                    continue
                if ".min." in name or name.endswith((".d.ts", ".d.mts", ".d.cts")):
                    continue
                selected.add(path)
    return sorted(selected, key=lambda p: p.relative_to(root).as_posix())
