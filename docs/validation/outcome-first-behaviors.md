# Outcome-first behavior validation

Validated: 2026-09-23
Branch: `pilot/outcome-first-trails`
Base: `4c5135c462adc334519e1bf23dc0f52e1272b100`

## Result

Flow-Code now generates a small opening set of root-to-leaf behaviors without a
user supplying outcomes. Entering a seed opens a focused child view, every
visible node retains source evidence, and every analyzed function has a focused
layer even when static analysis cannot place it under a detected root.

The simple flow is the default. It made alternate returns and exception paths
easier to distinguish than the mountain while remaining legible on a 390 px
viewport. The mountain is retained because it provides useful spatial context
and now consumes the same nodes and edges; each edge descends or stays level.

## Source-current projects

| Project | Languages | Functions | Detected starts | Unplaced but indexed |
|---|---|---:|---:|---:|
| Flow-Code | Python, JavaScript | 307 | 34 | 98 |
| Portfolio | Python, JavaScript | 138 | 46 | 77 |
| ScribbleScan | Python, JavaScript | 599 | 151 | 319 |

The public fixture also retains three structurally different prior validation
cases: a Python pipeline, a JavaScript reservation application, and a Java
indexing application. These cases use the same behavior schema and browser
acceptance checks.

High unplaced counts are reported rather than hidden. They include internal
helpers, framework-wired functions, and static-analysis gaps that have no honest
path from a detected root. **All code** keeps them inspectable.

## Leaf relevance decision

The source-current comparison found different project-wide and local leaf
orders in 56 Flow-Code layers, 10 Portfolio layers, and 114 ScribbleScan layers.
The retained **relative relevance** order combines:

- 50% similarity to the focused root;
- 22% similarity to the optional project purpose;
- 28% preference for a normal completion over an exception.

This keeps a focused child view about its local job while using the project
purpose to break ties. It also avoids treating exception exits as the preferred
educational path merely because their text closely resembles the function.
Both component orders remain in the artifact and can be inspected from the UI.

## Browser acceptance

The automated browser pass checks all six fixture projects on desktop, checks
the focused flow on mobile, opens the complete code inventory, follows a seed
into its child layer, and verifies that:

- primary behavior count never exceeds six;
- every analyzed function has one layer;
- every visible node has at least one source reference;
- both renderers show the same node IDs and exact modeled edge pairs;
- the mobile page does not overflow horizontally;
- no browser exception occurs.

Receipt: [behavior-prototype/receipt.json](behavior-prototype/receipt.json)
Source bake receipt: [outcome-first-receipt.json](outcome-first-receipt.json)

Representative captures:

- [ScribbleScan overview](behavior-prototype/scribblescan-overview.png)
- [ScribbleScan focused flow](behavior-prototype/scribblescan.png)
- [ScribbleScan mountain](behavior-prototype/scribblescan-mountain.png)
- [Flow-Code focused flow](behavior-prototype/flowcode.png)
- [Mobile focused flow](behavior-prototype/mobile.png)

## Limits

- Call order is lexical static evidence, not an observed runtime trace.
- Dynamic dispatch, reflection, framework wiring, and cross-process continuation
  may remain unresolved.
- Current recursive layers are function-centered. A later deterministic grouping
  pass can introduce higher-level stages without changing source identity.
- Return labels describe code exits. They are not automatically rewritten into
  business-language summaries by generative AI.
