# Product vision — consolidated spec

This folder holds the **single place** to read the **current** product direction without wading through the full Q&A trail in `docs/planning/`.

| File | Purpose |
|------|---------|
| **[SPEC.md](./SPEC.md)** | **Consolidated** vision: **§0 coherent spine**, then pipeline, rules, risks, links to deep planning. **Start here.** |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | **Logical** diagram: workspace, indexer, RAW store, diff, overlay, API, UI, agent, validation — must match **SPEC §0–§9**. |
| **[ROADMAP.md](./ROADMAP.md)** | **Full development phases** (0–8): order of work so the build stays on vision; **AI & tool hosts** (MCP + HTTP, solo v1); detail per phase when you start it. |
| **[goal.md](./goal.md)** | Narrative **why**: bridge human intent ↔ AI execution (map + anchors). |
| **[v1-strategy.md](./v1-strategy.md)** | **v1 architectural decision**: shared Python spine, **in-house graph shell first**, optional MCP/IDE **after**; **next steps** (bundle → API → UI → model → adapters). |
| **[ORCHESTRATOR-POC-PLAN.md](./ORCHESTRATOR-POC-PLAN.md)** | **Draft POC plan**: map-anchored **comments** → **Send/Go** orchestrator (group + order) → **review** → **one** execution item → existing apply path. |
| **[UPDATE-MAP-PLAN.md](./UPDATE-MAP-PLAN.md)** | **Update map**: AI fills **overlay** (`displayName`, `userDescription`) — **product-language**, bottom-up **symbols → files**, DeepSeek server-side, **`POST /update-map`**. |

## Relationship to other docs

- **`docs/planning/brainstorming.md`** — Full conversation-derived detail, section numbers (§8, §9, §10…), session logs, and explorations that didn’t make the cut.
- **`docs/planning/audience.md`** — Who / JTBD; **`idea.md`** — **elevator + paragraph pitch**, promises, non-goals, differentiation (**draft**, same spine as SPEC); **`how-to-use.md`** — **first-session / workflows / glossary**; **SPEC.md** remains the **invariant** summary and technical consolidation.

## Repo layout reminder

- **`poc-brainstorm-ui/`** — Throwaway **visual** POC (React Flow); not the product.

## Changelog

| Date | Note |
|------|------|
| 2025-03-21 | Created `product-vision/` + **SPEC.md** to isolate final brainstorming from mixed repo context. |
| 2025-03-21 | **SPEC §0** coherent vision spine; **`planning/how-to-use.md`** aligned to same spine (pass 1). |
| 2025-03-21 | **`planning/idea.md`** filled as pitch layer (pass 2). |
| 2025-03-21 | **`ARCHITECTURE.md`** — component diagram + table (pass 3). |
| 2026-03-21 | **SPEC §9** — Python-native v1 (FastAPI + `src/` canonical), adapter boundary; **`planning/idea.md`** pitches synced. |
| 2026-03-22 | **`ROADMAP.md`** — phased full development guide (Phase 0 done → agent + v1 polish). |
| 2026-03-22 | **ROADMAP** *AI and tool hosts* + **SPEC §6** / **ARCHITECTURE** alignment (platform-agnostic MCP + HTTP). |
| 2026-03-21 | **`goal.md`** + **`v1-strategy.md`** — narrative goal and **in-house-first** delivery order with numbered next steps. |
| 2026-03-22 | **`ORCHESTRATOR-POC-PLAN.md`** — comments + orchestrator + execution POC slices for review. |
| 2026-03-22 | **`UPDATE-MAP-PLAN.md`** — “Update map” AI overlay curation (DeepSeek, bottom-up, API + POC). |
