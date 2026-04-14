"""Overlay 'water' on the terrain: visit counts rendered as heat kernels.

Three modes:
  real       — blue water from real_trace.json
  predicted  — orange water from predicted_trace.json
  diverge    — both, plus per-point markers colored by divergence

Usage:
  python overlay_water.py {real|predicted|diverge} [out.png]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import gaussian_kde


def load_coords() -> dict:
    return {p["qname"]: p for p in json.loads(Path("terrain_coords.json").read_text())["points"]}


def load_visits(path: str) -> dict[str, int]:
    doc = json.loads(Path(path).read_text())
    if "in_embedding_set" in doc:
        return dict(doc["in_embedding_set"])
    return dict(doc.get("visit_counts", {}))


def water_density(coords: dict, visits: dict[str, int], grid_x, grid_y) -> np.ndarray:
    """Weighted KDE over the grid at traced-function positions."""
    pts_x: list[float] = []
    pts_y: list[float] = []
    weights: list[float] = []
    for qname, count in visits.items():
        if qname not in coords:
            continue
        p = coords[qname]
        pts_x.append(p["x"])
        pts_y.append(p["y"])
        weights.append(math.log1p(count))
    if not pts_x:
        return np.zeros_like(grid_x)
    pts = np.vstack([pts_x, pts_y])
    kde = gaussian_kde(pts, weights=np.array(weights), bw_method=0.18)
    Z = kde(np.vstack([grid_x.ravel(), grid_y.ravel()])).reshape(grid_x.shape)
    return Z


def render_terrain_base(ax, xi, yi, elevation):
    XI, YI = np.meshgrid(xi, yi)
    ax.contourf(XI, YI, elevation, levels=18, cmap="gist_earth", alpha=0.55)
    ax.contour(XI, YI, elevation, levels=10, colors="black", alpha=0.18, linewidths=0.4)


def make_water_cmap(color: str) -> LinearSegmentedColormap:
    """Transparent → color cmap so low water doesn't wash out the terrain."""
    import matplotlib.colors as mcolors
    rgb = mcolors.to_rgb(color)
    return LinearSegmentedColormap.from_list(
        f"water_{color}",
        [(1, 1, 1, 0), (*rgb, 0.25), (*rgb, 0.55), (*rgb, 0.85)],
    )


def annotate_points(ax, coords, highlight=None, faint=False):
    for qname, p in coords.items():
        if faint and (highlight is None or qname not in highlight):
            ax.scatter([p["x"]], [p["y"]], s=6, c="gray", alpha=0.25, zorder=3)
        else:
            ax.scatter([p["x"]], [p["y"]], s=10, c="black", alpha=0.5, zorder=3)
    return


def render_mode(mode: str, out_path: Path) -> None:
    coords = load_coords()
    grid = np.load("terrain_grid.npz")
    xi, yi, elevation = grid["xi"], grid["yi"], grid["elevation"]
    XI, YI = np.meshgrid(xi, yi)

    real = load_visits("real_trace.json") if mode in ("real", "diverge") else {}
    pred = load_visits("predicted_trace.json") if mode in ("predicted", "diverge") else {}

    fig, ax = plt.subplots(figsize=(14, 10))
    render_terrain_base(ax, xi, yi, elevation)

    if mode == "real":
        Z = water_density(coords, real, XI, YI)
        ax.contourf(XI, YI, Z, levels=14, cmap=make_water_cmap("#1f77b4"))
        title = "Real execution — water pools where code actually runs"
    elif mode == "predicted":
        Z = water_density(coords, pred, XI, YI)
        ax.contourf(XI, YI, Z, levels=14, cmap=make_water_cmap("#ff7f0e"))
        title = "Predicted execution — water pools where the LLM thinks code runs"
    else:  # diverge
        Zr = water_density(coords, real, XI, YI)
        Zp = water_density(coords, pred, XI, YI)
        ax.contourf(XI, YI, Zr, levels=12, cmap=make_water_cmap("#1f77b4"))
        ax.contourf(XI, YI, Zp, levels=12, cmap=make_water_cmap("#ff7f0e"))
        title = "Real (blue) vs predicted (orange) — overlap = matched flow"

    # Point markers: in diverge mode colored by category
    real_set = {q for q, c in real.items() if c > 0}
    pred_set = {q for q, c in pred.items() if c > 0}
    for qname, p in coords.items():
        in_real = qname in real_set
        in_pred = qname in pred_set
        if mode == "diverge":
            if in_real and in_pred:
                color, s = "#2ca02c", 26  # green - matched
            elif in_real and not in_pred:
                color, s = "#d62728", 32  # red - surprise (real only)
            elif in_pred and not in_real:
                color, s = "#ffd400", 32  # yellow - missed (predicted only)
            else:
                color, s = "lightgray", 6
            ax.scatter([p["x"]], [p["y"]], s=s, c=color, edgecolors="black",
                       linewidths=0.3, alpha=0.95, zorder=4)
        else:
            active = in_real if mode == "real" else in_pred
            color = "black" if active else "lightgray"
            alpha = 0.9 if active else 0.35
            s = 18 if active else 6
            ax.scatter([p["x"]], [p["y"]], s=s, c=color, alpha=alpha, zorder=4)

        # Label only if touched in this mode (keeps plot readable)
        if (mode == "real" and in_real) or (mode == "predicted" and in_pred) or (mode == "diverge" and (in_real or in_pred)):
            short = qname.split(".")[-1] if "." in qname else qname
            ax.annotate(short, (p["x"], p["y"]), fontsize=6, alpha=0.85,
                        xytext=(3, 3), textcoords="offset points", zorder=5)

    if mode == "diverge":
        from matplotlib.patches import Patch
        legend_elems = [
            Patch(facecolor="#2ca02c", edgecolor="black", label="matched (both real & predicted)"),
            Patch(facecolor="#d62728", edgecolor="black", label="real only (surprise)"),
            Patch(facecolor="#ffd400", edgecolor="black", label="predicted only (missed)"),
        ]
        ax.legend(handles=legend_elems, loc="best", fontsize=9)

    ax.set_title(title)
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    print(f"wrote {out_path}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "diverge"
    if mode not in ("real", "predicted", "diverge"):
        raise SystemExit("mode must be one of: real, predicted, diverge")
    default_out = {"real": "real_water.png", "predicted": "predicted_water.png", "diverge": "divergence.png"}[mode]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else default_out)
    render_mode(mode, out)


if __name__ == "__main__":
    main()
