# Progressive outcome graphs

Date: 2026-09-23

## Question

Does an established visualization pattern match this interaction?

1. Start with a project and a small set of meaningful outcomes.
2. Select an outcome to see its beginning-to-end flow.
3. Select a stage to replace or open it as a more detailed subgraph.
4. Repeat until the visible nodes are source functions and result sites.
5. Never render the complete graph at once; collapsed stages stand in for their
   hidden subgraphs.

## Finding

Yes. The established graph concepts are **compound (hierarchical) graphs** and
**graph folding**. The interaction also uses **focus+context** and **semantic
zoom**, but those terms describe the presentation more than the underlying data
model.

The closest implementation reference is yFiles folding. Its master graph keeps
the complete hierarchy while a separate view graph contains only the currently
expanded portions. A collapsed group becomes a folder node; it can later be
expanded inline or entered as a separate graph. This is nearly the proposed
"nesting eggs" behavior. [yFiles folding documentation](https://docs.yfiles.com/yfiles-html/dguide/folding/)

The closest standardized visual language is BPMN's **collapsed subprocess**. A
single activity carries a plus marker while collapsed and exposes the activities
inside it when expanded. The standard explicitly uses expanded subprocesses to
show grouped activities more compactly. Flow-Code does not need to adopt the
full BPMN notation, but this validates the proposed interaction.
[OMG BPMN 2.0.2, subprocesses](https://www.omg.org/spec/BPMN/2.0.2/PDF)

IDEF0 is the closest precedent for the information hierarchy: begin with a
context activity, then recursively navigate to the activity's decomposition,
carrying boundary inputs and outputs across levels. The NIST navigation guide
links every activity to its decomposition and describes parent-level boundary
arrows. [NIST IDEF0 navigation guide](https://pages.nist.gov/traction-lithium-battery-recovery/instructions.html)

The yFiles hierarchical-nesting demo also preserves the previous arrangement
while re-laying out the newly visible graph after every expansion. It explicitly
supports edges that cross group boundaries. [Hierarchical nesting demo](https://www.yfiles.com/demos/layout/hierarchical-nesting/)

This interaction is therefore established. The distinct Flow-Code contribution
would be constructing the hierarchy around **observable project outcomes and
their explanations**, rather than folders, packages, or manually authored
diagram groups.

## The correct graph model

The overall structure is not one tree. It has two structures:

- A **containment tree**: project → outcome → stage → substage → source element.
  Every item has one containing parent, so folding remains predictable.
- A **flow DAG at each level**: stages can branch and converge. A transcription
  flow may choose an AI provider and later merge into common response parsing.

Treating the whole thing as a tree would duplicate shared functions or hide
convergence. Treating it as one flat DAG would recreate the unreadable full
graph. Compound graphs combine the useful parts of both.

One source function may contribute to several outcomes or stages. The hierarchy
therefore contains **view occurrences** that all reference one canonical source
node; it must not force the code itself into one fabricated owner. Likewise,
loops and retries can be folded into a stage at higher levels and exposed only
inside that stage.

At the top level, the project contains outcome nodes such as **Transcription
returned**, **Document saved**, and **PDF downloaded**. Selecting an outcome
opens its stage-level flow. A stage such as **Extract image content** is a folded
compound node whose child graph explains that stage. Functions remain the
source-backed leaves of the containment hierarchy.

Collapsed stages must carry evidence rather than impersonating functions. A
stage should store:

- the source functions and result sites it contains;
- its incoming and outgoing boundary edges;
- its child flow graph;
- the structural or embedding evidence used to group it;
- an optional manual title or project-specific correction.

## Established interaction principles

### Folding, not deletion

The complete analyzed graph stays in a master model. Expansion changes only the
visible projection. This matches yFiles' master/view split and React Flow's
expand-collapse example, which keeps the complete graph while rendering only
the visible portion. [React Flow expand-collapse example](https://reactflow.dev/examples/layout/expand-collapse)

### Nested flows

React Flow calls a flow inside a node a **sub flow** and permits edges between a
child flow and nodes outside its parent. This is the direct UI analogue of a
stage containing a more detailed explanation. [React Flow sub-flow documentation](https://reactflow.dev/learn/layouting/sub-flows)

### Focus plus context

Research on focus+context exploration recommends increasing detail only for the
selected focus while retaining the rest at a lower level of detail in the same
view. This reduces the disorientation caused by opening disconnected plots.
[Focus+Context Exploration of Hierarchical Embeddings](https://diglib.eg.org/items/d21fd2ad-0ff8-4fa5-96cb-5a820f33e031)

For Flow-Code, expansion should keep the selected outcome flow visible and
replace only the selected stage with its children. Sibling stages remain folded.
Animated, incremental layout should preserve the user's mental map.

### Semantic zoom is optional

Pad++ established zooming as a way to navigate large information spaces while
preserving location and relationships. Flow-Code can later reveal more detail
based on zoom, but explicit selection is safer for the first prototype because
it makes the chosen abstraction level unambiguous. [Pad++ paper](https://hci.ucsd.edu/hollan/Pubs/JH1995-1.pdf)

## Existing code tools

SciTools Understand is a close code-navigation precedent. It provides
expandable architecture graphs, collapsible clusters, call/called-by trees, and
an Information Browser whose relationship branches expand one hop at a time.
Its architecture hierarchy can group code by feature or subsystem independently
of the directory layout. [Understand architecture graphs](https://docs.scitools.com/graphs/Graph_Architecture.html),
[graph variants](https://docs.scitools.com/help/graphs/open-a-graph.html), and
[Information Browser](https://docs.scitools.com/help/explore/information-browser.html)

Those features navigate architectural containment or code relationships. They
do not demonstrate Flow-Code's proposed outcome-first hierarchy in which a
human-facing result expands into explanatory stages and then source functions.
This is a scoped comparison, not a claim that no product has ever attempted it.

CodeSee Maps is another partial precedent: its codebase dependency map starts
with most folders collapsed and lets users expand them, but the hierarchy is
file/folder containment rather than outcome explanation.
[CodeSee map exploration](https://docs.codesee.io/docs/explore-your-map)

CodeQL path queries validate a useful part of the hidden analysis model: they
compute source-to-sink data-flow paths and associate every result with a path.
They require the query author to define the source and sink, so they do not solve
automatic product-outcome discovery or nested explanation.
[CodeQL path-query documentation](https://codeql.github.com/docs/writing-codeql-queries/creating-path-queries/)

## Implementation options

| Option | Relevant support | Material limitation |
| --- | --- | --- |
| **yFiles** | Mature master/view folding, drill-down, incremental layouts, cross-boundary edges | Commercial dependency |
| **Cytoscape.js + expand-collapse** | Open-source compound nodes and a purpose-built expand/collapse extension | More custom work for stable nested flow layout and product polish |
| **React Flow + ELK** | Subflows, custom nodes, straightforward web UI; ELK supplies hierarchical layered layout | React Flow's exact expand-collapse example is Pro; folding state and evidence model remain Flow-Code work |
| **ELK alone** | Open-source compound layered layout with cross-hierarchy edges and configurable hierarchy handling | Layout engine only; it does not render or own interaction state |

Sources: [Cytoscape.js compound-node extension index](https://js.cytoscape.org/),
[cytoscape.js-expand-collapse](https://github.com/iVis-at-Bilkent/cytoscape.js-expand-collapse),
[ELK graph hierarchy](https://eclipse.dev/elk/documentation/tooldevelopers/graphdatastructure.html),
and [ELK layered compound-graph support](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html).

## Recommendation for Flow-Code

Prototype a 2D **progressive outcome graph** before doing more mountain work.
Use a master evidence graph plus a folded view graph:

```text
ScribbleScan
├── Transcription returned
├── Document saved
└── PDF downloaded

Transcription returned
Images received → Prepare images → Extract content → Invoke AI
                → Parse response → Format → Return transcription

Invoke AI (expanded)
Choose provider → Build request → Call provider → Extract response
          └────→ Fallback provider ───────────────┘
```

The first experiment should answer only three questions:

1. Does expanding one stage in place preserve comprehension better than entering
   the stage as a separate subchart?
2. Can the layout remain stable enough that the user understands what changed?
3. Can every folded stage show concise evidence for the real source elements it
   contains without looking like a fabricated code node?

Do not begin with automated outcome or stage discovery. Hand-author one faithful
ScribbleScan outcome hierarchy from real source evidence, test the interaction,
and only then evaluate deterministic extraction and embedding-based grouping.
The visualization question should be proven before building a new analyzer.
