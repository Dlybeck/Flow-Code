# Brainstorming

**Status:** Living document — capture everything of value before converging on `idea.md`.

**Purpose:** Hold **exploration**: meanings of the product, options, tradeoffs, and assistant suggestions. This file can be messy; `idea.md` should be tight.

---

## 0. Process note (from conversation)

- The user wants **complete documentation** of brainstorming: **both user notes and assistant contributions**, not only what the user said.
- Staged flow: **audience → brainstorming → idea → how-to-use** (see [README](./README.md)).
- **No demo code** in this phase—documentation only.
- **Collaborative fill (2025-03-21):** User and assistant progress through **Q&A in chat**; after each exchange the assistant **merges distilled answers** into `audience.md` → `brainstorming.md` → later `idea.md` / `how-to-use.md`, and **logs Q&A threads** in this file under dated session headings.
- **Novel / surprising ideas — when to bring them in:** **Any time.** Say them in chat as soon as you want; the assistant logs them here (dated session or **§6 Ideas parking lot**). The linear doc order does **not** mean “wait until audience is finished.” It only means: if a novelty **changes who it’s for** or the **core promise**, we **revisit** `audience.md` / `idea.md` after capturing the raw thought. If it’s a **mechanism or feature** (UI pattern, agent behavior, integration), it usually stays in **brainstorming** until it survives skepticism, then gets promoted to `idea.md` or `how-to-use.md`.

---

## 1. Vocabulary: what “AI development platform” might mean

*(Assistant summary from early thread — refine or replace as the idea sharpens.)*

1. **Developer tooling** — IDE extensions, CLI, or web app that wires models, prompts, templates, and evaluation into a daily workflow (same *category* as AI-assisted coding tools, but could be a distinct product).
2. **Model / app lifecycle** — Training, fine-tuning, deployment, monitoring, versioning (MLOps / LLMOps).
3. **Agent / workflow orchestration** — Pipelines of tools, memory, and policies for building and running agents.
4. **API / marketplace** — Unified model access, billing, quotas for teams building on top.

**User action:** Strike items that are out of scope for v1 or mark “later.”

---

## 2. Scoping questions (assistant checklist)

These map to architectural and product choices:

| Topic | Question |
|-------|----------|
| User | Who is the user (solo dev, team, enterprise)? |
| Hosting | Hosted SaaS vs self-hosted vs hybrid? |
| Surface | Web, CLI, VS Code / Cursor-class extension, API-only, mix? |
| Models | OpenAI/Anthropic/etc., open weights, or both? |
| MVP | One-sentence “day one” capability? |
| Constraints | Language/stack, budget (e.g. GPUs), compliance? |

**User answers (living):**

- **User:** Solo — **yourself**; AI dev, CS background; side projects after work; avoid heavy dev process for the meta-tool and for spawned projects.
- **Surface / shape:** **Web-based**; **visual**; **apps** in general (not blockchain dapps). **Audio** not required for v1; instead **AI reaches out** with **summaries** and **short back-and-forth** for **periodic check-ins** and **issues** (channel TBD).
- **Interaction style:** **Hands-off = agentic, goal-based** — not a tight loop of quick change + check repeatedly.
- **Distribution:** **Open source** on Git; **run on your own machine**; user **does not imagine cloud** for their own use; ideally anyone can self-host.
- **Access:** **Remote into host PC from anywhere**; **Tailscale** for now (rough plan).

---

## 3. Suggested first milestone pattern (assistant)

A **thin vertical slice** often works:

- One **surface** (e.g. web *or* CLI).
- One **core capability** (e.g. run a prompt with a chosen model and persist “runs”).
- **Identity + project scoping** (even if minimal) so the meta-product feels like a platform, not a script.

Then expand: evals, agents, training, marketplace, etc.

**User reaction:** Agree / modify / reject — record why.

---

## 4. Raw notes and threads

### Session: 2025-03-21 (initial)

- User: Building a new AI development platform; project folder empty; wants organized markdown-driven brainstorming.
- User: Document **everything** of value from conversations, including assistant side.
- User: Proposed flow: audience → brainstorming → idea → how-to (usage vision). Confirmed as sensible with small addition of README to map stages.

### Session: 2025-03-21 (Round 1 — audience, collaborative Q&A)

**User (paraphrased + quotes):**

- Primary audience is **“me”** — an **AI developer** with a **CS degree**.
- Tool is for **personal projects after work**; does **not** want the **development process** for this platform to be **in-depth**.
- Wants it **visual** and **hands-off** for the most part.
- Building **any kind of apps**, **especially with AI**.
- **Current rough plan:** some kind of **visual or even audio-based**, **web-based** **dapp** development platform.
- **Access:** **Remote into a host PC from anywhere** using **Tailscale** (for now; rough plan).

**Assistant synthesis (for docs):**

- **Solo-first product** is a valid “audience”: design for one expert user simplifies auth, billing, and UX—at the cost of later generalization if you ever ship to others.
- **After-work + low ceremony** pairs naturally with **visual orchestration** and **delegation to agents**; the risk is ill-defined **hands-off** boundaries (safety, rollback, trust)—flagged as open question in `audience.md`.
- **Tailscale + host PC** is a concrete **network topology**: browser or thin client anywhere, compute/data on a machine you control. Implies **that host must run** the heavy parts (builds, runtimes, secrets, possibly local models).
- **“Dapp”** is ambiguous in industry usage; confirm whether **blockchain/Web3** is in scope or the term was casual.

**Merged into:** `audience.md` (sections 1–2, 4–6), §2 scoping answers above.

### Session: 2025-03-21 (Round 2 — clarifications)

**User:**

- Meant **“app”**, not **dapp** (no blockchain implication).
- **Audio** is **not a must-have for now**. Wants the **AI to reach them somehow**: **summarize**, then **quick back-and-forth** to decide **next steps**, for **periodic check-ins and issues** (chat wording: “medial check-ins” — captured here as **periodic** touchpoints).
- **Hands-off** means **mainly agentic**, **goal-based** — **not** “quick change and check in over and over.”
- **Does not imagine cloud**; ideally **open source on Git** so **anyone can run on their machines**.

**Assistant synthesis:**

- Product shape drifts toward **longer autonomous agent runs** punctuated by **human gates** (summary → decision), vs **pair-programming cadence**. That has implications for **job persistence**, **sandboxing**, and **rollback** on the host.
- **“AI calls me”** decomposes into: (a) **detection** (when to interrupt), (b) **payload** (summary + options), (c) **channel** (in-app, mobile push, email, voice later). For **OSS self-hosted**, (c) is often **pluggable** (bring your own SMTP, webhook, etc.).
- **No-cloud + OSS** aligns with **Tailscale-to-home-PC**; contributors/users still bring **their own** API keys for external LLMs unless you later document local-only mode.

**Merged into:** `audience.md` (JTBD, open questions, decisions log), §2 above.

### Session: 2025-03-21 (novel — node-based visual map of architecture / code)

**User (raw):**

- **Node-based visual “coding”** — nodes describe **actual architecture and codebase**, not the **development process** (i.e. the map is *of the product*, not of tickets/sprints).
- Imagery: a **web of nodes**; each node is how a **person visualizes** a part of the system.
- **Double-click** a node → see **sub-nodes**; repeat to go **deeper** into the code.
- A node is **not always a file**: can be **folder**, **file**, **function**, or maybe even a **concept**.
- Example **root-level** nodes: **UI**, **AI inference**, **Config**, **DB**.
- Drill **UI** → **Home**, **Account**, **About**; under **Account** → finer nodes like **personal info**, **privacy settings** (smaller, more detailed).

**Assistant — understanding check:**

- Yes: this is **intentional cartography** — a **graph (often hierarchical at the top)** where **granularity and abstraction can change per node**, and **navigation = zooming from “how I think about the app” into concrete artifacts**. User later clarified: **no separate “notes” artifact** — **everything is nodes** (“note” earlier was a **typo** for **node**).

**Merged into:** §8 below (fleshed-out design space).

### Session: 2025-03-21 (node-only UX — no file directory)

**User:**

- Rethinking **user × directory** interactions: user should **NEVER** see the **file directory**; **everything** should work **out of nodes**.
- Motivation: **easy dead code** discovery via **floating nodes**; **easy refactor** (common in **AI development**) via graph operations instead of **full codebase understanding**—work is **reconnecting, removing, renaming, adding** **nodes** only.

**Assistant synthesis:**

- This is a **strong product constraint**: **graph = primary shell**; filesystem is an **implementation layer** agents and tooling synchronize with—**not** a second navigation paradigm.
- **Floating nodes** and **orphan file detection** become **core hygiene** features, not nice-to-haves.
- **Refactor** story shifts from “understand entire repo” to **validated graph edits** (with preview/undo)—aligns with **goal-based** agents if agents operate on **nodes** as units of work.

**Merged into:** §8.0, §8.4, §8.6–8.7; `audience.md` decisions + frustration line.

### Session: 2025-03-21 (nodes only — no notes layer)

**User:**

- **Never notes, always nodes** — prior “notes” wording was a **typo**.
- Ideally the model **forces** both **AI and user** toward **modular, DRY** development: **easy cleanup** and **codebase navigation** via the graph.

**Assistant synthesis:**

- **Single primitive (the node)** simplifies the mental model: prose, rationale, or docs either live as **node fields** (title, description, links) or as **dedicated concept nodes**—not a parallel sticky-note system.
- **DRY / modularity** can be **enforced softly** (lints on duplicate anchors, “similar node” suggestions, required parent for new code) or **strongly** (agents may only create/edit through **node-scoped** operations)—TBD.
- **Navigation = graph traversal** only; **cleanup = graph hygiene** (merge, delete, rehome, float detection).

**Merged into:** §8.0, §8.7 (open Q4 replaced); `audience.md` decisions; parking lot.

### Session: 2025-03-21 (implementation architecture + any language)

**User:** How should **actual architecture** look **from a development perspective**? User should be able to use **any coding language**.

**Assistant:** Captured as **§9** (draft — pick concrete stack when you start building).

### Session: 2025-03-21 (visual POC for brainstorming)

**User:** Wanted a **temporary visual + codebase POC** to **understand** the plan; **mocked**, **easy to change** while brainstorming.

