# Capability Contract

This document completes tasks 1.1 through 1.3 for `add-scene-generation-skills`.
It defines the supported capability boundary for phase 1, selects the intermediate
recipe format, and fixes the vocabulary that generated outputs may reference.

## 1. Capability Boundaries

The source of truth for phase-1 support is the current retained-object inventory in
`Animation/draw_in_window_3d_framework`.

### 1.1 Scene Generation Skills

Scene generation is in bounds when a recipe guides creation or revision of existing
scene objects and materials without inventing renderer behavior.

Allowed framework-backed object families:

| Recipe primitive | Framework mapping | Allowed use in this change |
|---|---|---|
| `ground_plane` | `GroundPlane3D` | Flat terrain pads, plazas, courtyards, roads, water planes |
| `box` | `Box3D` | Buildings, walls, towers, gates, crates, keep volumes |
| `polygon` | `Polygon3D` | Flat wall panels, signs, simple roof faces, trim surfaces |
| `line` | `Line3D` | Borders, path markers, guide lines, utility scene accents |
| `polyline` | `Polyline3D` | Road centerlines, fence runs, wall outlines, route traces |
| `text_label` | `Text3D` | Named landmarks, debug labels, example annotations |
| `billboard` | `Billboard3D` | Trees, shrubs, banners, hanging signs, distant props |
| `triangle_mesh` | `TriangleMesh3D` | Roofs, cliffs, hill silhouettes, ramps, irregular terrain visuals |

Supported but out of scope for generated scene recipes in phase 1:

| Framework object or material | Boundary decision | Reason |
|---|---|---|
| `TetrahedralMesh3D` | Excluded | Engineering/field visualization surface, not a first-wave fantasy scene primitive |
| `DrawStream3D` | Documented but not recipe-allowed | Demo 14 uses it in a world-building pattern, but animation authoring remains separate from static scene-layout generation in phase 1 |
| `ScalarFieldMaterial` | Excluded | Encodes analysis/field rendering rather than fantasy-scene art direction |
| `AnimatedImageMaterial` outside billboards | Excluded | Phase 1 does not promise animated facade or mesh-surface textures |

Scene generation must refuse or rewrite requests that require:

- Curved or spline-native primitives
- Skeletal animation, particles, volumetrics, or GPU effects
- New collision, traversal, or terrain-query semantics
- Automatic Python source generation as the primary contract
- Traversable uneven terrain before task 5.25 in `add-draw-in-window-3d-framework`

### 1.2 Surface Art Recipes

Surface-art generation is a metadata capability, not a geometry capability.

In bounds:

- Wall, facade, sign, banner, and billboard artwork prompts
- Placement metadata for existing material paths
- Tiling, palette, weathering, and aspect-ratio controls
- Attachment to `Box3D` faces, `Polygon3D` panels, and `Billboard3D` quads

Out of bounds:

- New UV-mapping behavior, decal systems, or shader semantics
- Binary asset generation requirements inside this change
- Procedural mesh editing driven by art recipes
- Roof-surface projections that require geometry-aware unwrapping

### 1.3 Scene Example Catalog

The example catalog stores references and fixtures derived from supported patterns.

In bounds:

- Archetype entries that point to approved recipe primitives and materials
- Example metadata that records source demos, coverage, and variation knobs
- Recipe fixtures that can later be validated for vocabulary and schema conformance

Out of bounds:

- A runtime procedural generator or compiler pipeline
- Automatic expansion of framework capability through examples
- Terrain-traversal examples that assume milestone 5.25 semantics

## 2. Intermediate Recipe Format

Phase 1 uses YAML files constrained to a JSON-compatible subset.

Decision:

- Use `.yaml` recipe documents for scene recipes, surface-art recipes, and later example fixtures.
- Restrict values to maps, lists, strings, numbers, booleans, and `null`.
- Use snake_case keys and explicit enumerated strings for vocabulary fields.
- Forbid inline Python expressions, anchors, aliases, custom tags, and executable literals.

Rationale:

- YAML is easier for lightweight models and human contributors to author than raw JSON.
- The JSON-compatible subset keeps later validation straightforward in Python.
- The format cleanly supports comments and hand-edited example libraries without changing the data model.

### 2.1 Scene Recipe Shape

```yaml
schema_version: 1
recipe_kind: scene
scene_id: riverside_hamlet_a
archetype: town_hamlet
brief: Small riverside hamlet with timber houses and a gate road.
terrain_mode: flat
variation_seed: 17
palette: late_summer
objects:
  - primitive: ground_plane
    id: plaza_ground
    material: solid
    bounds: [-220, -180, 220, 180]
    z: 0
  - primitive: box
    id: house_01
    archetype_role: timber_house
    center: [40, 10, 0]
    size: [52, 36, 34]
    material: solid
  - primitive: triangle_mesh
    id: roof_01
    archetype_role: gable_roof
    material: solid
    vertices: []
    triangles: []
surface_art:
  - target_object: house_01
    face: north
    recipe_id: timber_window_small
notes: []
```

