# Product vision — consolidated spec

This folder holds the design docs for **`flowcode`** — a visualization layer for AI-assisted development, powered by a Python + TypeScript static analysis graph generator.

flowcode runs as a local MCP server alongside existing AI coding assistants (Claude Code, OpenCode, Cursor, Zed, etc.). It surfaces the codebase as a 3D execution terrain the user and the AI can both point at — a shared coordinate system that keeps functional questions anchored to real source without forcing the user back into the file tree.

| File | Purpose |
|------|---------|
| **[goal.md](./goal.md)** | Narrative **why**: AI-assisted development creates an understanding gap, and this is the bridge across it. **Start here.** |
| **[SPEC.md](./SPEC.md)** | Detailed engineering invariants: RAW/overlay split, pipeline, language strategy. Still accurate on the technical substrate; its higher-level framing predates the explicit execution-space-navigator thesis and should be read alongside **goal.md**. |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | **Logical** diagram: workspace, indexer, RAW store, diff, overlay, API, UI, agent — must stay consistent with SPEC §0–§9. |
| **[EXECUTION-MAP-PLAN.md](./EXECUTION-MAP-PLAN.md)** | Deprecated brainstorming from the structure-vs-execution-first debate. Execution-first won; see **goal.md** and **ARCHITECTURE.md** for the current framing. |

## Current implementation status

- **`flowcode` package** (`src/flowcode/`): Python + TypeScript indexing → execution IR → overlay. Working, tested against golden fixtures.
- **3D viz experiment** (`experiments/3d-layered/`): active iteration on the mountain renderer — height encodes importance via per-edge slope driven by the child node's own novelty-×-substance score.
- **MCP server**: next step. Target tools exposed to AI clients: `get_selected_node`, `get_upstream`, `get_downstream`, `get_important_nodes`, `highlight`.

See the [top-level README](../../README.md) for API, CLI, schema, and `.flowcode.toml` config reference.

## Changelog

| Date | Note |
|------|------|
| 2025-03-21 | Created `product-vision/` + **SPEC.md** to isolate final brainstorming from mixed repo context. |
| 2025-03-21 | **SPEC §0** coherent vision spine. |
| 2025-03-21 | **`ARCHITECTURE.md`** — component diagram + table. |
| 2026-03-21 | **SPEC §9** — Python-native v1 (FastAPI + `src/` canonical), adapter boundary. |
| 2026-04-11 | Scope narrowed to `flowcode` graph generation package. Orchestration docs removed. SPEC and ARCHITECTURE updated. |
| 2026-04-19 | Framing updated: flowcode is an **execution-space navigator / shared pointing surface for AI clients**, not a standalone editor. New [goal.md](./goal.md) replaces the prior "bridge human intent and AI execution" narrative. |
