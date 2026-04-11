# Plan — map comments, orchestrator, execution (POC)

**Status:** Aligned with owner 2026-03-22. Implement slice-by-slice; revise as decisions land.

**Reads with:** **[goal.md](./goal.md)** (why), **[v1-strategy.md](./v1-strategy.md)** (spine: apply path, API, in-house first).

---

## 0. Core value proposition

The execution map gives non-coders a meaningful view of the system — because it follows execution flow, not file structure, it maps to how people mentally model a product. When a user points at something on the map and says "this is wrong," they are working in human terms. The AI translates that directly to real file/symbol edits via hard references in RAW. **The map is the shared language; the code is the ground truth.**

---

## 1. What this POC is for

Ship a **thin vertical slice** that proves:

1. **Intent lives on the map** — anchored notes on nodes/groups, not one undifferentiated chat.
2. **Orchestrator AI** splits all pending comments into **independent chunks** (or explicitly ordered ones) before any code runs.
3. **Developer AI** executes one chunk at a time through the existing apply path.
4. **Changed nodes are visually flagged** on the map after each apply, so the user always knows what just moved.

**Explicitly not in this POC:** GitHub issues, Spec Kit wiring, parallel chunk execution, appearance/use-site nodes, MCP.

---

## 2. User journey (target)

1. **Comment** — User selects one or more nodes on the map and adds a short note. Repeat anywhere; notes stay **pending** until submitted. Notes are anchored to node IDs so the AI always has a hard reference to the relevant code.

2. **Send / Go** — Triggers the **orchestrator AI**. Its job is:
   - Read all pending comments at once.
   - Split them into **logical chunks** — each chunk should be **independently executable** (no shared edit sites, no ordering dependency).
   - If chunks *do* depend on each other, impose an **explicit order** and flag it. Do not silently invent a false sequence — say so.
   - Output a structured plan only. No code, no patches.

3. **Review plan** — User sees the chunk list with any dependency order noted. User can edit, merge, split, or reorder before execution unlocks. The orchestrator's independence guarantee is the primary value here; order is secondary.

4. **Execute (one chunk at a time)** — User picks one chunk. Developer AI gets: the approved chunk description + original comment anchors + node IDs + relevant file paths + small code reads. It proposes a change package compatible with `POST /apply-bundle`. User sees a diff preview → **Approve / Reject**.

5. **Apply + refresh** — On approve: patch applied, repo reindexed, validation runs. Changed nodes on the map are **visually flagged** (highlight or badge). Overlay AI re-annotates affected nodes — nodes show a **"pending annotation"** state during this (it takes time). Once done, updated labels appear.

6. **Repeat** — User reviews the updated map, adds more comments, sends again.

---

## 3. Slices (build order)

Each slice has a stop line so we can revise before the next.

### Slice A — Comments on the map (no AI)

- **Build:** Create/read comments keyed by **node id(s)** + body + timestamp + `pending` flag. Persist to a small server-side file (JSON under the API) so comments survive reload. Keep it boring.
- **UX:** Click node (or lasso selection) → "Add comment"; sidebar lists pending comments with their node anchors.
- **Exit:** User can place ≥2 comments on different nodes; both show as pending; reload does not lose them.

### Slice B — Send → orchestrator output (AI optional at first)

- **Build:** Send / Go gathers all pending comments + minimal context (node ids, overlay labels, file paths). Call orchestrator:
  - **v0 stub:** deterministic fake response (fixed chunks) to wire the UI.
  - **v1:** one model call, strict prompt — output structured plan (chunks + independence assertion + explicit order where needed + "unclear" flags), no code.
- **UX:** Show chunk list in an editable panel; user confirms before execution unlocks.
- **Exit:** From two pending comments, user gets a two-chunk plan they can reorder; no repo mutation yet.

### Slice C — Execution for one chunk + visual delta

- **Build:** For the selected chunk, developer AI gets: approved chunk + anchors + subgraph context (ids, file paths, small reads). Proposes a change package for `POST /apply-bundle`. UI: diff preview + Approve / Reject.
- After apply: map refreshes; **changed nodes get a visual flag** (e.g. amber ring or "updated" badge with timestamp). Nodes pending overlay re-annotation show a **spinner/pending state**.
- **Exit:** Full loop: comment(s) → orchestrator → one chunk → approve → repo updates → changed nodes visually flagged on the map.

### Slice D — Hardening (only after C is boring)

- Clear error surfaces: orchestrator failed, apply failed, validation failed, annotation timed out.
- Persist chunk plan across reloads (in case annotation is still running when user returns).
- **Defer:** parallel chunk execution, multi-item queue runner, GH issues.

---

## 4. Orchestrator prompt shape (conceptual)

Instructions to the model (when not stubbed), in plain language:

- You receive user notes tied to map node anchors. Each note has a node ID with a file path reference.
- **First:** group notes that touch the same logical concern or the same area of code into one chunk.
- **Second:** check each chunk pair for conflicts — shared edit sites, call-chain dependencies, or ordering constraints. Chunks must be **independently executable** or explicitly ordered.
- **Third:** if two chunks cannot be made independent, assign an explicit order and explain why. If order is genuinely unclear, say so — do not invent a sequence.
- **Do not** write patches, diffs, or solutions here. Output the plan only.

Output: JSON — array of chunks, each with: `id`, `summary`, `comment_ids[]`, `node_ids[]`, `depends_on[]` (chunk ids, empty if independent), `order_note` (string, blank if truly independent).

---

## 5. Visual update states (new)

Two distinct UI states to implement in Slice C:

| State | Trigger | Visual |
|-------|---------|--------|
| **Changed** | Node's file/symbol was in the applied diff | Amber ring or "updated N min ago" badge on the node |
| **Annotation pending** | Overlay AI is re-annotating this node after apply | Spinner or pulsing outline; tooltip: "Updating description…" |
| **Annotation done** | Overlay write completes | Badge clears; new label visible |

These states live as transient fields in the overlay (`lastModified`, `annotationPending`) and are surfaced in the UI layer only — they do not affect RAW.

---

## 6. Open questions

1. **Comment persistence:** Small JSON file served by the API (recommended) vs `localStorage`. Server file is better — survives hard refresh and works in API mode already used for overlay.
2. **Context budget:** For orchestrator, send only ids + labels first. Add file snippets only if the model produces bad chunks in practice.
3. **Naming in UI:** "Chunks" internally; consider "tasks" or "steps" in the user-facing panel.
4. **Provider:** Single env API key on server only — agree before Slice C. DeepSeek for overlay annotation; consider a stronger model for orchestrator planning.

---

## 7. Changelog

| Date | Note |
|------|------|
| 2026-03-22 | Initial draft: comments → orchestrator (group + order) → review → single-item execution → existing apply path. |
| 2026-03-22 | Realigned with owner: orchestrator primary job is independence guarantee (not just ordering); visual delta states (changed, annotation pending, done) added as first-class UX; core value prop section added. |
