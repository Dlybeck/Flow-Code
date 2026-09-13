"""Original Flow-Code semantic scoring and call-path terrain, promoted for reuse.

From experiments/3d-layered/build_graph.py (upstream 1e05ba91).
Importance is a heuristic, not a measurement of business value.
"""

import math

STEP = 3.5
MAX_WEDGE_DEG = 340


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
        loc = {
            q: max(1, getattr(functions[q], "source", "").count("\n") + 1)
            for q in qnames
        }
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


def _cos_sim(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def compute_semantic_density(
    qnames: list[str], embeddings: dict[str, list[float]], k: int = 10
) -> dict[str, float]:
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
) -> tuple[
    dict[str, tuple[float, float]], dict[str, float], list[str], set[tuple[str, str]]
]:
    """Ski-slope layout: one virtual peak at origin, entire slope fans within 340° south.

    A synthetic "__ROOT__" sits at origin with a 340° wedge aimed south. All real
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
    # forcing a single peak at origin and a single 340° slope south.
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
            parent_candidates = sorted(
                c for c in L_callers.get(child, []) if c in assigned
            )
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
    # lives inside a single 340° wedge aimed south from origin.
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
                positions[k] = (
                    k_radius * math.cos(k_angle),
                    k_radius * math.sin(k_angle),
                )
                angles[k] = k_angle
                queue.append(k)
                start = slot_max

    # Pass 0: seed with NN-chain ordering so we have initial angles
    place_tree(lambda parent, kids: nn_chain(kids, parent))

    # Keep embedding-neighbor order. The prototype barycenter pass cleared
    # its reference angles and could erase the semantic ordering.

    # Place orphan peaks behind the mountain (north of origin) so they don't
    # clutter the south-facing slope. Arrange them in a compact grid.
    placed_ys = [positions[q][1] for q in qnames if q in positions]
    orphan_offset_y = (max(placed_ys) if placed_ys else 5.0) + 4.0
    side = max(1, math.ceil(math.sqrt(len(orphan_peaks))))
    for i, p in enumerate(orphan_peaks):
        row, col = i // side, i % side
        positions[p] = ((col - side / 2) * 1.8, orphan_offset_y + row * 1.8)

    # --- Per-edge slope driven by the CHILD's own importance ---
    #
    # Simple rule: each primary edge descends at an angle determined by the
    # child node's importance. Important children → shallow slope (stays
    # high, forms a ridge). Unimportant children → steep slope (drops fast,
    # forms a ravine). No chain logic, no density-delta, no clamping based
    # on parent. Just: steeper if unimportant, shallower if important.
    #
    # Height computation: BFS from the virtual root starting at h=0 and
    # subtracting drops. All heights end up ≤ 0. Once done, shift every
    # height up so the deepest node sits at 0 (touching the ground). The
    # peak ends up at whatever height the path structure dictates.
    SLOPE_SHALLOW_DEG = 10.0  # top-importance node: this angle from its parent
    SLOPE_STEEP_DEG = 60.0  # zero-importance node: this angle from its parent

    imp = importance or {q: 0.0 for q in qnames}

    heights: dict[str, float] = {VIRTUAL: 0.0}
    origin = (0.0, 0.0)
    desc_queue = [VIRTUAL]
    while desc_queue:
        p = desc_queue.pop(0)
        p_h = heights[p]
        p_pos = positions.get(p, origin) if p != VIRTUAL else origin
        for c in primary_children.get(p, []):
            c_pos = positions[c]
            h_dist = math.hypot(c_pos[0] - p_pos[0], c_pos[1] - p_pos[1])
            c_imp = max(0.0, min(1.0, imp.get(c, 0.0)))
            slope_deg = SLOPE_STEEP_DEG - c_imp * (SLOPE_STEEP_DEG - SLOPE_SHALLOW_DEG)
            slope_tan = math.tan(math.radians(slope_deg))
            heights[c] = p_h - slope_tan * h_dist
            desc_queue.append(c)
    # Shift every height so the deepest node sits at y=0. The peak ends up
    # at whatever positive value falls out of the structure — no normalization,
    # no stretching, just "deepest touches ground."
    real_heights = [h for q, h in heights.items() if q != VIRTUAL]
    if real_heights:
        shift = -min(real_heights)
        for q in list(heights.keys()):
            heights[q] += shift

    # Orphans go just ABOVE the lowest mountain node (not below) — otherwise
    # they sink under the ground-plane disc in the renderer.
    lowest_real = min((h for q, h in heights.items() if q != VIRTUAL), default=0.0)
    orphan_level = lowest_real + 0.1
    for q in orphan_peaks:
        heights.setdefault(q, orphan_level)
    # Any still-missing (shouldn't happen but safety net)
    for q in qnames:
        heights.setdefault(q, orphan_level)

    # Heights are determined entirely by primary-tree descent from the root:
    # h(child) = h(parent) − drop(parent, child), where drop is small for
    # important chains and large for unimportant ones (set during the BFS
    # above). No normalization, no ring caps, no percentile rescaling — each
    # node's height is relative to its parent's height, and that's the whole
    # mental model. Ridges and valleys emerge naturally from the drops,

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
