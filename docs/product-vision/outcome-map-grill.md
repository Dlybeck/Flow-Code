# Outcome map product grill

Status: implemented and validated on review branch
Started: 2026-09-23

## Purpose

Resolve Flow-Code's product model before approving another implementation run.
This document records settled owner intent, explicit uncertainties, decisions
made during the grilling session, and assumptions that earlier prototypes got
wrong.

## Settled context entering the session

- Flow-Code is primarily a codebase familiarization tool for someone who has
  never seen the project.
- The core analysis must work without generative AI. A later optional AI pass
  may add summaries, but it cannot be required to regenerate the map.
- Every low-level fact should remain connected to real source files, symbols,
  and eventually lines.
- Showing every function at once creates an unreadable graph. Omitting large
  parts of the repository also creates an incomplete and potentially misleading
  explanation.
- A call-graph leaf is not necessarily a meaningful result. Internal helpers
  such as image normalization can return to their caller while the project's
  actual behavior continues.
- The promising interaction is progressive disclosure: a small high-level view
  expands into increasingly detailed subgraphs while preserving access to the
  complete analyzed codebase.
- Flow-Code may later become shared visual context between a person and an
  external coding agent. The agent should be able to refer to, focus, and
  explain source-grounded regions rather than inventing a separate diagram.

## Settled during the session

### Generality comes before one showcase

The product model must not be designed around ScribbleScan. ScribbleScan may be
one validation input, but no project is the canonical shape. Design and
evaluation must use several structurally different codebases so that a pipeline,
web application, library, interactive frontend, and long-running service are
not forced into one project's vocabulary or control flow.

### The opening view is minimal and self-explanatory

The first view should be as simple and high-level as possible. It should use
very little text, avoid presenting an overwhelming complete graph, and make the
next interaction obvious. If the view is a flow, a visible beginning and end
plus clear expansion affordances are a promising form. The mountain remains an
option only if it can satisfy the same clarity requirement.

### Analysis is broadly inclusive; presentation is folded

Flow-Code should analyze nearly every function. Ideally every analyzed function
is reachable somewhere in the hierarchy or branches. Exceptional code that
cannot be placed honestly may use an explicit fallback chosen during technical
design. Completeness of the evidence model does not require simultaneous
visibility of every node.

### Visible nodes are source-backed abstractions

A visible node does not have to display source code or correspond one-to-one
with a function. It may summarize a verified group of source elements. Every
node must retain exact references to its backing files, symbols, and available
line ranges so an external AI can inspect the relevant code when the user points
to that node. Whether source is exposed directly in the human UI remains open.

### Seed navigation enters a focused child view

Opening a seed node dives into it. The seed becomes the root node of a new
focused layer with its own nodes and leaf nodes. The interface retains a simple
path back through the parent layers rather than expanding the child graph inline
by default.

### Leaf relevance is delegated for comparative validation

The owner delegated the choice between project-wide and locally relative leaf
relevance. Test both across several structurally different projects. Prefer the
strategy that produces clearly more intuitive leaf ordering; combine signals if
the evidence supports it. Do not return for a routine technical judgment. Return
only if the comparison exposes a consequential product trade-off that cannot be
resolved from evidence.

### Compare two presentations over one model

The next discovery work should try the mountain and a simpler alternative, such
as a nested two-dimensional flow, against the same underlying graph and
interaction. The comparison should determine which is clearer rather than
preserving either presentation by assumption.

## Superseded assumptions

- Entrypoints alone provide a sufficient high-level story.
- Every terminal node in a call graph is a project outcome.
- Rendering a complete call graph and visually emphasizing a small region is
  enough for familiarization.
- The mountain renderer should determine the new product model before the
  information hierarchy is understood.

## Current hypothesis, not yet approved

Flow-Code may need two related structures:

1. A complete evidence graph derived from source.
2. One or more folded explanatory views whose highest level presents the
   project's behavior with minimal text and obvious expansion.

