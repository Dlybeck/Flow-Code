"""Build the hosted behavior prototype from existing portable fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flowcode.behaviors import build_behavior_map


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("experiments/3d-layered/prototype-fixtures.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("experiments/3d-layered/behavior-fixtures.json"),
    )
    args = parser.parse_args()
    fixtures = json.loads(args.fixtures.read_text())
    output = {}
    for project, fixture in sorted(fixtures.items()):
        behavior_map = fixture.get("behaviors") or build_behavior_map(
            fixture["nodes"],
            fixture["edges"],
            fixture.get("entrypoints", []),
        )
        output[project] = {
            "title": fixture.get("title", project),
            "purpose": fixture.get("purpose", ""),
            "source_digest": fixture.get("coverage", {}).get("source_digest"),
            "behaviors": behavior_map,
        }
    args.out.write_text(
        json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(
        json.dumps(
            {
                project: {
                    "behaviors": len(row["behaviors"]["behaviors"]),
                    "layers": len(row["behaviors"]["layers"]),
                    "unplaced": len(
                        row["behaviors"]["coverage"]["unplaced_function_ids"]
                    ),
                }
                for project, row in output.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
