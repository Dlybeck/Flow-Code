# Product goal — execution-space navigator for AI-assisted development

**Status:** Narrative "why" for the project. Formal invariants and engineering detail live in **[SPEC.md](./SPEC.md)** and **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

---

## The situation this is designed for

AI coding assistants are now a normal part of writing software. Lots of a codebase gets produced this way — the developer describes intent, the AI implements, the developer reviews the result. As a consequence, developers know their own code **less deeply than a developer who wrote every line** would.

That gap isn't a bug. Offloading comprehension to the AI is part of what makes AI-assisted development work. The problem is that the gap still has to be **crossable on demand** — when something breaks, when you want to extend a feature, when you need to brief a collaborator, you have to be able to get into the structure quickly without reading every file.

Traditional tools don't help this mode of work:

- **File trees** are organized by artifact (files and folders), not by what the code does. If you have a functional question ("how does this handle retries?"), you have to guess which files to open before you can ask it.
- **Reading source** is exactly the thing AI-assisted workflows are trying to avoid for most questions. If you could skim the code fast enough to answer it, you probably wouldn't have delegated implementation in the first place.
- **Chat-only AI** has no shared coordinate system. Pointing at "this part" requires copy-pasting code or remembering function names, and when the AI references something back ("the issue is in the plugin loader"), you're stuck translating words back to files.

## What this is

A **visualization layer that sits alongside existing AI coding assistants** (Claude Code, OpenCode, any MCP-capable client). It shows the codebase as a 3D execution terrain where:

- **Height = importance.** A peak at the entry point; ridges for the substantive architectural spine; leaves for helpers. Branches that matter stick out.
- **Structure = call flow.** Descent from peak to leaves follows primary-tree call edges. You read "what triggers what" by walking the mountain outward.
- **Spatial layout = execution flow, not filesystem.** Sibling branches correspond to call-graph siblings, not file-system siblings.

Crucially, the viz does **two** jobs that are both essential and neither is optional:

### 1. User-to-AI: shared pointing surface

You can select a node, a branch, or a region and ask a question. The AI receives:

- The **functional context** your selection implies ("this branch," "this entry's flow," "this subsystem")
- The **concrete source code** for those nodes — call sites, neighbors, types, whatever's needed

You never have to say "open `x.py` line 47." You stay in functionality-space; the AI is handed both your intent and the underlying source for free.

### 2. AI-to-user: where-is-this reification

When the AI references part of the code ("the issue is in how the plugin loader resolves entry points"), it can programmatically highlight the corresponding branch on the mountain. You don't translate words back to files — your eyes go straight to the region.

## Why this matters more than a file tree or a chat

The two paradigms compose badly without a middle layer:

- Chat alone = no shared spatial reference between user and AI.
- File tree alone = wrong organization for functional questions.
- Code-reading alone = high cost, which is the whole thing AI-assisted workflows are trying to reduce.

The mountain is the **shared coordinate system** that lets chat-based AI interaction stay in functionality-space while still being anchored to real source. It's not replacing the chat, the IDE, or the AI — it's making them usable together without the constant translation tax.

## What has to be true for this to work

Three invariants that drive design:

1. **The map's structure must be deterministic and stable.** Same codebase produces the same mountain every time. Users build muscle memory for "the plugin-loading subsystem is over here."

2. **The selection → AI-context pipeline must be rich.** Selecting a branch has to hand the AI enough to reason with — source, neighbors, summaries, call context — or the paradigm falls back to copy-pasting.

3. **The height metric must survive scrutiny.** If you click what looks like an important peak and discover it's a trivial wrapper, or dig into what looks like a valley and find critical logic, you stop trusting the map and slide back into file-tree thinking. The metric (currently `novelty × log(LOC)` — embedding-distinctiveness × code substance) has to consistently surface what a reader would recognize as architectural.

Everything in SPEC and ARCHITECTURE about deterministic indexing, overlay labels keyed to RAW ids, validation gates, and drift handling is **in service of these three invariants**. The indexer has to produce stable structure; the overlay has to stay anchored; the AI tools have to deliver rich context; the validation has to keep importance honest.

---

## UX principles (still in force)

**1. Code stays in AI-space; user stays in functionality-space.**
The map is the user's surface. Source code is what the AI handles when you ask a question. When the AI explains, it explains in plain language and highlights the map. The user doesn't open files to understand — they point and ask.

**2. Node annotations are starting points, not bug locations.**
Clicking a node tells the AI "roughly here." The AI is expected to explore, follow threads, and potentially make changes far from the click. The user may be wrong about the exact location; resolving that gap is the AI's job.

**3. PM-to-developer, not pair programming.**
The user has high-level intent and general direction. The AI does the investigation and coding. Not fire-and-forget (the user clarifies when asked) and not true pair programming (the user isn't watching code being written). Progress and change signals show up as map badges — conversational check-ins, not code-review gates.

---

## AI integration — MCP server

**MCP is the chosen path.** flowcode runs as a local MCP server that any MCP-capable client (Claude Code, OpenCode, Cursor, Zed, etc.) can connect to. The same server hosts the map's HTTP surface for the browser viz.

Exposed tools (target set):
- `get_selected_node()` — what the user clicked most recently + its context
- `get_node(id)`, `search_nodes(query)`
- `get_upstream(id)` / `get_downstream(id)` — call-graph cones
- `get_important_nodes(n)` — architectural spine
- `highlight(node_ids)` — AI lights up a region on the map for the user

In-house LLM calls (`_chat_completion_json`) are used **only for overlay curation / labeling**, never for coding tasks. Coding is the external client's job.

---

*Captured from the current thesis, 2026-04-19. Supersedes the prior "bridge human intent and AI execution" framing by making the two-way pointing loop and the execution-space navigation paradigm explicit.*
