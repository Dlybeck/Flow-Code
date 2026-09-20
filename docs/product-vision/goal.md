# Product goal — make an unfamiliar codebase explorable

**Status:** Current product direction as of 2026-09-20. Engineering boundaries
live in [SPEC.md](./SPEC.md) and [ARCHITECTURE.md](./ARCHITECTURE.md).

## The reader

Flow-Code is for a person who has never seen the codebase. They may be a
portfolio visitor, collaborator, interviewer, new maintainer, or curious user.
They should be able to form a useful mental model without starting from a file
tree or reading every function.

The product gives them tools to explore. It does not force a narrated tour or
pretend it can explain the whole system literally.

## The map

The central interface is a terrain-like 3D map:

- Each point represents a function.
- Call edges show how mapped work connects.
- Nearby points contain semantically similar code.
- Higher points are more important to why this selected project exists.
- A 2D fallback preserves exploration when WebGL is unavailable.

The terrain metaphor is structural rather than decorative. A project does not
need mountain-themed labels or scenery. The third dimension earns its place by
making importance visible while the ground plane carries similarity or call
structure.

For ScribbleScan, the OCR path should rise above hosting glue and routine error
handling because OCR is the distinctive work at the center of the product. The
same rule generalizes: code rises when it is both specific to this project and
substantive to its purpose. Generic infrastructure can still be visible and
connected without defining the skyline.

## Interaction

The initial view should invite free exploration:

1. Start from a likely entry point or inspect the whole landscape.
2. Click a function to see its upstream and downstream connections.
3. Switch between call paths and code similarity.
4. Follow source locations when more detail is useful.
5. Read analysis limits where the static map is incomplete.

A host may add a short human-written introduction or an authored source tour.
These are optional context around the map. Flow-Code itself remains useful with
only the repository and a project name.

## Meaning of importance

The default code-only signal combines:

- embedding distinctiveness within the selected codebase;
- code substance, so tiny unusual wrappers do not dominate;
- bounded graph centrality, so connections inform the score without turning
  generic dispatch into the most important work.

An optional human-written project purpose can guide the score through local
vector similarity. It is a hint with a visible receipt, not an AI-authored
claim. Importance is relative to the selected project and is always presented
as an estimate.

## Independence

Flow-Code owns source discovery, language parsing, execution IR, local vector
generation, terrain scoring, snapshot export, and the standalone viewer. It can
generate and display a map without the Portfolio repository.

Portfolio is one host. It may provide navigation, themes, or prose, and it may
publish reviewed snapshots. Host integration cannot become a dependency of the
core pipeline.

## Generative AI boundary

Generative AI is not part of normal map generation. A map must be reproducible
without API keys, provider accounts, or source uploads.

There is one possible later extension: an explicit one-time summary pass over a
completed map. If built, it must be optional, separately invoked, persisted as
a reviewable artifact, reusable across ordinary updates, and unable to change
technical graph edges or terrain scores. Continuous summary generation after
each code change is outside the product direction.

Agentic coding and MCP integration remain possible future uses of the same map.
They are not the current wedge and cannot shape the core around an AI client.

## Delivery sequence

1. Prove Python as the baseline.
2. Prove JavaScript, TypeScript, Java, C, C#, and Haskell independently.
3. Compare adapter limitations and harden the shared execution IR.
4. Design honest mixed-language linking from evidence gathered in those proofs.
5. Integrate reviewed static maps into Portfolio without coupling the products.
6. Consider Kotlin, Go, and other languages as real projects require them.

The current implementation has completed the independent-language foundation.
Mixed-language semantics are the next major design problem.
