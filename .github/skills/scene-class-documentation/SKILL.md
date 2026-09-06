---
name: scene-class-documentation
description: 'Choose and apply the retained 3D scene-authoring classes used by framework demos 11, 14, and 15. Use when deciding between Box3D, GroundPlane3D, Polygon3D, Line3D, Polyline3D, Text3D, Billboard3D, TriangleMesh3D, DrawStream3D, or the small set of supporting utilities and materials that those demos depend on.'
---

# Scene Class Documentation

Use this skill when a model needs to create or revise a world using the
retained 3D framework in `Animation/draw_in_window_3d_framework/`. The goal is
to keep authoring inside the proven primitive and material boundary documented
for this repo's scene-generation change.

Primary phase-1 authoring classes:

- `GroundPlane3D`
- `Box3D`
- `Polygon3D`
- `Line3D`
- `Polyline3D`
- `Text3D`
- `Billboard3D`
- `TriangleMesh3D`

Directly documented supporting surfaces because demos 11, 14, or 15 use them
to build visible world patterns:

- `DrawStream3D`
- `Scene3D`
- `SolidMaterial`
- `ImageMaterial`
- `AnimatedImageMaterial`
- `MeshEdgeStyle`
- `ProjectionPipeline`

Non-primary or out-of-scope surfaces for this phase:

- `TetrahedralMesh3D` is an advanced engineering surface, not a first-wave
  fantasy scene primitive.
- `ScalarFieldMaterial` is for field visualization rather than the demo-backed
  scene-authoring patterns covered here.
- No class here implies terrain-aware placement, curved geometry, skeleton
  animation, spline roads, or freeform mesh editing workflows.

## Quick chooser

| Need | Prefer | Why | Avoid when |
|---|---|---|---|
| Large flat ground or base terrain | `GroundPlane3D` | Lowest-friction retained ground surface | You need a shaped surface, cutout, or slope |
| Rectangular building, wall block, crate, or player token | `Box3D` | Fastest solid volume with automatic faces | The shape needs a ridge, diagonal roof, or non-rectangular silhouette |
| One flat filled surface with arbitrary outline | `Polygon3D` | Good for roads, water bands, pads, and cut-in map regions | You need thickness, multiple slopes, or per-triangle control |
| World measurement or utility line segment | `Line3D` | Single segment with explicit render layer | You need a path or border made of several segments |
| Border, route, or closed outline | `Polyline3D` | Keeps a connected path together | You need a filled surface rather than an outline |
| Ground label or simple annotation | `Text3D` | Cheapest world-space naming and coordinate labels | The label must always face the camera as an image |
| Camera-facing sprite stand-in for tree, bush, sign, or figure | `Billboard3D` | Best for thin vertical art that should yaw toward the camera | The object needs real side/top geometry or collision volume |
| Explicit roof, cliff, ramp, road strip, or custom planar mesh | `TriangleMesh3D` | Full control over triangle layout and edge accents | A box or polygon already matches the shape |
| Screen-projected or overlay animation tied to world context | `DrawStream3D` | Lets demo 14 add animated water and a hovering marker without new geometry | A static polygon, text, billboard, or mesh would do |

## Material boundaries

- Prefer `SolidMaterial` for almost every retained solid in demos 11 and 15.
- Use `ImageMaterial` when one box face should show a single texture, such as
  demo 14's player top face.
- Use `AnimatedImageMaterial` only with `Billboard3D` when the visible object is
  fundamentally sprite-like and camera-facing.
- `MeshEdgeStyle` is optional polish for `TriangleMesh3D`. It is not a generic
  outline system for every primitive.

If a request can be satisfied with a flat color and outline, stay on
`SolidMaterial`. That is the safest fallback for smaller models.

## Class guides

### `GroundPlane3D`

Purpose: axis-aligned rectangular ground at a single `z` height.

Key parameters:

- `bounds=(x0, y0, x1, y1)` sets the world rectangle.
- `z` sets one constant elevation for the whole plane.
- `material` should usually be an unshaded `SolidMaterial` for terrain bases.

Prefer over nearby alternatives:

- Prefer it over `Polygon3D` for large rectangular terrain because the intent is
  clearer and back-face culling is already disabled safely.
- Prefer it over `TriangleMesh3D` when the ground is flat and does not need cuts
  or slopes.

Important limits:

- It cannot represent holes, banks, ramps, or curved terrain.
- It always emits one quad at one elevation.

Safe fallback: if the desired terrain is not flat, either approximate it with a
small number of `TriangleMesh3D` surfaces already backed by an example, or keep
it flat and state that richer terrain needs new examples.

Examples:

- [Animation/ported_demos/11_dearcygui_cpu_3d_map.py](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py)
- [Animation/ported_demos/15_engineering_mesh_roofs.py](../../../Animation/ported_demos/15_engineering_mesh_roofs.py)

### `Box3D`

Purpose: retained rectangular prism used for buildings, walls, towers, simple
volumes, and controllable world pieces.

Key parameters:

