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

*Captured from product discussion, 2026-03-21.*

**Execution order (v1):** see **[v1-strategy.md](./v1-strategy.md)** — shared spine, in-house graph shell first, optional MCP/IDE after.