**Assistant:** Added **`poc-brainstorm-ui/`** — Vite + React + **React Flow** interactive graph: **no directory UI**, **double-click** expand/collapse on expandable nodes, **floating** nodes for **unlinked / dead-code** metaphor, dashed **cross edges**, **legend + mock check-in / goal** panels. **Shape of graph** lives in **`src/mockGraph.ts`** for quick edits. See **`poc-brainstorm-ui/README.md`**.

### Session: 2025-03-21 (interaction with code, dependencies, AI vs user)

**User asks:** Overall take? Gaps: **how much** does the user interact with **code** — never? **by node**? How do **dependencies** work — **rules** for how nodes are **separated**? **AI** should be central for **node development** but **user-led**, especially **refactors**.

**Assistant:** Captured as **§10** (draft stance + open decisions).

### Freeform dump (use for bullets, links, sketches)

- 

---

## 5. Risks and tensions (fill as they appear)

| Risk | Mitigation idea |
|------|-----------------|
| Goal-based agents with broad host access can **damage repos or systems** if mis-scoped | Strong **sandbox**, **allowlists**, **snapshots/branches**, **dry-run** mode; explicit **approval tiers** in `how-to-use` / `idea`. |
| **Outbound notifications** for self-hosted OSS are **non-trivial** (secrets, deliverability, user trust) | Start with **in-app** + optional **webhook/email** adapters; treat voice/SMS as late. |
| **Node-only shell** hides familiar file navigation | Mitigate with **floating/orphan UX**, **search**, **copy path** (optional advanced), **diff preview**—not a full directory tree. |

---

## 6. Ideas parking lot (not yet committed)

- **Visual web** environment for **general app** creation with **AI**; **goal-based agent** with **periodic human check-ins** (summaries + decisions).
- **Tailscale** as the **remote access** layer to a **home/workstation host**.
- **OSS** — runnable **on user hardware**; optional **pluggable** notification channels.
- **Node graph map** — **only** primary navigation (**no directory tree**); **nodes-only** primitive (**no sticky-note layer**); **floating nodes** for **dead code**; **refactor = graph ops**; **push modularity + DRY** for human + AI; see **§8**.

---

## 7. What must move to `idea.md` when ready

When brainstorming converges, promote:

- One **paragraph** product description.
- **Non-goals** for v1.
- **Differentiator** vs “just ChatGPT” or “just Cursor.”

---

## 8. Node-based visual map of architecture (raw — design space)

**Intent:** A **spatial / graph UI** where each **node** is a **lens** on the system at a chosen level of abstraction. The user **drills in** (e.g. double-click) to reveal **children** — finer structure — until you reach **concrete code** (or **documented concepts** tied to code).

### 8.0 UX principle (2025-03-21 — user direction)

- The user should **never see the file directory** as a navigation metaphor. **All primary interaction is through nodes** in the graph (secondary panes: **preview, tests, diffs, agent trace / read-only snippets**—**not** a tree of folders, **not** a separate sticky-note layer). **Implementation is AI-authored** (see **§10.10**); the user is **not** the primary typist in source.
- **Single primitive:** **No parallel “notes” product surface** — earlier “notes” in conversation was a **typo** for **nodes**. Any explanation or rationale is either **node metadata** (fields on a node) or **its own node** (e.g. concept / doc node), still part of the same graph.
- **Cognitive load:** The product does **not** ask the user to maintain a **mental model of the full codebase**. **Structural** graph changes (**nodes, edges, rewires**) are **not** free-form user authoring like a Blueprint tool—they come from **AI + user-approved refactors** and/or **code-derived** updates. The user **may** adjust **visualization only**: **layout, order, positions**, pan/zoom, collapse—**not** “rewire parameters” by dragging graph topology.
- **Modular + DRY (design goal):** The graph and agent rules should **steer** both **human and AI** toward **small, reusable units** and **clear ownership**—making **cleanup** and **navigation** natural (duplicate logic might surface as **overlapping anchors**, **similar-node** hints, or **lints**—mechanics TBD).
- **Dead code:** Artifacts **not reachable** from the living graph appear as **floating / unattached nodes** (or an explicit **“unlinked”** queue)—making **dead code visible** without global codebase comprehension.
- **Refactor-friendly:** **Renames, splits, merges, and rewiring** happen as **graph-level outcomes** (often **agent-proposed**, **user-approved**), not as the user **manually** sculpting the graph like a visual programming IDE.
- **Implementation note (assistant):** Files and folders still **exist on disk** and in Git; the system **projects** them through the graph. Open design work: **sync semantics**, **escape hatches** for debugging, and **agent** rules that never require the user to open a directory tree.

### 8.1 Node kinds (taxonomy — mix and match)

| Kind | Examples | Typical depth |
|------|----------|----------------|
| **Subsystem / capability** | UI, AI inference, Config, DB | Near root |
| **Product surface** | Home, Account, About, Settings | Mid |
| **Feature / user story** | “Personal info”, “Privacy settings” | Mid–deep |
| **Package / folder** | *(may exist as backing structure; not shown as a directory UI)* | Implementation / agent layer |
| **File / symbol** | Concrete artifacts **behind** nodes — user may open **content** via a node, not by browsing `src/…` | Deepest |
| **Pure concept** | “Auth trust boundary”, “Rate limits” | Any; may link to **docs, tests, ADRs**, or **many files** |

Nothing forces **one row per node** — **Account** might be both a **product surface** and a **cluster of backed artifacts** (still no directory browser).

### 8.2 Edges (2025-03-21 — user direction)

- **Hierarchy:** **parent → child** (**contains / refines**) for drill-down still makes sense as **structure**, not something the user **draws** arbitrarily by hand.
- **Cross-links (conceptual):** Between any **two** nodes, **at most one** edge—no parallel edges, no “parameter ports.” It represents a **single conceptual connection** (“these parts relate / depend in the product sense”), **not** fine-grained data plumbing like node-based game or shader editors.
- **Who edits topology:** **Not** the user dragging new relationships for routine dev; **AI / system** proposes or derives links; user steers via **approval** and **refactor flows**, plus **layout-only** tweaks.

### 8.2.1 Leaf-only code (draft principle — 2025-03-21)

**User question:** Should **only leaf nodes** hold **code**; everything above is **connections**, **orchestration**, and **groupings**?

**Assistant take:** **Strong default — yes**, with **narrow exceptions**. It matches how you already talk about the graph: **capsules group work**; **implementation** lives at the **bottom**.

| Role | Inner (non-leaf) nodes | Leaf nodes |
|------|-------------------------|------------|
| **Purpose** | **Group**, **name**, **route** attention; **orchestrate** tests and agent scope; **conceptual** links between capsules | **Actual implementation** (source files, symbols) |
| **Anchors** | Optional **non-code** attachments only if you allow: **README**, **ADR**, **diagram**—or **none** | **Primary** code anchors (files / symbols) |
| **Tests** | **Aggregate** / smoke over subtree (your POC “parent Test” idea) | **Concrete** unit/integration targets |

**Why it’s good:** One clear answer to “**where does code live?**” → **only under leaves**; **where does the AI edit?** → **scoped leaf anchors**. Parents stay **stable labels**. Reduces “logic smeared across three levels.”

**Exceptions to allow (so the rule doesn’t fight reality):**

- **Glue / barrel** files (`index.ts` re-exports) — either **forbid** at inner nodes (push to a leaf child) or treat as **non-behavior** glue with a **strict** policy.
- **Single config** sitting “at” a group — often cleaner as a **leaf** child **Config** under that group anyway.
- **Shallow trees** — if a capability truly has **one file**, that node **is** the leaf; don’t invent empty parents.

**Risk:** Forcing **extra depth** just to satisfy “leaf-only” creates **busywork** nodes. **Rule of thumb:** inner nodes **should not** own behavioral LOC; if they do, **refactor** into a leaf.

### Session: 2025-03-21 (leaf-only code vs grouping nodes)

**User:** Should **only leaves** have **code**; rest are **connections / orchestration / groups**?

**Assistant:** **Yes as default** — see **§8.2.1**; exceptions for **glue/docs** and **avoid fake depth**.

### 8.2.2 Shared implementation across multiple product leaves (linked / “twin” leaves — 2025-03-21)

**User idea:** Modular UI may **reuse** one component (e.g. a **text box**) from **many** product places. Each **use** sits under a different branch as a **leaf**, but the **actual code** is **multi-use**. Need to **see** that it’s the **same** implementation—not silent duplication—e.g. **different color or shape**, “twin” metaphor (open to better names).

**Does it make sense?** **Yes.** You’re separating **where it shows in the product map** (multiple **use-site** leaves) from **where it lives on disk** (often **one** module/file). DRY stays real; the graph stays honest about **reuse**.

**Naming (pick one vocabulary for the product):**

| Name | Pros |
|------|------|
| **Linked leaves** | Neutral; scales to N peers |
| **Shared-implementation group** | Explicit |
| **Definition leaf + use-site leaves** | Clear roles: one **canonical** home, others **reference** |
| **Twin leaf** | Friendly for exactly **two**; awkward for 3+ |

**Technical sketch (implementation-agnostic):**

- Each **leaf** has **anchors** (e.g. `components/SharedTextField.tsx` + import sites or symbol refs).
- Leaves that **share the same primary anchor** (same module) get a common **`sharedImplementationId`** (or link to a **canonical** node id).
- **Validation:** agent must not **copy-paste** the component into multiple files when policy says **link**; linter or graph check: “same component path anchored from N leaves → OK if **linked**; **fail** if **divergent file copies**.”

**UX sketch:**

- **Use-site** leaves: normal position in subtree; **badge** e.g. `shared ×3` or icon; **border** (dashed / second color) **same for all members** of the group.
- Optional **focus**: click badge → **highlight all** linked leaves + jump to **definition** leaf.
- **Tests:** definition leaf runs **unit** tests; use-site leaves might run **integration** slice only; parent aggregate still works.

**Relation to floating nodes:** **Shared** is **intentional** reuse; **floating** is **orphan / dead**—different signal.

### 8.2.3 User graph “exploded” — node per function/method **appearance**; AI side canonical (2025-03-21)

