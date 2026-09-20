"""Build a host-independent static viewer directory from a terrain snapshot."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

_CONFIG_PATTERN = re.compile(
    r'(<script id="viewer-config" type="application/json">).*?(</script>)',
    re.DOTALL,
)


def default_viewer_root() -> Path:
    """Return the viewer source in a Flow-Code checkout."""
    return Path(__file__).resolve().parents[2] / "experiments" / "3d-layered"


def build_standalone_site(
    snapshot_path: str | Path,
    output_dir: str | Path,
    *,
    viewer_root: str | Path | None = None,
) -> dict[str, Any]:
    """Copy one snapshot and the built viewer into a self-contained directory.

    The resulting directory has no Portfolio dependency and makes no runtime
    request outside itself. It can be served by any static HTTP server.
    """
    snapshot = Path(snapshot_path).resolve()
    output = Path(output_dir).resolve()
    viewer = Path(viewer_root).resolve() if viewer_root else default_viewer_root()

    document = json.loads(snapshot.read_text(encoding="utf-8"))
    if not isinstance(document.get("views"), dict):
        raise TypeError("Snapshot must be a Flow-Code terrain export with views")
    project = str(document.get("project") or snapshot.stem)

    required_files = [
        viewer / "index.html",
        viewer / "portfolio.css",
        viewer / "dist" / "app.js",
    ]
    required_directory = viewer / "assets"
    missing = [str(path) for path in required_files if not path.is_file()]
    if not required_directory.is_dir():
        missing.append(str(required_directory))
    if missing:
        raise FileNotFoundError(
            "Build the viewer first with `npm ci && npm run build` in "
            f"{viewer}. Missing: {', '.join(missing)}"
        )

    source_html = required_files[0].read_text(encoding="utf-8")
    config = json.dumps(
        {
            "project": "graph",
            "projects": [{"id": "graph", "label": project}],
            "mapUrl": "graph.json",
        },
        separators=(",", ":"),
    )
    config = (
        config.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    html, replacements = _CONFIG_PATTERN.subn(
        lambda match: f"{match.group(1)}{config}{match.group(2)}",
        source_html,
        count=1,
    )
    if replacements != 1:
        raise ValueError("Viewer index is missing its viewer-config block")

    output.mkdir(parents=True, exist_ok=True)
    (output / "dist").mkdir(exist_ok=True)
    shutil.copytree(required_directory, output / "assets", dirs_exist_ok=True)
    shutil.copy2(viewer / "portfolio.css", output / "portfolio.css")
    shutil.copy2(viewer / "dist" / "app.js", output / "dist" / "app.js")
    shutil.copy2(snapshot, output / "graph.json")
    (output / "index.html").write_text(html, encoding="utf-8")

    return {
        "status": "built",
        "project": project,
        "output": str(output),
        "entry": str(output / "index.html"),
        "snapshot": str(output / "graph.json"),
    }
