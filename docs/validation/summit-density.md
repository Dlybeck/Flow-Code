# Summit crowding follow-up

The user rejected the full-inventory viewer as too crowded near the summit.
Baseline: `4f75d16a982bb7345822a54213d491100e8cd427`.

## Reproduction and alternatives

At 1500×1100 in the default ScribbleScan view, 69 of 75 function markers in the
highest fifth had another summit marker within 10 screen pixels. The original
browser suite caught overlapping **labels**, but had no marker-density check.
The new browser regression reproduces the original failure with **All nodes**.

151 declared entries fan out near one project summit: 76 event callbacks, 66
routes, and nine other entry-evidence combinations. These are not simply
callerless functions incorrectly promoted to entries. A 30-entry equal-score
star did not reproduce the crowding; quantity and the real graph's distribution
relative to its full extent matter.

Three candidate causes were examined: insufficient first-branch radius, too
much simultaneous detail, and excessive entry detection. Tripling only the
first-branch radial distance reduced the measured overlap from 92% to 84%; it
was not retained. Dropping entries or keeping only globally top-ranked functions
would risk hiding real entry paths and bridge functions.

## Mitigation

**Overview**, enabled by default, chooses markers with 28 screen pixels of
separation, favoring raw embedding relevance within competing neighborhoods.
Zooming or rotating recomputes that choice. The synthetic project anchor stays
available. Selecting a function pins its complete primary caller chain plus its
direct call neighbors, including low-relevance bridges. Explicitly showing all
secondary calls pins their endpoints as well. These intentional detail requests
can bring back crowding; they take priority over overview spacing.

The complete terrain is still generated from all functions. Heights, parent
assignments, scores and original call edges are unchanged. The renderer hides
some markers and their incident primary lines at overview scale; it never draws
an invented shortcut over hidden functions. Search retains the full inventory.
**All nodes** restores every marker. The sidebar reports how many markers are
currently enabled in the viewport (terrain can still occlude them).

This addresses marker density, not incomplete static analysis or the quality of
the embedding relevance estimates. A screen-space overview is not a claim that
only its visible functions matter. Close markers can appear/disappear while
rotating; search and All nodes provide stable access to any function.

## Evidence

- Ten JavaScript tests passed, including spacing, deterministic selection,
  zoom disclosure and preservation of selected bridge nodes; build passed.
- Five-project browser detail checks passed. Default overview summit overlap:
  zero for all five. ScribbleScan shows 48 function markers in the overview,
  with five in the highest fifth, instead of drawing all 599 simultaneously.
- The unchanged full-view control reproduces 69 crowded summit markers.
- Detail toggles preserve the graph and height/position maps byte-for-byte.
- Browser checks confirm zoom reveals previously hidden functions, selection
  exposes all primary callers and direct neighbors, and secondary endpoints stay
  available when their connections are explicitly shown.
- The existing 20-case viewer suite also passed, including desktop/mobile label
  separation, inventory navigation, source import and downhill invariants.
- Lead visual inspection covered overview, zoom, and selected-path views.

Receipts: [detail checks](summit-density/receipt.json),
[existing viewer regression](summit-density/viewer-regression.json).
Screenshots: [overview](summit-density/overview.png),
[all-node control](summit-density/all.png).

Run `node --test prototype-*.test.js` and `npm run build` in
`experiments/3d-layered`; serve that directory, then run
`scripts/verify_terrain_detail.py --url VIEWER_URL --out OUTPUT_DIR` with
Playwright/Chromium installed. No parser or fixture data changed in this follow-up.