**User direction (simplifying idea):** **User-facing** graph should be **all-inclusive**, **even repetitive**: a **node for every function or method**, shown in the UI **every time** it is **used or referenced**—so the human sees **full surface area** of “where things matter.” On the **code + AI** side it stays **one file / one definition** — **clean**, **DRY**, optimized for **tooling and agent** understanding.

**Does it make sense?** **Yes** as a **UX philosophy**: **presentation** (verbose, pedagogical) **decoupled** from **storage** (canonical). Same pattern as **call graph / reference** views in IDEs, but as the **default** map.

**Technical sketch:**

| Concept | Role |
|---------|------|
| **Definition identity** | Stable id: symbol FQ name, or `(file, span)` — **one** anchor on disk |
| **Appearance / use-site node** | One graph node per **reference** or **call site** the product cares to show — **many** nodes, **same** `definitionId` |
| **AI tools** | Resolve `definitionId` → **single** file/range to edit; optionally `list_appearances(definitionId)` for impact |
| **User UI** | Sees **every** bubble; **expand/collapse** by capsule; **visual link** (same color, edge to definition) |

**Contrast with minimal graph:** Earlier sketches used **coarse** leaves (e.g. one node per screen). This model is **finer-grained** for **humans** while **§9.13** keeps **`src/`** **functionally** tidy for machines.

**Worked example (verification):** **One** implementation — e.g. `Title` / `renderTitle()` in **one** module on disk. In the **user** UI tree, **one leaf (or appearance node) wherever titles appear**: **Home hero**, **Account header**, **Settings section A**, etc. — **many** graph spots, **same** `definitionId` → **one** function. Editing that function updates **all** those appearances in the app; the graph **shows** each place the user should care about.

**Risks — must design around:**

- **Cardinality** — thousands of calls to `log` or getters → need **filters**: e.g. only **project** symbols, only **public** API, **collapse** by package, or **lazy** “load references” on demand.
- **Noise vs clarity** — policy knobs: **depth** (file-level vs symbol-level vs call-level) **per subtree**.
- **Sync** — every **appearance** node must **resolve** to a **real** ref (LSP or tree-sitter); **regen** when code changes.

**Relation to §8.2.2:** **Linked leaves** become the **special case** of **one definition, many appearance nodes**; naming can stay **“appearance”** / **“use-site node”** vs **definition home**.

### Session: 2025-03-21 (exploded user graph — node per use; canonical for AI)

**User:** User-facing **all-inclusive**, **repetitive** — **node for every function/method**, **each** use/reference in UI; code/AI side **one** file/function for **cleanliness** and **AI understanding**.

**Assistant:** **§8.2.3** — **appearance nodes** share **`definitionId`**; **filters / lazy load** for scale.

### Session: 2025-03-21 (validation pipeline + shared / linked leaves)

**User:** (1) Need **testing/validation** so the **agent adheres** to dev guidelines. (2) **Shared code** across modular leaves—**twin leaf** or similar—**same** implementation appearing at **multiple** leaves, **visually** indicated (color/shape).

**Assistant:** **§10.11** (validation stack); **§8.2.2** (linked leaves / shared implementation).

### 8.3 What double-click means (UX options)

- **Expand in place** (accordion / subgraph appears).
- **Focus mode** (node becomes center; children around it; **breadcrumb** back).
- **Split view** (graph on one side, **selected node’s content** — preview, diff, tests, read-only snippet — on the other; **no folder pane**).

Open question: which feels best for **after-work, low-friction** use?

### 8.4 Binding nodes to reality (how it stays honest)

The hard design problem: **the graph is the interface**, but **bytes still live in files**.

- **Anchors:** Each node can have **zero or many anchors** (paths, symbols, URLs to docs). If **§8.2.1** holds, **behavioral** anchors cluster on **leaves**; **inner** nodes might anchor **docs only** or **nothing**—a **concept** that truly spans files is often modeled as a **leaf** with **multiple file anchors** or split into **child leaves**. **§8.2.2:** multiple **leaves** may **share** one **primary** anchor (reuse); link with **`sharedImplementationId`** or **definition / use-site** roles.
- **Sources of truth (rethink):** Strong tilt toward **graph-first UX** implies either (a) **graph + anchors drive** how the user thinks and agents edit (repo follows via **projections** / codegen / moves), or (b) **repo remains canonical** but **directory UI is banned**—only **sync status**, **drift**, and **floating nodes** expose filesystem truth. **Bidirectional** rules must be explicit so **rename in graph** ↔ **rename on disk** stays consistent.
- **Floating / orphan signals:** **Unlinked nodes** (in graph) vs **unlinked files** (on disk, detected by scan) — two sides of **dead code** and **cleanup** workflows.
- **AI role:** Propose / repair graph from repo; execute **refactors as graph ops** (rewire, merge, split) with **validated** filesystem updates; surface **“this file has no node”** without showing a file tree.

### 8.5 Relation to the rest of the product (hypothesis)

This map could be the **main visual surface** for **goal-based agents**: tasks attach to **nodes** (“finish Privacy settings subtree”), and **check-ins** summarize **what changed under this node**. Not decided — **design fork**.

### 8.6 Risks (specific to this idea)

| Risk | Notes |
|------|--------|
| **Map–code drift** | Concept graph goes stale after refactors; needs **regen**, **diff**, or **warnings**. **Node-only UI** raises the bar—drift must be **visible** (badges, floating orphans) not hidden behind a tree. |
| **Too free-form** | Without anchors, it’s **pretty fiction**; need **lightweight** rules so it stays trustworthy. |
| **Same as folder tree** | If every node is 1:1 a folder, value drops; strength is **cross-cutting and conceptual** nodes. **Hiding the tree** avoids **accidentally** rebuilding Explorer-with-graph-skin. |
| **No escape hatch** | Power users may need **path copy**, **log traces**, **grep**—without exposing a **directory navigator**. Design **targeted** affordances (e.g. “copy backing path,” “open raw” advanced panel) vs full tree. |
| **Agent mistakes on graph** | Rewiring graph could **delete or orphan** real code; need **undo**, **branch**, **preview diff** before apply. |

### 8.7 Open questions to flesh out next (conversation)

1. Should **root layout** be **stable templates** (UI / API / DB / AI) vs **fully custom** per project?
2. Is the graph **one canonical map per repo** or **personal views** (same code, different mental models)?
3. Minimum v1: **tree-only drill** + anchors, or **edges + focus mode** from day one?
4. **Prose on nodes:** Is long-form text **only** `description` (or similar) **fields on nodes**, or do you require **child “doc / ADR” nodes** so even documentation stays **graph-native**?
5. **DRY enforcement level:** **Soft** (hints, duplicate detection) vs **hard** (agents cannot add code without a **parent node** / **single anchor** rule)?
6. **Escape hatch:** What minimal **non-tree** exposure is allowed (copy path, search hits list, diff view)?
7. **Canonical direction:** Does **renaming a node** always rename backing file(s), or can labels diverge from paths with explicit mapping?

---

## 9. Development architecture (language-agnostic) — assistant draft

**Goal:** A **host service** (runs on your PC, reachable via **Tailscale**) exposes a **web UI** and APIs. The **graph is the product’s spine**; **repos stay normal files + Git**. **Any language** is supported through a **capability matrix**: universal baselines + optional **per-language plugins**.

### 9.1 Layered breakdown

| Layer | Responsibility | Language coupling |
|-------|----------------|-------------------|
| **Graph kernel** | Persist **nodes**, **edges**, **anchors** (repo-relative paths, optional symbol ranges / stable IDs), **drift state** | **None** — paths and UTF-8 text are universal |
| **Workspace / repo binding** | Clone path, Git status, ignore rules, **orphan scan** (on-disk files not anchored), apply **moves/renames** from graph ops | **None** for file moves; **some** for smart refactors |
| **Language services (pluggable)** | Per workspace (or folder): **detect** stack, **index** symbols, **run** build/test/lint, **rename symbol** where available | **Per adapter** (TypeScript, Python, Go, …) |
| **Analysis backends** | **Tree-sitter** (broad syntax / outline), **LSP** (where installed — rich nav/refactor), **regex / text** fallback | Optional per language |
| **Agent runtime** | Tools: graph CRUD, **scoped** file read/write, run **commands** in **node context** (cwd, env), **preview diff**, **undo** | Commands are whatever the project uses (`npm`, `cargo`, `make`, …) |
| **Presentation** | **Web client**: graph canvas, drill-down, editors/preview, check-in inbox — **no directory tree** | Editor can embed **Monaco**, **CodeMirror**, or **delegate** to LSP in backend |

### 9.2 “Any language” strategy

1. **Universal floor:** Every project can use **file-anchored nodes** + **text search** + **terminal commands** scoped to a working directory. No LSP required.
2. **Progressive enhancement:** If a **language adapter** exists (or LSP is available), you gain **symbol-level** children under a file node, **go-to-definition**-style links, and **safer renames**.
3. **Polyglot / monorepo:** A workspace declares **roots** or **globs**; multiple adapters can run side by side (e.g. `frontend/` → Node, `api/` → Go).
4. **Unknown / niche langs:** Still first-class at **file** (and maybe **Tree-sitter** if a grammar exists); **no blocking** on “official support.”

### 9.3 Anchors (the bridge to disk without showing a tree)

- **Minimum:** `{ repoRoot, relativePath }` for a file (or folder backing).
- **Optional:** `{ line, column }` or LSP **document + range** for **function / class** nodes.
- **Refactor operations:** **Path-level** (move/rename file) is generic; **symbol rename** delegates to **LSP** when present, else **warn** or **textual rename** with preview.

### 9.4 Modularity / DRY (engineering hooks)

- **Graph invariants** (configurable): e.g. “new file must attach to a parent node,” “duplicate anchor warning,” “floating node report.”
- **Static hooks:** run **per-adapter** or **user-defined** checks after agent edits (same as CI would run).
- **Agents** reason in **node IDs** + **anchors**, not “open `src/foo` in tree.”

### 9.5 Suggested implementation shape (non-prescriptive)

