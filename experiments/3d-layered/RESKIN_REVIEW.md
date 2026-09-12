# Flow-Code portfolio reskin

This is a working reskin of the actual Three.js terrain viewer, prepared on
`codex/portfolio-reskin` from upstream `1e05ba91e8c599f66fd31424518e6b7606ad3631`.
It is a local, uncommitted implementation preview. Nothing was pushed or deployed
to the public portfolio.

## Preview

- Reskin: <http://100.118.63.4:8096/>
- Preserved original: <http://100.118.63.4:8096/original.html>
- Both URLs are served by `flowcode-portfolio-preview`, bound only to the host's
  Tailscale address. The service is temporary and uses a read-only directory mount.

The art direction borrows the canonical portfolio's green board, handwriting,
cream paper, blue ink and restrained red accents. The real terrain uses paper
colours, toon shading, stronger crease lines and readable call strokes. Its flat
grounding apron fades into the board. There are no illustrative replacement
mountains or manually placed function landmarks.

The page supports orbiting, zooming, hover previews, persistent click/tap selection,
an entry-point action, a keyboard-accessible function picker, both existing
layouts, and an exact camera reset. Details remain visible after the pointer moves
away. The selected function label follows its real position in the 3D view.

## Source and boundaries

`graph.json` is the existing upstream Flow-Code snapshot: 46 functions and 49
calls. It has not been regenerated. It is a historical snapshot of Flow-Code's
Python code, not a graph of the portfolio or a claim to cover Flow-Code's current
entire repository. `provenance.json` records the source revision and input hash.

Graph SHA-256:
`88abd91ffcab761a07c2816e31578efcf8d7f024b29fdac16a87b0b0fe45adc3`

The call-path view retains exactly the upstream terrain vertex coordinates,
1,268 triangle indices, node positions and call edge paths. Browser verification
compares these arrays against `original-app.js`; style, line width and node size
are allowed to differ.

The original similarity mode throws `Cannot read properties of undefined
(reading 'upperIds')` in its constrained triangulator for this snapshot. Calls can
cross when laid out by similarity, so those segments cannot all be forced into
terrain ridges. The reskin constrains ridges only in call-path mode. Similarity
mode triangulates the existing coordinates without those crossing constraints,
producing 1,678 triangles while preserving all 46 functions and 49 call records.

The browser downloads only local static assets. Dependencies are pinned and
bundled; no model call, credential or third-party runtime request is needed.
`original-app.js` is deliberately preserved for comparison, with only its CDN
imports replaced by equivalent package imports for the local bundle.

Portfolio integration is still a separate step: generate a source-grounded map
of its Python/browser interactions, add the optional Home entry and project
links, and review any private-project export before publishing it. This preview
does not alter Home navigation, Board Themes or other project selections.

## Run

From this directory, with Node and Python installed:

```sh
npm ci
npm run build
python3 -m http.server 8096 --bind 127.0.0.1
```

This host uses Docker for Node. Rebuild the existing preview with:

```sh
docker run --rm --network none \
  -v /home/dlybeck/Projects/Portfolio/.scratch/flowcode-portfolio/experiments/3d-layered:/app \
  -w /app node:22 npm run build
```

The running server sees rebuilt files immediately. `node_modules/` and `dist/`
are generated and ignored by the upstream repository's existing `.gitignore`.

## Validation and review

`../../evidence/verification.json` records 24 passing browser checks. The full
acceptance script is `../../evidence/verify_viewer.py`. It runs in Chromium using
actual WebGL2 rendering through SwiftShader, including emulated touch viewports
at 390 × 844 and 360 × 740, and desktop views at 1440 × 960 and 1024 × 768.

Checks cover geometry preservation, functioning similarity mode, entry-point
selection, persistence, labels, clicking real 3D spheres, orbiting, zooming,
reset, keyboard selection, the complete function list, mobile UI bounds and
touch, reduced-motion damping, the existing Canvas2D fallback, browser errors
and runtime network requests. All final screenshots were inspected. There were
no browser errors, failed requests or third-party runtime requests.

This is browser emulation, not acceptance on physical phones or every GPU.
The inherited 2D fallback remains a simpler hover-based graph view; it does not
provide the 3D viewer's full controls. No parser/export code changed, and the
Python analysis suite was outside this frontend change's validation scope.

Whole-change review was performed locally against the user's corrected request
and the viewer's `CLAUDE.md` screenshot/error-checking workflow. The Standards and
Spec reviews were not independent agent reviews. The original/reskin copies are
intentional comparison fixtures for this preview, not a proposed permanent
duplication of the analysis engine. Findings fixed before delivery included
mobile framing, persistent selection state, camera reset momentum, the broken
similarity triangulation and an inappropriate error overlay on the 2D fallback.

## Assets

- Board texture: canonical Portfolio theme, revision `c6cf613`,
  `static/themes/canonical/assets/background.svg`.
- Palette: the same theme's `presentation.json`.
- Fonts: Architects Daughter and Patrick Hand, downloaded from Google Fonts;
  their OFL notices are included beside the local font assets.
