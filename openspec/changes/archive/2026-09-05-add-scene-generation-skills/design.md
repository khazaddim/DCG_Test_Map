## Context

The current framework has already extracted core 3D scene capabilities from demos 11 through 15: solid boxes, lines and grid utilities, billboards, textured materials, ground surfaces, and irregular triangle meshes. That is enough to represent many stylized tabletop environments, but the repo still expects a strong model or a human author to translate ideas such as "small hill town with timber houses" into concrete framework objects and revise those scenes as requirements change.

This change does not expand renderer capability. Instead, it adds documentation skills and example-navigation artifacts that teach a model how to stay inside the framework's current object set while producing or revising scenes. The main stakeholders are contributors authoring examples, lightweight models choosing classes and demos, and downstream users composing imaginary Dungeons and Dragons style environments.

Constraints:
- Existing framework primitives and materials are the boundary; the skills must not assume new renderer features
- Smaller models need concise, class-local documentation and reliable demo references more than they need a broad generation pipeline today
- The current source of truth for supported visual patterns is the ported demos and framework object model

## Goals / Non-Goals

**Goals:**
- Document every application-level scene authoring class with guidance on when to use it, how it composes with neighbors, and what limitations matter to a small model
- Build demo-by-demo reference documentation that helps a small model navigate to the most relevant example for a requested world feature or edit
- Keep the capability contract available as a boundary document for future structured authoring work without committing to a compiler or broad recipe workflow now

**Non-Goals:**
- Adding new rendering primitives, sorters, or material systems to the framework
- Building scene-generation, surface-art, or terrain-expansion skills in this phase
- Building a compiler, source generator, or full procedural world generator in this phase

## Decisions

### Decision: Start with documentation skills instead of generation skills
- Decision: Phase 1 SHALL focus on class-by-class documentation skills and demo-by-demo reference navigation rather than scene-generation or art-generation skills.
- Rationale: Smaller models need better access to proven patterns before broader authoring workflows can be reliable.
- Alternatives considered:
  - Broad scene-generation skills first: rejected because the example base is still too thin.
  - Surface-art workflows now: rejected because class guidance and example coverage are more urgent.

### Decision: Keep the capability contract as a boundary reference
- Decision: The capability contract SHALL remain in the change as a reference document for supported primitives, materials, and future structured authoring vocabulary.
- Rationale: Even in a documentation-first phase, the repo benefits from an explicit allowlist and boundary statement.
- Alternatives considered:
  - Remove the contract entirely: rejected because it would discard useful boundary work.

### Decision: Derive documentation scope from demos 11, 14, and 15 plus the framework object inventory
- Decision: Documentation and example navigation SHALL be built from the classes and patterns used to make world objects in demos 11, 14, and 15, anchored to the current framework object inventory.
- Rationale: Those demos are the current proven surface for map layout, billboards, water-adjacent stream usage, and mesh-roof world authoring.
- Phase-1 boundary: documentation should center `GroundPlane3D`, `Box3D`, `Polygon3D`, `Line3D`, `Polyline3D`, `Text3D`, `Billboard3D`, and `TriangleMesh3D`. `DrawStream3D` should also be documented because demo 14 uses it directly for a world-building pattern, but it remains outside the phase-1 recipe allowlist unless the capability contract changes. Supporting authoring utilities used directly in those demos, such as `ProjectionPipeline`, should be documented where they are required to understand or modify a demonstrated world-building pattern. `TetrahedralMesh3D` and `ScalarFieldMaterial` may be documented separately as advanced or non-primary surfaces.
- Alternatives considered:
  - Designing the class list from aspirational future features: rejected because that would create skills that over-promise and under-deliver.

### Decision: Use examples as documentation and navigation anchors
- Decision: Example scenes SHALL include enough metadata to act as prompt references and navigation anchors for future documentation skills.
- Rationale: Smaller models need examples that are easy to retrieve with a small, maintainable metadata set.
- Retrieval shape: phase 1 should start with two required fields per demo entry: a list of the primary classes used and a short plain-language summary of what the demo builds or demonstrates. Class lookup should be the most reliable retrieval path at first because the demo set is still sparse. Plain-language summaries should provide a second routing path for blueprint-style requests such as towns, streams entering water, or later castles, and that path can become richer as new demos are added.
- Future expansion: additional metadata should grow first through composition-pattern notes, not world-edit-intent tags. More specific edit-intent routing depends on future pick-style scene-selection context so the model can be grounded in selected points, lines, surfaces, or objects rather than broad text alone.
- Pattern granularity: a useful composition pattern may be either a single object choice or a multi-object assembly, and the documentation should capture both. Some classes, such as `Box3D`, can act as near-self-contained patterns for buildings, walls, or simple volumes while also participating in larger assemblies such as stacked wall blocks or crenellated castle edges. Other classes, such as `Billboard3D`, may stay single-object at the geometry level but still need multiple semantic pattern notes because the same primitive can stand in for trees, bushes, signs, or NPC-like figures. More variable classes, especially `TriangleMesh3D`, need pattern notes tied to specific demonstrated uses such as roofs, cliffs, ramps, or carved openings.
- Documentation standard: composition-pattern notes should live as concise inline comments near the relevant code blocks inside the demo files. Comment wording should follow a consistent style rather than a rigid template. Each comment should state the class being used, how it is being used, and what larger structure or pattern the code block contributes to. Demo index entries can then stay lightweight by listing the primary classes, a short summary, and pointers to the commented code regions that explain reusable patterns.
- Alternatives considered:
  - Documentation-only examples with no structured metadata: rejected because retrieval would be less reliable.

## Risks / Trade-offs

- [Documentation remains too abstract for small models] -> Mitigation: anchor each class guide to one or more concrete demos and composition patterns.
- [Documentation scope drifts away from proven examples] -> Mitigation: keep class guides and demo references tied to the capability contract and current framework-backed demos.
- [Documentation becomes stale as framework grows] -> Mitigation: refresh class guides and demo notes whenever new framework-backed examples land.

## Implementation Status

1. Completed: the capability contract now records the supported scene-authoring boundary, recipe vocabulary, and authoring rules for phase 1.
2. Next: author repo-local documentation for the primary application-level scene classes and targeted supporting utilities used directly by demos 11, 14, and 15.
3. Next: add demo-by-demo navigation notes for world creation and revision requests.
4. Later: expand documentation coverage as new framework-backed examples appear.

