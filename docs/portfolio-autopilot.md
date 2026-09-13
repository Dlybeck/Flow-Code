# Confirmed Flow-Code Autopilot contract

Status: confirmed by the owner on 2026-09-12: "Go ahead! I give you free reign this is my ai dev pc after all. I have safeguards. DO whatever is needed". This approves autonomous technical choices and the proposed two-phase local delivery contract. No renewed routine approval is needed. Publication and production boundaries in the approved contract remain in force.

## Objective and endpoint

Complete both phases of the [two-phase plan](/home/dlybeck/Projects/Portfolio/.scratch/portfolio-projects/flowcode-two-phase-plan.md): first
make Flow-Code generate useful, source-grounded maps across the portfolio and
ScribbleScan Original, then integrate the reusable viewer directly into the
portfolio with theme support. Finish with tested local feature-branch commits,
a working private preview and a review receipt. Production publication is a
separate action.

Proceed from phase 1 to phase 2 when phase 1's proof conditions pass. A routine
milestone does not require another approval. Preserve the accepted reskin as the
visual baseline; delegate reversible implementation and design decisions within
the approved portfolio language to the agent.

## Observable proof

1. The same generation/export workflow supports Flow-Code, the portfolio and
   ScribbleScan Original. Mixed Python and browser JavaScript/TypeScript are
   retained, source references are inspectable, and unresolved/inferred
   relationships are distinguished from resolved calls.
2. Demonstrate a representative feature through the portfolio's browser/server
   boundary and a document/demo-processing flow in ScribbleScan Original. Check
   those connections against source and relevant fixtures. Static analysis is
   never presented as an observed runtime trace.
3. Repeated exports from the same pinned inputs are reproducible. Dependencies
   and generated files are excluded appropriately, and unsupported scope is
   visible. The common viewer handles all reference maps without a project-specific
   parser or viewer fork.
4. Portfolio Home's optional How it works entry opens the portfolio map. Flow-Code
   has a project presentation, and eligible project pages open their corresponding
   maps. Destination links restore context and provide a coherent return path.
5. Integrate the viewer with existing Board Themes, starting from the accepted
   chalkboard/paper reskin. Palette, typography, controls and terrain treatments
   adapt without changing graph meaning, selection or Neighborhood navigation.
   This does not require inventing new themes or replacing existing theme scenes.
6. Pass the relevant analysis/export suites, viewer browser acceptance, portfolio
   integration/regression suite, canonical fidelity check and visual inspection
   across the installed themes at desktop/mobile sizes. Complete whole-change
   review, fix real findings, and distinguish pre-existing failures from new ones.
   Final evidence includes screenshots, source revisions, commands and receipts.

## Scope and permitted actions within the confirmed scope

- Modify Flow-Code's analysis, graph/export, viewer, fixtures, tests and relevant
  documentation. Reuse the accepted reskin changes and evidence from this task in
  the isolated review worktree; preserve the original preview until its replacement
  is verified.
- Modify Portfolio's viewer integration, project presentation, theme connections,
  routes/assets, relevant tests and documentation. Preserve unrelated work.
- Read pinned Portfolio and ScribbleScan Original source for analysis. ScribbleScan
  application code is an acceptance input, not an application to rewrite.
- Perform relevant research, install project-scoped dependencies, use existing
  local compute, run tests and deterministic evaluations, create private local or
  Tailscale previews, and make scoped commits on the named feature branches.
- Use source fixtures and explicitly disabled paid-model paths for graph generation.
  Do not invoke paid OCR/LLM services merely because credentials are present.
- Use single-agent execution and local whole-change review. Do not add agents or
  recurring AI status checks. Long jobs use identified processes, logs, terminal
  receipts and a supported blocking wait within the host's actual limits.

## Git bases and delivery targets

Verified remote heads at preparation time:

| Repository | Starting revision | Review branch | Worktree |
| --- | --- | --- | --- |
| Flow-Code | `1e05ba91e8c599f66fd31424518e6b7606ad3631` (main) | `codex/flowcode-capability` | `/home/dlybeck/Projects/Flow-Code-worktrees/portfolio-capability` |
| Portfolio | `c6cf613f5f656b36b48b3d7a3198675b53e8141c` (main) | `codex/flowcode-integration` | `/home/dlybeck/Projects/Portfolio-worktrees/flowcode-integration` |

Portfolio's remote `dev` is `c25d62e7f2d03fd31b110716e52f11a24e8a20f4`, an ancestor
of the selected main baseline. No Flow-Code remote `dev` exists. These are facts,
not authority to update either branch.

Dedicated linked worktrees were created after confirmation. The Flow-Code checkout
holding the reskin is a primary clone with uncommitted task changes; only those
accepted changes may be carried into the new worktree. Portfolio's primary
checkout and existing theme worktrees contain unrelated work and remain untouched.
The inspected ScribbleScan checkout is clean at
`d08d4c33d02a62df3a6d9d42ff0a0ce1059f84d9`; record the exact source roots selected
for Original before generation.