- **Single long-running daemon** on the host: REST or WebSocket + optional subprocess isolation for **untrusted** commands.
- **Graph persistence:** SQLite or JSON/YAML **in repo** (e.g. `.yourtool/graph.sqlite` or `graph.yaml`) so Git tracks map history—or separate DB with export; **tradeoff** to decide.
- **Plugin boundary:** Load language adapters as **WASM**, **subprocess RPC**, or **dynamic libs** — pick based on your preferred stack (Rust/Go/Node/Python all viable for the daemon).

### 9.6 Risks specific to multi-language

| Risk | Mitigation |
|------|------------|
| **LSP sprawl** | Lazy-start language servers; cap concurrent; clear “degraded mode” in UI |
| **Inconsistent depth** | UI shows **capability badges** per subtree (“symbols: rich / file-only”) |
| **Agent runs arbitrary `make install`** | **Sandbox**, allowlists, **dry-run**, user approval for network |

### 9.6.1 Does leaf-only + graph work across common languages? (2025-03-21)

**User question:** Does this model work with **JS, Python, Go, Rust, Java, C, C++, C#**, and others?

**Answer:** **Yes at the conceptual level** — all of them have **files**, **some module/package boundary**, and **symbols** you can anchor **leaf nodes** to. The graph does not depend on a single language semantics; **adapters** handle **how** you discover symbols, tests, and “what counts as a leaf” per ecosystem.

| Family | Fit | Caveats |
|--------|-----|---------|
| **JS / TS** | Strong | **Barrels** / `index.ts` vs **leaf-only** rule (see **§8.2.1**); monorepos span many roots |
| **Python** | Strong | Packages, `__init__.py`, namespace packages; test layout varies (`tests/` vs colocated) |
| **Go** | Strong | **Package = directory** maps cleanly to grouping; leaves = `.go` files / exported symbols |
| **Rust** | Strong | **Crate / mod tree** aligns well with parent/child graph |
| **Java / Kotlin / C#** | Strong | **Packages / namespaces / projects**; solution/csproj or Gradle modules as extra grouping |
| **C / C++** | Moderate | **Headers + translation units**, **CMake/Make**; symbol identity messier; still **file-anchored leaves** work, **LSP** (clangd) helps |
| **Other managed / native** | Usually fine | Same pattern: **file + optional symbol range** as anchor; richness depends on **LSP / Tree-sitter** |

**What varies by language** (not whether the idea “works”): **default project layout**, **how tests are discovered**, **import graph extraction**, and **refactor** safety (rename symbol vs text). The **product** can still show **one conceptual graph** with **per-language capability badges** (already in **§9.6**).

### Session: 2025-03-21 (language coverage)

**User:** Does the architecture work with **JS, Py, Go, Rust, Java, C, C++, C#**, etc.?

**Assistant:** **§9.6.1** — yes in principle; **C/C++** and polyglot repos need **more adapter work**, not a different core idea.

### 9.6.2 Where this model breaks or strains (assistant inventory — 2025-03-21)

**Note (2025-03-21):** If the **user never authors code** and the **AI** is **prompted and linted** to emit **graph-compliant** repos, many rows below shift from “human can’t maintain this” to “**agent must not be asked** to target this shape” or “**validators** must catch bad output.” **Domain** mismatches (Blueprints, Excel) still mean **wrong product target**, not a typing workaround.

**User ask:** Architectures, languages, programs, or **uses** that could **break** the graph-centric, **leaf-only code**, **single conceptual edge**, **no user topology editing** idea.

**Legend:** **Break** = hard mismatch with core metaphors; **Strain** = works in **degraded** or extended mode; **Scope** = not wrong, but the product may **choose** not to serve it.

| Category | Examples | What happens |
|----------|----------|----------------|
| **Visual / dataflow programming** | Unreal Blueprints, LabVIEW, TouchDesigner, shader node editors | **Break** as *the same product* — execution *is* the graph, not a map over text; you already excluded this. |
| **Notebook / cell-first** | Jupyter, Observable | **Strain** — **linear / cell** order; modeling cells as **leaves** works but fights the usual **file+branch** mental model and diff story. |
| **Grid / document “programs”** | Excel logic, heavy Airtable formulas | **Break** for **path-based** anchoring — truth lives in **cells**, not files. |
| **Spec / schema drives codegen** | OpenAPI → server, protobuf, Prisma | **Strain** — **generated** leaves; graph must treat **spec** as authoritative sibling or **generated** nodes as **read-only** leaves. |
| **Heavy metaprogramming** | Lisp macros, Rust proc-macros, big C preprocessor | **Strain** — behavior **appears** away from the “leaf” you edit; needs **expanded / derived** view honesty. |
| **Cardinality explosion** | Hundreds of Lambdas, giant K8s resource sets | **Strain** — raw 1:1 nodes **break** cognition and UI; need **cluster** nodes and lazy expansion. |
| **Chromium-scale monorepos** | Millions of files | **Strain** — **subgraphs** and lazy loading; one global canvas **breaks**. |
| **Binary-only / closed SDK** | Proprietary `.dll`, no sources | **Strain** — **opaque** leaves (surface API only). |
| **No files / no Git** | REPL-only, live image systems | **Break** for a **repo-centric** host unless you **export** artifacts into a synthetic project. |
| **Build graph is canonical** | Heavy Bazel (BUILD is law) | **Strain** — avoid **duplicating** truth; **import** or **mirror** the build graph instead of a second manual map. |
| **Pipeline DAGs** | Airflow, Dagster | **Scope / fit** — often **already a DAG**; **leaves** may be **tasks** not source files; aligns structurally if you embrace that. |

**Cross-cutting tensions:**

- **Multiple distinct relations** between the same two nodes (e.g. import *and* events) vs **one conceptual edge** — mitigate with **tags / notes on that single edge**, or revisit the rule for power users.
- **Import cycles** — graph can represent cycles; **tooling** for “allowed cycle” vs **lint** is separate.
- **Single-file products** — valid but **low leverage** for the graph unless you use **symbol** sub-leaves inside the file.

**Session:** User asked what could **break** this; **§9.6.2**.

### 9.7 Open implementation choices (for later)

- Host daemon language (Rust vs Go vs Node vs Python) — affects packaging for OSS users.
- Whether **graph state** is **in-repo** (merge conflicts on graph) vs **sidecar DB** (easier runtime, harder backup story).
- **Web editor** depth vs **attach external IDE** for heavy editing while keeping **graph** as system of record.

### 9.8 Throwaway visual POC (brainstorming only)

- Path: **`poc-brainstorm-ui/`** — run `npm run dev` inside it; edit **`src/mockGraph.ts`** to reshape nodes/edges. Not the real product—delete when no longer useful.

### 9.9 MCP-like agent interface — graph traverse + tools (2025-03-21)

**User idea:** Make **AI interaction** almost like **MCP**: a **rough high-level** representation (**nodes / web map**) the AI **traverses** to find **functionality**, and **calls / investigates** code **on demand**. Could it work, or is **too much context** missing?

**Assistant take:** **Yes, it can work** — and it’s a **good** fit for **large repos** and **limited context windows**. It’s the same **pattern** as MCP: a **host** exposes **structured capabilities** (tools/resources); the model **requests** detail only where needed instead of ingesting the whole tree.

#### How the pieces line up

| Piece | Role |
|-------|------|
| **Graph API** (MCP-like) | `list_children(nodeId)`, `get_node`, `neighbors`, `subtree_summary(depth)`, `resolve_anchors` — **cheap**, high-level |
| **Investigation tools** | `read_file`, `read_symbol`, `grep`, `run_tests(scope)`, `import_graph(slice)` — **expensive**, pull **just-in-time** |
| **User goal / focus** | Task attached to a **start node** → agent **walks** from there first |

The **map** is not the whole truth; it’s the **index**. **Code** is always **one tool call** away when the agent decides it needs it.

#### Where context can be **lost** (and mitigations)

| Gap | Mitigation |
|-----|------------|
| **Stale or wrong graph** | **§8.6** — drift UI, regen, validators after edits (**§10.11**) |
| **Agent stops too shallow** | Tools that return **breadcrumb + parent summary**; policy: “before editing a leaf, **summarize** its parent goal” |
| **Cross-cutting / linked leaves** | **`get_linked_leaves(sharedId)`** tool; editing one **warns** or **updates** definition (**§8.2.2**) |
| **Long dependency chains** | **`trace_dependency(node, depth)`** or LSP-backed “who imports this” |
| **Agent under-calls tools** | **Validation** catches blind edits; **required** read of anchor before patch in policy |

#### Verdict

**Not missing too much** if **tools are rich enough** and **graph stays honest**. The **risk** is **under-exploration** (lazy agent), not the **architecture** — address with **prompting**, **tool design**, and **hard gates** in **§10.11**.

**Session:** User asked about **MCP-style** traverse + investigate; **§9.9**.

### 9.10 What a codebase “looks like” on disk vs the graph (2025-03-21)

**User struggle:** Hard to picture a **real project**; what does **shared code** look like? Does it **live inside** the node structure?

**Short answer:** The **repo is mostly a normal codebase** (folders + files + Git). **Shared code** is **ordinary modules** (e.g. one `SharedTextField.tsx`) stored **once** on disk. The **graph** does **not** contain the source text as the system of record—it **indexes** paths (**anchors**) and **relationships**. (Optional: small **graph export** file **in** the repo next to `src/`.)

#### Typical on-disk layout (example)

```text
my-app/
├── .yourtool/                    # example: product-specific metadata (name TBD)
│   └── graph.yaml                # nodes, edges, anchor paths, sharedImplementationIds
├── src/
│   ├── ui/
│   │   ├── components/           # “library” area — good home for reuse
│   │   │   └── SharedTextField.tsx
│   │   └── features/
│   │       ├── account/
│   │       │   └── AccountForm.tsx    # imports ../components/SharedTextField
│   │       └── settings/
│   │           └── SettingsPanel.tsx  # imports ../../components/SharedTextField
│   ├── api/
│   └── ...
├── package.json
└── ...
```

**Nothing magic in the folders** — you could `grep SharedTextField` and see normal imports. **CI, ESLint, TypeScript** work as usual.

#### How the **graph** relates (conceptual)

