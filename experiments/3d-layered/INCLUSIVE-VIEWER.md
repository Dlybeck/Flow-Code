# Inclusive circular terrain experiment

This viewer consumes Flow-Code exports without a Portfolio dependency. It keeps
all indexed functions within the export's selected source roots. Static call
inference remains partial; a function without an entry path is not labelled dead
or unimportant.

## Try the bundled examples

From this directory, run `npm install` and `npm run build`, then
`python3 -m http.server 8766`. Open
`http://localhost:8766/terrain-rules-prototype.html`.

The default **Essential** mountain retains up to 40 items across six entry
branches, selected from existing relevance scores with their primary paths.
Supporting chains become diamond markers labelled **N supporting steps**.
Expand them from the marker or the **Expandable supporting steps** list. Search
reveals an omitted function and its caller path; **Reset overview** clears these
expansions. Original scores and cumulative heights do not change when pruning.

**Complete** restores the full terrain. Its **Visible detail** control can space
markers in screen pixels or show all markers. The function inventory always
contains the full selected source, in either content mode. Important-looking
unplaced functions remain in **Relevant functions with unknown entry paths**;
selecting one displays it outside the terrain without inventing an entry link.

Primary routes use curvature-based sampling rather than a fixed number of mesh
vertices per call. Facet shading supplies depth without drawing polygon outlines
that could be mistaken for connections. There are two line styles: solid branch
paths and dotted extra calls. Gold highlights the selected path. Selecting a node
explains whether a branch segment is a call, collapsed supporting steps or
project membership, including the available call evidence.

Primary routes are explicit terrain-mesh constraints, so the surface descends
along the same path as the call line. Collapsed-path strokes represent multiple
original steps and can be expanded. Neighbouring branches can have different
altitudes; the guarantee does not apply when walking sideways between branches.
Unplaced-to-unplaced relationships use dotted lines, like other calls outside
the anchored terrain. Invalid geometry reports an error, not a free-mesh fallback.

Search by function, file, or language. Select a search result to center and label
it. Caller/callee buttons navigate known relationships, including secondary
calls. The terrain has no automatic floating titles: a title appears only for
the selected or hovered node, keeping the nodes and branch shapes readable.

All indexed functions remain in the inventory. Displayed unplaced functions sit outside the terrain;
white rings mark unknown entry paths while size/color retain relevance. The
project summit's spokes group entries and are not runtime calls. Inferred calls
remain labelled as possible; source locations and unresolved boundaries are
available in the panel. Additional calls use the shortest angular route around
the circle, including across its display seam.

## Open another project

Generate a normal semantic export, then convert it to the viewer's portable
fixture. The exporter uses a local embedding model, not generative AI.

```bash
flowcode export /path/to/project --project example --src-root src -o map.json
flowcode prototype map.json --title Example -o example.fixture.json
```

Use **Open your map** in the viewer to open `example.fixture.json`. The file is
read locally in the browser; no upload service is involved. A project description
is optional (`--purpose` on export).

To apply updated static analysis to an unchanged semantic snapshot:

```bash
flowcode prototype map.json --repo /path/to/project -o refreshed.fixture.json
```

This refuses a different source digest or function inventory. It refreshes
relationships and entry evidence while preserving the export's relevance scores.
If the code changed, regenerate the semantic export first. There are no
project-name patterns, top-N cuts, or manually fabricated edges in conversion.

## Bundled snapshot provenance

`prototype-fixtures.json` contains complete function inventories from existing
Jina code-embedding exports. Each fixture retains source roots, source digest,
analysis limits and relationship provenance. Four have refreshed relationships
from the analyzer in this branch: ScribbleScan (599 functions), Chef (32),
Fieldhouse Manager (41), and the Algorithms red-black/word-frequency slice (46).
The selected roots are shown in the viewer; these are not claims to index every
file or asset in their repositories.

Flow-Code's 256-function example is explicitly a **saved snapshot**. Its old
source differs from the available checkout, so its relationships were preserved
instead of mixing new analysis with stale scores. Separately, the validation
round analyzed the current available Python source (175 functions).

See `../../docs/validation/inclusive-terrain-run.md` for comparisons, source
checks, browser evidence, remaining limitations and the review outcome.

See `../../docs/validation/essential-terrain.md` for the Essential-view contract and actual-surface validation.

See `../../docs/validation/terrain-linework.md` for before/after mesh quality, graph-preservation checks and line-style validation.
