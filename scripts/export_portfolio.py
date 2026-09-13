"""Build three reference snapshots and install the same viewer into Portfolio.

Run npm ci && npm run build in experiments/3d-layered first. Embeddings run
locally at build time, with content-addressed caching. Nothing is published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from flowcode.embeddings import CodeEmbedder
from flowcode.guides import attach_guide
from flowcode.terrain import export_terrain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", type=Path, required=True)
    parser.add_argument("--scribblescan", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    viewer = root / "experiments/3d-layered"
    references = [
        (
            "flowcode",
            root,
            [
                "src/flowcode",
                "experiments/3d-layered/app.js",
                "experiments/3d-layered/snapshot.js",
            ],
            ["flowcode.terrain.export_terrain"],
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
    purposes = {
        "scribblescan": "ScribbleScan turns uploaded handwritten notes and document images into editable digital text. It processes uploaded files, recognizes handwriting with OCR, and returns organized transcription results to the user.",
        "portfolio": "An interactive personal portfolio where visitors explore connected projects and interests on a spatial board, open project documents, and switch coherent visual themes while preserving navigation.",
        "flowcode": "Flow-Code analyzes source code across programming languages, extracts functions and call relationships, embeds code to measure semantic similarity, and visualizes meaningful code architecture as an interactive 3D terrain.",
    }
    guides = json.loads((root / "scripts/portfolio_guides.json").read_text())
    documents = {}
    embedder = CodeEmbedder()
    for project, path, roots, entries in references:
        print(f"Baking {project}", flush=True)
        documents[project] = export_terrain(
            path,
            project=project,
            src_roots=roots,
            entries=entries,
            embedder=embedder,
            purpose=purposes[project],
        )
        documents[project] = attach_guide(documents[project], guides[project])
    # Install only after every project's semantic analysis succeeds.
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
    receipt = {}
    for project, document in documents.items():
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
        for destination in [viewer / "maps", target / "maps"]:
            destination.mkdir(exist_ok=True)
            (destination / (project + ".json")).write_text(content)
        receipt[project] = {
            "embedding": document["analysis"]["embedding"],
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
