# Scene Example Catalog Specification

## Purpose

Define the demo-navigation documentation expected for routing world-creation and world-edit requests toward the framework-backed examples in this repository.

## Requirements

### Requirement: The repository documents demos as navigable scene references
The system SHALL maintain demo-by-demo documentation that maps world-authoring needs onto composition patterns already demonstrated by the framework and ported demos.

#### Scenario: Small model needs a reference for a world edit
- **WHEN** a smaller model needs to add or revise a world feature such as a road, wall, tree cluster, roof shape, or billboard prop
- **THEN** the demo documentation points it to one or more relevant demos or examples
- **AND** it explains why those references are a good starting point

### Requirement: Demo documentation records feature coverage per example
The system SHALL document a small, maintainable metadata set for each demo so a smaller model can find appropriate references quickly.

#### Scenario: Demo index clarifies what each example teaches
- **WHEN** a smaller model scans the demo index for a requested world feature
- **THEN** each relevant entry identifies the primary classes used by that demo
- **AND** it includes a short plain-language summary of what the demo builds or demonstrates
- **AND** it may include notable constraints or composition notes when they materially affect retrieval

### Requirement: Demo code carries inline pattern comments
The system SHALL place concise inline comments near important demo code blocks so reusable scene-building patterns remain understandable when a smaller model reads the source directly.

#### Scenario: Small model reads a demo code block directly
- **WHEN** a smaller model lands on a code block that builds a reusable structure such as a roof, stacked wall section, billboard cluster, or similar scene pattern
- **THEN** the surrounding demo code includes a concise inline comment that identifies the class being used, the structure the block helps build, and how the block fits into that structure
- **AND** the comment uses a consistent style without requiring a rigid fixed template
- **AND** the comment stays local to the code it describes instead of requiring a separate long-form explanation

### Requirement: Demo documentation supports world creation and revision workflows
The system SHALL organize demo references so a smaller model can use them for both greenfield world creation and edits to an existing world.

#### Scenario: Demo references help with revisions
- **WHEN** a user asks to modify an existing world rather than create a new one
- **THEN** the documentation can direct the model to demos that match the affected class or the closest plain-language summary instead of forcing a full redesign

### Requirement: Demo documentation stays inside supported framework boundaries
The system SHALL keep demo navigation guidance aligned with the documented capability boundary so under-exampled or unsupported features are not presented as mature references.

#### Scenario: Under-exampled feature is flagged honestly
- **WHEN** a smaller model looks for a reference covering a feature that is technically possible but not yet well represented in demos
- **THEN** the documentation notes the gap instead of pretending the repo already has a settled pattern