Required top-level fields:

- `schema_version`
- `recipe_kind`
- `scene_id`
- `archetype`
- `terrain_mode`
- `objects`

Reserved scene fields for later phases:

- `terrain_query`
- `movement_rules`
- `slope_regions`

These reserved fields must not be populated before milestone 5.25 is complete.

### 2.2 Surface Art Recipe Shape

```yaml
schema_version: 1
recipe_kind: surface_art
recipe_id: timber_window_small
surface_type: facade_panel
subject: window
style_family: fantasy_timber
material_family: timber
palette: weathered_oak
weathering: light
aspect_ratio: 1.0
tiling: none
placement:
  anchor: centered
  margin_ratio: 0.12
  target_faces: [north, south]
prompt:
  positive: Small leaded glass window framed by dark timber.
  negative: modern aluminum frame, photograph, neon lighting
```

Required top-level fields:

- `schema_version`
- `recipe_kind`
- `recipe_id`
- `surface_type`
- `subject`
- `style_family`
- `material_family`
- `placement`
- `prompt`

## 3. Allowed Vocabulary

Generated outputs may reference only the following controlled vocabulary in phase 1.

### 3.1 Primitive Vocabulary

| Allowed token | Maps to | Notes |
|---|---|---|
| `ground_plane` | `GroundPlane3D` | Flat terrain and pads only |
| `box` | `Box3D` | Primary building and fortification volume |
| `polygon` | `Polygon3D` | Flat panels and simple planar faces |
| `line` | `Line3D` | Single segment utility geometry |
| `polyline` | `Polyline3D` | Multi-segment roads, walls, fences |
| `text_label` | `Text3D` | Annotation or named location marker |
| `billboard` | `Billboard3D` | Camera-facing vegetation or sign art |
| `triangle_mesh` | `TriangleMesh3D` | Roofs, cliffs, visual hills, irregular solids |

Forbidden primitive tokens in phase 1:

- `tetrahedral_mesh`
- `draw_stream`
- `curve`
- `decal`
- `particle_system`
- `heightfield_traversal`

### 3.2 Material Vocabulary

| Allowed token | Maps to | Notes |
|---|---|---|
| `solid` | `SolidMaterial` | Default geometry material |
| `image` | `ImageMaterial` | Static textured facade or sign surface |
| `animated_image` | `AnimatedImageMaterial` | Billboard-only in phase 1 |

Forbidden material tokens in phase 1:

- `scalar_field`
- `shader_custom`
- `normal_mapped`
- `terrain_query_material`

### 3.3 Archetype Vocabulary

Allowed scene archetype tokens:

- `town_hamlet`
- `town_square`
- `town_walled`
- `forest_edge`
- `forest_path`
- `forest_clearing`
- `castle_keep`
- `castle_gate`
- `castle_outpost`
- `road_straight`
- `road_bend`
- `road_bridgehead`
- `hill_backdrop`
- `hill_ruin`

Archetype boundary notes:

- `hill_*` archetypes are visual-only in phase 1 and may use static meshes or billboards.
- No archetype may assume traversable slopes, slope-following placement, or terrain-aware movement before milestone 5.25.
- New archetype names are not allowed unless a follow-on change updates this contract first.

### 3.4 Surface Art Vocabulary

Allowed `surface_type` tokens:

- `facade_panel`
- `door_panel`
- `window_panel`
- `sign_panel`
- `banner_panel`
- `billboard_panel`
- `roof_trim_panel`

Allowed `subject` tokens:

- `door`
- `window`
- `brick`
- `stone`
- `timber`
- `banner`
- `roof_trim`
- `shop_sign`

Allowed `material_family` tokens:

- `timber`
- `stone`
- `brick`
- `plaster`
- `painted_cloth`
- `slate`
- `thatch`
- `iron`

Allowed `weathering` tokens:

- `clean`
- `light`
- `moderate`
- `heavy`

Allowed `tiling` tokens:

- `none`
- `repeat_x`
- `repeat_xy`

## 4. Authoring Rules

- Generated outputs must reference recipe tokens, not raw Python code, as the primary artifact.
- Recipes may map to framework classes in documentation, validation, manual example authoring, or later helper tooling.
- Phase 1 treats recipes as iterative planning and editing artifacts, not as mandatory inputs to a Python source generator.
- If a brief asks for unsupported renderer behavior, the skill must refuse or degrade to the nearest allowed flat-ground or static-art result.
- Any future validator should treat this document as the phase-1 allowlist.