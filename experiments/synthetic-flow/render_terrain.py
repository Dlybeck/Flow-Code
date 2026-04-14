"""Render inverted-density terrain: dense clusters = valleys, isolated code = peaks.

Reads `terrain_coords.json` (UMAP 2D projection) and builds a KDE-based contour
map. Elevation is inverted density so the metaphor holds: you see hills and
basins. Points plotted on top with tiny labels.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde


def render(coords_path: Path, out_path: Path, grid_px: int = 300) -> None:
    doc = json.loads(coords_path.read_text())
    pts = doc["points"]
    xs = np.array([p["x"] for p in pts])
    ys = np.array([p["y"] for p in pts])
    files = [p["file"] for p in pts]
    qnames = [p["qname"] for p in pts]

    # KDE on the point cloud
    kde = gaussian_kde(np.vstack([xs, ys]), bw_method=0.25)

    pad_x = (xs.max() - xs.min()) * 0.1
    pad_y = (ys.max() - ys.min()) * 0.1
    xi = np.linspace(xs.min() - pad_x, xs.max() + pad_x, grid_px)
    yi = np.linspace(ys.min() - pad_y, ys.max() + pad_y, grid_px)
    XI, YI = np.meshgrid(xi, yi)
    Z = kde(np.vstack([XI.ravel(), YI.ravel()])).reshape(XI.shape)

    # Invert: max density → low elevation, sparse → high
    elevation = Z.max() - Z

    fig, ax = plt.subplots(figsize=(14, 10))
    # Filled contour — gist_earth is a terrain-like colormap
    cf = ax.contourf(XI, YI, elevation, levels=18, cmap="gist_earth", alpha=0.85)
    # Thin contour lines for readability
    ax.contour(XI, YI, elevation, levels=10, colors="black", alpha=0.25, linewidths=0.5)

    # Points colored by file, markers small
    uniq_files = sorted(set(files))
    cmap = plt.get_cmap("tab10" if len(uniq_files) <= 10 else "tab20")
    file_to_color = {f: cmap(i % cmap.N) for i, f in enumerate(uniq_files)}
    for f in uniq_files:
        idx = [i for i, ff in enumerate(files) if ff == f]
        ax.scatter(
            xs[idx],
            ys[idx],
            s=18,
            c=[file_to_color[f]],
            edgecolors="black",
            linewidths=0.3,
            alpha=0.9,
            label=Path(f).name,
            zorder=3,
        )

    # Labels — only for short names, small font
    for i, q in enumerate(qnames):
        short = q.split(".")[-1] if "." in q else q
        ax.annotate(
            short,
            (xs[i], ys[i]),
            fontsize=6,
            alpha=0.75,
            xytext=(3, 3),
            textcoords="offset points",
            zorder=4,
        )

    cbar = fig.colorbar(cf, ax=ax, shrink=0.7)
    cbar.set_label("elevation (inverted density)")
    ax.legend(loc="best", fontsize=8, framealpha=0.9, title="source file")
    ax.set_title("Semantic terrain — dense clusters are valleys, isolated code is peaks")
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    print(f"wrote {out_path}")

    # Also save the grid for water rendering to reuse
    grid_out = out_path.with_name("terrain_grid.npz")
    np.savez(grid_out, xi=xi, yi=yi, elevation=elevation)
    print(f"wrote {grid_out}")


if __name__ == "__main__":
    render(Path("terrain_coords.json"), Path("terrain.png"))
