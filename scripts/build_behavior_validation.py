"""Bake source-current real-project behavior maps without touching those projects."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from flowcode.embeddings import CodeEmbedder
from flowcode.prototype import terrain_fixture
from flowcode.terrain import export_terrain


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ranking_comparison(behavior_map: dict) -> dict:
    changed = []
    multi_leaf = 0
    for layer in behavior_map["layers"].values():
        orders = layer["leaf_orders"]
        if len(orders["hybrid"]) <= 1:
            continue
        multi_leaf += 1
        if orders["project"] != orders["local"]:
            by_id = {node["id"]: node for node in layer["nodes"]}
            changed.append(
                {
                    "source_node_id": layer["source_node_id"],
                    "project_first": by_id[orders["project"][0]]["label"],
                    "local_first": by_id[orders["local"][0]]["label"],
                    "hybrid_first": by_id[orders["hybrid"][0]]["label"],
                }
            )
    return {
        "multi_leaf_layers": multi_leaf,
        "different_order_layers": len(changed),
        "examples": changed[:25],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", type=Path, required=True)
    parser.add_argument("--scribblescan", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("evidence/outcome-first"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = [
        {
            "id": "flowcode",
            "title": "Flow-Code",
            "path": root,
            "roots": [
                "src/flowcode",
                "experiments/3d-layered/app.js",
                "experiments/3d-layered/snapshot.js",
            ],
            "purpose": "Flow-Code analyzes source code across programming languages, extracts execution relationships, and presents source-grounded codebase behavior for unfamiliar readers.",
        },
        {
            "id": "portfolio",
            "title": "Portfolio",
            "path": args.portfolio.resolve(),
            "roots": ["main.py", "apis", "core", "static/scripts"],
            "purpose": "An interactive personal portfolio where visitors explore projects and interests, open connected documents, and change visual themes while preserving navigation.",
        },
        {
            "id": "scribblescan",
            "title": "ScribbleScan",
            "path": args.scribblescan.resolve(),
            "roots": ["app", "static/js"],
            "purpose": "ScribbleScan turns uploaded document images into editable digital text, organizes the transcription, and returns useful document results to the user.",
        },
    ]
    args.out.mkdir(parents=True, exist_ok=True)
    maps = args.out / "maps"
    maps.mkdir(exist_ok=True)
    embedder = CodeEmbedder()
    receipt = {"status": "running", "projects": {}}
    fresh_fixtures = {}
    for case in cases:
        print(f"Baking {case['id']}", flush=True)
        document = export_terrain(
            case["path"],
            project=case["id"],
            src_roots=case["roots"],
            embedder=embedder,
            purpose=case["purpose"],
        )
        map_path = maps / f"{case['id']}.json"
        map_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        fixture = terrain_fixture(document, title=case["title"])
        fresh_fixtures[case["id"]] = {
            "title": fixture["title"],
            "purpose": fixture["purpose"],
            "source_digest": fixture["coverage"]["source_digest"],
            "behaviors": fixture["behaviors"],
        }
        behavior = document["behaviors"]
        receipt["projects"][case["id"]] = {
            "map_sha256": digest(map_path),
            "source_digest": document["analysis"]["source_digest"],
            "functions": behavior["coverage"]["analyzed_functions"],
            "behaviors": len(behavior["behaviors"]),
            "unplaced": len(behavior["coverage"]["unplaced_function_ids"]),
            "entry_selection": document["analysis"]["entry_selection"],
            "detected_entries": document["entries"],
            "ranking": ranking_comparison(behavior),
        }
    existing_path = root / "experiments/3d-layered/behavior-fixtures.json"
    existing = json.loads(existing_path.read_text()) if existing_path.exists() else {}
    existing.update(fresh_fixtures)
    existing_path.write_text(
        json.dumps(existing, sort_keys=True, separators=(",", ":")) + "\n"
    )
    receipt["fixture_sha256"] = digest(existing_path)
    receipt["status"] = "passed"
    (args.out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
