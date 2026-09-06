## ADDED Requirements

### Requirement: The repository catalogs scene archetypes derived from supported patterns
The system SHALL maintain a reusable scene-example catalog that maps fantasy environment archetypes onto composition patterns already demonstrated by the framework and ported demos.

#### Scenario: Existing demo knowledge becomes reusable references
- **WHEN** a contributor seeds the catalog from current ported demos and framework examples
- **THEN** each entry records the supported primitive families and composition patterns it demonstrates for future generated scenes

### Requirement: Catalog entries support variation without changing framework capability
The system SHALL allow example catalog entries to carry bounded variation inputs such as layout seed, building mix, vegetation density, roof style, or palette while staying inside existing framework support.

#### Scenario: Example family produces controlled variants
- **WHEN** a user requests multiple variations of a village, hill fort, or forest road example
- **THEN** the catalog provides variation knobs that diversify the output without requiring new primitives or renderer behavior

#### Scenario: Terrain-aware catalog entries are gated by the framework milestone
- **WHEN** a catalog entry depends on traversable slopes or other uneven-terrain movement semantics
- **THEN** the entry remains deferred or explicitly marked as requiring task 5.25 in `add-draw-in-window-3d-framework`

### Requirement: Catalog entries double as validation fixtures
The system SHALL define example entries with enough structure to serve as documentation references and acceptance fixtures for future skill outputs.

#### Scenario: New skill output is checked against catalog expectations
- **WHEN** a scene-generation skill is updated or a new archetype is added
- **THEN** the repository can compare the output against cataloged supported patterns and identify drift outside the approved framework surface