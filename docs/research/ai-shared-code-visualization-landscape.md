# AI-Shared Code Visualization Landscape

Research date: 2026-09-23

## Question

How much of the following product already exists?

1. Decompose a codebase into an approachable visual hierarchy.
2. Let a person move from project outcomes into progressively deeper implementation detail.
3. Tie every visible element to concrete files, symbols, or lines.
4. Let a person and an AI use the same visual state to discuss the code.
5. Let the AI focus, highlight, expand, and animate verified paths while explaining them.

This review used public project pages, papers, documentation, and source repositories. It is a scoped landscape review, not evidence that no unpublished or private product has implemented the complete idea.

## Finding

Most components already exist, and several projects combine two or three of them. I did not find one system that combines all five into an outcome-first, recursively folded, source-grounded code map with two-way human/agent visual control.

The closest research precedent is **CodeMap**. The closest usable open-source products are **Understand Anything**, **GitNexus**, and **Axon**. **VibeGraph** demonstrates an early AI-narrated animated traversal. Outside code comprehension, **Graphologue**, **Sensecape**, and **CoMAP** show how a graph can become persistent common ground between a person and an AI.

This suggests Flow-Code should not compete as another repository diagram generator. Its distinct opportunity is a shared, evidence-backed visual language through which a person and a coding agent can point to, inspect, and explain the same program behavior.

## Examples to inspect

### CodeMap

