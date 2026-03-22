# Idea (solid product concept)

**Status:** Draft — **aligned to** **[`../product-vision/SPEC.md`](../product-vision/SPEC.md) §0–§11**; mark **Locked** only when the **gate checklist** (this file, §9) is satisfied.

**Purpose:** Decision-ready **what / for whom / why** in one place. **SPEC** is the **invariant** source; **brainstorming** is the **trail**.

---

## 1. One-sentence pitch

*(Write for a stranger on an elevator.)*

> A **self-hosted**, **graph-first** workspace where **you steer** with **goals and approvals** on a **live map of your app**, and an **AI implements** the code—**v1 is Python-native** (web services, **FastAPI**-style as the reference shape); **other languages** ship as **adapters** on the same core—**RAW truth from the repo**, **friendly overlay** for understanding, **validators** so “done” means **checked**, not **guessed**.

---

## 2. One-paragraph pitch

*(Expand: problem, approach, who benefits.)*

Side projects **refactor often**; **folder trees** and **chat-only** editors force you to **rebuild a mental map** by hand. This product is a **web-first** environment (e.g. reach your **host** via **Tailscale**) where the **primary UI is nodes**, not directories: a **deterministic indexer** builds a **RAW** graph from real code; an **overlay** adds **names and descriptions** keyed by **stable ids**. **v1 proves the loop** on a **canonical Python web repo**—**`src/`** package, **pytest**, **FastAPI** (or similar) as the **reference** stack—then **widens** layouts and adds **more adapters** (e.g. TypeScript) without rewriting the core. The map can **show every important use** of shared logic (**appearances**) while **`src/`** stays **DRY** and **tool-friendly**. An **agent** changes the repo through **MCP-style tools**, **bundled applies**, and a **validation stack**; **orphans and drift** after edits are handled with **logic**, not model improvisation. **You** set **intent**, **review diffs**, answer **check-ins** on **risky** steps, and run **tests**—**default story: you do not author source**.

---

## 3. For whom (link to audience)

- **Primary:** **You** — solo builder, **after-work** apps, **low ceremony**; technical background but **not** wanting a **second job** of filesystem archaeology. Details: [audience.md](./audience.md) §2, JTBD §4.
- **Secondary (if any):** **Deferred** for v1 (see audience §2.2).

---

## 4. Core promise (3 bullets max)

- **Steer, don’t type:** Goals, approvals, check-ins, tests, and **layout**—**not** default hand-authoring of code.
- **One repo, two layers:** **RAW** = truth from code; **overlay** = **understanding**—**labels never replace ids**.
- **Trust through enforcement:** Bundled edits + **linters / types / graph rules / tests**; **honesty** when analysis is **partial**.

---

## 5. Non-goals (v1)

Explicitly **not** building yet (see **SPEC §11** and [audience.md](./audience.md) §2.3):

- **Blueprint-style** visual programming or **user-drawn** topology as the **routine** dev model.
- **Multi-tenant SaaS** or **team-first** product requirements.
- **Vendor cloud** as the **default** story — **self-hosted / OSS** on **your machine** is the baseline.
- **Replacing** Git or normal language tooling — **complement** them.

---

## 6. Differentiation

Why this is not redundant with:

- **General chat LLM UIs:** Persistent **project graph** tied to **real symbols and use sites**, not a **thread** and a **paste buffer**.
- **Existing AI coding tools:** **Graph-first** shell (no **directory tree** as primary nav); **exploded** reuse UX; **split RAW vs overlay** for **non-dev-shaped** mental models on the same repo.
- **Raw API + scripts:** **Bundled**, **validated** agent path with **deterministic** index and **orphan** handling—**product**, not **glue**.

---

## 7. Success signals (pre-metrics)

Qualitative “we’re onto something” signals before hard KPIs:

- You can **name a goal**, **walk away**, and return to a **summarized check-in** with **mergeable** output—not **micro-prompt** marathons.
- **Shared** behavior **shows up** wherever it matters on the **map** without **duplicating** files **by mistake**.
- After a **refactor**, **overlay** and **map** **recover** via **rules** (orphans, remap), without **silent** lies about **what exists**.

---

## 8. Open questions (remaining before build phase)

Carry **audience** and **engineering** unknowns forward; **SPEC §7–§9** name product-shaped ones:

- **Outbound check-in channel** for v1 (in-app only vs more) under **self-hosted** constraints — [audience.md](./audience.md) §5.
- **Agent boundaries:** unsupervised vs **always-approve** for **network**, **installs**, **git** destructive ops.
- **Blocking vs warn-only** validation; where **§10.11-style** rules live so prompts and CI stay aligned.
- **MVP language** adapter depth (e.g. **TS first**) vs time-to-first **RAW** spike.

---

## 9. Gate: “Idea is solid” checklist

Check when you can honestly mark **Status: Locked** at the top:

- [ ] Audience paragraph in `audience.md` matches this file.
- [ ] MVP is one clear capability, not a bundle of ten.
- [ ] Non-goals are written and agreed.
- [ ] `how-to-use.md` describes a plausible first session without hand-waving.

---

## Changelog

| Date | Note |
|------|------|
| 2025-03-21 | Filled from **SPEC §0–§11** + **audience** pointers (pass 2 — coherent vision). |
| 2026-03-21 | Pitches updated for **Python-native v1** + **adapter expansion** (matches **SPEC §9**). |
