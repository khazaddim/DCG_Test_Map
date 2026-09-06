## ADDED Requirements

### Requirement: Surface art recipes describe facade imagery independently from geometry
The system SHALL provide a repo-local capability for expressing building-side and billboard artwork as structured prompt metadata separate from the geometry recipe that places it.

#### Scenario: Door and window art is specified without new geometry semantics
- **WHEN** a user needs artwork for a building facade such as doors, windows, shutters, timber framing, brick, or stone
- **THEN** the workflow emits structured art metadata that can be attached to supported material or billboard paths without requiring new framework primitives

### Requirement: Surface art recipes include placement and presentation metadata
The system SHALL define metadata fields for target surface type, aspect ratio, tiling expectations, palette, weathering level, and intended placement so artwork recipes can be applied consistently across scenes.

#### Scenario: Facade art includes placement constraints
- **WHEN** a surface-art recipe is generated for a wall or banner
- **THEN** the recipe includes enough placement and presentation metadata to determine how the image should be used on the target surface within current framework material behavior

### Requirement: Surface art recipes use a shared stylistic vocabulary
The system SHALL define a shared vocabulary for art subjects and style controls so contributors and lightweight models produce consistent facade and prop-art prompts across the repository.

#### Scenario: Two contributors target the same wall material family
- **WHEN** different contributors generate weathered timber or stone-wall facade recipes
- **THEN** both recipes use the same core descriptive fields and style vocabulary, enabling consistent prompting and asset organization