## ADDED Requirements

### Requirement: Scene generation skills use constrained framework recipes
The system SHALL provide repo-local scene-generation skills that convert a high-level scene brief into a constrained recipe that references only framework primitives, material types, and composition patterns already supported by the repository.

#### Scenario: Town brief becomes a supported recipe
- **WHEN** a user requests a town, hill, forest, castle, or similar fantasy environment from the skill workflow
- **THEN** the generated recipe references only supported scene constructs such as terrain surfaces, boxes, triangle-mesh roofs, billboards, lines, polygons, text labels, and existing image or solid materials

### Requirement: Scene generation skills decompose broad requests into archetypes and parameters
The system SHALL require scene-generation skills to express open-ended world requests through named archetypes, typed parameters, and bounded variation controls rather than unconstrained code generation.

#### Scenario: Lightweight model fills an archetype schema
- **WHEN** a smaller model is asked to generate a forest hamlet scene
- **THEN** the skill output identifies an archetype, supplies typed placement and variation fields, and avoids emitting freeform framework code as the primary contract

### Requirement: Scene generation skills reject unsupported framework demands
The system SHALL include validation guidance that causes the skill workflow to reject or rewrite outputs that require unsupported renderer capabilities, primitive families, or material semantics.

#### Scenario: Unsupported primitive request is blocked
- **WHEN** a generated scene plan depends on a capability not present in the current framework, such as arbitrary curved mesh primitives or new shading systems
- **THEN** the workflow flags the request as out of bounds and keeps the output within the existing framework surface instead of silently inventing new features

#### Scenario: Uneven-terrain traversal waits for framework prerequisite
- **WHEN** a skill output depends on traversable hillsides, terrain-following movement, or other uneven-terrain behavior
- **THEN** the workflow treats task 5.25 in `add-draw-in-window-3d-framework` as a prerequisite and does not present that behavior as available before the framework milestone is complete