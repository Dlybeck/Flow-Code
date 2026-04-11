# Product vision — consolidated spec

This folder holds the design docs for **`flowcode`** — a static analysis graph generation library for Python and TypeScript codebases.

| File | Purpose |
|------|---------|
| **[SPEC.md](./SPEC.md)** | **Consolidated** vision: §0 coherent spine, pipeline, rules, language strategy, flowcode package. **Start here.** |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | **Logical** diagram: workspace, indexer, RAW store, diff, overlay, API, UI, agent — must match **SPEC §0–§9**. |
| **[goal.md](./goal.md)** | Narrative **why**: bridge human intent ↔ AI execution (map + anchors). |

## Implementation

The `flowcode` package at [`packages/flowcode`](../../packages/flowcode) is the delivered graph generation layer. See its [README](../../packages/flowcode/README.md) for API, CLI, schema, and `.flowcode.toml` config reference.

## Changelog

| Date | Note |
|------|------|
| 2025-03-21 | Created `product-vision/` + **SPEC.md** to isolate final brainstorming from mixed repo context. |
| 2025-03-21 | **SPEC §0** coherent vision spine. |
| 2025-03-21 | **`ARCHITECTURE.md`** — component diagram + table. |
| 2026-03-21 | **SPEC §9** — Python-native v1 (FastAPI + `src/` canonical), adapter boundary. |
| 2026-04-11 | Scope narrowed to `flowcode` graph generation package. Orchestration docs (ROADMAP, ORCHESTRATOR-POC-PLAN, UPDATE-MAP-PLAN, EXECUTION-MAP-PLAN, NEXT-STEPS, LLM-TESTING) and `docs/planning/` removed. SPEC and ARCHITECTURE updated. |
