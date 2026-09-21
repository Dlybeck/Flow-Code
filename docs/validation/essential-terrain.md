# Essential terrain implementation

Baseline: `8aac9959bae6b1345e0bc98c357ec3cfd73861f9`.

## Approved contract

Default Essential content: at most 40 visible items (functions plus expandable
supporting groups, excluding project summit), at most six entry branches. Rank
reachable candidates by existing raw relevance with stable ID ties; admit their
full entry paths only when the simplified result fits. Suppress additional
near-duplicate highlights at exported cosine >= 0.9; retain connecting steps.
Keep entry functions and retained branching junctions. Collapse maximal
non-highlight connecting sequences, retaining ordered IDs and original call
evidence. Distinguish collapsed paths from direct calls. Do not recompute scores
or original cumulative heights from the selected subset.

Expand groups beyond the initial budget, reveal searched functions and entry
paths, expose omitted supporting branches, and list five high-scoring functions
with unknown entry paths. Unknown functions cannot receive invented entry links.
Complete content preserves the whole graph and its marker-density controls.
Essential shows all retained markers. Reset overview clears expansions/reveals.

The downhill guarantee applies along code branches, not arbitrary directions
across neighboring branches. Use a common next radius for siblings and sector
paths; constrain the terrain triangulation to the same descending primary
polylines drawn as call lines. Preserve all original node elevations; no ridge
bonuses or fixed elevation bands. Validate invalid paths before triangulation;
never silently render unconstrained terrain after a failure. Secondary dotted
calls remain separate from the terrain guarantee.

No parser, embedding model, source fixture or generative-AI changes. Validate
against ScribbleScan, Chef, Fieldhouse, Java and Flow-Code; report semantic
limitations with source evidence. Deliver reviewed feature branch and persistent
local preview; no public deployment or merge.

## Validation

The original free triangulator allowed rises along 47 of ScribbleScan's 280
anchored primary paths even though their endpoint heights descended. Primary
paths are now shared polylines between the renderer and constrained terrain.
Unplaced-to-unplaced links are dotted relationships outside the terrain guarantee.

The first simplified layout still put seven of ten summit markers within ten
screen pixels. Square-root subtree sector weights and a doubled first radial
band in Essential mode removed those collisions in the same default view,
without changing relevance, heights, or parent relationships. Supporting-group
markers are diamonds, with a separate clickable list when terrain occludes them.

### Source-backed selection review

- ScribbleScan retains image processing, transcription orchestration, conversion,
  digitization and related UI callbacks. Its collapsed three-step provider
  setup chain is `get_ai_handler → AIHandler.__init__ → get_provider_instance`,
  corroborated by `app/api/services/ai_handler.py:115–152`. Bounding-box/provider
  code with unknown entry paths remains in the separate relevant-function list.
- Chef retains `analyze_image → ImageAnalyzerTool._run → _identify_food_items`.
  `RecipeSearchTool._run` remains an important unknown-entry candidate rather
  than receiving an invented call from its external agent executor.
- Fieldhouse retains reservation browser functions and route callbacks. The
  six-entry cap gives a focused slice, not coverage of all route behavior.
- Java retains tree mutation, balancing and lookup functions. Existing scores
  still favor the tree demo; the entry-to-core choice is an estimate, not an
  assertion that the demo is the entire project's purpose.
- Flow-Code's saved snapshot selects terrain export, parser/IR construction,
  application-edge attachment and scoring. Its unplaced CLI is still accessible.
  This is the same recorded source snapshot, not a newly embedded checkout.

The automatic view contains 40, 19, 10, 38 and 40 items respectively. Only
ScribbleScan needs a collapsed chain in these initial sibling-scored examples;
smaller graphs are not padded to meet the budget.

### Checks and review

Python: 149 tests passed. JavaScript: 21 tests passed and bundled build passed.
Actual browser mesh tests cover all five projects, both content modes, both
normalization modes and both summit modes, plus expansion, reset, search,
unknown-function navigation and no-entry fixtures. Sampling checks the surface
at every route vertex and segment midpoint against the line height (tolerance
0.0002 world units), rather than only comparing function endpoints.

- [Surface and interaction receipt](essential-browser/receipt.json): 50 cases,
  204,282 surface samples, zero rises or missing samples. Maximum route/surface
  mismatch was 0.00000184 world units, below the 0.0002 threshold. The verifier
  uses tight barycentric containment so nearby thin triangles are not sampled
  through extrapolation.
- [Existing viewer regression](essential-browser/viewer-regression.json): all 20
  project/normalization/summit cases passed, including navigation and labels.
- [Complete detail regression](essential-browser/detail-regression.json): five
  projects passed; zoom reveals hidden functions, selected paths remain visible,
  and marker filtering leaves geometry and call evidence unchanged.
- New navigation regressions cover selecting an already-visible endpoint below
  a collapsed chain and retaining known dotted calls between revealed unplaced
  functions, without assigning them entry paths.
- [Source hashes](essential-browser/source-hashes.json) identify the tested HTML,
  renderer sources, bundle and verifier. All three browser receipts match the
  same fixture and built renderer. Build outputs remain generated/ignored.
- Screenshots were inspected for [ScribbleScan](essential-browser/scribblescan.png),
  [Chef](essential-browser/chef.png), [Fieldhouse](essential-browser/fieldhouse.png),
  [Java](essential-browser/redblack.png), [Flow-Code](essential-browser/flowcode.png)
  and [mobile navigation](essential-browser/mobile.png). The mobile image shows
  explicit selection of an unplaced function, so the camera centers that point.

Reproduction: run `PYTHONPATH=src .venv/bin/python -m pytest -q` in the worktree;
run `node --test prototype-*.test.js` and `npm run build` in
`experiments/3d-layered`; serve that directory on port 8766 and run each of
`scripts/verify_essential_viewer.py`, `scripts/verify_inclusive_viewer.py`, and
`scripts/verify_terrain_detail.py` in a Python Playwright environment with
Chromium, supplying `--out` to a writable evidence directory. This validation
used Node 22 in Docker and the local `flowcode-playwright-python` image.

Independent whole-change Standards review found three navigation/display issues:
original-caller drop text, retained-endpoint expansion, and unplaced known-call
preservation. All were fixed and the final delta received clean Standards closure.
Independent Spec review verified the frozen source hashes, three browser receipts,
six screenshots, test results and persistent preview. It closed with no actionable
findings. Both review axes cover the complete change from the stated baseline.

The local preview is served by the persistent user service
`flowcode-terrain-preview` at `http://127.0.0.1:8766/terrain-rules-prototype.html`.
Public Pages remains unchanged; this delivery is an unmerged feature branch.