| Graph concept | On disk |
|----------------|---------|
| **Inner node** “UI” | No file of its own (grouping only); maybe `description` in `graph.yaml` |
| **Leaf** “Account → form” | **Anchor:** `src/ui/features/account/AccountForm.tsx` |
| **Leaf** “Settings → panel” | **Anchor:** `src/ui/features/settings/SettingsPanel.tsx` |
| **Linked / shared** | **One** file `SharedTextField.tsx`; **definition** leaf anchors it; **use-site** leaves anchor **consumer** files + same **`sharedImplementationId`** (or point to definition id) |

So **shared code “lives” in the repo** under something like `components/` or `lib/`; the graph **records** that multiple **product** leaves **depend on** the same module—it doesn’t **duplicate** the file inside the graph.

#### Anti-pattern vs intended

| Anti-pattern | Intended |
|--------------|----------|
| Copy-paste `TextField` into `account/` and `settings/` as two files | **One** component file; two **leaves** **link** to it (validators catch dupes) |
| Put TSX source **inside** `graph.yaml` | Graph **references** paths; **bytes** stay in `.tsx` |

#### Session

**User:** What does a codebase look like for this product? What does **shared** code look like? Is it **in** the node structure?

**Assistant:** **§9.10** — normal **tree on disk** + **sidecar graph** (or embedded metadata) that **points at** files; **shared** = **one file**, **many graph leaves** linked.

**Visual explainer (POC):** `poc-brainstorm-ui/public/repo-model.html` — open **`/repo-model.html`** while `npm run dev` is running; linked from the POC header.

### 9.11 Graph ↔ `src/` correlation — how it works, why it’s scary, how to tame it (2025-03-21)

**User concern:** Understands the pieces but not **how graph and `src/` stay correlated**; feels like a **massive hassle** and **failure point** for the **AI**.

**Honest take:** Two representations (**graph** + **files**) **can** drift. That **is** a risk. The product only works if you pick a **clear contract** and **automate** alignment so humans and models are not hand-keeping two truths.

#### What “correlation” means (one bridge)

Correlation is **anchors**: each **leaf** (and sometimes other nodes) stores **repo-relative paths** (and optionally symbol ids) that **point** into `src/`. The graph says *“this capsule = these paths”*; `src/` holds the bytes.

```text
graph leaf "account-form"  ──anchor──►  src/ui/features/account/AccountForm.tsx
```

No magic: it’s **data** in `graph.yaml` (or DB) that must **match** real files.

#### How the **AI** handles it (without going insane)

Treat it like **MCP** (**§9.9**): the agent never “remembers” the whole repo; it **calls tools**.

| Step | What happens |
|------|----------------|
| **1. Start from task** | User attaches goal to a **node id** (or product path in graph). |
| **2. Resolve** | Tool `resolve_node(id)` returns **anchors** → concrete paths. |
| **3. Edit** | Agent only allowed to **patch** paths that are **in scope** for that node (or proposals that **update anchors** in the same transaction). |
| **4. Sync graph** | **Same run** that moves/renames files **updates** `graph.yaml` (or agent emits **two** artifacts: diff + graph patch). |
| **5. Validate** | **§10.11** — if anchors point to missing files, or files exist with no leaf, **fail** the run. |

So the AI’s job is not to “keep two mental models”; it’s to **emit consistent machine-readable output** (files + graph metadata) under **tool + policy** constraints.

#### Strategies to **reduce** hassle (pick one dominant story)

| Strategy | Idea | Tradeoff |
|----------|------|----------|
| **A — Files primary, graph derived** | Scan `src/` + conventions; **regenerate** or **suggest** graph; user approves structural moves | Graph may feel “laggy” until scan; very predictable |
| **B — Graph primary for structure** | Agent **must** update graph **whenever** it creates/moves files; validators enforce | Strong product vision; **strict** tooling required |
| **C — Single transaction object** | Every agent apply = **one bundle**: file ops + graph delta; **atomic** commit | Best integrity; more engineering on apply pipeline |

**Recommendation for your direction:** lean **B + C**: the **agent** always outputs **paired** file changes + graph updates; **CI** rejects commits that break anchor integrity. That turns “hassle” into **one automated gate**, not ongoing manual sync.

#### Failure modes (name them so you can detect them)

- **Orphan file** — on disk, not anchored → **floating** in UI (**§8.0**).
- **Ghost anchor** — graph points to deleted path → **validator error** after agent run.
- **Split brain** — file moved in Git but graph not updated → **same**; fix with **required graph patch** on rename operations.

#### Session

**User:** Not seeing **correlation** graph ↔ `src/`; worried AI handling it is **hassle** / **failure point**.

**Assistant:** **§9.11** — anchors are the bridge; **tool-scoped** agent + **atomic file+graph** apply + **§10.11** validation; **dual truth** is real risk, **tamed** by automation not hope.

### 9.12 Does graph testing + node rules guarantee a “clean standard” codebase for the AI? (2025-03-21)

**User question:** UI stays clean for the user — but how does it stay **clean for the AI**? Do **graph testing** and **node / connection adherence** **guarantee** a **clean, standard** codebase for the model?

**Short answer:** They **strongly help** with **structure the AI depends on** (where things live, what’s shared, what’s orphan, boundaries between capsules). They **do not alone guarantee** everything people mean by “clean standard code” (style inside a file, security, performance, full correctness). You want **graph validators + normal language/tooling CI** as **one stack**.

#### What graph-level adherence **can** guarantee (if implemented)

| Guarantee | Why it helps the AI |
|-----------|---------------------|
| **Anchors valid** | Paths resolve; tools don’t return ghosts (**§9.11**). |
| **Leaf-only policy** | Implementation **only** under leaves — agent knows **where** code may exist. |
| **Linked-leaf / duplicate rules** | Shared component is **one file**, not silent copies — fewer contradictory reads. |
| **Conceptual edges + layer lint** | “UI may not import DB raw” — **reduces** illegal moves the agent might try. |
| **Orphan / floating detection** | Repo matches declared ownership — less dead weight confusing retrieval. |
| **Tests scoped to nodes** | Agent gets **reliable feedback** after edits in a capsule. |

That’s **architectural cleanliness** and **navigability** — huge for **context + tool** workflows.

#### What graph rules **do not** guarantee (need other gates)

| Gap | Typical tooling |
|-----|-----------------|
| **Idiomatic / readable** code inside a file | Linters (ESLint, Ruff, clippy…), style config, maybe AI review prompts |
| **Types / static correctness** | `tsc`, `mypy`, compiler |
| **Security** | Dependency scan, SAST, secret scan |
| **Behavioral correctness** | Unit/integration/E2E tests beyond “node test” mock |
| **Performance** | Profilers, budgets — not graph-shaped |

So: **graph adherence ⇒ predictable shape**; **not ⇒ masterpiece**.

#### How to phrase the promise

- **For the user:** clean **map** and **trust** that structure matches reality.
- **For the AI:** **lower surprise** — stable **index**, **scoped edits**, **verifiable** invariants — which **is** a form of “clean” for agent operations, but **stack** it with **language-standard** CI so **bytes** are also **healthy**.

**Session:** User asked whether graph testing + connection rules **guarantee** standard clean code for AI; **§9.12**.

### 9.13 Dual layout — functional `src/` for AI vs conceptual graph for user (2025-03-21)

**User idea:** **Two structures**: (1) **AI / internal** — directory **by functionality**, **tests and checks** tuned for **dependencies, syntax**, same class of gates as normal engineering, **clean for the agent**; (2) **Graph** — **for the user**, **conceptual** understanding. The two can be **very different** but must **always document the connections** between them.

**Does it make sense?** **Yes.** It’s a clear split of concerns:

| Layer | Audience | Optimized for |
|-------|----------|----------------|
| **Disk / repo layout** | AI, linters, compilers, CI | **Dependency direction**, **build units**, **test discovery**, **syntax/module** boundaries — “how the machine and tools reason” |
| **Graph** | Human | **Product concepts**, **features**, **ownership** in **mental-model** order — “how the builder thinks” |

**The bridge is non-optional:** every meaningful link must be **data**, not tribal knowledge:

- **Anchors** (graph leaf → path(s) under `src/`)
- Optional **reverse index** (path → node id) for agent bootstrapping
- **Versioned** mapping in `graph.yaml` (or equivalent) **committed** with the repo
- **Validators** that fail if a path is unmapped or a node has **ghost** anchors (**§9.11**)

**Why it’s powerful:** The user never has to **think** in `src/features/auth/adapters/oauth/` first; they think **“Account → sign-in.”** The AI still gets **clean functional grouping** for imports, cycles, and tooling.

**Risk (same as before, explicit):** **Two shapes** can **drift** if connections aren’t **updated atomically** with moves/renames. Mitigation: **paired apply** (file ops + mapping delta in one transaction), or **generated** mapping from annotations the agent must maintain, plus **§10.11**.

**Relation to earlier notes:** Complements **§9.10** (example tree was already “normal” on disk); this **names** the intentional **mismatch** between **functional** disk and **conceptual** graph as a **feature**, not an accident.

**Session:** User proposed **dual structure** — functional dirs for AI, conceptual graph for user; **always document connections**; **§9.13**.

### 9.14 MCP actions for “connecting code to the graph” + multi-sided locks (2025-03-21)

**User idea:** **MCP-based** with **actions** for **connecting code** to **notes** — possibly **locking files** so they **cannot** be edited unless changes are reflected on **both** (or **more than two**) “sides.” Is this **possible**?

**Terminology:** Earlier product direction was **nodes**, not parallel **notes** layers (**§8.0**). Below, **“connecting code to the graph”** means **anchors**, **linked leaves**, **metadata** — MCP **tools** that **read/write** those links. If you still want **free-text annotations**, treat them as **node fields** or **doc nodes**, same **tool** surface.

#### Is it possible?

**Yes, in degrees:**