Delivery is local commits plus private preview. No push, pull-request publication,
merge into `dev`, or write to `main` is authorized by this contract.

## Human-return boundaries and exclusions

Return for explicit authority if the next necessary action requires money, new
credentials/account access, public deployment, a push or integration outside the
named review branches, repository visibility/licensing changes, material deletion,
safeguard changes, publication of private source-derived exports, or a consequential
product change outside this plan. Continue useful independent work when possible.

Forge and Pocket remain outside public showcase scope. Bowling remains excluded;
David Skills, TennisCourtFinder and Living Forms are not implementation targets.
Universal language support and Flow-Code's broader AI-assistant/MCP product vision
are outside this run unless separately authorized.

Do not return merely because a build or evaluation needs time. Follow the account's
quiet-wait policy and the pursue-goal Codex adapter; do not claim an untested
continuation mechanism works. Mark the goal complete only when all proof and
delivery conditions pass. Otherwise preserve the exact evidence and explain the
real authority or capability boundary using the host's permitted goal controls.

## Available validation surface

The existing reskin has a 24-check passing browser receipt and an active private
preview at `http://100.118.63.4:8096/`. Python, uv, Docker, Git and GitHub CLI are
available. Node/npm run through Docker on this host. Playwright's Chromium Docker
image and Python dependency cache were used successfully in this task for actual
WebGL2 rendering, emulated touch, screenshots and console checks. The portfolio
also supplies browser/server test fixtures and canonical fidelity validation.

The pursue-goal Codex adapter and confirmed native goal govern this run. The linked worktrees and exact validation commands are recorded below. Reuse this document as the compact execution checkpoint rather than
creating competing plans.

## Execution checkpoint — 2026-09-12

- Goal active; both phases implemented locally, verification and delivery still in progress. Original preview and unrelated work preserved. Flow-Code base reskin checkpoint is a504cc5.
- Analysis now merges Python/browser producers, indexes IIFEs/closures/JSX, keeps duplicate Python route definitions separate, fixes import resolution, exports deterministic terrain and retains confidence/source evidence. 78 Flow-Code tests pass; ruff passes. Use `uv run --no-sync pytest tests -q` (repository-wide discovery also collects an uninstalled example application under fixtures).
- Actual source proof: Portfolio activate -> loadPack -> theme_pack_payload; ScribbleScan DemoHandler.processDemoFiles -> demo_digitize -> DemoService.process_demo_files (scheduled by asyncio.create_task). HTTP/service links remain heuristic. Original source unchanged at d08d4c33d02a62df3a6d9d42ff0a0ce1059f84d9.
- One exporter installs the viewer and all three maps: `uv run --no-sync python scripts/export_portfolio.py --portfolio /home/dlybeck/Projects/Portfolio-worktrees/flowcode-integration --scribblescan /home/dlybeck/Projects/ScribbleScan`. Latest inputs change during delivery; regenerate and verify final hashes before committing snapshots.
- Portfolio adds /how-it-works, Flow-Code's document under existing Programs, corresponding project links, a small Home link, bounded return routes and theme-preserving URLs. Board relationships and Programs' original destination retained.
- Private preview: http://100.118.63.4:8097/ from the integration worktree, uvicorn PID recorded in tests/results/flowcode/preview.pid. Original 8096 preview unchanged.
- First browser receipt: 48 passed, /tmp/flowcode-review/acceptance-1/receipt.json. Inspected desktop/phone contact sheets for all seven themes. Found/fixed light-theme label contrast, long floating labels, Planets control/terrain contrast. Added functional 2D evidence/selection fallback; final browser run pending.
- First Portfolio full run timed out at 600s with failures caused by Home's extra row overflowing content-fit. Exact failing 320px Clouds test + Home theme dial now 5 passed after moving the link into existing writing. Full 423-test rerun active (exec session 74167); OS wrapper records /tmp/flowcode-review/portfolio-suite-final.log, .xml, .json, with a 900s timeout. Do not poll. Wait for completion while doing remaining review work.
- Disk filled during work. Preserved task npm dependencies in /tmp/flowcode-capability-node-modules and /tmp/flowcode-original-node-modules, and stale July package-cache temp content in /tmp/flowcode-disk-recovery/uv-tmpFYM1Zw (receipt there). No project source or built preview assets deleted. New evidence uses /tmp/flowcode-review. For Docker builds bind the capability dependency directory to /app/node_modules alongside the viewer /app mount. About 756 MiB was available after recovery; do not broadly clean unrelated data.
- Outstanding: finalize browser/phone/reduced-motion/fallback/real click evidence, resolve full-suite findings, recheck canonical fidelity and final source digests, complete local Standards + Spec review, scoped commits in both feature branches, final private preview screenshots and completion receipt. Native goal must stay active until these finish.
