# Inclusive terrain improvement round

## Contract and initial interpretation

Started 2026-09-21 07:07 UTC; user limit: three hours, ending by 10:07 UTC.
Worktree: `/home/dlybeck/Projects/Flow-Code-worktrees/terrain-rules-prototype`.
Branch: `codex/inclusive-terrain-audit`.
Baseline: `b5b8d1b90f15515a7688ed49d9f5b30904857283`.

Improve Flow-Code's general source analysis and inclusive, understandable terrain.
ScribbleScan is a historical example; independent projects are equally valid acceptance cases.
Initial hypothesis: unresolved Python calls and sampled-out bridge functions cause
important execution paths to appear detached. Preserve parent-relative downhill
heights, circular layout, embedding relevance and textured terrain. No generative
AI in map generation. Static inference cannot promise a complete runtime graph.

Proof: independent parser regressions; source-backed real-project audits;
reproducible snapshots retaining all functions within declared source roots;
visible uncertainty/coverage; browser inspection and interaction checks; relevant
full test suite; independent Standards and Spec reviews of the complete branch.

Authority: local changes, compute, dependencies, tests, small commits, feature
branch push. No deployment (including Pages), main/integration branch edits,
spending, new credentials, unrelated changes or material deletion. Leave an
unmerged review branch. The user's follow-up explicitly confirms reusable
Flow-Code tooling, not hand-wired ScribbleScan fixes.

Validation commands and evidence are recorded below.

User steering: choose appropriate independent test projects autonomously.
ScribbleScan was the historical first example, not a required exclusive focus.
The target and acceptance criteria are general Flow-Code behavior.

## Implementation and source-grounded findings

The missing graph had two independent causes: source calls that adapters could
not recognize, and the old demo builder's top-N/project-name selection omitting
bridge functions. The circular demo now uses `flowcode prototype` to retain the
entire indexed function inventory. It has search, caller/callee navigation,
local fixture loading, entry evidence, source locations and analysis boundaries.
No project-specific edge rules or function-name selectors were added.

Python now propagates finite source candidates through constructors, local
receivers, fields, factories, single inheritance, imported classes/functions and
literal `getattr` dispatch. Candidate links are heuristic and preserve unresolved
call records. Explicit module initialization contributes labelled entry
candidates. Propagation is bounded at 24 rounds, with convergence recorded and
an explicit limitation if the bound is reached. Python object analysis does not
execute/import target code.

Java now uses explicit local/parameter receiver types and arity, with lexical
scope checks. Unknown receivers are not matched merely to the only method with
the same name. Express route and event-registration support was recovered from
existing commit `adb83e6`, whose separate parser branch had produced some prior
demo snapshots. Its tests were carried over; the old heuristic Python service
expansion and the old layout changes were not copied.

All terrain paths retain parent-relative relevance drops. Unplaced functions sit
outside the mesh without execution altitude; their color and size still encode
relevance, and a white ring marks the unknown entry path. Additional calls use
explicit shortest-angle circular routes. Entry labels are bounded, clickable,
collision-checked and hidden when occluded by terrain. Search centers a selected
function. The camera faces the highest-scoring entry without altering geometry.

Graph receipts now include an analyzer source fingerprint and parser package
versions. A source digest alone had been insufficient to distinguish divergent
parser branches. Fixture refresh refuses changed source/function inventories and
preserves explicit entry selections from new exports.

## Same-source comparison

These are **static may-reachability counts**, not runtime coverage or evidence
that disconnected code is unused. Adapter entry sets include legacy fallbacks in
the baseline; the viewer does not turn a fallback-first-symbol into a summit.
Selected roots and exact source digests are recorded in
[`inclusive-coverage.json`](inclusive-coverage.json).

| Selected project source | Indexed functions | Entry-reachable before | Entry-reachable after | Internal pairs before → after |
| --- | ---: | ---: | ---: | ---: |
| ScribbleScan (`app`, `static/js`) | 599 | 138 | 280 | 317 → 462 |
| Chef (`app`, `agents`, `config`) | 32 | 7 | 20 | 2 → 20 |
| Fieldhouse Manager (`index.js`, `models`, `public/js`) | 41 | 1 | 28 | 16 → 23 |
| Algorithms word-frequency/tree slice (two Java files) | 46 | 6 | 39 | 28 → 71 |
| Flow-Code available Python source (`src/flowcode`) | 175 | 126 | 142 | 199 → 230 |

The old ScribbleScan demo displayed 38 functions; this viewer includes all 599 in
its declared roots. Counts for the other complete fixtures are 32, 41, 46 and
256. The 256-function Flow-Code viewer example is explicitly a **saved source
snapshot**, separate from the 175-function Python-only analysis above; its source
has changed, so refreshed calls were not mixed with its stored scores.

Source checks beyond the original example:

- Chef `app/main.py:108–109` constructs `ImageAnalyzerTool` and invokes `_run`;
  `agents/tools/image_analyzer.py:97` invokes `_identify_food_items`. The new graph
  retains those intermediate calls and labels the object links as candidates.
