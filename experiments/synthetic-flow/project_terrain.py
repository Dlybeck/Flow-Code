"""Project per-function embeddings to 2D with UMAP and render a scatter plot.

Color = source file (so we can see if modules cluster — natural boundary test).
Labels = function qname (short). Size = source line count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import umap


def main() -> None:
    emb_path = Path(sys.argv[1] if len(sys.argv) > 1 else "function_embeddings.json")
    png_out = Path(sys.argv[2] if len(sys.argv) > 2 else "terrain.png")
    json_out = Path(sys.argv[3] if len(sys.argv) > 3 else "terrain_coords.json")

    data = json.loads(emb_path.read_text())
    funcs = data["functions"]
    vectors = np.array([f["vector"] for f in funcs])
    qnames = [f["qname"] for f in funcs]
    files = [f["file"] for f in funcs]
    sizes = [f["source_lines"] for f in funcs]

    print(f"UMAP projecting {len(vectors)} vectors to 2D...")
    reducer = umap.UMAP(
        n_neighbors=min(15, len(vectors) - 1),
        min_dist=0.1,
        n_components=2,
        metric="cosine",
        random_state=42,
    )
    coords = reducer.fit_transform(vectors)

    # Color per file
    uniq_files = sorted(set(files))
    cmap = plt.get_cmap("tab10" if len(uniq_files) <= 10 else "tab20")
    file_to_color = {f: cmap(i % cmap.N) for i, f in enumerate(uniq_files)}

    fig, ax = plt.subplots(figsize=(14, 10))
    for f in uniq_files:
        idx = [i for i, ff in enumerate(files) if ff == f]
        ax.scatter(
            coords[idx, 0],
            coords[idx, 1],
            s=[max(30, sizes[i] * 3) for i in idx],
            c=[file_to_color[f]],
            alpha=0.75,
            edgecolors="black",
            linewidths=0.5,
            label=Path(f).name,
        )

    # Label every point; small font to avoid overlap hell
    for i, q in enumerate(qnames):
        short = q.split(".")[-1] if "." in q else q
        ax.annotate(
            short,
            (coords[i, 0], coords[i, 1]),
            fontsize=7,
            alpha=0.8,
            xytext=(3, 3),
            textcoords="offset points",
        )

    ax.legend(loc="best", fontsize=9, framealpha=0.9, title="source file")
    ax.set_title(f"Semantic terrain — {len(funcs)} functions, colored by file")
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(png_out, dpi=140, bbox_inches="tight")
    print(f"wrote {png_out}")

    json_out.write_text(
        json.dumps(
            {
                "points": [
                    {
                        "qname": qnames[i],
                        "file": files[i],
                        "x": float(coords[i, 0]),
                        "y": float(coords[i, 1]),
                        "source_lines": sizes[i],
                    }
                    for i in range(len(funcs))
                ]
            },
            indent=2,
        )
    )
    print(f"wrote {json_out}")


if __name__ == "__main__":
    main()