- `center=(x, y, z0)` uses `z` as the base height, not the vertical midpoint.
- `size=(width, depth, height)` controls footprint and height.
- `material` is the default face material.
- `face_materials` optionally overrides specific faces; it must contain exactly
  six entries when provided.

Prefer over nearby alternatives:

- Prefer it over `TriangleMesh3D` for rectangular buildings and collision
  blocks.
- Prefer it over stacked `Polygon3D` faces because `Box3D` keeps normals and
  face layout consistent.

Important limits:

- Footprint is always rectangular and axis-aligned in world space.
- There is no per-face transform, bevel, or roof shaping beyond material
  overrides.
- `face_materials` is ordered by the built-in face table, so partial tuples are
  invalid.

Safe fallback: if a building only needs boxy massing, stop at `Box3D` and do
not introduce a mesh roof. For a more complex silhouette, combine one `Box3D`
wall volume with one `TriangleMesh3D` roof, as in demo 15.

Examples:

- [Animation/ported_demos/11_dearcygui_cpu_3d_map.py](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py)
- [Animation/ported_demos/14_dearcygui_cpu_3d_trees.py](../../../Animation/ported_demos/14_dearcygui_cpu_3d_trees.py)
- [Animation/ported_demos/15_engineering_mesh_roofs.py](../../../Animation/ported_demos/15_engineering_mesh_roofs.py)

### `Polygon3D`

Purpose: one flat filled polygon for map bands, pads, or other single-surface
regions.

Key parameters:

- `points` defines the world-space corners in draw order.
- `material` is always `SolidMaterial` here.
- `cull_back_face=False` is often correct for horizontal or thin map patches.
- `normal` can be supplied when the automatic normal would be ambiguous.

Prefer over nearby alternatives:

- Prefer it over `TriangleMesh3D` for one flat region with no need for explicit
  triangle authoring.
- Prefer it over `GroundPlane3D` when the shape is not an axis-aligned
  rectangle.

Important limits:

- It is still a single planar face; no thickness or vertical sides are created.
- Point order matters for normals and back-face culling.
- Concave or self-crossing shapes are higher risk than simple convex bands.

Safe fallback: split a risky complex region into a few simple convex polygons,
or use a two-triangle `TriangleMesh3D` if you need explicit control.

Examples:

- [Animation/ported_demos/11_dearcygui_cpu_3d_map.py](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py)

### `Line3D`

Purpose: one retained world-space line segment.

Key parameters:

- `start` and `end` define the segment.
- `color` and `thickness` control styling.
- `render_layer` chooses whether the segment behaves like world geometry or a
  utility overlay.

Prefer over nearby alternatives:

- Prefer it over `Polyline3D` for one independent segment.
- Prefer it over thin polygons when the intent is measurement or guidework.

Important limits:

- It is only one segment.
- It does not create width in world units; line thickness is a render style.

Safe fallback: if the line is purely optional grid or boundary guidance, keep
it in `LineRenderLayer.UTILITY` and avoid inventing thicker geometry.

Examples:

- [Animation/ported_demos/11_dearcygui_cpu_3d_map.py](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py)

### `Polyline3D`

Purpose: connected retained path for borders, outlines, and routes.

Key parameters:

- `points` defines the path vertices.
- `closed=True` closes the loop back to the first point.
- `render_layer` often belongs on `UTILITY` for map borders.

Prefer over nearby alternatives:

- Prefer it over several `Line3D` objects when the segments form one logical
  path.
- Prefer it over `Polygon3D` when no fill is needed.

Important limits:

- It never fills the interior.
- Fewer than two points emit nothing.

Safe fallback: if the visual goal is a border only, stay with `Polyline3D`
instead of promoting the shape into a mesh.

Examples:

- [Animation/ported_demos/11_dearcygui_cpu_3d_map.py](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py)

### `Text3D`

Purpose: world-anchored text for labels, coordinates, and simple annotations.

Key parameters:

- `position` anchors the text in world space.
- `size` is the desired size before min/max screen clamps.
- `min_size` and `max_size` keep labels readable across zoom levels.

Prefer over nearby alternatives:

- Prefer it over billboards when plain text is enough.
- Prefer it over UI-only `dcg.Text` when the label should live in world space.

Important limits:

- It is textual annotation, not a textured signboard.
- Large numbers of labels can clutter the scene quickly.

Safe fallback: if labels become noisy, keep only the most important world text
and move diagnostics or instructions into regular UI widgets.

Examples:

- [Animation/ported_demos/11_dearcygui_cpu_3d_map.py](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py)

### `Billboard3D`

Purpose: camera-yaw-facing textured quad for trees, signs, bushes, or other
thin upright art.

Key parameters:

- `anchor` is the world-space bottom center of the billboard.
- `world_size=(width, height)` sets the physical footprint of the sprite.
- `material` should be `ImageMaterial` or `AnimatedImageMaterial`.
- `facing` currently only supports `BillboardFacing.CAMERA_YAW`.

Prefer over nearby alternatives:

- Prefer it over `Box3D` when the object is visually thin and sprite-based.
- Prefer it over `DrawStream3D` when the animation is texture-driven and should
  live in occludable world space.

