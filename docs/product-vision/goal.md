# Product goal — bridge human intent and AI execution

**Status:** Narrative “why” for the project. Formal invariants and engineering detail live in **[SPEC.md](./SPEC.md)** and **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

---

## The problem

In AI-assisted development, **one side is often clueless**: the human thinks in **intent and plain names** (“the thing that handles checkout retries”), while the model needs **paths, symbols, and concrete edit sites**. Usually one side guesses. That mismatch drives slow fixes, wrong edits, and endless exploration.

## What we’re building

A **deliberate bridge** between those two ways of understanding the same codebase:

- **Code stays normal** — real files, real tools (Git, tests, linters). Nothing replaces the repo as source of truth for bytes.
- **A parallel map** — user-friendly **names and descriptions** plus structure, **anchored** to stable technical ids and locations so “what the user said” and “what the AI should touch” can be the **same handle**.

Technically this is the **RAW + overlay** split in SPEC: deterministic index from code (truth), plus presentation keyed by those ids (friendly layer). **Labels never replace ids.**

## The “extensive” map (reuse and leaves)

The map should be **honest about where behavior matters**, not only where it is **defined**:

- Shared implementation stays **one place on disk** (DRY, tool-friendly).
- The graph **explodes important reuse**: repeated or widely used code appears as **distinct leaves (or branches) at use sites**, not only as a single isolated node—so when someone points at “this branch,” the system resolves to a **specific** place (file, range, symbol id) without the model inferring which of many call sites they meant.

That **shared reference**—human wording on the map, machine anchors underneath—is what makes fixes **fast** compared to open-ended repo spelunking or “smarter prompting” alone.

## The bet

**Alignment through a maintained, validated bridge** (index + overlay + drift/orphan handling + scoped agent tools + validation gates), not through hoping the model “gets” the codebase from vibes.

---

## UX principles (non-negotiable)

These emerged from product discussion and override convenience-driven design choices:

**1. No code ever surfaces to the user.**
After an AI run, the user sees the map (with amber badges on changed nodes) and a plain-language summary. Diffs, file paths, and line numbers are never shown. The map *is* the diff visualizer.

**2. Node annotations are starting points, not bug locations.**
When a user points at a node on the map, that is a rough area for the AI to begin from — not a precise symbol to patch. The AI should explore the full call graph, follow threads, and potentially make large changes far from the annotated node. The user may be wrong about the exact location; it is the AI's job to resolve that gap.

**3. PM-to-developer, not pair programming.**
The user has high-level intent and the general direction of what needs fixing. The AI does the investigation and coding. The user is available to clarify when the AI needs it, but is not watching code being written. This is not fire-and-forget (one prompt, walk away) and not true pair programming (both looking at code together) — it's closer to a PM briefing a developer. Check-in surfaces should be conversational and plain-language, not code review gates. Progress signals on the map (pulsing badges) let the user know work is happening without demanding attention.

---

## AI integration architecture

**OpenCode + MCP** is the chosen path (2026-03-22):
- **MCP server** exposes the execution graph to any AI client (Claude Code, Cursor, OpenCode, Zed)
- **OpenCode** (`sst/opencode`) acts as the coding agent — model-agnostic, open-source, REST API + SSE
- `session.diff` SSE events from OpenCode drive amber badge updates on the map
- In-house LLM wrappers (`_chat_completion_json`) are for annotation/overlay only, not for coding tasks

See **[ORCHESTRATOR-POC-PLAN.md](./ORCHESTRATOR-POC-PLAN.md)** for the v0 scaffold (comment → plan → execute) that this architecture supersedes.

---

*Captured from product discussion, 2026-03-21 / 2026-03-22.*

**Execution order (v1):** see **[v1-strategy.md](./v1-strategy.md)** — shared spine, in-house graph shell first, optional MCP/IDE after.