The view could expand through stages and substages until it reaches canonical
source nodes. The exact cross-project meaning of starts and ends, the top-level
semantic unit, and the handling of multiple concurrent or recurring behaviors
remain open.

## Proposed language awaiting confirmation

The owner's root/seed/leaf description identifies a recursive, folded execution
view. The model is coherent as a presentation hierarchy, but literal tree terms
would obscure callbacks, convergence, loops, and source functions reused in
more than one flow. The following vocabulary is proposed:

- **Behavior**: one understandable execution story from an external trigger to
  one observable result.
- **Trigger**: the boundary event that begins a behavior, such as a user action,
  request, command, message, public API call, scheduled tick, or startup.
- **Outcome**: an observable result of a behavior, such as a response, returned
  value, persisted change, emitted event, rendered state, or produced artifact.
- **Entry boundary**: the input through which execution enters the currently
  visible flow. A top-level behavior's entry boundary is a trigger; a child
  flow's entry boundary receives control or data from its parent step.
- **Exit boundary**: the point through which execution leaves the currently
  visible flow. A top-level behavior's exit boundary is an outcome; a child
  flow's exit boundary returns control or data to its parent flow.
- **Step**: one visible action inside a behavior.
- **Compound step**: a step backed by a hidden child flow that can be expanded.
  This corresponds to the proposed seed node.
- **Atomic step**: a step with no useful child flow at the current level of
  explanation. It may still call runtime or third-party code outside the useful
  project explanation.
- **Focused flow**: the child flow shown when a compound step is opened. Its
  selected compound step becomes the local context, not a new global root.
- **Source node**: a canonical file, symbol, or line-backed fact in the evidence
  graph. Several visible step occurrences may reference the same source node.

The term **call-graph leaf** remains available for a function with no resolved
outgoing project call. It is intentionally different from an **outcome** because
the function can return to its caller and execution can continue.

### Owner vocabulary decision

Flow-Code will currently use **root node**, **node**, **seed node**, and **leaf
node** as its product vocabulary. The precise analysis terms remain useful
underneath:

| Product term | Analysis meaning |
| --- | --- |
| Root node | Trigger or local entry boundary |
| Node | Visible execution step |
| Seed node | Compound step with an expandable child flow |
| Leaf node | Outcome or local exit boundary |

The mapping is provisional but approved for continued design. It is recorded in
the repository's root `CONTEXT.md` glossary.

### Deferred mountain metaphor

Peak, stream, and lake-like language was proposed as a possible future visual
vocabulary if the mountain remains the chosen architecture. It is not part of
the current model and creates no present requirements. Revisit it only while
designing or comparing the mountain renderer.

### Edge cases the model must represent

- branches that later converge;
- a parent calling several sibling helpers in sequence;
- loops, retries, and streams without pretending they are one-way trees;
- externally invoked callbacks and framework routes;
- asynchronous work whose result appears in another process or callback;
- several success and failure outcomes from one trigger;
- long-running services where startup is not the useful beginning of every
  behavior;
- one source function reused by several behaviors or compound steps.

## Open decision frontier

1. Decide whether every top-level behavior must connect one trigger to at least
   one outcome.
2. Decide how multiple independent behaviors appear in the minimal opening
   view.
3. Settle how leaf nodes are ranked at the project level and inside focused seed
   views.
4. Decide how automatically inferred boundaries and groupings communicate
   uncertainty without adding substantial text.
5. Define the evidence that will decide between the mountain and the simpler
   presentation.

## Autopilot resolution

The implementation and real-project comparison resolved the current frontier:

- A user does not declare an outcome. Flow-Code detects source-backed roots and
  extracts normal and exceptional exits from each focused function.
- A top-level behavior must have a detected root and at least one local exit.
  The UI calls these endings, not guaranteed business outcomes, because static
  analysis cannot prove an externally observable result in every framework.
- Every analyzed function receives a focused layer. Functions that cannot be
  reached from a detected root remain available in **All code** with an honest
  `No root path · still indexed` label.
