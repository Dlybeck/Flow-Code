"""Build graph.json for the 3D layered prototype.

Emits multiple layout signals so the browser can toggle between variants:
  - (x_umap, y_umap)  : UMAP-based layout (pure embedding)
  - (x_fan, y_fan)    : radial fan — ski-slope layout from call graph + embedding
                        sibling ordering. Radial distance from each peak = depth.
  - depth             : call-graph depth (time)
  - importance        : ancestors × descendants (path flow width)
  - semantic_density  : avg cos-sim to k-nearest neighbors in embedding space

Renderer composes height = f(depth, importance, semantic_density), with a
monotonic clamp applied client-side.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from parse_calls import parse_directory

MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"
STEP = 3.5          # radial distance per depth level
MAX_WEDGE_DEG = 120 # max fan-out per node
SHRINK = 0.9        # wedge shrink factor per level


def compute_importance(
    qnames: list[str],
    calls_by_q: dict[str, list[str]],
    functions: dict | None = None,
    density: dict[str, float] | None = None,
) -> dict[str, float]:
    """Architectural importance = embedding novelty × substance.

    - novelty: 1 − semantic_density. How unlike the rest of the codebase this
      function's embedding is. High = a conceptually distinct idea expressed
      here (not boilerplate).
    - substance: log(LOC + 1), normalized. Size proxy for "there's real work
      in this function." Without it, a 2-line novelty outlier (an obscure
      edge-case helper) can outrank a substantive one.

    Deliberately DROPS graph-centrality (betweenness, fan-in) — those signals
    reward hot-path utilities (loggers, setup, error paths) that run often
    but aren't conceptually what the code is about. A reader pointing at the
    map would flag "the novel concept with real code behind it" as important,
    not "the function every stack trace passes through."
    """
    if density:
        novelty = {q: max(0.0, 1.0 - density.get(q, 0.5)) for q in qnames}
    else:
        novelty = {q: 0.5 for q in qnames}

    if functions:
        # source_lines is already attached to each FuncInfo; use it directly.
        loc = {q: max(1, getattr(functions[q], "source", "").count("\n") + 1) for q in qnames}
    else:
        loc = {q: 10 for q in qnames}  # neutral fallback
    log_loc = {q: math.log(loc[q] + 1) for q in qnames}
    ll_min = min(log_loc.values(), default=0.0)
    ll_max = max(log_loc.values(), default=1.0)
    ll_range = ll_max - ll_min if ll_max > ll_min else 1.0
    # Normalize substance to [0, 1] but floor at 0.15 — a novel 5-line function
    # still deserves *some* prominence, just not the full ridge treatment.
    substance = {q: 0.15 + 0.85 * (log_loc[q] - ll_min) / ll_range for q in qnames}

    raw = {q: novelty[q] * substance[q] for q in qnames}
    max_raw = max(raw.values(), default=1.0) or 1.0
    return {q: raw[q] / max_raw for q in qnames}


def pull_toward_parents(
    coords: dict[str, tuple[float, float]],
    qnames: list[str],
    calls_by_q: dict[str, list[str]],
    depths: dict[str, int],
    iterations: int = 4,
    strength: float = 0.35,
) -> dict[str, tuple[float, float]]:
    """Move each non-entry node partway toward the centroid of its parents'
    XY positions. Over a few iterations this makes parent-child physically
    adjacent so the Delaunay mesh forms smooth slopes from peaks to leaves."""
    callers: dict[str, list[str]] = {q: [] for q in qnames}
    for q, outs in calls_by_q.items():
        for c in outs:
            if c in callers:
                callers[c].append(q)

    pos = dict(coords)
    for _ in range(iterations):
        new_pos = dict(pos)
        # Apply in depth order so each layer uses its parents' already-placed positions
        for q in sorted(qnames, key=lambda x: depths[x]):
            ps = callers[q]
            if not ps:
                continue
            cx = sum(pos[p][0] for p in ps) / len(ps)
            cy = sum(pos[p][1] for p in ps) / len(ps)
            new_pos[q] = (
                pos[q][0] * (1 - strength) + cx * strength,
                pos[q][1] * (1 - strength) + cy * strength,
            )
        pos = new_pos
    return pos


def compute_depths(qnames: list[str], calls_by_q: dict[str, list[str]]) -> dict[str, int]:
    """Longest-path depth from any caller-less root. Cycle-safe.

    Uses two-pass (read old, write new) per iteration so each pass propagates
    depth by at most +1. Hard-caps final depth at len(qnames)-1 (longest simple path).
    """
    callers: dict[str, set[str]] = {q: set() for q in qnames}
    for q, outs in calls_by_q.items():
        for c in outs:
            if c in callers and c != q:  # skip self-recursion
                callers[c].add(q)

    depth: dict[str, int] = {q: 0 for q in qnames if not callers[q]}
    # Cap at a reasonable slope height even if there's a 30-deep call chain.
    # Keeps the mountain legible for any codebase.
    max_allowed = min(12, max(1, len(qnames) - 1))

    changed = True
    passes = 0
    while changed and passes < len(qnames):
        changed = False
        passes += 1
        new_depth = dict(depth)
        for q in qnames:
            inbound = [p for p in callers[q] if p in depth]
            if not inbound:
                continue
            nd = 1 + max(depth[p] for p in inbound)
            if nd > max_allowed:
                nd = max_allowed
            if q not in new_depth or new_depth[q] < nd:
                new_depth[q] = nd
                changed = True
        depth = new_depth

    for q in qnames:
        depth.setdefault(q, 0)
    return depth


def compute_depths_old(qnames: list[str], calls_by_q: dict[str, list[str]]) -> dict[str, int]:
    """Depth = longest path from an entry point. Entry = no inbound edges."""
    callers: dict[str, set[str]] = {q: set() for q in qnames}
    for q, callees in calls_by_q.items():
        for c in callees:
            if c in callers:
                callers[c].add(q)

    depth: dict[str, int] = {q: 0 for q in qnames if not callers[q]}
    # iterate to convergence; bound iterations to break cycles safely
    changed = True
    passes = 0
    while changed and passes < len(qnames) + 5:
        changed = False
        passes += 1
        for q in qnames:
            inbound = callers[q]
            if not inbound:
                continue
            known_inbound = [p for p in inbound if p in depth]
            if not known_inbound:
                continue
            new_d = 1 + max(depth[p] for p in known_inbound)
            if q not in depth or depth[q] < new_d:
                depth[q] = new_d
                changed = True

    # Any leftover (e.g. isolated cycle nodes): assign to 0
    for q in qnames:
        depth.setdefault(q, 0)
    return depth


def embed_and_project(functions: dict) -> tuple[dict[str, tuple[float, float]], int]:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import umap

    print(f"Loading {MODEL_NAME} on CPU...", flush=True)
    model = SentenceTransformer(MODEL_NAME, trust_remote_code=True, device="cpu")

    qnames = sorted(functions.keys())
    # Truncate pathologically long sources — Jina v2 caps at 8192 tokens (~32k chars)
    MAX_CHARS = 20000
    texts = [functions[q].source[:MAX_CHARS] for q in qnames]
    print(f"Embedding {len(qnames)} functions (CPU, batch=4)...", flush=True)
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=4)

    print("UMAP → 2D...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=min(15, len(qnames) - 1),
        min_dist=0.15,
        metric="cosine",
        random_state=42,
    )
    vecs_np = np.asarray(vectors)
    coords = reducer.fit_transform(vecs_np)
    coords = _relax_overlap(coords, min_dist=1.3, iterations=200)
    return (
        {q: (float(coords[i, 0]), float(coords[i, 1])) for i, q in enumerate(qnames)},
        {q: vecs_np[i].tolist() for i, q in enumerate(qnames)},
        len(vectors[0]),
    )


def _relax_overlap(coords, min_dist: float = 1.3, iterations: int = 200):
    """Vectorized push-apart relaxation so no two points sit closer than min_dist.
    Preserves rough layout from UMAP but guarantees visibility from top-down."""
    import numpy as np
    pts = np.asarray(coords, dtype=float).copy()
    for _ in range(iterations):
        diffs = pts[:, None, :] - pts[None, :, :]
        dists = np.sqrt((diffs ** 2).sum(-1))
        np.fill_diagonal(dists, np.inf)
        if dists.min() >= min_dist:
            break
        # For each overlapping pair, push apart along their vector
        mask = dists < min_dist
        unit = np.zeros_like(diffs)
        nonzero = dists > 1e-8
        unit[nonzero] = diffs[nonzero] / dists[nonzero, None]
        push = np.where(mask[..., None], unit * ((min_dist - dists)[..., None] * 0.5), 0.0)
        # Jitter coincident points
        coincident = dists < 1e-6
        if coincident.any():
            jitter = np.random.default_rng(0).standard_normal(pts.shape) * 0.05
            pts += jitter * coincident.any(axis=1)[:, None] * 0.01
        pts += push.sum(axis=1)
    return pts


def _cos_sim(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def compute_semantic_density(qnames: list[str], embeddings: dict[str, list[float]], k: int = 10) -> dict[str, float]:
    """For each node: avg cosine similarity to k nearest neighbors in embedding space.
    High = in a dense concept neighborhood. Normalized to [0, 1]."""
    import numpy as np
    vecs = np.array([embeddings[q] for q in qnames])
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vecs_n = vecs / norms
    sims = vecs_n @ vecs_n.T
    np.fill_diagonal(sims, -np.inf)
    kk = min(k, len(qnames) - 1)
    if kk < 1:
        return {q: 0.5 for q in qnames}
    topk = np.sort(sims, axis=1)[:, -kk:]
    avg = topk.mean(axis=1)
    mn, mx = avg.min(), avg.max()
    if mx > mn:
        scaled = (avg - mn) / (mx - mn)
    else:
        scaled = np.full_like(avg, 0.5)
    return {q: float(scaled[i]) for i, q in enumerate(qnames)}


def radial_fan_layout(
    qnames: list[str],
    callees_of: dict[str, list[str]],
    callers_of: dict[str, list[str]],
    embeddings: dict[str, list[float]],
    density: dict[str, float],
    importance: dict[str, float] | None = None,
) -> tuple[dict[str, tuple[float, float]], dict[str, float], list[str]]:
    """Ski-slope layout: one virtual peak at origin, entire slope fans within 120° south.

    A synthetic "__ROOT__" sits at origin with a 120° wedge aimed south. All real
    entry-point functions (no callers in the parsed set) are placed as its children,
    which means the whole codebase forms a single mountain with a single directional
    slope. Orphan peaks (no callers and no callees) are moved behind the mountain so
    they don't clutter the slope.

    Sibling ordering inside every wedge uses greedy NN on embedding cosine similarity,
    so semantically related subtrees sit angularly adjacent.
    """
    # Identify real peaks (no callers in the set).
    real_peaks = [q for q in qnames if not callers_of.get(q)]
    if not real_peaks:
        real_peaks = [qnames[0]] if qnames else []

    # Filter: peaks with ≥1 child form the mountain; peaks with no children
    # are orphans (looks like dead code to the parser) and get stashed aside.
    connected_peaks = [p for p in real_peaks if callees_of.get(p)]
    orphan_peaks = [p for p in real_peaks if not callees_of.get(p)]
    if not connected_peaks:
        connected_peaks = real_peaks
        orphan_peaks = []

    # Inject a synthetic VIRTUAL root. All connected peaks become its children —
    # forcing a single peak at origin and a single 120° slope south.
    VIRTUAL = "__ROOT__"
    L_callees: dict[str, list[str]] = {q: list(callees_of.get(q, [])) for q in qnames}
    L_callers: dict[str, list[str]] = {q: list(callers_of.get(q, [])) for q in qnames}
    L_callees[VIRTUAL] = list(connected_peaks)
    L_callers[VIRTUAL] = []
    for p in connected_peaks:
        L_callers[p] = [VIRTUAL]
    L_qnames = list(qnames) + [VIRTUAL]

    # Primary-parent spanning tree rooted at VIRTUAL.
    assigned: set[str] = {VIRTUAL}
    primary_children: dict[str, list[str]] = {q: [] for q in L_qnames}
    frontier = [VIRTUAL]
    while frontier:
        parent = frontier.pop(0)
        for child in L_callees.get(parent, []):
            if child in assigned:
                continue
            parent_candidates = sorted(c for c in L_callers.get(child, []) if c in assigned)
            if parent_candidates and parent_candidates[0] == parent:
                primary_children[parent].append(child)
                assigned.add(child)
                frontier.append(child)

    # Cycle-only nodes → treat as orphans.
    for q in qnames:
        if q not in assigned:
            orphan_peaks.append(q)
            assigned.add(q)

    # Subtree size (via primary-children tree = DAG-safe because we built a tree).
    def subtree_size(q: str) -> int:
        stack = [q]
        seen: set[str] = set()
        n = 0
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            n += 1
            stack.extend(primary_children.get(cur, []))
        return n

    max_wedge = math.radians(MAX_WEDGE_DEG)
    positions: dict[str, tuple[float, float]] = {}

    # Polar layout: every node's distance from origin = depth × STEP.
    # Children are always further out than their parents — no backward edges.
    # Each node owns an angular range within its parent's range; the whole tree
    # lives inside a single 120° wedge aimed south from origin.
    south = -math.pi / 2
    angle_range: dict[str, tuple[float, float]] = {
        VIRTUAL: (south - max_wedge / 2, south + max_wedge / 2),
    }
    radii: dict[str, float] = {VIRTUAL: 0.0}
    # VIRTUAL is at origin; don't add to positions (it's only for angular bookkeeping)

    def nn_chain(children: list[str], ref: str) -> list[str]:
        """Greedy nearest-neighbor ordering by embedding cosine similarity."""
        if not children:
            return []
        ref_emb = embeddings.get(ref)
        remaining = list(children)
        if ref_emb:
            first = max(remaining, key=lambda c: _cos_sim(embeddings.get(c), ref_emb))
        else:
            first = remaining[0]
        ordered = [first]
        remaining.remove(first)
        while remaining:
            last_emb = embeddings.get(ordered[-1])
            nxt = max(remaining, key=lambda c: _cos_sim(embeddings.get(c), last_emb))
            ordered.append(nxt)
            remaining.remove(nxt)
        return ordered

    angles: dict[str, float] = {}  # node → polar angle of final position

    def _clamp_to_wedge(angle: float, a_min: float, a_max: float) -> float:
        """Wrap `angle` onto the same 2π cycle as the wedge, then clamp."""
        mid = (a_min + a_max) / 2
        while angle < mid - math.pi:
            angle += 2 * math.pi
        while angle > mid + math.pi:
            angle -= 2 * math.pi
        return max(a_min, min(a_max, angle))

    def barycenter_order(parent: str, kids: list[str]) -> list[str]:
        """Sibling order that minimizes edge crossings: sort by the circular
        mean of each child's non-parent neighbors' angles."""
        if len(kids) < 2:
            return list(kids)
        a_min, a_max = angle_range[parent]
        kid_pref: dict[str, float] = {}
        for k in kids:
            neighbor_angles: list[float] = []
            for n in callers_of.get(k, []):
                if n != parent and n in angles:
                    neighbor_angles.append(angles[n])
            for n in callees_of.get(k, []):
                if n in angles:
                    neighbor_angles.append(angles[n])
            if neighbor_angles:
                s = sum(math.sin(a) for a in neighbor_angles)
                c = sum(math.cos(a) for a in neighbor_angles)
                pref = math.atan2(s, c)
            else:
                pref = angles.get(k, (a_min + a_max) / 2)
            kid_pref[k] = _clamp_to_wedge(pref, a_min, a_max)
        return sorted(kids, key=lambda k: kid_pref[k])

    def place_tree(order_fn) -> None:
        """Run a BFS from VIRTUAL, placing children in the order returned by order_fn.
        Writes into `positions`, `angles`, `angle_range`, `radii`."""
        # Reset mutable state (preserves VIRTUAL's initial wedge / radius)
        angles.clear()
        positions.clear()
        angle_range_local = {VIRTUAL: angle_range[VIRTUAL]}
        radii_local = {VIRTUAL: 0.0}
        queue = [VIRTUAL]
        while queue:
            parent = queue.pop(0)
            kids = primary_children[parent]
            if not kids:
                continue
            a_min, a_max = angle_range_local[parent]
            a_width = a_max - a_min
            parent_radius = radii_local[parent]
            # Update the outer angle_range so order_fn can read parent's wedge
            angle_range[parent] = (a_min, a_max)
            ordered = order_fn(parent, kids)
            sizes = [max(1, subtree_size(c)) for c in ordered]
            total = sum(sizes)
            start = a_min
            for k, s in zip(ordered, sizes):
                slot_w = a_width * (s / total)
                slot_min, slot_max = start, start + slot_w
                angle_range_local[k] = (slot_min, slot_max)
                angle_range[k] = (slot_min, slot_max)
                k_angle = (slot_min + slot_max) / 2
                k_radius = parent_radius + STEP
                radii_local[k] = k_radius
                radii[k] = k_radius
                positions[k] = (k_radius * math.cos(k_angle), k_radius * math.sin(k_angle))
                angles[k] = k_angle
                queue.append(k)
                start = slot_max

    # Pass 0: seed with NN-chain ordering so we have initial angles
    place_tree(lambda parent, kids: nn_chain(kids, parent))

    # Passes 1..N: barycenter reorder, using fresh angles each time
    BARYCENTER_ITERATIONS = 10
    for _ in range(BARYCENTER_ITERATIONS):
        place_tree(barycenter_order)

    # Place orphan peaks behind the mountain (north of origin) so they don't
    # clutter the south-facing slope. Arrange them in a compact grid.
    placed_xs = [positions[q][0] for q in qnames if q in positions]
    placed_ys = [positions[q][1] for q in qnames if q in positions]
    mountain_south = min(placed_ys) if placed_ys else -10.0
    orphan_offset_y = (max(placed_ys) if placed_ys else 5.0) + 4.0
    side = max(1, math.ceil(math.sqrt(len(orphan_peaks))))
    for i, p in enumerate(orphan_peaks):
        row, col = i // side, i % side
        positions[p] = ((col - side / 2) * 1.8, orphan_offset_y + row * 1.8)

    # --- Relative-descent heights, clamped to [20°, 60°] slope range ---
    # Every edge descends at least 20° (never level) and at most 60°. The density
    # delta between parent and child decides where each edge lands in that range:
    # the largest density drop in the graph = 60° slope, the smallest = 20°.
    PEAK_HEIGHT = 18.0
    density_lookup = {**density, VIRTUAL: 1.0}

    # Pass 1: gather raw "signal" per primary edge (p_density - c_density, can be
    # negative if child is denser). We use the full range so "denser child" still
    # gets the minimum 20° slope; steepest density drop gets 60°.
    raw_signals: list[float] = []
    edges_list: list[tuple[str, str]] = []
    for parent, kids in primary_children.items():
        p_d = density_lookup.get(parent, 0.5)
        for c in kids:
            c_d = density_lookup.get(c, 0.0)
            raw_signals.append(p_d - c_d)
            edges_list.append((parent, c))

    # Normalize: smallest signal → 0, largest → 1
    if raw_signals:
        smin = min(raw_signals)
        smax = max(raw_signals)
        srange = smax - smin if smax > smin else 1.0
    else:
        smin, srange = 0.0, 1.0

    # Slope range. Regular terrain clamps to 10°–60°.
    # Important chains may drop as low as 3° so architectural spines read as
    # visible ridges — a chain of near-flat links between two otherwise-steep
    # slopes is the visual definition of a ridge on a mountain.
    SLOPE_MIN = math.tan(math.radians(10))
    SLOPE_MAX = math.tan(math.radians(45))  # per-link cap; also bounds visual
                                              # slope between siblings in the mesh
    RIDGE_SLOPE_MIN = math.tan(math.radians(5))
    SHALLOW_PULL = 0.55  # how much importance pulls slope toward flat
    # Rationale: at 0.75 the spine barely drops at all — mountain becomes a
    # wide mesa. 0.55 keeps ridges visibly shallower than normal terrain while
    # the overall mountain profile still reads as a mountain, not a plateau.

    # Per-link hard-cap: no single parent→child link may drop more than
    # MAX_LINK_DROP units, regardless of slope × h_dist. Without this cap, a
    # low-importance 2-LOC leaf hanging off a high-importance substantial
    # parent plummets to an isolated valley pocket surrounded by higher
    # angular neighbors — violating the user's invariant "only down as we
    # move away from the root" when read across branches.
    MAX_LINK_DROP = PEAK_HEIGHT * 0.25

    imp = importance or {q: 0.0 for q in qnames}

    # Pass 2: BFS from virtual root, apply slope per edge.
    # An edge p→c has "ridge-ness" = min(imp[p], imp[c]) — both endpoints must
    # be architecturally important for the link between them to sit on a ridge.
    # (If only one side matters the descent stays normal; isolated important
    # nodes become bumps, not spines.)
    heights: dict[str, float] = {VIRTUAL: PEAK_HEIGHT}
    origin = (0.0, 0.0)
    desc_queue = [VIRTUAL]
    while desc_queue:
        p = desc_queue.pop(0)
        p_d = density_lookup.get(p, 0.5)
        p_h = heights[p]
        p_pos = positions.get(p, origin) if p != VIRTUAL else origin
        # Virtual root has no importance of its own; use its child's value so
        # the very first link into the true entry point can still be shallow.
        p_imp = 1.0 if p == VIRTUAL else imp.get(p, 0.0)
        for c in primary_children.get(p, []):
            c_pos = positions[c]
            h_dist = math.hypot(c_pos[0] - p_pos[0], c_pos[1] - p_pos[1])
            c_d = density_lookup.get(c, 0.0)
            raw = p_d - c_d
            t = (raw - smin) / srange  # 0..1 across the graph
            base_slope = SLOPE_MIN + t * (SLOPE_MAX - SLOPE_MIN)
            # Ridge modulation: shrink slope when both endpoints are important.
            chain_imp = min(p_imp, imp.get(c, 0.0))
            slope_tan = base_slope * (1.0 - SHALLOW_PULL * chain_imp)
            slope_tan = max(RIDGE_SLOPE_MIN, min(slope_tan, SLOPE_MAX))
            drop = min(slope_tan * h_dist, MAX_LINK_DROP)
            heights[c] = p_h - drop
            desc_queue.append(c)
    # Orphans go just ABOVE the lowest mountain node (not below) — otherwise
    # they sink under the ground-plane disc in the renderer.
    lowest_real = min((h for q, h in heights.items() if q != VIRTUAL), default=0.0)
    orphan_level = lowest_real + 0.1
    for q in orphan_peaks:
        heights.setdefault(q, orphan_level)
    # Any still-missing (shouldn't happen but safety net)
    for q in qnames:
        heights.setdefault(q, orphan_level)

    # Radial-monotonicity post-pass: raise any node whose nearby-outward
    # neighbors sit higher than it. Without this, a low-importance leaf
    # close in (x,z) to a high-importance cross-branch node produces a
    # visible pocket — the mesh rises past the leaf as you walk radially
    # outward, violating the user's "only down as we move away from the
    # root" invariant. We lift the low node to match the outward neighbor,
    # clamped by its primary parent's height to preserve tree monotonicity.
    node_r: dict[str, float] = {}
    for q, (x, y) in positions.items():
        node_r[q] = math.hypot(x, y)
    # Build primary-parent lookup so we can clamp each node below its parent
    primary_parent: dict[str, str] = {}
    for par, kids in primary_children.items():
        for c in kids:
            primary_parent[c] = par
    # Proximity threshold — cross-branch neighbors must be within this fan-space
    # distance to count as "nearby" for monotonicity purposes.
    NEAR_DIST = STEP * 1.3
    # Iterate a few times so lifts propagate: lifting A may reveal A's other
    # neighbor B must also lift. Converges fast.
    for _ in range(4):
        changed = False
        for q in list(heights.keys()):
            if q == VIRTUAL:
                continue
            rx, ry = positions.get(q, (0.0, 0.0))
            r_q = node_r.get(q, 0.0)
            h_q = heights[q]
            # Cap we can ever raise to: primary parent's height (or VIRTUAL peak).
            par = primary_parent.get(q)
            h_cap = heights.get(par, PEAK_HEIGHT) if par else PEAK_HEIGHT
            # Find nearby neighbors that are higher; treat same-r as outward too.
            # A node at equal or greater radial distance that's higher would
            # create a visible uphill when walking outward (or sideways) from q,
            # so we lift q to match.
            max_outward_h = h_q
            for p, (px, py) in positions.items():
                if p == q or p == VIRTUAL:
                    continue
                # Only consider neighbors at r ≥ r(q) - small tolerance.
                # Nodes strictly closer to peak are ancestors or cousins-closer-in
                # — their heights already bound q via primary invariants.
                if node_r.get(p, 0.0) < r_q - 1e-6:
                    continue
                d = math.hypot(px - rx, py - ry)
                if d > NEAR_DIST:
                    continue
                if heights[p] > max_outward_h:
                    max_outward_h = heights[p]
            if max_outward_h > h_q:
                new_h = min(max_outward_h, h_cap)
                if new_h > h_q + 1e-6:
                    heights[q] = new_h
                    changed = True
        if not changed:
            break

    # Simple min-max normalization: map actual min/max heights to [0, TARGET_SPAN].
    TARGET_SPAN = 10.0
    mountain_heights = [h for q, h in heights.items() if q != VIRTUAL]
    if mountain_heights and len(mountain_heights) >= 2:
        h_lo = min(mountain_heights)
        h_hi = max(mountain_heights)
        core_span = h_hi - h_lo
        if core_span > 0.01:
            scale = TARGET_SPAN / core_span
            for q in list(heights.keys()):
                if q == VIRTUAL:
                    continue
                y_new = (heights[q] - h_lo) * scale
                heights[q] = y_new

    # Build set of primary-tree edges (parent, child) — these are the only
    # edges that are guaranteed monotonic in radius and should be rendered as arcs.
    primary_edges: set[tuple[str, str]] = set()
    for parent, kids in primary_children.items():
        if parent == VIRTUAL:
            continue
        for c in kids:
            primary_edges.add((parent, c))

    # Remove VIRTUAL from output
    positions.pop(VIRTUAL, None)
    heights.pop(VIRTUAL, None)
    return positions, heights, connected_peaks, primary_edges


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "../../src/flowcode")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "graph.json")
    entry = sys.argv[3] if len(sys.argv) > 3 else "main"

    print(f"Parsing {root.resolve()}...")
    functions = parse_directory(root)
    print(f"  {len(functions)} functions/methods before filtering")

    # Filter to functions reachable from the chosen entry (BFS forward on calls).
    # This makes the view a single flow with a single real peak.
    if entry not in functions:
        matches = [q for q in functions if q == entry or q.endswith(f".{entry}")]
        if not matches:
            raise SystemExit(f"entry {entry!r} not found in parsed functions")
        entry = matches[0]
    print(f"  entry point: {entry}")

    reachable: set[str] = {entry}
    queue = [entry]
    while queue:
        cur = queue.pop(0)
        for callee in functions[cur].calls:
            if callee in functions and callee not in reachable:
                reachable.add(callee)
                queue.append(callee)

    functions = {q: f for q, f in functions.items() if q in reachable}
    print(f"  {len(functions)} functions reachable from {entry!r}")

    calls_by_q = {q: [c for c in functions[q].calls if c in functions] for q, info in functions.items()}

    qnames = sorted(functions.keys())
    depths = compute_depths(qnames, calls_by_q)
    max_depth = max(depths.values(), default=0)
    print(f"  depth range: 0..{max_depth}")

    umap_coords, embeddings, dim = embed_and_project(functions)

    # Build callers/callees maps for layout
    callees_of: dict[str, list[str]] = {q: list(functions[q].calls) for q in qnames}
    callers_of: dict[str, list[str]] = {q: [] for q in qnames}
    for q, outs in callees_of.items():
        for c in outs:
            if c in callers_of:
                callers_of[c].append(q)

    # Semantic density first — it feeds the fan layout's height computation
    density = compute_semantic_density(qnames, embeddings)

    # Architectural importance = novelty × substance. Drives ridge formation
    # in radial_fan_layout: high-importance chains descend shallowly (ridges),
    # low-importance chains descend steeply (ravines).
    importance = compute_importance(qnames, calls_by_q, functions, density)

    # Radial fan (ski-slope) layout with relative-descent heights
    fan_coords, fan_heights, peaks, primary_edges = radial_fan_layout(
        qnames, callees_of, callers_of, embeddings, density, importance
    )

    # Measure crossings in the 2D fan layout (purely informational)
    def _segments_cross(p1, p2, p3, p4):
        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
        return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

    edge_segments = []
    for q in qnames:
        if q not in fan_coords:
            continue
        for c in functions[q].calls:
            if c in fan_coords and q != c:
                edge_segments.append((q, c, fan_coords[q], fan_coords[c]))
    crossings = 0
    for i in range(len(edge_segments)):
        for j in range(i + 1, len(edge_segments)):
            a, b, p1, p2 = edge_segments[i]
            c, d, p3, p4 = edge_segments[j]
            if len({a, b, c, d}) < 4:
                continue  # share an endpoint, not a true crossing
            if _segments_cross(p1, p2, p3, p4):
                crossings += 1
    print(f"  2D edge crossings: {crossings}")
    print(f"  connected peaks: {len(peaks)}")

    # Orphans = real peaks with no children (isolated, dead-code looking). The
    # layout moved them behind the mountain. Mark them so the renderer can skip
    # them from the terrain mesh.
    real_peaks_set = {q for q in qnames if not callers_of.get(q)}
    orphan_set = {q for q in real_peaks_set if not callees_of.get(q)}
    # Also flag cycle-only unreachable nodes as orphans (layout put them with orphans)
    # Compute: any node whose fan position has y_fan > 0 is an orphan (mountain is south of origin).
    for q, (_, y) in fan_coords.items():
        if y > 0:
            orphan_set.add(q)

    # importance was computed above (before the fan layout) and already used
    # to scale per-edge slopes into ridges/ravines. Kept on each node for
    # the tooltip / debug panel.

    nodes = []
    for q in qnames:
        info = functions[q]
        doc = info.docstring.strip().split("\n")[0] if info.docstring else ""
        nodes.append({
            "id": q,
            "qname": q,
            "label": q.split(".")[-1],
            "file": info.file,
            "class": info.class_name,
            "depth": depths[q],
            "x_fan": fan_coords[q][0],
            "y_fan": fan_coords[q][1],
            "height": fan_heights[q],
            "x_umap": umap_coords[q][0],
            "y_umap": umap_coords[q][1],
            "importance": importance[q],
            "semantic_density": density[q],
            "is_orphan": q in orphan_set,
            "description": doc,
            "source_lines": info.source.count("\n") + 1,
            "n_callees": len(info.calls),
        })

    edges = []
    for q in qnames:
        for callee in functions[q].calls:
            if callee in functions:
                edges.append({
                    "from": q,
                    "to": callee,
                    "is_primary": (q, callee) in primary_edges,
                })

    payload = {
        "root": str(root.resolve()),
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "max_depth": max_depth,
        "peaks": peaks,
        "embedding_model": MODEL_NAME,
        "embedding_dim": dim,
        "nodes": nodes,
        "edges": edges,
    }
    out.write_text(json.dumps(payload))
    print(f"wrote {out}  ({len(nodes)} nodes, {len(edges)} edges, {len(peaks)} peaks, max_depth={max_depth})")


if __name__ == "__main__":
    main()