| Mechanism | What it does | Strength |
|-----------|----------------|----------|
| **MCP / daemon as write gate** | All edits go through **`apply_change`** tools that **require** a **bundle**: file patch + graph delta (+ optional test run id). **Reject** incomplete bundles. | **Strong** if **nothing** bypasses the daemon (fits **user never codes** + agent-only apply). |
| **Pre-commit / CI hook** | Git hook runs **validator**: graph ↔ disk ↔ rules; **block commit** if inconsistent. | **Strong** for **any** editor that commits; **after** local edit, not always **before** keystrokes. |
| **Advisory lock files** | `.lock` or daemon-held lock per path while a **session** is open. | **Medium** — cooperative; easy to ignore outside tool. |
| **OS / FS mandatory locks** | Rare in dev workflows; **poor** UX on Unix for shared repos. | Usually **skipped**. |

**“More than two sides”** is just **more validators** in the same transaction, e.g.:

1. **`src/`** file content  
2. **`graph.yaml`** anchors / edges  
3. **Linked-leaf** group consistency (**§8.2.2**)  
4. **Import graph** / dependency lint for touched paths  

The **apply** tool **atomically** checks **all** before write, or writes to **staging** then runs **full** validator before **commit**.

#### “Lock file unless graph updated”

**Possible patterns:**

- **Soft lock (recommended baseline):** Editing **outside** the blessed path is **allowed** on disk but **`validate`** **fails** and **check-in / agent-done** is **blocked** until mapping is fixed — or **auto-suggest** graph patch.  
- **Hard lock:** Host process **owns** writes; **IDE** integration only through **MCP** — **possible** for a **closed** workflow; breaks if someone runs `vim` on the repo unless **hooks** catch it.

#### Honest limit

If **humans or other tools** edit files **directly**, **mandatory** dual-sided sync is **hard** without **Git hooks + CI** as the real **enforcer**. Your **“AI only writes”** assumption (**§10.2**) makes **daemon-gated MCP** much more **feasible**.

**Session:** User asked **MCP actions** to connect code to graph (**notes** → read as **graph links**); **locks** until **2+ sides** consistent; **§9.14**.

### 9.15 MCP-controlled vs parse-generated graph — research stance (2025-03-21)

**User question (big):** Should this be **AI-controlled MCP** end-to-end, OR **parse code → auto-generate** the graph while **AI + human** collaborate, with **editing diving into code** (implying code-centric edit loop with graph kept in sync)?

**Assistant:** Treat it as a **false dichotomy** in practice. **Industry pattern:** static **index** (LSP, Tree-sitter, import/call analysis) **derives** structure; **agents** use **tooling** (often MCP-shaped) to **read/write** that index and the repo. Examples in that spirit: **call graphs from LSP** (e.g. crabviz-style tooling), **workspace analysis → diagrams** (e.g. traverse-style), **dependency graphs** from parsers — not mutually exclusive with **MCP**.

#### Two pure extremes (both incomplete alone)

| Approach | Strength | Weakness |
|----------|----------|----------|
| **MCP-only (agent builds graph by inspection)** | Flexible, no indexer to build | **Slow**, **costly**, **drift** if model skips files; weak **guarantee** graph matches disk |
| **Parse-only (100% generated from code)** | **Honest** symbol/ref layer; fast refresh on save/CI | **Poor** at **product** capsules (**§9.13**) — folders ≠ “Account section”; **conceptual** labels need **overlay** |

#### Recommended **hybrid** (fits your docs so far)

1. **Derived core (“machine graph”)** — **Continuously** (or on save / commit) build: files, symbols, **references** → powers **§8.2.3** **appearance** nodes for **truth**. **Single source of truth = code** for *what exists*.
2. **Conceptual overlay (“human graph”)** — **Nodes/edges** for **UI breakdown**, **capsules**, **goals** — **linked** to derived ids (`definitionId`, paths). **AI + user** maintain overlay via **approved** ops; **validators** ensure anchors still resolve after parse.
3. **MCP as the agent’s hands** — Tools: `query_graph`, `read_file`, `apply_bundle`, `reindex_status` — **read** both layers; **write** code + **patch overlay** in **one transaction** (**§9.14**).

**“When editing, dive only into code”** — Two compatible readings:

- **Human edits code** (if you allow it): **IDE/code view** is primary; **reindex** updates **derived** appearances; **overlay** warns on conflict. **Low MCP** during human typing; **high validation** on save.
- **User never codes** (**§10.2**): **User** stays on **graph**; **agent** “dives” into code via **MCP tools**; **user** sees **diffs** — still **parse-backed** graph so the map **updates** when apply lands.

#### Verdict

- **Do not** rely on **MCP alone** to **invent** the whole map from scratch each time.
- **Do** use **parsing / LSP** to **auto-generate** the **reference/appearance** substrate.
- **Do** use **MCP (or equivalent tool protocol)** so the **AI** acts **safely** on repo + overlay.
- **Collaboration:** **person** on **concept + approval**; **AI** on **implementation + bundle apply**; **indexer** on **truth**.

**Session:** User asked **MCP vs auto-parse + collaborate + code dive**; **§9.15** — **hybrid** recommended.

### 9.15.1 Two-phase pipeline — parse builds full tree, then AI names & organizes (2025-03-21)

**User idea:** Use **code / function parsing** tools to build the **full tree** from **references** and **method calls** — is that **possible**? Then have the **AI** go through to **name**, **organize**, and **clean up** for **user** understanding.

**Answer:** **Yes, that’s possible** and it matches the **hybrid** in **§9.15**. Typical shape:

| Phase | Input | Output |
|-------|--------|--------|
| **1 — Machine** | Repo + **LSP / Tree-sitter / import & call analysis** | **Dense** graph: files, symbols, **call edges**, **reference sites** — the **exploded** substrate for **§8.2.3** |
| **2 — Curation** | That substrate + (optional) **user hints** / product docs | **Overlay only** (separate artifact): **friendly names**, **short descriptions** for user understanding, **grouping** / capsules (“Home”, “Account”), **hide** noise, **merge** trivial nodes — all keyed by **stable RAW ids**. **Display strings never replace ids**; ids stay authoritative for **diff** and **reparse**. |

**What parsing can recover (language-dependent):** static **calls**, many **references**, **imports**, **implements** relationships; **not** always: dynamic dispatch, reflection, heavy macros, string-based calls — **degraded** regions flagged.

**AI’s job in phase 2:** **Suggest** names and groupings; **user approves** (**§10.4**) for anything that **changes** committed overlay; **validators** ensure **overlay → still anchors** to real symbol ids from phase 1.

**Why not only AI for phase 1:** **Deterministic** parse is **cheaper**, **repeatable**, and **CI-testable**; the model focuses on **meaning**, not rediscovering `grep` facts.

**Session:** User proposed **parse → full tree**, then **AI organize** for UX; **§9.15.1**.

### 9.16 RAW technical graph — what exists today, your pipeline, language scope (2025-03-21)

**User (step back):** What would **automatic codebase parsing** look like? **Does it exist?** Imagining: split **down to function**, **each use** in codebase, **RAW tree** with **technical** names → **keep** RAW → **AI** parse/cleanup/label for **non-technical** users → on future changes **reparse**, **diff** against RAW, **update** AI abstraction. **Doable?** **How?** **Language-specific** vs **agnostic**?

#### Does something like this exist today?

**Pieces exist; your exact product does not off-the-shelf.** Building blocks:

| Piece | Examples / notes |
|-------|-------------------|
| **Syntax trees** | **Tree-sitter** — many grammars; fast incremental parse; **language-agnostic driver**, **per-language grammar** |
| **Go-to-def / references** | **LSP** (`textDocument/definition`, `references`) — **per language server** (TS, Rust, Pyright, gopls, clangd…) |
| **Call hierarchy** | LSP `callHierarchy/incoming|outgoing` — **not** always implemented or complete |
| **Workspace-wide index** | **SCIP** / **LSIF** indexes (Sourcegraph-style), **rust-analyzer** crate graph, **TypeScript** project references |
| **Call graphs (batch)** | Commercial / research tools, **crabviz**-style LSP extensions, **import graphs** from static analysis |

So: **“every symbol + many references”** is **routine** in mature stacks; **“every call edge with full precision”** is **harder** and **language-dependent** (static vs dynamic).

#### What your **RAW tree** would look like (conceptually)

- **Nodes:** at minimum **file** + **symbol** (function, method, class, …) with stable ids (`uri + range` or SCIP-style symbol).
- **Edges:** `imports`, `references`, `calls` (where available), `contains` (parent symbol).
- **Use sites:** each **reference** or **call site** → **appearance** row pointing at **`definitionId`** (**§8.2.3**).
- **Labels:** **FQ names**, module paths — **technical**, **stable** — this is the **RAW** layer you **retain** and **never let the AI rename** without a code change.

**Storage:** SQLite / graph DB / serialized index (SCIP, custom JSON) — **recomputable** from disk.

#### Your pipeline — **doable**

1. **Build RAW** — indexer job: walk repo, parse, query LSP or batch index, emit **RAW graph** + **content hash** per file.
2. **AI curation pass** — reads RAW, writes **overlay**: `displayName`, `capsuleId`, `hidden`, `userOrder` — **separate store** keyed by **stable RAW ids**.
3. **On change** — **reparse** → **new RAW** → **structural diff** (added/removed/moved symbol ids, changed reference sets).
4. **Update abstraction** — **rules**: new RAW nodes → **AI suggest** labels (or **inherit** from path); **removed** ids → **prune** overlay; **moved** → **follow** id if stable else **remap**; optionally **small AI pass** only on **delta** to save cost.

**Hard parts (solvable):** **ID stability** across renames (LSP rename often tracks; file split may churn ids — **remap table**). **Scale** — **incremental** index, not full workspace every keystroke for huge repos.

#### Language-specific vs language-agnostic

| Layer | Agnostic? |
|-------|-----------|
| **Orchestration** (“run indexers, merge graph, diff, store”) | **Yes** — one pipeline |
| **Syntax / AST** | **Per language** grammar (Tree-sitter) or parser |
| **Semantics** (refs, types, **calls**) | **Per language** via **LSP** or dedicated analyzer — **adapter interface** in your app: `LanguagePlugin.index(workspace) → RawGraphFragment` |
| **Quality** | **Uneven** — TS/Rust/Java **strong**; Python **good** with types; **C++** **heavier**; **dynamic** JS patterns **worse** |

**Practical:** **Language-agnostic product** with **pluggable** backends; **quality** is **per-language** until you invest in each adapter.