Important limits:

- Only camera-yaw facing is supported.
- It has no real side depth or top face.
- Collision still needs a separate world representation if required.

Safe fallback: for a smaller model, use a static billboard first. If a request
needs fully modeled foliage or arbitrary facing modes, state that the current
framework examples do not support that as a mature workflow.

Examples:

- [Animation/ported_demos/14_dearcygui_cpu_3d_trees.py](../../../Animation/ported_demos/14_dearcygui_cpu_3d_trees.py)

### `TriangleMesh3D`

Purpose: explicit triangle-authored geometry for roofs, custom ground strips,
ramps, cliffs, or other shapes that are not well expressed as boxes or single
polygons.

Key parameters:

- `vertices` stores reusable world-space points.
- `triangles` stores triples of vertex indices.
- `material` can be one shared material for all triangles.
- `edges` optionally emits one line packet per unique mesh edge.
- `cull_back_faces` should usually stay on for opaque solids.

Prefer over nearby alternatives:

- Prefer it over `Polygon3D` when the shape needs multiple planes or explicit
  triangulation.
- Prefer it over `Box3D` for roof forms and sloped surfaces.

Important limits:

- Indices must be valid and each triangle must contain exactly three vertices.
- Degenerate triangles emit nothing.
- This class does not generate wall thickness, closed volumes, or automatic UVs.

Safe fallback: for smaller models, build the simplest two-triangle or four-to-
six-triangle roof that matches an existing demo pattern. If the requested shape
needs freeform mesh editing, stop and ask for a new example rather than
inventing topology.

Examples:

- [Animation/ported_demos/15_engineering_mesh_roofs.py](../../../Animation/ported_demos/15_engineering_mesh_roofs.py)

### `DrawStream3D`

Purpose: animated draw callback wrapped as a retained world-linked packet.
Demo 14 uses it for moving water dashes and a hovering marker.

Key parameters:

- `projection_policy` decides whether the stream is a persistent overlay,
  preprojected background effect, or world-occludable animation.
- `frame_count` and `loop_seconds` define the loop cadence.
- `frame_builder` draws one frame into a temporary drawing list.
- `anchor` and `world_size` matter when the stream is spatially attached.

Prefer over nearby alternatives:

- Prefer it over `Billboard3D` when the frame contents are generated by drawing
  commands rather than pre-made textures.
- Prefer it over hand-rebuilding the whole scene when only one local animated
  overlay or projected effect is needed.

Important limits:

- `frame_count` must be at least 1 and `loop_seconds` must be positive.
- Persistent overlays require an `anchor`.
- It is not part of the phase-1 recipe allowlist even though demo 14 uses it as
  a documented world-building pattern.

Safe fallback: if the effect is decorative and static, replace it with a
`Polygon3D`, `Text3D`, or billboard. Use `DrawStream3D` only when animation is
the point of the example.

Examples:

- [Animation/ported_demos/14_dearcygui_cpu_3d_trees.py](../../../Animation/ported_demos/14_dearcygui_cpu_3d_trees.py)

## Supporting utility notes

### `Scene3D`

Use `Scene3D` as the retained container for authoring objects. Add world
objects once, then mutate the object instance when a demo needs movement or a
material change. It is the right place to compose `GroundPlane3D`, `Box3D`,
`TriangleMesh3D`, billboards, and streams into one world.

### `SolidMaterial`, `ImageMaterial`, and `AnimatedImageMaterial`

- `SolidMaterial` is the default for terrain, boxes, polygons, and roofs.
- `ImageMaterial` is the low-risk way to put one texture on a box face.
- `AnimatedImageMaterial` is best paired with `Billboard3D`; do not treat it as
  a generic mesh animation system.

### `MeshEdgeStyle`

Use `MeshEdgeStyle` only when edge packets explain form, as in demo 15's roof
ridges and eaves. Skip it when the roof already reads clearly; smaller models
should not assume every mesh needs edge accents.

### `ProjectionPipeline`

Use `ProjectionPipeline` only when a demo needs to project custom world-space
overlay geometry itself, as demo 14 does for animated water dashes. It is a
supporting utility, not a replacement for `TriangleMesh3D` or `Billboard3D`.

Safe fallback: if a custom effect can be expressed with retained world objects,
do that instead of manually projecting ad hoc geometry.

## Refusal and boundary guidance

Refuse or narrow the request when it implies any of the following without a new
example or follow-on change:

- Curved roads, spline fences, or bevel-heavy architecture
- Terrain-aware placement on sloped or sculpted ground
- Freeform mesh editing, UV authoring, or skinned character animation
- Arbitrary billboard facings beyond camera yaw
- Treating `DrawStream3D` as a general replacement for retained world geometry

When possible, fall back to one of these safe patterns instead:

- `Box3D` massing plus `TriangleMesh3D` roof
- Flat `GroundPlane3D` or simple `Polygon3D` regions
- `Billboard3D` for thin vertical art
- Plain `Text3D` or utility lines for annotation and diagnostics