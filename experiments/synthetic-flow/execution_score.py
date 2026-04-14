"""Execution-score view: X = time (call index), Y = 1D semantic projection.

Reads real_trace.json (ordered events) + function_embeddings.json (vectors).
Projects embeddings to 1D with UMAP and plots the trace as a timeline.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import umap


def main() -> None:
    emb = json.loads(Path("function_embeddings.json").read_text())
    trace = json.loads(Path("real_trace.json").read_text())

    qname_to_vec = {f["qname"]: np.array(f["vector"]) for f in emb["functions"]}
    qname_to_file = {f["qname"]: f["file"] for f in emb["functions"]}
    all_qnames = sorted(qname_to_vec.keys())
    vectors = np.array([qname_to_vec[q] for q in all_qnames])

    print("UMAP → 1D...")
    reducer = umap.UMAP(n_components=1, n_neighbors=15, min_dist=0.05,
                       metric="cosine", random_state=42)
    ys = reducer.fit_transform(vectors).ravel()
    qname_to_y = dict(zip(all_qnames, ys))

    # Build the timeline from the ordered event list
    events = trace["events"]
    series_t: list[int] = []
    series_y: list[float] = []
    series_q: list[str] = []
    series_depth: list[int] = []
    for i, ev in enumerate(events):
        q = ev["qname"]
        if q not in qname_to_y:
            continue
        series_t.append(i)
        series_y.append(float(qname_to_y[q]))
        series_q.append(q)
        series_depth.append(ev.get("depth", 0))

    # Color per source file
    files_in_trace = sorted(set(qname_to_file[q] for q in series_q))
    cmap = plt.get_cmap("tab10" if len(files_in_trace) <= 10 else "tab20")
    file_to_color = {f: cmap(i % cmap.N) for i, f in enumerate(files_in_trace)}

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(16, 9), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # Top: semantic position over time, connected path + points
    ax_top.plot(series_t, series_y, color="gray", alpha=0.4, linewidth=0.8, zorder=1)
    for i, q in enumerate(series_q):
        f = qname_to_file[q]
        ax_top.scatter(series_t[i], series_y[i], s=22, c=[file_to_color[f]],
                       edgecolors="black", linewidths=0.3, alpha=0.85, zorder=2)

    # Labels: show qname at transition points (when semantic position jumps)
    prev_y: float | None = None
    for i, (t, y, q) in enumerate(zip(series_t, series_y, series_q)):
        big_jump = prev_y is None or abs(y - prev_y) > 0.8
        if big_jump:
            short = q.split(".")[-1] if "." in q else q
            ax_top.annotate(short, (t, y), fontsize=6.5, alpha=0.85,
                            xytext=(3, 4), textcoords="offset points", zorder=3)
        prev_y = y

    # Semantic bands — show where each file lives in 1D space
    for f in files_in_trace:
        qs = [q for q in all_qnames if qname_to_file[q] == f]
        ys_f = [qname_to_y[q] for q in qs]
        if ys_f:
            ax_top.axhspan(min(ys_f), max(ys_f), color=file_to_color[f], alpha=0.07)

    ax_top.set_ylabel("semantic position (1D UMAP)")
    ax_top.set_title("Execution score — time → right, semantic height → up")
    ax_top.grid(True, alpha=0.25)

    # File legend (dedupe)
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=file_to_color[f], edgecolor="black", label=Path(f).name)
               for f in files_in_trace]
    ax_top.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9, title="file")

    # Bottom: call depth as flame-graph-ish
    ax_bot.fill_between(series_t, 0, series_depth, step="post",
                        color="#4c78a8", alpha=0.4)
    ax_bot.plot(series_t, series_depth, color="#1f3b66", linewidth=0.8)
    ax_bot.set_xlabel("call index (time)")
    ax_bot.set_ylabel("call depth")
    ax_bot.grid(True, alpha=0.25)

    plt.tight_layout()
    out = Path("execution_score.png")
    plt.savefig(out, dpi=140, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
