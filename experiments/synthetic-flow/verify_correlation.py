"""Three correlation checks between tier embeddings and ground-truth flow structure."""
from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path


def cos(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def load(flow_path: str = "ground_truth_flow.json", emb_path: str = "tier_embeddings.json") -> tuple[dict, dict]:
    flow = json.loads(Path(flow_path).read_text())
    emb = json.loads(Path(emb_path).read_text())
    return flow, emb


def build_graph(flow: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    children = {n["id"]: list(n["children"]) for n in flow["nodes"]}
    parents: dict[str, list[str]] = {n["id"]: [] for n in flow["nodes"]}
    for nid, kids in children.items():
        for k in kids:
            parents[k].append(nid)
    return children, parents


def descendants(children: dict[str, list[str]], node_id: str) -> set[str]:
    out: set[str] = set()
    queue = list(children.get(node_id, []))
    while queue:
        cur = queue.pop(0)
        if cur in out:
            continue
        out.add(cur)
        queue.extend(children.get(cur, []))
    return out


def tree_distance(children: dict[str, list[str]], parents: dict[str, list[str]], a: str, b: str) -> int:
    """Undirected tree distance between two nodes."""
    if a == b:
        return 0
    # BFS from a
    seen = {a: 0}
    q = [a]
    while q:
        cur = q.pop(0)
        for nxt in children.get(cur, []) + parents.get(cur, []):
            if nxt in seen:
                continue
            seen[nxt] = seen[cur] + 1
            if nxt == b:
                return seen[nxt]
            q.append(nxt)
    return -1


def spearman(xs: list[float], ys: list[float]) -> float:
    def rank(vals: list[float]) -> list[float]:
        indexed = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(vals):
            j = i
            while j + 1 < len(vals) and vals[indexed[j + 1]] == vals[indexed[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                ranks[indexed[k]] = avg
            i = j + 1
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    n = len(xs)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    dx = math.sqrt(sum((r - mean_x) ** 2 for r in rx))
    dy = math.sqrt(sum((r - mean_y) ** 2 for r in ry))
    return num / (dx * dy) if dx and dy else 0.0


def ancestors_of(children: dict[str, list[str]], node_id: str, root: str) -> set[str]:
    """Walk up from node_id to root via BFS over the inverse edges."""
    parents_of: dict[str, list[str]] = {nid: [] for nid in children}
    for p, kids in children.items():
        for k in kids:
            parents_of[k].append(p)
    out: set[str] = set()
    q = list(parents_of.get(node_id, []))
    while q:
        cur = q.pop(0)
        if cur in out:
            continue
        out.add(cur)
        q.extend(parents_of.get(cur, []))
    return out


def test_a_containment(
    emb: dict, children: dict[str, list[str]], root: str
) -> tuple[float, list[str], list[str]]:
    """For each (parent, descendant), descendant should be closer to parent
    than any TRULY UNRELATED node (neither ancestor nor descendant). Ancestors
    are excluded because their tier embeddings contain the parent's content
    as a subset — they're expected to be close for the same containment reason."""
    node_ids = list(emb["nodes"].keys())
    vecs = {nid: emb["nodes"][nid]["vector"] for nid in node_ids}

    total = 0
    passes = 0
    failures: list[str] = []
    skipped: list[str] = []

    for parent in node_ids:
        desc = descendants(children, parent)
        if not desc:
            continue
        ancs = ancestors_of(children, parent, root)
        unrelated = [n for n in node_ids if n != parent and n not in desc and n not in ancs]
        if not unrelated:
            skipped.append(f"{parent} (no unrelated nodes exist — tree too small)")
            continue
        best_unrelated_sim = max(cos(vecs[parent], vecs[n]) for n in unrelated)
        for d in desc:
            total += 1
            d_sim = cos(vecs[parent], vecs[d])
            if d_sim > best_unrelated_sim:
                passes += 1
            else:
                failures.append(
                    f"{parent}→{d}: cos={d_sim:.3f} but best unrelated = {best_unrelated_sim:.3f}"
                )
    rate = passes / total if total else 0.0
    return rate, failures, skipped


def test_b_split_distinctness(emb: dict, flow: dict) -> dict:
    """At each split, the branches should be less similar to each other than
    to the common parent."""
    vecs = {nid: emb["nodes"][nid]["vector"] for nid in emb["nodes"]}
    results = []
    for nid_obj in flow["nodes"]:
        if len(nid_obj["children"]) < 2:
            continue
        parent = nid_obj["id"]
        branches = nid_obj["children"]
        for a, b in combinations(branches, 2):
            sib = cos(vecs[a], vecs[b])
            pa = cos(vecs[parent], vecs[a])
            pb = cos(vecs[parent], vecs[b])
            ok = sib < pa and sib < pb
            results.append({
                "split": parent,
                "branches": [a, b],
                "sibling_cos": sib,
                "parent_a_cos": pa,
                "parent_b_cos": pb,
                "pass": ok,
            })
    return {"pairs": results, "pass": all(r["pass"] for r in results)}


def test_c_distance_correlation(
    emb: dict, children: dict[str, list[str]], parents: dict[str, list[str]]
) -> dict:
    """Cosine distance vs tree distance across all pairs — expect negative Spearman
    (close in embedding space ↔ close in tree)."""
    node_ids = list(emb["nodes"].keys())
    vecs = {nid: emb["nodes"][nid]["vector"] for nid in node_ids}

    cos_dists: list[float] = []
    tree_dists: list[float] = []
    pairs: list[tuple[str, str]] = []

    for a, b in combinations(node_ids, 2):
        cd = 1.0 - cos(vecs[a], vecs[b])
        td = tree_distance(children, parents, a, b)
        cos_dists.append(cd)
        tree_dists.append(float(td))
        pairs.append((a, b))

    rho = spearman(cos_dists, tree_dists)
    return {"spearman": rho, "n_pairs": len(pairs)}


def main() -> None:
    import sys as _sys
    if len(_sys.argv) >= 3:
        flow, emb = load(_sys.argv[1], _sys.argv[2])
    else:
        flow, emb = load()
    children, parents = build_graph(flow)

    print("=" * 60)
    print("TEST A — Containment")
    print("=" * 60)
    rate, failures, skipped = test_a_containment(emb, children, flow["root"])
    verdict_a = "PASS" if rate >= 0.95 else "FAIL"
    print(f"pass rate: {rate:.1%}  → {verdict_a} (target ≥95%)")
    if failures:
        print("failing pairs:")
        for f in failures:
            print(f"  {f}")
    if skipped:
        print("skipped (no unrelated nodes to compare against):")
        for s in skipped:
            print(f"  {s}")

    print()
    print("=" * 60)
    print("TEST B — Split distinctness")
    print("=" * 60)
    b_res = test_b_split_distinctness(emb, flow)
    for r in b_res["pairs"]:
        mark = "✓" if r["pass"] else "✗"
        print(
            f"  {mark} split at {r['split']}: branches {r['branches']}  "
            f"sibling={r['sibling_cos']:.3f}  parent→a={r['parent_a_cos']:.3f}  "
            f"parent→b={r['parent_b_cos']:.3f}"
        )
    verdict_b = "PASS" if b_res["pass"] else "FAIL"
    print(f"→ {verdict_b}")

    print()
    print("=" * 60)
    print("TEST C — Embedding-distance vs tree-distance correlation")
    print("=" * 60)
    c_res = test_c_distance_correlation(emb, children, parents)
    rho = c_res["spearman"]
    # Negative Spearman means: as tree-dist grows, cos-dist grows too (i.e. they agree).
    # Wait — we computed cos_dist (1-sim) and tree_dist (hops). BOTH should grow together,
    # so expect POSITIVE Spearman.
    verdict_c = "PASS" if rho >= 0.5 else ("WEAK" if rho >= 0.2 else "FAIL")
    print(f"Spearman(cos-distance, tree-distance) = {rho:+.3f} over {c_res['n_pairs']} pairs")
    print(f"  (positive = embedding distance agrees with tree distance)")
    print(f"→ {verdict_c} (≥0.5 pass, 0.2–0.5 weak, <0.2 fail)")

    print()
    print("=" * 60)
    print("OVERALL")
    print("=" * 60)
    verdicts = [verdict_a, verdict_b, verdict_c]
    if all(v == "PASS" for v in verdicts):
        overall = "CORRELATION HOLDS — scale up next"
    elif verdict_a == "PASS" and verdict_b == "PASS":
        overall = "STRUCTURE PARTIALLY ENCODED — try weighted concat before scaling"
    else:
        overall = "HYPOTHESIS NOT SUPPORTED — revisit embedding strategy"
    print(overall)


if __name__ == "__main__":
    main()