- [Project page and embedded demo](https://gaojie058.github.io/code-map/)
- [Paper](https://arxiv.org/abs/2504.04553)
- [Source](https://github.com/gaojie058/code-map)

CodeMap is unusually close to the human-comprehension problem. It uses hierarchical maps to support movement from global architecture to local functions and detailed code. Selecting a node opens a local map, and the selected context can be passed to an LLM chatbot. Its evaluation compared the system with a static architecture tool and reported substantially more map use and less dependence on interpreting long chatbot responses.

The main differences are consequential. CodeMap organizes around business modules and code entities rather than human-meaningful outcomes. Its maps and summaries rely heavily on LLM generation and can be wrong. The published interaction shows the human selecting context for the chatbot; it does not show an external coding agent controlling the same visible map through stable highlight, expansion, camera, and animation commands.

### Understand Anything

- [Live demo](https://understand-anything.com/demo/)
- [Product site](https://understand-anything.com/)
- [Source](https://github.com/Egonex-AI/Understand-Anything)

Understand Anything combines Tree-sitter extraction with AI summaries and domain interpretation. Its interactive graph links files, classes, and functions to source; supports hierarchical drill-down; provides domain and process views; offers semantic search and chat; and can generate dependency-ordered tours. It also integrates with coding tools through plugins and skills.

This is the strongest current example to study before building more analysis machinery. Its structural facts are source-derived, but the high-level meaning and tours are AI-generated. It does not appear to begin with a compact list of observable project outcomes or expose a public protocol by which an external agent manipulates the exact graph state the person is viewing.

### GitNexus

- [Web explorer](https://gitnexus.vercel.app/)
- [Source](https://github.com/abhigyanpatwari/GitNexus)

GitNexus builds a Tree-sitter knowledge graph of dependencies, calls, communities, entrypoints, and execution flows. It offers a visual explorer and exposes graph context to coding agents through MCP, including process traces and source paths. This establishes that a code graph can serve both a human-facing explorer and an agent-facing context service.

The two clients share underlying graph data, but the public material does not show the agent steering the visible graph itself. Its principal narratives begin with entrypoints and call flows rather than meaningful results such as “PDF exported” or “transcription returned.”

### Axon

- [Source and demonstrations](https://github.com/harshkedia177/axon)

Axon links nodes to exact code, exposes callers, callees, impact, process membership, and entrypoint flow traces, and provides MCP integration for agents. Its visualizer includes animated flow-trace and impact-ripple modes. It is a useful precedent for presentation actions over a grounded graph.

It currently supports a narrower language set and remains call-graph/process centered. It does not supply the outcome-first recursive folding or a shared conversational visual state.

### GitDiagram

- [Interactive site](https://gitdiagram.com/)
- [Source](https://github.com/ahmedkhaleel2004/gitdiagram)

GitDiagram converts a GitHub repository into an interactive AI-generated architecture diagram, streams an explanation, and links components back to files or directories. It is a polished example of rapid orientation, but it trades depth and deterministic provenance for a concise generated overview.

### VibeGraph

- [Live site](https://vibegraph.dev/)
- [Source](https://github.com/madara88645/VibeGraph)

VibeGraph combines an interactive call graph, source lines, AI explanations, and a “Ghost Runner” animated traversal with narration. It is the closest visible example of the AI-walkthrough behavior in the proposed vision. The project is very early and remains a call-graph explorer rather than an outcome model.

### Eraser and Relayer

- [Eraser codebase diagrams](https://docs.eraser.io/codebase-diagrams)
- [Eraser MCP](https://docs.eraser.io/mcp)
- [Relayer Labs](https://relayerlabs.ai/)

Eraser demonstrates shared artifact control: an AI agent can create, read, search, and update diagrams through MCP while a person works with the visual artifact. It does not provide a deterministic code graph or line-level evidentiary model.

Relayer presents a live graph of a coding agent’s activity. A person can inspect nodes, follow its context, and redirect work. This is strong evidence that visual state can mediate human-agent collaboration, but its graph represents agent activity rather than stable program behavior.

## Relevant work outside code visualization

### Graphologue

- [Paper](https://arxiv.org/abs/2305.11473)
- [Prototype](https://graphologue.app/)

Graphologue turns an LLM conversation into a live node-link diagram. People can select nodes for context-specific prompts, grow or collapse branches, merge diagrams, and move between prose and graph elements. Its authors describe the interaction as graphical, non-linear dialogue. This is nearly the desired conversation model, but its nodes are generated concepts rather than verified code entities.

### Sensecape

- [Paper](https://arxiv.org/abs/2305.11483)
- [Project](https://sensecape.github.io/)

Sensecape uses a multi-level abstraction hierarchy. A person can move among levels and ask the model to explain or expand a selected concept. It provides a strong interaction precedent for nested, progressively disclosed subgraphs.

### CoMAP

- [Project and paper](https://comap2025.github.io/)

CoMAP treats a visual graph as persistent shared context. A global agent receives the serialized graph, local agents receive a selected node and its neighborhood, and people and agents can both modify the workspace. Although its domain is project-based learning rather than software, it is the clearest research precedent for a graph acting as common ground between human and AI.

## Capability comparison

| System | Source-linked decomposition | Progressive hierarchy | AI conversation | Agent-facing graph | Visual AI walkthrough/control | Outcome-first |
|---|---:|---:|---:|---:|---:|---:|
| CodeMap | Yes | Yes | Selected-node context | No public protocol | Limited | No |
| Understand Anything | Yes | Yes | Yes | Skills/plugins | AI tours | No |
| GitNexus | Yes | Partial | Yes | MCP | Not demonstrated | No |
| Axon | Yes | Partial | Limited | MCP | Animated traces | No |
| GitDiagram | File/directory | Limited | Generated explanation | No | Limited | No |
| VibeGraph | Yes | Limited | Yes | No | Animated narration | No |
| Eraser | Weak for code truth | Manual/generated | Yes | MCP | Diagram editing | No |
| Relayer | Agent activity only | Yes | Yes | Native agent | Live activity graph | No |
| Graphologue | No code grounding | Yes | Native interaction | No | Shared graph dialogue | Not code |
| CoMAP | No code grounding | Yes | Native interaction | Agent contexts | Shared graph editing | Not code |

## What remains distinct

The reviewed tools leave a coherent unoccupied product shape:

1. **Outcome-first orientation.** The first view names meaningful results, not every file or inferred architecture component.
2. **Recursive successful-process folding.** An outcome expands into stages; a stage expands into substages; the user reaches actual symbols and lines only when desired.
3. **A deterministic evidence graph.** Files, symbols, calls, data movement, return sites, writes, emissions, and external effects remain source-derived and inspectable.
4. **A shared conversation focus.** Human and agent refer to stable node and path IDs, so “this step” has an exact meaning.
5. **Agent presentation commands.** The agent can focus, highlight, expand, collapse, open source, and play a path without inventing graph structure.
6. **A separate AI overlay.** Explanations, inferred meaning, summaries, and proposed relationships are visually distinct, removable, and never silently promoted into the evidence graph.

The important correction to the motivating premise is that an AI does not fully understand a codebase. It often has broader recent working context than its owner, but that context is partial and fallible. The shared graph is useful because it exposes the AI’s claims and assumptions against verifiable program evidence.

## Recommended architecture

```text
source code
    |
    v
evidence graph ---------> folded outcome view
    ^                            |
    |                            v
agent reads exact IDs <--- conversation focus
    |
    v
temporary explanation and presentation actions
```

The core visualizer can remain independent of generative AI. Parsing and graph construction produce the evidence graph. Deterministic folding and optional manual project descriptions produce the default view. AI is an optional client of that graph and an author of clearly marked overlays.

A narrow agent interface could begin with:

- `get_visible_graph`
- `focus_nodes(ids)`
- `focus_path(ids)`
- `expand(node_id)` and `collapse(node_id)`
- `open_source(symbol_id)`
- `play_tour(steps)`
- `annotate(target_id, text, provenance)`
- `clear_overlay()`

Stable IDs matter more than pixel coordinates. They let a portfolio visitor, Flow-Code, and an external coding agent refer to the same evidence while each controls its own presentation.

## Product implication

The market and research evidence validate both halves of the idea: people use interactive graphs to learn code, and AI can converse through or act upon visual graphs. The underdeveloped part is the bridge between them.

Flow-Code’s strongest framing is therefore:

> A source-grounded visual conversation protocol for code, organized around what a project accomplishes and expandable down to the exact implementation.

The next practical validation should run ScribbleScan and Flow-Code through Understand Anything, GitNexus, and Axon. The comparison should record what each system identifies as a process, how it links to source, where it loses the outcome story, and whether its output could become input to Flow-Code rather than being rebuilt.
