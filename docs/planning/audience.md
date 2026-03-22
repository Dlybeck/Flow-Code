# Audience

**Status:** Draft — fill and refine before locking `idea.md`.

**Purpose:** Define who this platform serves first. Everything else (features, pricing, tone, compliance) hangs off this.

---

## 1. Product context (shared understanding)

- This project is a **platform for developing projects** (meta: tools/process for building *other* software or deliverables with AI).
- **v1 audience is intentionally single-user:** the builder (you). Design can stay personal—speed and low ceremony over enterprise patterns unless you later choose otherwise.

---

## 2. Audience hypotheses (yours — edit freely)

### Primary audience

- **Who:** **You** — AI developer with a **computer science degree**; building **personal projects after work**; capable technically but **does not want a heavy, in-depth development process** for this tool or for the projects it helps spawn.
- **What they build:** **Apps** (general software—not blockchain “dapps”); strong tilt toward **AI-assisted** creation. Environment: **web-based**, **visual** first. **Remote access** to a **host PC** (e.g. **Tailscale** — rough plan).
- **What frustrates them today:** **AI-heavy projects refactor often**; wanting **lightweight structural work** (**rewire / rename / remove / add**) **without** maintaining a **full mental map of the filesystem** or hunting **dead code** by reading the entire tree. *(See node-only graph direction in `brainstorming.md` §8.)*

### Secondary audience (optional)

- **Who:** *Deferred — not a goal for v1.*
- **Why they matter later:** *If ever productized.*

### Non-audience (explicit exclusions)

- **Teams / multi-tenant SaaS** as a v1 requirement (solo-first).
- **Deep “professional IDE all day” workflow** as the target experience for *this* platform — you want **visual**, **goal-based / agentic** use, not constant micro-editing loops.
- **File-directory–first navigation** as the **primary** UI — intent is **node-graph–first**; paths may exist only as **backing detail**, not the main shell (see §8.0 in `brainstorming.md`).
- **Vendor-hosted cloud** as the default product story — intent is **open source** others can **run on their own machines** (you personally still imagine **no cloud** for your deployment).
- *(Add more as you rule segments out.)*

---

## 3. Segmentation dimensions (assistant suggestion — adapt or delete)

Use these to stress-test whether you have one product or several:

| Dimension | Questions |
|-----------|-----------|
| **Org size** | Solo vs team vs enterprise — affects auth, billing, audit, SSO. |
| **Technical depth** | Developers only vs mixed technical + PM/design — affects UX and guardrails. |
| **Hosting** | **Self-hosted / OSS on your machine** (aligned); not optimizing for cloud SaaS as the default. |
| **Model stance** | API-only (commercial LLMs) vs open weights vs both — affects infra and compliance. |
| **Regulatory** | Healthcare/finance/education — affects data handling and claims you can make. |

---

## 4. Jobs-to-be-done (JTBD) — fill when ready

**Draft (from 2025-03-21 conversation):**

> When I **have limited energy after work**, I want to **set goals and let an agentic system work toward them** through a **visual, low-friction** web UI (from **anywhere** via **Tailscale** to my **host**), with the **AI reaching out for short summaries and decisions** on **periodic check-ins and issues**—not constant back-and-forth—so I can **ship or iterate on AI-backed apps** without treating side projects like a second day job.

Add variants if multiple jobs matter equally.

**Hands-off (clarified):** **Agentic and goal-based**—avoid a workflow of **quick change → check → repeat** as the primary mode; prefer **delegated runs** with **punctuated human steering**.

**Audio / “call me” (clarified):** **Not a v1 must-have.** Direction is **asynchronous reach-out**: AI **summarizes state**, you **decide next steps** in **brief exchanges** (implementation channel TBD—phone, push, messaging, in-app only, etc.).

---

## 5. Open questions (carry forward to brainstorming)

- **Outbound “call me” channel** — What’s acceptable for v1 (in-app notifications only vs email vs push vs voice/SMS)? Self-hosted + OSS constrains options and secrets handling.
- **Agent boundaries** — What the agent may do unsupervised (filesystem, network, installs, git) vs what always requires your approval; how that interacts with **goal-based** runs.
- **Host machine** — GPU needs for local models; single host vs multiple environments.
- **Graph vs disk canonicality** — When **node rename** or **rewire** conflicts with on-disk layout, which wins and how is conflict shown **without** a directory tree?
- **Agent validation** — Which checks are **blocking** vs **warn-only**; where **guidelines** live (versioned config + skills) so **§10.11** stays in sync with prompts.

---

## 6. Decisions log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-03-21 | **Primary user = self**; personal, after-work projects | Keeps scope and UX honest. |
| 2025-03-21 | Prefer **visual**, **mostly hands-off**; **web-based**; **Tailscale** for remote-to-host (rough) | Shapes access model and UI. |
| 2025-03-21 | **“App” not dapp** — no blockchain-specific meaning assumed | Clarifies stack and scope. |
| 2025-03-21 | **Audio not v1 must-have**; want **AI-initiated summaries** + **short decision** loops for **periodic** check-ins / issues | Defines interaction rhythm without committing to voice. |
| 2025-03-21 | **Hands-off = agentic, goal-based** (not rapid tweak-and-check) | Core UX promise. |
| 2025-03-21 | **Open source on Git**; **run on your machine**; **no cloud** as personal ideal | Distribution and trust model. |
| 2025-03-21 | **No file directory in the primary UX** — **nodes only** are the shell (no separate **notes** layer; “notes” was a **typo** for **nodes**); **floating nodes** / **orphans** signal **dead code**; **refactor** as **graph operations** | Matches **AI-heavy** churn and lowers **whole-codebase** cognitive load. |
| 2025-03-21 | **Modular + DRY** as **design pressure** on **both AI and user** — graph + conventions should ease **cleanup** and **navigation** | Aligns product with maintainable side-project velocity. |
| 2025-03-21 | **User does not author code** in the default product story — **AI implements**; **prompting + validators** enforce graph rules (**leaf-only** code, topology, etc.); user **steers** via goals, **approvals**, **check-ins**, **tests** | Matches “after work, hands-off” and shifts risk to **agent + policy** quality. |
| 2025-03-21 | **Validation pipeline** required for agent adherence — layered **lint/graph invariant/tests/approval/rollback** (see `brainstorming.md` **§10.11**) | Prompt-only compliance is insufficient. |
| 2025-03-21 | **Shared implementation** across multiple **product** leaves — **linked leaves** / **definition + use-site**; **visual** grouping (badge, border); detect **copy-paste duplicate** vs **intentional link** (see **§8.2.2**) | Supports DRY under a modular graph. |
| 2025-03-21 | **MCP-like agent interface** plausible — **graph** as **traversable index** + **tools** to **read / search / test** code on demand (**§9.9**) | Scales under context limits; needs **good tools** + **anti-lazy** policy. |
| 2025-03-21 | **Dual layout** — **`src/`** organized **by functionality** for **AI/tooling** (deps, syntax, tests); **graph** **conceptual** for **user**; shapes may **differ**; **connections always documented** (anchors / mapping) (**§9.13**) | Separates human mental model from machine-friendly tree; **drift** managed by **atomic** updates + validation. |
| 2025-03-21 | **Exploded user graph** — **node per function/method appearance** (each use/reference visible); **one** canonical definition on disk for **AI/cleanliness** (**§8.2.3**) | Max **human** clarity; needs **filters / lazy** load to control **noise** and scale. |
