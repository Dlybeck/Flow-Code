# Terrain linework cleanup

## Provisional Yolopilot contract

User handoff: clean up the concentrated skinny polygons and ambiguous long lines
identified after Essential-view delivery. Initial diagnosis: 48 segments on every
primary route concentrate mesh vertices; outlined polygon creases resemble calls;
collapsed primary paths share the secondary-call dash style.

Objective: clearer terrain and connections while preserving the textured mountain,
original relevance/height/selection/parent rules and full inventory. Improve route
sampling and triangle proportions; separate decorative surface from graph lines;
distinguish direct primary, collapsed primary, secondary and project membership.

Worktree: `/home/dlybeck/Projects/Flow-Code-worktrees/terrain-rules-prototype`.
Branch: `codex/inclusive-terrain-audit`.
Baseline: `06082bb377feb6dfcc6010b4d4259c0ef7d53430` (clean at launch).

Authority: local code/docs/evaluations/dependencies/compute, feature commits and
push, persistent local preview. No public/production deployment, merging or
integration-branch writes, money/new credentials, material deletion or unrelated
scope. Existing source snapshots and code-analysis semantics stay unchanged.

Proof: comparable before/after screenshots and mesh metrics across five saved
projects; actual rendered primary surfaces stay downhill; scores, heights and
parent evidence remain unchanged; distinct line styles survive selection;
expansion/search/unknown navigation/mobile/Complete detail regressions pass.
Run `node --test prototype-*.test.js` and `npm run build` in the viewer directory,
`PYTHONPATH=src .venv/bin/python -m pytest -q` in this worktree, and the three
existing Playwright verifier scripts plus focused linework checks. Inspect
screenshots and review whole change on Standards and Spec axes before pushing.

## Progress

The baseline confirmed the initial diagnosis: 48 subdivisions per primary path
produced thousands of thin facets, and the sharp-edge overlay drew non-call
lines across unrelated terrain. Reducing route samples was sufficient to improve
triangle proportions; no extra smoothing, inserted terrain points, relevance
changes or node rearrangement was needed.

Sampling now depends on path curvature, with a 1.2 layout-unit chord-error bound
and a conservative outward-chord bound. Siblings share sampling fractions to
preserve their circular order. Straight spokes need only their endpoints. The
surface and primary lines still use exactly the same constrained polylines.

Polygon outlines were removed; lighting, color and flat-shaded facets still
provide depth. Connection patterns distinguish direct primary calls (solid),
collapsed primary paths (long dashes), secondary calls (dotted arrows) and
synthetic project membership (short dashes). Selection changes color/opacity,
not the relationship pattern. The in-view key explains all four.

## Evidence

All metrics below use the same Essential, sibling-scored project-summit view.
A thin triangle has shape quality below 0.1, where quality is
`4 * sqrt(3) * area / sum(squared edge lengths)` in rendered 3D coordinates;
an equilateral triangle has quality 1. This is a geometry metric, not code quality.

| Project | Triangles before → after | Thin triangles before → after |
| --- | ---: | ---: |
| ScribbleScan | 3,880 → 310 | 2,401 → 9 |
| Chef | 1,864 → 140 | 1,325 → 0 |
| Fieldhouse | 1,000 → 92 | 621 → 0 |
| Java | 3,688 → 416 | 1,984 → 6 |
| Flow-Code | 3,880 → 404 | 2,573 → 33 |

The graph comparison hashes nodes, positions, parents, scores, heights and
primary/secondary edge evidence. All five before/after hashes match. Source
fixtures are unchanged; Flow-Code is the existing saved snapshot. The remaining
thin facets follow constraints/uneven node distributions and are not evidence
of extra calls. Genuine long calls can remain where connected nodes are far
apart; this pass does not invent shorter graph relationships or reposition nodes.

Validation: 149 Python tests and 22 JavaScript tests passed; bundled build,
focused Ruff and diff checks passed. The existing browser suite passed all
50 surface/interaction cases, with 12,914 samples, zero rises/missing samples,
and maximum surface/line mismatch of 0.00000184 world units. Existing viewer
navigation/labels (20 cases) and Complete detail controls (five projects) passed.
The new comparison verifier checks reduced thin-facet counts, no decorative line
overlay, unchanged graph hashes, all four stroke kinds, and pattern preservation
after selection. Five before/after renderings were visually inspected.

Reproduce mesh comparison with `scripts/verify_terrain_linework.py --out DIR` on
the baseline viewer, then run it on the new viewer with
`--compare BASELINE_DIR/receipt.json --out NEW_DIR`. Use the same Python Playwright
Chromium environment and local preview as the existing verifier scripts. Baseline
and final receipts identify the HTML, fixture and bundled renderer hashes.

Independent Standards and Spec reviews closed with no actionable findings.
Review caught a proof gap in the first version of the style verifier: it checked
only the reset view. The final verifier explicitly selects both a group and a
real function, preserves all style signatures, and checks that the four patterns
are distinct. Both reviewers verified the final matching evidence; Standards
also independently ran the 22 JavaScript tests.


Receipts: [baseline](linework-browser/before.json),
[final comparison](linework-browser/after.json),
[actual surface](linework-browser/surface.json),
[viewer regression](linework-browser/regression.json),
[detail regression](linework-browser/detail.json),
[tested source hashes](linework-browser/source-hashes.json).
The fixture hash is unchanged. All final browser receipts share the same bundle
hash, `793a911b2a1e13a8d29bf7afbed2f0ec5ac275f46b6aa420ad21044a59d7ebba`.
Before/after screenshots for all five projects are beside the receipts;
[ScribbleScan before](linework-browser/before-scribblescan.png) and
[after](linework-browser/after-scribblescan.png) show the removed triangle fans.
The [mobile screenshot](linework-browser/mobile.png) checks the expanded line key
while navigating to an unplaced function.

Delivery target: the persistent local `flowcode-terrain-preview` service on port
8766 and the unmerged `codex/inclusive-terrain-audit` feature branch. Public Pages
is outside this handoff and remains unchanged.
