"""Build three reference snapshots and install the same viewer into Portfolio.

Run npm ci && npm run build in experiments/3d-layered first. No model, network,
application startup, or publishing is performed by this command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from flowcode.terrain import export_terrain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", type=Path, required=True)
    parser.add_argument("--scribblescan", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    viewer = root / "experiments/3d-layered"
    target = args.portfolio / "static/flowcode"
    target.mkdir(parents=True, exist_ok=True)
    for name in ["portfolio.css", "assets"]:
        source = viewer / name
        if source.is_dir():
            shutil.copytree(source, target / name, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target / name)
    (target / "dist").mkdir(exist_ok=True)
    shutil.copy2(viewer / "dist/app.js", target / "dist/app.js")
    html = (viewer / "index.html").read_text()
    html = html.replace(
        "<body>",
        '<body>\n<script id="viewer-config" type="application/json">{{ viewer_config | tojson }}</script>',
    )
    for path in ["assets/fonts.css", "portfolio.css"]:
        html = html.replace(f'href="{path}"', f'href="/static/flowcode/{path}"')
    html = html.replace(
        'import("./dist/app.js")', 'import("/static/flowcode/dist/app.js")'
    )
    html = html.replace(
        'href="original.html">See original Flow-Code ↗',
        'href="/projects/flowcode">About Flow-Code ↗',
    )
    (args.portfolio / "templates/shared/code_map.html").write_text(html)
    (args.portfolio / "templates/pages/code_map.html").write_text(
        '{% extends "shared/code_map.html" %}\n'
    )
    references = [
        (
            "flowcode",
            root,
            [
                "src/flowcode",
                "experiments/3d-layered/app.js",
                "experiments/3d-layered/snapshot.js",
            ],
            ["flowcode.generate_graph"],
        ),
        (
            "portfolio",
            args.portfolio,
            ["main.py", "apis/route_portfolio.py", "core", "static/scripts"],
            ["static.scripts.themeEngine.$callback_8_2.activate"],
        ),
        (
            "scribblescan",
            args.scribblescan,
            ["app", "static/js"],
            [
                "static.js.uploads.demo.DemoHandler.processDemoFiles",
                "static.js.uploads.demo.DemoHandler.init",
            ],
        ),
    ]
    receipt = {}
    for project, path, roots, entries in references:
        document = export_terrain(
            path, project=project, src_roots=roots, entries=entries
        )
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
        for destination in [viewer / "maps", target / "maps"]:
            destination.mkdir(exist_ok=True)
            (destination / (project + ".json")).write_text(content)
        receipt[project] = {
            "source_digest": document["analysis"]["source_digest"],
            "export_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "functions": document["analysis"]["function_count"],
            "featured_functions": len(document["views"]["feature"]["nodes"]),
        }
    (target / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
