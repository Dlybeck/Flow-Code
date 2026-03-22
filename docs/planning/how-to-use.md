# How to use (product vision)

**Status:** Aligned to **[`../product-vision/SPEC.md`](../product-vision/SPEC.md) §0** — same coherent spine; refine as you ship.

**Purpose:** How the product **shows up in someone’s day**: first session, recurring flows, words on screen, guardrails. Not low-level architecture (that’s **SPEC** + **brainstorming**).

---

## 1. Relationship to other docs

- **[`../product-vision/SPEC.md`](../product-vision/SPEC.md)** — **§0** is the **single spine**; this file is the **experience** layer on top.
- [audience.md](./audience.md) — who this is for (v1: you, solo, after-work).
- [brainstorming.md](./brainstorming.md) — full rationale and session history.
- [idea.md](./idea.md) — **elevator + paragraph pitch** and promises (**draft**, same spine as SPEC); **lock** when checklist passes.

---

## 2. Mental model you want users to have

> Users should think of this product as **a live map of their app** (built from their real code) that **they steer**, while an **AI implements** changes **safely** through **checked** steps—not as a **folder tree** or a **chat-only** code editor.

**Primary job:** **Ship and reshape** side projects with **low ceremony**: set intent on the **map**, **approve** or **redirect** when the system **checks in**, **trust** that **structure** and **code** stay **aligned** without maintaining two mental models by hand.

---

## 3. First-time experience (Day 0)

1. **Open** the app (e.g. to your machine via Tailscale) and **point** it at a **project** (or start from a template).
2. **See the map** — **friendly names and descriptions** on **nodes** (from the **overlay**); optional **technical** detail on demand. **No** primary **file-directory** view.
3. **Understand reuse** — the same **shared** behavior (e.g. a title helper) can **appear** in **many** places on the map; **one** implementation underneath (**exploded** appearances, **§0** invariant 3).
4. **Set a goal** on a **node** or capsule (e.g. “polish Account copy”) and **let the agent run**; **review** **diff** + **validation** result; **accept** or **send back**.
5. **Respond to a check-in** when the system **summarizes** and asks for a **decision** (especially for **structural** or **risky** changes).

**Time-to-value target:** First **meaningful** change merged or previewed **under an hour** for a small repo; **tune** with real usage.

---

## 4. Core recurring workflows

### Workflow A — Goal-based build / change

- **Trigger:** You want a **feature or fix** expressed in **product** terms.
- **Steps:** Attach **goal** to the right **map region** → agent **plans + edits** (code + overlay + rules as needed) → **validators** run → you **approve** or **revise** → optional **check-in** for big moves.
- **Outcome:** **Working** behavior + **map** still **matches** repo (**§0** invariant 4).

### Workflow B — Understand before touching

- **Trigger:** “Where does X live?” / “What uses Y?”
- **Steps:** **Pan/zoom** map; **expand** capsules; read **descriptions**; follow **appearance** nodes to **one** definition; optional **diff / read-only** snippet (you’re **not** expected to **type** source by default).
- **Outcome:** **Confidence** where to attach the **next goal**.

### Workflow C — Handle check-ins & issues

- **Trigger:** Agent **pauses** with **summary** + **options** (periodic or on **blocker**).
- **Steps:** Read **short** summary → choose **direction** → agent **continues** or **rolls back** per policy.
- **Outcome:** **Goal-based** progress without **chatty** micro-steering.

### Workflow D — Layout only (no structure change)

- **Trigger:** Map feels **cluttered** or hard to read.
- **Steps:** **Auto-layout**, **drag** nodes for **your** view, **collapse** subtrees — **visualization only**; **topology** changes still flow through **agent + approval** when product rules say so.
- **Outcome:** **Cleaner** personal view **without** pretending to **rewire** the product by hand-drawing graph edges.

---

## 5. Objects and language (glossary)

| Term | Meaning for users |
|------|-------------------|
| **Map / graph** | The **main** screen: **nodes** and **links** describing the app **as you think about it** (plus **appearances** where things are **used**). |
| **Node** | One **unit** on the map — may be a **group** or a **leaf**; **not** “a file” by default in the **headline** (paths stay **behind** the node). |
| **Appearance** | “**This** place **uses** that behavior” — may **repeat** for **shared** code so you **see** every **important** use. |
| **Description** | **Plain-language** text on a node — from the **overlay**, for **understanding**; **not** a second source of truth. |
| **Goal / task** | What you want **done**, **attached** to part of the map. |
| **Check-in** | Agent **stops** with a **summary** and asks for a **decision** — **not** constant back-and-forth. |
| **Run / apply** | When the agent’s **proposed** changes are **validated** and (if required) **approved** and **landed**. |
| **(Behind the scenes)** **RAW** | **Technical** graph from **code** — users **rarely** name it; **power** view only if you add it. |

---

## 6. Boundaries and guardrails (user-facing)

- **API keys / model access:** Clear **error** if missing; **no** silent failure. **Self-hosted** story: **you** configure **keys** on the host.
- **Destructive changes:** **Preview** + **confirm** for **big** deletes or **structural** rewires; **undo / branch** where the product supports it (**SPEC** / engineering).
- **What should never happen silently:** **Merging** changes that **fail** validation; **dropping** overlay or map **links** without **visible** **audit** (orphans handled by **rules**, but **you** can see **what changed**).
- **Misleading descriptions:** **Stale** or **wrong** copy is **bad UX** — mitigate with **curation** policy, optional **approve** on **sensitive** areas, and showing **“last updated”** when you ship it (**brainstorming §9.19**).

---

## 7. Dimensions (intent for v1)

| Dimension | Intent |
|-----------|--------|
| **Collaboration** | **Solo** first; **no** multi-tenant **requirement** in v1. |
| **Artifacts** | **Git** history + **RAW** index + **overlay** + **agent run logs** / **diffs** as the **default** saved story. |
| **Integrations** | **Git** required; **Tailscale** (or similar) for **remote host** access; **external IDE** optional **escape hatch**, not the **default** path. |
| **Observability** | **Validation** output, **test** results per **node** scope, **clear** **pass/fail** on **apply**. |

---

## 8. Delight and trust

- **Delight:** **One** shared **title** helper **visible** on **every** screen that uses it — **no** hidden reuse. **Auto-layout** makes a **messy** session **readable** again.
- **Trust:** **Validators** and **bundled** applies mean **“done”** implies **checked**, not **guessed**. **Honest** **partial** map where **static analysis** is **weak** (**degraded** regions), not **pretend** completeness.

---

## 9. Scenarios to validate (read aloud)

- **As a** builder **I want to** attach a goal to **Account** **so that** the AI **implements** it **without** me **browsing** `src/`.
- **As a** builder **I want to** see **every** place a **shared** control **shows up** **so that** I **don’t** **assume** **duplicated** code.
- **As a** builder **I want** **check-ins** on **risky** steps **so that** I **stay** **hands-off** but **not** **out of control**.

When these sound **concrete** without **“trust us”** hand-waving, this doc matches **SPEC §0**.

---

## Changelog

| Date | Note |
|------|------|
| 2025-03-21 | Rewritten to align with **`docs/product-vision/SPEC.md` §0**; removed empty template placeholders. |
| 2025-03-21 | §1 cross-link: **`idea.md`** now a filled pitch draft (pass 2). |
