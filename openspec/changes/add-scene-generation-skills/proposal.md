# Change: Add Scene Generation Skills

## Why

The framework now covers the core rendering primitives needed to build fantasy scenes, but the repo does not yet provide enough targeted documentation for smaller models to reliably choose the right application-level classes or find the best reference demos when making or editing a world. We need repo-local documentation skills and curated example navigation that help inexpensive models stay inside patterns the framework already supports.

## What Changes

- Add repo-local documentation skills for each application-level framework class used to author scenes, including usage guidance, constraints, and nearby examples
- Add demo-by-demo documentation and navigation aids that help a smaller model find appropriate references when creating or editing a world
- Keep the capability contract as an allowlist and boundary reference for future structured authoring work, without requiring recipe compilation or art-generation workflows in this phase

Phase 1 is intentionally documentation-first: the immediate goal is to help cheap models reason better about existing classes and demos before adding richer scene or art generation workflows.

## Capabilities

### New Capabilities
- `scene-class-documentation`: Documentation skills for choosing and applying the existing application-level scene classes correctly
- `scene-example-navigation`: Demo-by-demo documentation and reference mapping for world creation and revision tasks

### Modified Capabilities

None.

## Impact

- Affected code: `.github/skills/`, `Animation/draw_in_window_3d_framework/`, `Animation/ported_demos/`, and supporting docs for scene-authoring workflows
- Affected APIs: no required renderer API expansion in the first phase; this change is intentionally constrained to supported framework primitives and materials
- Affected systems: OpenSpec planning artifacts, Copilot skill authoring, and documentation/example discovery workflows for smaller models