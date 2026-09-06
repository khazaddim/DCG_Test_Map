# Scene Generation Skills Specification

## Purpose

Define the repo-local documentation skill behavior for choosing the retained 3D scene-authoring classes that are already supported by the framework and demonstrated by the ported examples.

## Requirements

### Requirement: Scene class documentation covers application-level authoring surfaces
The system SHALL provide repo-local documentation skills that explain the application-level scene-authoring classes, when to use them, how they compose, and which limitations matter when creating or revising a world.

#### Scenario: Small model asks which scene class to use
- **WHEN** a smaller model needs to decide between classes such as `Box3D`, `GroundPlane3D`, `Billboard3D`, `Polygon3D`, or `TriangleMesh3D`
- **THEN** the documentation skill explains the intended use of each relevant class
- **AND** it points to nearby examples or demos that show those classes in practice

### Requirement: Scene class documentation includes constraints and refusal guidance
The system SHALL document which requests fall outside the intended use of each application-level class so a smaller model can avoid unsupported scene edits.

#### Scenario: Small model asks for an unsupported usage
- **WHEN** a smaller model tries to use a class for behavior that the current framework or examples do not support
- **THEN** the documentation skill calls out the limitation
- **AND** it suggests a safer nearby pattern or states that more examples are needed

### Requirement: Scene class documentation stays aligned to the capability contract
The system SHALL keep its class guidance aligned with the approved primitive and material boundary documented for this change.

#### Scenario: Class guidance matches the allowlist
- **WHEN** the documentation skill describes supported authoring surfaces
- **THEN** it centers the current primary scene-authoring classes and approved material families
- **AND** it avoids implying support for excluded or under-exampled features as if they were mature workflows