- The retained leaf order is **relative relevance**, a hybrid led by similarity
  to the focused root, with project-purpose similarity and a success-path bias
  as secondary signals. Pure project-wide ranking sometimes promoted a generic
  completion; pure local ranking sometimes promoted an exception over the
  useful result.
- The simple flow is the default presentation. It exposed alternate exits and
  branching more clearly across the tested projects and on mobile. The mountain
  remains a first-class optional view over exactly the same nodes and edges.
- All connectors now come from the behavior model. The renderer does not draw a
  decorative chain between sibling exits.

The remaining product questions concern better semantic grouping above the
function layer and richer outcome names. They do not block this source-grounded
prototype.

## Decision log

- Do not center the design or implementation on ScribbleScan.
- Favor a minimal opening view with obvious interaction and very little text.
- Analyze nearly every function and keep it reachable where an honest placement
  exists.
- Compare a mountain and a simpler flow presentation over the same data model.
- Use root node, node, seed node, and leaf node as the current product language,
  mapped to more precise analysis terms underneath.
- Permit visible nodes to summarize multiple source elements, while requiring
  exact source references that an AI can inspect.
- Enter a focused child view when opening a seed node; the seed becomes that
  view's local root.
- Compare project-wide and root-relative leaf relevance and choose from evidence
  without routine owner involvement.

## Confirmed Autopilot goal contract

### Objective

Deliver a source-grounded Flow-Code prototype that automatically discovers
understandable root-to-leaf behaviors, presents them through recursively focused
seed views, and establishes whether a mountain or a simpler flow is the clearer
default presentation. The user must not have to declare outcomes before the
tool can generate a useful view.

### Observable proof

1. Flow-Code derives root and leaf candidates from source boundaries and
   execution evidence, distinguishing an internal no-call helper from a true
   end of the visible behavior.
2. The opening view is minimal, high-level, and gives an obvious next action.
   It ranks a manageable set of primary behaviors while keeping the rest
   accessible.
3. Opening a seed enters a focused child view in which the seed becomes the
   local root and the child behavior has its own leaf nodes and path back.
4. Every visible node retains stable references to its backing files, symbols,
   and available line ranges for future AI inspection. Nearly every analyzed
   function remains accounted for; honest unplaced coverage is explicit.
5. Project-wide and root-relative leaf relevance are compared across several
   structurally different projects and the retained strategy has recorded
   evidence.
6. A mountain and a simpler flow presentation consume the same behavior model
   and are inspected on desktop and mobile. The clearer default is selected
   from comprehension, legibility, and stability evidence.
7. Core generation is deterministic and independent of generative AI. Relevant
   automated tests, reproducibility checks, browser validation, and whole-change
   review pass.
8. A hosted review prototype is available for remote owner inspection.

### Scope and authority

- Work in `/home/dlybeck/Projects/Flow-Code-worktrees/terrain-rules-prototype`
  on `pilot/outcome-first-trails`, based on revision `4c5135c`.
- Modify Flow-Code analysis, schemas, folding and ranking logic, prototype
  renderers, tests, evidence, and relevant documentation.
- Read other local projects as equal validation inputs without modifying their
  application code.
- Install project-scoped dependencies, use local compute, run tests and browser
  evaluations, make scoped commits, push the review branch, and update the
  existing public GitHub Pages prototype.
- Preserve a stable machine-readable node/evidence contract for later AI
  integration. A full MCP/chat implementation is outside this run.
- New language adapters, production Portfolio integration, paid APIs,
  generative map construction, and unrelated mountain polish are excluded.

### Safety boundary and delivery

Money, new credentials, private-source publication beyond the existing bounded
prototype artifacts, material deletion, safeguard changes, changes to other
applications, and any merge into `main`, `dev`, or Portfolio production require
fresh owner authority. Delivery is reviewed commits on the named branch, its
authorized push, and the hosted review prototype; protected integration branches
remain untouched.
