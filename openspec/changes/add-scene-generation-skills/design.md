## Context

The current framework has already extracted core 3D scene capabilities from demos 11 through 15: solid boxes, lines and grid utilities, billboards, textured materials, ground surfaces, and irregular triangle meshes. That is enough to represent many stylized tabletop environments, but the repo still expects a strong model or a human author to translate ideas such as "small hill town with timber houses" into concrete framework objects.

This change does not expand renderer capability. Instead, it adds skill definitions, reusable recipe structures, and example catalogs that teach a model how to stay inside the framework's current object set while producing more scenes, more variations, and more facade artwork. The main stakeholders are contributors authoring examples, lightweight models generating structured scene plans, and downstream users composing imaginary Dungeons and Dragons style environments.

Constraints:
- Existing framework primitives and materials are the boundary; the skills must not assume new renderer features
- Smaller models need strongly typed intermediate outputs instead of open-ended code generation
- Generated facade art may come from external image models later, so the repo needs stable placement metadata and prompt conventions even before a full asset pipeline exists
- The current source of truth for supported visual patterns is the ported demos and framework object model
- Any uneven-terrain or hillside skill behavior that depends on traversable terrain MUST wait for task 5.25 in `add-draw-in-window-3d-framework`

## Goals / Non-Goals

**Goals:**
- Define a constrained skill workflow that decomposes scene generation into reliable, lightweight-model-friendly steps
- Capture scene archetypes that map directly onto existing framework objects and materials
- Separate geometry recipes from facade-art recipes so image generation can evolve independently from scene layout
- Turn current demos and framework-backed examples into a reusable catalog of patterns, seeds, and validation fixtures
- Provide validation rules that reject scene outputs requiring unsupported primitive types, occlusion behavior, or material semantics

**Non-Goals:**
- Adding new rendering primitives, sorters, or material systems to the framework
- Building a full procedural world generator or runtime content pipeline in this phase
- Solving image generation, texture storage, or licensing policy beyond repo-local prompt/metadata conventions
- Guaranteeing photorealistic assets; the target is stylized, framework-compatible scene composition

## Decisions

### Decision: Use structured scene recipes instead of direct code-first prompting
- Decision: Skills SHALL generate a constrained intermediate recipe format before any Python example is authored.
- Rationale: Smaller models are much more reliable at filling schemas than synthesizing framework code directly.
- Alternatives considered:
  - Direct Python generation from prose: rejected because it invites unsupported object usage and brittle scene composition.
  - Pure natural-language scene notes: rejected because they are too ambiguous to validate automatically.

### Decision: Organize capability scope around three separate skill surfaces
- Decision: Split the work into `scene-generation-skills`, `surface-art-recipes`, and `scene-example-catalog`.
- Rationale: Layout composition, facade art, and example-library reuse have different inputs, outputs, and validation rules.
- Alternatives considered:
  - One monolithic "world generation" capability: rejected because it obscures what is geometry planning versus art prompting.
  - Per-scene-type capabilities only: rejected because it duplicates shared constraints and recipe vocabulary.

### Decision: Derive scene archetypes from current demos and object inventory
- Decision: Archetypes SHALL be built from current framework-backed patterns such as terrain planes, line grids, box buildings, roof meshes, billboard vegetation, and textured facades.
- Rationale: The ported demos are the only proven examples of what the framework can already render correctly.
- Alternatives considered:
  - Designing archetypes from aspirational future features: rejected because that would create skills that over-promise and under-deliver.

### Decision: Gate uneven-terrain skills on the framework terrain milestone
- Decision: Any skill, schema, or example in this change that depends on traversable uneven terrain SHALL treat task 5.25 in `add-draw-in-window-3d-framework` as a prerequisite.
- Rationale: Terrain-following movement, terrain queries, and traversable-versus-boundary policy belong to the framework contract, not the skill layer.
- Alternatives considered:
  - Defining terrain-aware skill behavior ahead of the framework milestone: rejected because it would force the skill change to invent framework semantics.
  - Blocking all hill-themed content: rejected because non-traversable hill visuals can still be generated with existing mesh support.

### Decision: Treat facade art as prompt-plus-placement metadata, not immediate binary assets
- Decision: The initial capability stores art recipes as metadata describing subject, palette, tiling, aspect ratio, and target surface placement.
- Rationale: This lets the repo standardize how doors, windows, bricks, timber, and banners attach to geometry before deciding on a generation backend or asset packaging format.
- Alternatives considered:
  - Requiring committed image assets in the initial phase: rejected because it slows iteration and mixes generation policy with asset storage.

### Decision: Use examples as both documentation and evaluation fixtures
- Decision: Example scenes SHALL include enough metadata to act as prompt references, composition templates, and acceptance fixtures for future skill updates.
- Rationale: The repo needs a feedback loop that shows whether smaller models stay within supported scene patterns over time.
- Alternatives considered:
  - Documentation-only examples: rejected because they do not create a reliable validation surface.

## Risks / Trade-offs

- [Schema too loose for lightweight models] -> Mitigation: keep recipe fields small, typed, and bound to explicit primitive families and enumerated archetypes.
- [Skill scope drifts into framework design] -> Mitigation: add validation rules that fail outputs requiring unsupported primitives or renderer behavior.
- [Facade-art prompts become inconsistent across contributors] -> Mitigation: define a shared vocabulary for subject, material, palette, weathering, and tiling.
- [Example catalog becomes stale as framework grows] -> Mitigation: store source primitive coverage and refresh examples whenever new framework-backed demos land.
- [Generated scenes look repetitive] -> Mitigation: include variation seeds and composition knobs while keeping the primitive vocabulary fixed.

## Migration Plan

1. Add OpenSpec capability definitions for the three skill surfaces.
2. Author repo-local skill files and recipe schemas that encode supported primitives and composition patterns.
3. Seed the example catalog from existing ported demos and a first wave of fantasy-scene archetypes.
4. Add validation guidance or focused tests that confirm generated examples remain within current framework boundaries.
5. Treat task 5.25 in `add-draw-in-window-3d-framework` as the prerequisite for any traversable uneven-terrain archetype, schema, or skill behavior in this change.
6. Iterate on scene diversity and asset-library volume without expanding the renderer unless a separate approved framework change requires it.

## Open Questions

1. What intermediate format should scene recipes use in-repo: JSON, YAML, or Python literals with validation helpers?
2. Should facade-art recipes target only wall polygons at first, or also billboards, banners, and roof decals?
3. How much deterministic seeding is needed for scene/example regeneration across models?
4. Do we want one generic scene-generation skill with archetype parameters, or multiple thin skills for town, forest, castle, and terrain families that share a base schema?
5. What is the minimal acceptance check for generated examples: schema validation only, import/render smoke tests, or curated visual baselines?
6. Once the framework supports hill traversal, do terrain-aware recipes describe raw terrain meshes directly or reference higher-level slope archetypes that compile down to meshes?