- Chef's `RecipeSearchTool._run` (`agents/tools/recipe_searcher.py:32`) is meaningful
  recipe-search functionality but remains outside an established entry path.
  `RecipeAgent.continue_conversation` invokes the external executor at
  `agents/recipe_agent.py:154`. This is a concrete counterexample to assuming
  disconnected functions are irrelevant.
- Java's word-frequency entry reaches tree insertion and balancing through typed
  receiver calls and overload arity. Same-name methods on unrelated classes,
  unknown inherited targets and locals from a different block stay unresolved.
- Fieldhouse's literal browser requests connect to source-declared Express route
  callbacks; route receivers that are reassigned or shadowed do not qualify.

## Validation and reproduction

Use the same source checkout with the baseline and candidate analyzer on
`PYTHONPATH`, and run `scripts/audit_graph_coverage.py REPO --src-root PATH -o
receipt.json`. The baseline for this round is `b5b8d1b`.

Relevant checks:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
node --test prototype-entrypoints.test.js prototype-routing.test.js
npm run build
python scripts/verify_inclusive_viewer.py \
  --url http://127.0.0.1:8766/terrain-rules-prototype.html --out BROWSER_OUTPUT
```

The browser script requires Playwright/Chromium. In this environment it runs in
`flowcode-playwright-python` with host networking; Node build/tests run in
`node:22-alpine`. The Python environment was created locally with the project's
language/dev extras and its pinned NumPy/scikit-learn/UMAP dependencies.

The browser matrix covers all five fixtures, both normalization modes and both
summit modes. It checks finite positions and downhill invariants, searches and
selects a formerly omitted dispatch function, filters unplaced functions, tests
local import and literal HTML-like labels, checks mobile overflow, verifies
clickable landmarks, desktop/mobile label separation, and asserts identical relevance color/size for connected
and unplaced nodes with equal scores. The receipt records fixture and renderer
hashes. Screenshots were also inspected by the lead agent; automated geometry
checks alone do not establish readability.

## Limits and stopping boundary

This is a complete inventory of **indexed functions in selected supported
source**, not every asset/file in a repository and not a complete runtime graph.
External frameworks, dynamic mutation, multiple inheritance, closures and
higher-order dispatch can still leave useful code without an entry path.
Alternative providers may share conservative candidate edges. Call records can
retain unresolved evidence alongside candidate targets; their count is not a
count of unique missing runtime calls.

Embedding scores were reused from existing source-matched exports. They remain
estimates: the Java tree-demo `main` scores above the word-frequency `main`.
The highest ridge is therefore not yet a universally reliable project summary.
Large projects also remain dense, particularly their unplaced regions. Search,
entry landmarks and source evidence improve inspection without claiming that
all codebases now tell a perfect story at a glance.

No generative AI was used to generate map content. This run leaves a feature
branch for review. Main, Portfolio integration and the public Pages deployment
are outside this run's contract.

## Review

Standards review found two false-link bugs (local Python import shadowing and
Java `this` resolving an unrelated method); both were fixed with regressions.
An additional Java sibling-block binding regression was reproduced and fixed.
Follow-up Standards review found no remaining actionable issues. Final renderer/test delta review also remained clear after inspecting overlay collision handling and the 20-case browser receipt.

Spec review requested clearer unplaced relevance encoding, readable entry
landmarks and explicit circular secondary routing; those changes were made.
Final Spec review: **no remaining actionable findings**. The reviewer confirmed the current work satisfies the inclusive-terrain contract and the documented limits are honest stopping boundaries.

## Validation results

- Python suite: **149 passed** in 20.52 seconds.
- JavaScript forest/routing checks: **7 passed**; bundled build passed.
- New Python modules, regression files and audit/browser scripts: Ruff passed.
  Existing unrelated whole-repository Ruff violations remain outside this round.
- Fixture generation repeated twice with byte-identical output:
  `0db44357b5d356fdd7405624405b68575dc77e1f6d5498ffe4eeb14227548101`.
- Browser: **20 cases passed**, no page errors; inventory, selection, local import, mobile overflow, landmark clicks, label separation and equal-relevance marker checks passed.
- Browser results and exact renderer hash: [`inclusive-browser/receipt.json`](inclusive-browser/receipt.json).
- Eyeballed screenshots: [ScribbleScan](inclusive-browser/scribble-all.png),
  [Chef](inclusive-browser/chef.png), [Java](inclusive-browser/redblack.png),
  [mobile](inclusive-browser/mobile.png).

The initial diagnosis was partly confirmed: omitted bridges and missed source
calls fragmented the maps. The further finding is that no amount of finite static
inference makes connectivity a reliable filter for project importance. Full
inventory and inspectable uncertainty are therefore part of the result, rather
than hiding anything the analyzer cannot yet place.


## Delivery

Implementation commits:

- `77c9bf9`: bounded call candidates, evidence and analyzer provenance.
- `f74a623`: complete portable exports, explicit entries and source identity guards.
- `cf07125`: inclusive circular viewer, fixtures and browser validation.

Review range: combined branch changes from `b5b8d1b90f15515a7688ed49d9f5b30904857283`,
including the added validation evidence. Feature branch: `codex/inclusive-terrain-audit`.
Public Pages and integration branches remain unchanged. The local preview is
`http://localhost:8766/terrain-rules-prototype.html` on this computer.