#### Summary

- **Yes, doable:** RAW from **parsers + LSP/index**; curated **overlay** from **AI**; **reparsed diff** to **patch** overlay — standard **incremental** / **ETL** thinking.
- **Exists today** as **components**, not usually one **merged** “RAW + friendly + diff” product — that’s your integration work.
- **Not fully language-agnostic** at the **semantic** layer without **one adapter per ecosystem**; the **architecture** can be agnostic.

**Session:** User asked **RAW full parse**, **AI label**, **reparse + diff** — **§9.16**.

### 9.17 Overlay schema note — descriptions (2025-03-21)

**User:** Curation overlay should include **descriptions** for user understanding, not only friendly names; still **keyed by RAW ids**, **labels don’t replace ids**.

**Assistant:** Treat overlay fields per RAW node (or per capsule id) as e.g. `displayName`, `userDescription` (plain language), `capsuleParentId`, `hidden`, `sortKey` — all **references** to **immutable RAW symbol/file ids** from the indexer. **Merge** overlay in Git like any config; **diff** RAW separately from **diff** overlay on republish.

### 9.18 Overall risks & issues (pre-architecture — assistant review)

**User:** Any **issues** with the idea **overall**? Next: **architecture mapping** and **dev prep**.

**Issues to respect (not fatal — design around them):**

| Area | Risk |
|------|------|
| **Dual artifact** | RAW + overlay can **diverge** in process (overlay points to deleted RAW id) — need **validators** on every publish and **orphan overlay** cleanup UX. |
| **ID stability** | Reparse after refactors may **churn** ids — **remap** table or **fuzzy** match heuristics; worst case **user-facing** grouping **shifts** until curation reruns. |
| **Indexer blind spots** | Dynamic calls, macros, generated code — RAW **incomplete**; UI must show **confidence** / “unknown edges” or **degraded** badge per region. |
| **Scale** | Full **function × every use** on huge repos — **CPU**, **storage**, **UI** — need **tiers**, **lazy** expansion, **filtered** RAW exports. |
| **AI curation cost & drift** | Re-labeling after every small diff is **expensive**; prefer **delta**-scoped curation; **version** prompts; **wrong** friendly text **doesn’t break** code but **misleads** users — **edit + approve** for sensitive copy. |
| **Security / trust** | Agent writes **code + overlay** — **injection** in descriptions if rendered rich; **sanitize**; **sign** or **review** overlay commits for teams later. |
| **“User never codes”** | If only agent edits, **overlay** updates must be part of **bundled** workflows (**§9.14**) or **auto**-suggested after reparse — still **human approve** for big renames of meaning. |
| **Language coverage** | **MVP** = 1–2 languages with **strong** LSP; “agnostic” is **product** claim, **implementation** is **per adapter**. |
| **Competition with IDE** | You’re rebuilding slices of **IDE index +** **doc generator** — **differentiator** must be **graph UX + agent + validation**, not raw indexing alone. |

**Verdict:** Idea is **coherent** and **buildable**; success is **discipline** on **ids**, **validation**, **incremental** scale, and **honest** limits of static analysis.

**Suggested next steps (toward architecture & dev):**

1. **Spike indexer** — one repo, **one language** (e.g. TS): emit **minimal RAW** (files + symbols + refs) to **JSON/SQLite**.  
2. **Schema** — freeze **RAW node/edge** types + **overlay** record shape (`displayName`, `userDescription`, …).  
3. **Diff** — implement **RAW v1 → v2** diff; define **overlay patch** rules for **add/remove/move**.  
4. **Thin curation** — script or **one** AI pass: labels + descriptions; **validate** keys ⊆ RAW ids.  
5. **MCP mock** — 3–5 tools: `get_raw_subgraph`, `get_overlay`, `apply_bundle` (stub).  
6. **Architecture doc** — one diagram: **indexer | store | diff | overlay | API | UI | agent**.  

### 9.19 FAQ — elaborations on §9.18 risks (2025-03-21)

**Orphan overlay (dead RAW ids)** — User: cleanup must be **logical**, not AI-driven, for **reliability**; maybe **notify AI** only when something needs attention.

- **Deterministic rules:** After each reparse, `overlay_keys - valid_raw_ids` → **orphan set**. Auto-actions: **drop** overlay row; or **quarantine** file (`overlay.orphans.json`) for audit; **never** require a model to guess whether to delete.  
- **AI later:** Optional **“summarize what disappeared”** for the user using **diff of RAW** + **list of pruned overlay ids** — **input is structured**, not “figure out orphans.”

**ID stability after big refactors** — Proposed approach (layered):

1. **Prefer stable keys from tooling** where available (e.g. **SCIP**-style symbols, or `uri#symbolName` heuristics) — **not** only volatile line numbers.  
2. **RAW diff emits events:** `symbol_removed`, `symbol_added`, `symbol_moved` (best-effort from LSP **previousResultId** / file-level diff if needed).  
3. **Remap table** (deterministic): optional checked-in `id_map.old → new` for one migration, or **heuristic** “same FQN in new file” for **suggest** only; **auto-apply** remap only when **confidence** high.  
4. **Overlay:** rows keyed by old id → **orphan** until **remapped** or **re-curated**; **UX** can show “moved — review label” without losing the **node** if user confirms link.  
5. **Worst case:** **re-run curation** on **affected subtree** only — **§9.18** **delta** curation.

**Incomplete RAW — what it means (plain)** — Static analysis **cannot see every call**. Examples: `obj[methodName]()` where `methodName` is a **variable**; `eval`; some **macros** that emit code the indexer never expands; **generated** `.ts` from codegen the indexer didn’t run. Those edges **don’t appear** in RAW (or appear as **file-level** only). **“Confidence / degraded”** = mark file or region: **“partial view — dynamic calls possible.”** Not a moral judgment — **honesty** so users don’t trust the graph as **complete** control-flow.

**Scale — who is it heavy for?** — Primarily **indexer** (CPU, disk), **API** (payload size), and **browser** (how many nodes to render) — **not** specifically “the user-facing AI.” **Cheap** curation API still runs **after** you’ve already **paid** to build/store/query RAW. **Filters / incremental** index reduce **all** of that.

**AI curation — user’s cheaper approach** — **Tree walk** (root → children), **small context** (current RAW node + children + short code snippets), **cheap** model, **versioned** prompt — **reasonable**. **Helps** consistency (descriptions **inherit** story from parent). **Still validate:** output keys ⊆ RAW ids; **optional** second **lint** pass for **PII** / **wrong module** in description (can be **rule-based** or tiny model).

**Wrong descriptions — mitigations** — (1) **Structured** curation with **local** context **reduces** hallucinated cross-module claims. (2) **User approve** on **first** write or on **sensitive** capsules. (3) **Sanitize** rendering (**plain text** or safe markdown). (4) **Show** “last curated / hash of RAW subtree” so **stale** copy is visible. (5) **Diff overlay** in PR for teams later.

**Language reality — is it an issue?** — **Not a flaw in the idea** — it means: **one** codebase for the **pipeline**, but you **ship** or **enable** **per-language** **plugins** (TS plugin, Go plugin, …). **MVP** = one **strong** language; “works everywhere” is **roadmap**, not day-one **parity**.

**Positioning / wedge — expanded** — **Raw index** (symbols, refs) is what **IDEs**, **Sourcegraph**, **GitHub code nav** already do **well**. **Your** product is **not** “we indexed code.” It is **(a)** **RAW + overlay** for **non-dev** mental model, **(b)** **agent + MCP** that **must** obey **graph rules**, **(c)** **validation / bundles** so **structure** stays **honest**, **(d)** **exploded** use-site UX — **together** that’s a **different** surface than “search code in browser.”

**Session:** User deep-dived **§9.18** topics + deterministic orphan handling; **§9.19**.

---

## 10. Interaction model, dependencies, AI vs user (draft — assistant stance)

### 10.1 Overall take

The direction is **coherent**: a **graph-first shell** that **reduces** “whole-repo in your head” and makes **refactors** and **dead code** legible. With **§10.10**, the main design work shifts to **agent reliability**, **prompting + policy** so the AI **obeys** graph invariants (leaf-only code, topology, etc.), **validation/lint** after edits, and **trust / rollback** — not teaching the user to type in a repo.

### 10.2 How much does the user touch code?

**Update (2025-03-21):** User direction: the **user does not author code**; **only the AI** writes implementation. The user **steers** via **goals, approvals, check-ins, tests, layout** — not keystrokes in source files.

| Mode | Role |
|------|------|
| **Primary** | User works **by node** (intent, scope, **approve/reject** plans and diffs, run **Test**, respond to **check-ins**). |
| **Read / inspect** | User may view **diffs, logs, previews, read-only snippets** attached to a node — **not** as the main authoring surface. |
| **Escape** | Optional **advanced** read-only affordances (search hits, copy path, export) **without** a directory tree — still **no expectation** the user fixes code by hand in v1. |

So: **all bytes are produced by the agent** (under **prompting + automated checks**); the user’s job is **judgment and structure**, not typing implementation. This is explicitly a **100% agent-authored code** product for the human in the loop — **trust and failure modes** are central engineering risk (see **§10.10**).

### 10.3 Dependencies — how they work; rules for separation

**Two layers** are useful to keep separate:

1. **Graph edges (intent)** — “UI **calls** AI,” “DB **feeds** inference,” etc. as **conceptual** links (**one edge per node pair** where a link exists). Authored by **AI suggestion + user approval** or **derived** from analysis—not by the user **dragging** topology like a visual programming tool (see **§10.9**).
2. **Code references (truth)** — imports, RPC, schema FKs, etc. Best **mined** from language tooling (**LSP / static analysis**) and shown as **overlays** or **warnings** when they **diverge** from the graph (“graph says A→B, code imports A→C”).

**Rules for “how nodes are separated”** (starter set — all tunable):

- **Ownership:** every anchored artifact has a **primary node** (one “home”); **aliases** allowed but visible.
- **Boundary:** cross-node **calls** are allowed; the graph records **allowed directions** or **layers** (e.g. UI → API ok, DB → UI not ok without an adapter) — **layer rules** as **lints**, not necessarily hard blocks at first.
- **Size:** soft caps (e.g. “warn if node anchors > N files or > M LOC”) to **push** modularity without being dogmatic.

