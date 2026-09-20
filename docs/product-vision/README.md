# Product vision

This folder records the current design for Flow-Code, an independent codebase
familiarization tool for people who have not seen the source before.

| File | Purpose |
|---|---|
| [goal.md](./goal.md) | Audience, experience, terrain meaning, independence, and AI boundary. Start here. |
| [SPEC.md](./SPEC.md) | Product invariants, supported languages, artifacts, and current non-goals. |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | The implemented source-to-static-viewer pipeline and host boundary. |
| [EXECUTION-MAP-PLAN.md](./EXECUTION-MAP-PLAN.md) | Historical execution-IR plan with a note showing what shipped. |

## Current implementation

- Python, JavaScript, TypeScript, Java, C, C#, and Haskell each produce a
  single-language execution graph and semantic terrain.
- Terrain uses local code embeddings plus deterministic scoring. An optional
  human-written purpose is embedded locally.
- The 3D viewer works as a self-contained static site and has a 2D fallback.
- Portfolio integration is an adapter around the same static output.
- General mixed-language semantics, Kotlin, and Go are later phases.

## Direction change

Earlier documents described an MCP shared surface for AI-assisted development.
That idea remains a possible later consumer. Since 2026-09-20 the product focus
has been newcomer familiarization and portfolio presentation. Core map
generation has no generative-AI dependency. A possible future summary feature
is limited to an explicit one-time enrichment artifact.
