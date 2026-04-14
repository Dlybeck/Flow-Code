"""Execution-score with real AND predicted traces overlaid.

Real: ordered events from real_trace.json (178 calls).
Predicted: LLM-ordered entries from predicted_trace.json, each expanded by
approx_calls to form a sequence (~84 calls).

Both are plotted with normalized time (0→1) on X, same semantic 1D position on Y.
Divergence = vertical distance between the two melodies at the same proportional time.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import umap


def build_1d_projection() -> tuple[dict[str, float], dict[str, str]]:
    emb = json.loads(Path("function_embeddings.json").read_text())
    qname_to_vec = {f["qname"]: np.array(f["vector"]) for f in emb["functions"]}
    qname_to_file = {f["qname"]: f["file"] for f in emb["functions"]}
    qnames = sorted(qname_to_vec.keys())
    vectors = np.array([qname_to_vec[q] for q in qnames])
    reducer = umap.UMAP(
        n_components=1, n_neighbors=15, min_dist=0.05,
        metric="cosine", random_state=42,
    )
    ys = reducer.fit_transform(vectors).ravel()
    return dict(zip(qnames, ys)), qname_to_file


def real_sequence() -> list[str]:
    trace = json.loads(Path("real_trace.json").read_text())
    return [e["qname"] for e in trace["events"]]


def predicted_sequence() -> list[str]:
    pred = json.loads(Path("predicted_trace.json").read_text())
    seq: list[str] = []
    for item in pred["predictions"]:
        q = item["qname"]
        n = int(item.get("approx_calls", 1) or 1)
        seq.extend([q] * n)
    return seq


def plot_line(ax, seq: list[str], qname_to_y: dict[str, float], color: str, label: str):
    xs: list[float] = []
    ys: list[float] = []
    n = len(seq)
    for i, q in enumerate(seq):
        if q not in qname_to_y:
            continue
        xs.append(i / max(1, n - 1))
        ys.append(qname_to_y[q])
    ax.plot(xs, ys, color=color, alpha=0.55, linewidth=1.1, zorder=2, label=label)
    ax.scatter(xs, ys, s=18, c=color, edgecolors="black", linewidths=0.25,
               alpha=0.8, zorder=3)
    return xs, ys


def main() -> None:
    qname_to_y, qname_to_file = build_1d_projection()
    real = real_sequence()
    pred = predicted_sequence()

    print(f"real: {len(real)} calls, predicted: {len(pred)} calls")

    fig, (ax_top, ax_depth) = plt.subplots(
        2, 1, figsize=(16, 9), sharex=True,
        gridspec_kw={"height_ratios": [4, 1]},
    )

    # Semantic bands per file (light)
    files = sorted(set(qname_to_file.values()))
    cmap = plt.get_cmap("tab10" if len(files) <= 10 else "tab20")
    file_to_color = {f: cmap(i % cmap.N) for i, f in enumerate(files)}
    for f in files:
        qs = [q for q, ff in qname_to_file.items() if ff == f]
        if qs:
            vals = [qname_to_y[q] for q in qs]
            ax_top.axhspan(min(vals), max(vals), color=file_to_color[f], alpha=0.05)

    # Two melodies
    rx, ry = plot_line(ax_top, real, qname_to_y, "#1f77b4", "real")
    px, py = plot_line(ax_top, pred, qname_to_y, "#ff7f0e", "predicted")

    # Label functions at big vertical jumps on each line (avoid clutter)
    def annotate_jumps(xs, ys, seq, color):
        prev_y = None
        for i, (x, y) in enumerate(zip(xs, ys)):
            if prev_y is None or abs(y - prev_y) > 1.2:
                short = seq[i].split(".")[-1] if "." in seq[i] else seq[i]
                ax_top.annotate(short, (x, y), fontsize=6, alpha=0.85, color=color,
                                xytext=(3, 4), textcoords="offset points", zorder=4)
            prev_y = y
    annotate_jumps(rx, ry, [q for q in real if q in qname_to_y], "#1f3b66")
    annotate_jumps(px, py, [q for q in pred if q in qname_to_y], "#a0430a")

    ax_top.set_title("Execution score — real (blue) vs predicted (orange). Same semantic height = melodies agree.")
    ax_top.set_ylabel("semantic position (1D UMAP)")
    ax_top.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax_top.grid(True, alpha=0.25)

    # Call depth below (real only — predicted has no depth info)
    trace = json.loads(Path("real_trace.json").read_text())
    n = len(trace["events"])
    xs_d = [i / max(1, n - 1) for i in range(n)]
    ys_d = [e.get("depth", 0) for e in trace["events"]]
    ax_depth.fill_between(xs_d, 0, ys_d, step="post", color="#4c78a8", alpha=0.35)
    ax_depth.plot(xs_d, ys_d, color="#1f3b66", linewidth=0.7)
    ax_depth.set_xlabel("normalized time")
    ax_depth.set_ylabel("real call depth")
    ax_depth.grid(True, alpha=0.25)

    plt.tight_layout()
    out = Path("execution_score_duet.png")
    plt.savefig(out, dpi=140, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