**AI** proposes splits/merges; **user** confirms **refactors** that change boundaries (your stated priority).

### 10.4 AI key for development, user-led (especially refactors)

A workable governance model:

- **AI proposes:** new nodes, rewires, renames, “this file is orphan,” dependency suggestions, test plans **scoped** to a node.
- **User decides:** **refactors** that change **ownership** or **public boundaries** — via explicit **approve / edit plan / reject** (and **preview diff** before apply).
- **Check-ins** (your earlier idea) align: agent runs **goal-based** work, then **stops** for **summary + decision** on **structural** changes; **trivial** edits can be **policy-auto** later.

### 10.5 Open decisions (carry forward)

- **Read-only inspector** depth in-product (diff, trace, preview) vs minimal UI.
- **Strictness** of graph–code sync (soft warnings vs hard gates) **after agent edits**.
- **Which refactor steps** require user approval vs agent autonomy (tiered policy).
- **Prompt/skill versioning** and how **invariants** stay in sync with product rules.

### 10.6 User’s gaps — direct answers (short)

- **Interact with code never?** → **Yes (v1 intent):** user **does not author** code; **AI writes**; user **reviews** diffs / approves / steers by **node** (see **§10.2**, **§10.10**).
- **By node only?** → **Primary navigation and task attachment = yes**; **no user typing** implementation in the default story.
- **Dependencies?** → **Intent edges on graph** + **extracted code refs**; **rules** = ownership, layers, soft size/boundary **lints**, **user approval** on **refactor** rewires.
- **AI vs user?** → **AI executes and proposes**; **user leads** on **structure** and **risk** — especially **refactors**.

### 10.10 AI-only authoring + prompting to adhere (2025-03-21)

**User:** Of course **different methodologies** can break the model; the **user will never code**; **always the AI**, with **prompting** so it **knows how to adhere** to the architecture.

**Assistant synthesis:**

- **Methodology mismatches** (Blueprints, Excel-as-logic) then mean “**this product isn’t targeting that kind of output**,” not “the human can’t hand-jam it.” The **AI** is still constrained to emit **file-based**, **graph-shaped** repos if that’s the **product contract**.
- **Enforcement stack** (conceptual): (1) **system prompts + skills** stating invariants (**leaf-only** code, **one conceptual edge**, no parent behavior, etc.); (2) **per-run context** (subgraph, anchors, allowed files); (3) **post-edit validators** (lint, import rules, “no code on inner nodes,” drift vs graph); (4) **user approval** on **structural** changes; (5) **rollback / branch** on bad apply.
- **§9.6.2** still lists **domains** that don’t fit **file+graph** outputs; the AI doesn’t remove Excel’s nature — you **scope** what kinds of apps you generate.
- **Risk:** model **drift** from rules → invest in **deterministic** checks, not prompt-only compliance.

### 10.11 Agent adherence — testing & validation pipeline (2025-03-21)

**User:** There must be a **testing/validation procedure** so the **agent** follows **development guidelines**.

**Assistant — layered stack (all of these beat “prompt only”):**

| Layer | Purpose | Examples |
|-------|---------|----------|
| **1. Prompts & skills** | State invariants in natural language | Leaf-only code, topology rules, linked-leaf policy, one conceptual edge |
| **2. Scoped context per run** | Limit what the agent may touch | Allowed paths for this node; subgraph JSON; “do not create files outside …” |
| **3. Pre-apply static checks** | Fast fail before merge | Formatter, linter, typecheck, import-boundary rules, custom **graph lint** (inner node has no `.ts` anchor, etc.) |
| **4. Graph / repo invariants** | Deterministic rules on output | No duplicate file for shared component when **linked-leaf** policy applies; **orphan** scan; **drift** vs declared edges |
| **5. Tests** | Behavior + regression | Unit (per leaf), aggregate (parent), CI same as human projects |
| **6. Human gate** | Structural risk | User **approve** refactor plans / big diffs (**§10.4**) |
| **7. Rollback** | Safety net | Branch, undo, snapshot before apply |

**Operational shape:** every **agent run** ends with **validate** → **report** (pass / fail + file:line); failed runs **do not** land as “done” until fixed or reverted. **Guidelines** should live in **versioned** rules (config + skills) so validation and prompts **stay aligned**.

### Session: 2025-03-21 (user never codes; AI + prompts adhere)

**User:** User **never** codes; **AI always**; **prompting** teaches adherence. Methodology differences **will** break some targets — understood.

**Assistant:** **§10.2** rewritten; **§10.10** added; **§9.6.2** lead note; **§10.5–10.6** adjusted; `audience.md` decision.

### 10.7 How different from “standard code”? Skin vs new substrate

**Short answer:** You do **not** have to throw away standard code. On disk, a project can stay a **normal Git repo** — directories, files, language tooling, CI — unchanged. The open choice is **how hard** the graph **binds** to that reality.

| Stance | What stays “standard” | What the graph is |
|--------|------------------------|-------------------|
| **A — Skin / shell (weaker)** | **Everything** on disk; any editor/CLI works as today | **Metadata + navigation + agent context** layered on top; graph is **derived** or **maintained** alongside the tree |
| **B — Primary UX, standard disk (middle — close to your POC direction)** | **Files and folders** remain the **artifact format**; Git, LSP, builds unchanged | **No directory tree in the product UI**; **human steers by node**; **agent** applies edits to **anchors**; refactors **update** disk to match graph ops |
| **C — Graph as source of truth (strongest)** | Even layout/codegen might **follow** the graph | **Highest** divergence from “normal” workflows; bigger build cost and migration story |

**So:** It can be **“just a skill” / shell** on normal structure (**A**), or **the main interface** while disk stays boring (**B**), or a **deeper rewrite** of how repos are produced (**C**). Your notes so far align most with **B**: **standard code underneath**, **graph-first** above — not necessarily **replacing** the filesystem, **hiding** it as the default mental model.

**Not changing “code” itself:** languages, compilers, packages, tests — still normal. **Changing (optionally):** default **navigation**, **task attachment**, **who types** (here: **agent**, with user **approval** on risky structure), and **how rules are enforced** (prompt + lint).

### Session: 2025-03-21 (standard code vs graph — skin or substrate?)

**User:** How **different** is this architecture from standard code? Are we **changing everything** to focus on the graph? Is it **just a skin** on normal directory/file structures?

**Assistant:** See **§10.7** — spectrum **A / B / C**; current direction ≈ **B** (standard disk, graph-primary UX); **A** is valid if you want maximum compatibility with “normal” dev; **C** is optional and heavy.

### Session: 2025-03-21 (graph-driven + drag-drop connections)

**User:** Wants **graph-driven** architecture; user might **drag-and-drop connections** between nodes. Does it **make sense**? Struggling to **picture technically**.

**Assistant:** See **§10.8** — yes, it’s coherent; technical picture = **persisted graph** + **edge types** + **materialization / validation loop** (agent or compiler step turns intent into code or flags drift).

---

### 10.8 Graph-driven architecture + user-drawn edges (technical picture)

**Update (2025-03-21):** The user **does not** want **user-authored** structural graph edits (no drag-to-connect as the normal dev loop). **§10.9** is the current stance on **who** changes topology and **what** edges mean. Keep this section as background for **graph-driven + materialization** ideas; ignore **user-drawn edges** as a product requirement.

**Original note:** A **declarative** graph **can** be bound to the repo through **anchors** and **materialization rules**. **Graph-driven** still works when **topology** is changed by **agents + approvals**, not by the user **drawing** the graph like Blueprints.

#### What “graph-driven” can still mean (concretely)

1. **Canonical structure** lives in a **graph store** (nodes + edges), versioned (e.g. export in repo).
2. **Code on disk** **follows** or is **checked against** that graph; **implementation** stays in normal files.
3. **Changing structure** = **graph operations** executed via **approved refactors** (agent or guided wizard), **not** ad-hoc user rewiring in the canvas.

#### Mental model (revised — user adjusts view, not topology)

```text
[ User: layout, order, pan/zoom — view only ]
[ User: approve / reject structural proposals ]
              ↓
[ Graph store — source of truth for structure ]
              ↓
     ┌────────┴────────┐
     ↓                 ↓
[ Materialize ]   [ Validate / drift ]
  agent diff        analysis vs graph
     ↓                 ↓
[ Git / files ]   [ Warnings, fix suggestions ]
```

#### Risks (brief)

- **Drift** between graph and code if updates are **only** half-applied.
- **Merge** on graph files in Git — keep diffs **human-readable**.

---

### 10.9 Graph topology — user may not edit; single conceptual edge (2025-03-21)

**User direction:**

- The user should **not** change the graph except **visualization** and **order** (e.g. **node positions**, **layout**, **what is expanded**)—**not** “normal development” style rearrangement of **parameters** or **topology** like visual scripting.
- **At most one edge** between any **pair** of nodes; it means a **conceptual connection** only—not typed ports, multi-wires, or execution graphs.

**Assistant synthesis:**

- This **avoids** the product being mistaken for **Unreal Blueprints** / **shader graphs** / **LabVIEW**. The graph is a **map and contract**, not a second programming language.
- **Structural** edits stay in the **refactor / agent / approval** lane you already wanted; the canvas stays **readable** and **low-fiddly**.
- **Implementation:** enforce **simple graph** (no multi-edges) in the store; **hierarchy** (parent/child) can remain a **special** case of “contains” distinct from **optional** undirected or single **conceptual** link between siblings/capsules—**design detail**: either **tree + at most one cross-edge per pair** or **collapse** cross-links into one semantic “related” edge.
- **POC:** keep **dashed cross-links** as **mock**; do **not** add **user-drawn** `onConnect` unless you revisit this decision.

### Session: 2025-03-21 (topology not user-edited; one conceptual edge)

**User:** User should **not** edit the graph except **visualization** and **order**; not like moving **parameters** in visual dev. **Only one edge** between nodes = **conceptual** connection.

**Assistant:** **§8.0**, **§8.2**, **§10.3**, **§10.8** (annotated), **§10.9** updated.
