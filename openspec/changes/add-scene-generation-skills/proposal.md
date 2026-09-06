# Change: Add Scene Generation Skills

## Why

The framework now covers the core rendering primitives needed to build fantasy scenes, but the repo does not yet provide a structured way for smaller models to turn high-level world ideas into valid framework examples, reusable scene recipes, or building-surface art assets. We need repo-local skills and capability contracts that scale content generation by constraining outputs to patterns the framework already supports.

## What Changes

- Add repo-local skills for generating towns, hills, forests, castles, roads, and other scene layouts using existing framework primitives and demo-proven composition patterns
- Define constrained scene-recipe contracts that map high-level prompts onto supported objects such as `Box3D`, `TriangleMesh3D`, `Billboard3D`, `GroundPlane3D`, `Line3D`, and existing material types
- Add a surface-art recipe capability for generating facade imagery and placement metadata for doors, windows, brick, stone, timber, banners, and similar building-side artwork
- Add an example-scene catalog capability that turns ported demos and framework patterns into reusable references, templates, and variation seeds for future generated examples
- Establish validation rules so generated skills, examples, and assets stay within existing framework capability boundaries instead of silently demanding new renderer features

## Capabilities

### New Capabilities
- `scene-generation-skills`: Skills and recipe contracts for converting constrained world briefs into framework-backed scene examples
- `surface-art-recipes`: Skills and recipe contracts for generating facade and billboard artwork prompts plus placement metadata usable by existing material paths
- `scene-example-catalog`: A reusable catalog of scene archetypes, composition patterns, and variation fixtures derived from current demos and framework objects

### Modified Capabilities

None.

## Impact

- Affected code: `.github/skills/`, `Animation/ported_demos/`, example/template data folders, and supporting docs for scene-generation workflows
- Affected APIs: no required renderer API expansion in the first phase; this change is intentionally constrained to supported framework primitives and materials
- Affected systems: OpenSpec planning artifacts, Copilot skill authoring, prompt/schema validation, and generated example asset organization