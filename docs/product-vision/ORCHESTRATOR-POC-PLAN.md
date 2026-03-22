# Plan — map comments, orchestrator, execution (POC)

**Status:** Draft for review with the owner. When aligned, implement slice-by-slice; revise this file as decisions land.

**Reads with:** **[goal.md](./goal.md)** (why), **[v1-strategy.md](./v1-strategy.md)** (spine: apply path, API, in-house first).

---

## 1. What this POC is for

Ship a **thin vertical slice** that proves:

1. **Intent lives on the map** (anchored notes, not one undifferentiated chat).
2. **Send / Go** turns scattered notes into a **structured plan** the user can **fix before any code runs**.
3. **One execution pass** can run against that plan using the **existing** “propose → review → apply + checks” path you already validated.

**Explicitly not in this POC:** GitHub issues, Spec Kit wiring, multi-item auto-pipelines, appearance/use-site nodes, MCP.

---

## 2. User journey (target)

1. **Comment** — User selects one or more nodes on the map and adds a short note (Google Docs–style anchor). Repeat anywhere they want; notes stay **pending** until processed.
2. **Send / Go** — Opens an **orchestrator** view (presented as a **chat** is fine). The system’s job here is **planning only**: **group related notes**, then **suggest an order** that respects **“nothing before its prerequisites.”** It does **not** output final patches here.
3. **Review plan** — User sees **clusters** (or a numbered list with **depends-on** hints). User can **edit, merge, split, or reorder** when the guess is wrong — especially order, since grouping is expected to be easier for the model than perfect scheduling.
4. **Execute** — User picks **one** cluster or **one** line (POC: **only one active execution at a time**). Standard **coding** flow: proposal → preview → **Approve** → your existing **apply + validate + refresh map** path.

**Ordering rule (product):** Items may **depend** on each other; they do **not** need to be independent. The plan must **not** put work **before** what it needs. If order is unclear, the orchestrator says so and the user decides.

---

## 3. Slices (build order)

Each slice has a **stop line** so we can revise before the next.

### Slice A — Comments on the map (no AI)

- **Build:** In the brainstorm POC (or minimal successor shell): create/read **comments** keyed by **node id(s)** + body + timestamp + `pending` flag. Persist in memory first, then **local JSON** or a tiny API file under `public/` if you need reload survival — keep it boring.
- **UX:** Click selection → “Add comment”; list pending comments somewhere visible (sidebar or panel).
- **Exit:** User can place **≥2** comments on **different** nodes; both show as pending; reload does not lose them (if persistence is in scope for A; otherwise state “session only” in the plan).

### Slice B — Send → orchestrator output (AI optional at first)

- **Build:** **Send / Go** gathers all **pending** comments + **minimal context** (e.g. labels, ids, optional tiny code snippets for selected nodes — exact shape TBD). Call **orchestrator**:
  - **v0 stub:** deterministic fake response (fixed clusters) to wire UI.
  - **v1:** one model call with a **strict prompt**: output **only** structured plan (clusters + suggested order + “unclear” flags), **no code**.
- **UX:** Show plan in an editable list; user **confirms** before execution unlocks.
- **Exit:** From two pending comments, user gets a **two-row or two-cluster** plan they can **reorder**; **no** repo mutation from this step alone.

### Slice C — Execution chat for **one** plan item

- **Build:** For the **selected** row/cluster, **execution** chat gets: user-approved plan line + **same anchors** + subgraph/snippet policy (start small: **ids + file paths + small reads**). Model proposes a **change package** compatible with **`POST /apply-bundle`** (or internal equivalent). UI: read-only preview + **Approve / Reject**.
- **Exit:** One **end-to-end** path: comment(s) → plan → **one** item → **approve** → repo updates → map refreshes (API mode as today).

### Slice D — Hardening (only after C is boring)

- Clear **error** surfaces (orchestrator failed, apply failed, validation failed).
- **Optional:** second model pass “check plan for ordering mistakes” (flag only).
- **Defer:** GH issues, Spec Kit, parallel execution, multi-item queue runner.

---

## 4. Orchestrator prompt shape (conceptual)

Instructions to the model (when not stubbed), in plain language:

- You receive **user notes** tied to **map anchors**.
- **First:** group notes that are **about the same thread** of work.
- **Second:** within and between groups, propose **execution order** so **no step assumes work that appears later**. If unsure, **say order is unclear** and ask the user to choose — do not invent a false sequence.
- **Do not** write patches or full solutions in this step.

(Output format: JSON schema or numbered markdown + machine-parseable block — pick one in implementation; JSON is easier for “edit plan” UI.)

---

## 5. Open questions (for our review pass)

1. **Persistence:** Session-only vs `localStorage` vs small server file for comments — preference for POC?
2. **Context budget:** For orchestrator, do we send **only ids + labels**, or **first N lines** of each file under selected nodes? (Start tiny to control cost and noise.)
3. **Naming in UI:** **Topics**, **work items**, or **phases** for the plan list?
4. **Provider:** Single env API key on **server** only (recommended) — agree before Slice C?

---

## 6. Changelog

| Date | Note |
|------|------|
| 2026-03-22 | Initial draft: comments → orchestrator (group + order) → review → single-item execution → existing apply path. |
