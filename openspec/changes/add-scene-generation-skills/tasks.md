## 1. Capability Definitions

- [ ] 1.1 Finalize the capability boundaries for scene generation, surface art recipes, and example cataloging against the current framework object inventory
- [ ] 1.2 Choose and document the intermediate schema format for scene recipes and facade-art recipes
- [ ] 1.3 Define the allowed primitive, material, and archetype vocabulary that generated outputs may reference

## 2. Skill Authoring

- [ ] 2.1 Create repo-local skill instructions for constrained scene generation from high-level world briefs
- [ ] 2.2 Create repo-local skill instructions for facade and billboard art recipe generation with placement metadata
- [ ] 2.3 Add guidance that forces skills to reject requests requiring unsupported renderer capabilities

## 3. Example and Asset Seed Data

- [ ] 3.1 Build an initial archetype catalog covering towns, hills, forests, castles, and roads using existing framework patterns
- [ ] 3.2 Create example recipe fixtures derived from current ported demos and at least one fantasy-scene composition per archetype family
- [ ] 3.3 Define a starter surface-art recipe library for doors, windows, brick, stone, timber, banners, and roof treatments

## 4. Validation and Workflow

- [ ] 4.1 Add validation checks or focused tests for recipe/schema conformance and supported primitive usage
- [ ] 4.2 Add documentation showing how to go from a world brief to a recipe, from a recipe to an example scene, and from a surface-art recipe to framework material usage
- [ ] 4.3 Review the seeded examples with a lightweight-model-oriented workflow and capture gaps as follow-on changes instead of expanding framework scope implicitly

## 5. Terrain-Dependent Scene Expansion

- [ ] 5.1 Treat Milestone 5.25 in `add-draw-in-window-3d-framework` as a prerequisite gate for any uneven-terrain or hillside skill work in this change
- [ ] 5.2 Revisit hill-town, slope-road, and uneven-terrain archetypes only after task 5.25 in `add-draw-in-window-3d-framework` is complete
- [ ] 5.3 Extend the scene schema to describe traversable terrain surfaces only after task 5.25 in `add-draw-in-window-3d-framework` exposes stable terrain-query and movement semantics
- [ ] 5.4 Add late-phase examples that place settlements, forests, or roads on hillsides while remaining aligned with the terrain contract delivered by task 5.25 in `add-draw-in-window-3d-framework`
- [ ] 5.5 Validate that terrain-aware scene skills degrade cleanly to flat-ground recipes when task 5.25 in `add-draw-in-window-3d-framework` is unavailable or incomplete