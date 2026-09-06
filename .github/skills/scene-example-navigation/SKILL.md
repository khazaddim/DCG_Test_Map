---
name: scene-example-navigation
description: 'Route world-creation and world-edit requests to the most relevant framework-backed demos and ported examples, with concise notes about the classes, reusable patterns, and current example gaps.'
---

# Scene Example Navigation

Use this skill when a model needs to find the best demo before creating or
editing a world in `Animation/draw_in_window_3d_framework/`. The goal is to
route requests toward existing composition patterns instead of inventing new
renderer capabilities.

## Primary authoring references

### `Animation/ported_demos/11_dearcygui_cpu_3d_map.py`

Primary classes:

- `Scene3D`
- `GroundPlane3D`
- `Polygon3D`
- `Line3D`
- `Polyline3D`
- `Text3D`
- `Box3D`

What it builds:

- A flat playable map with terrain bands, measurement overlays, named building
  masses, and one movable player piece.

Reusable patterns:

- Start a world with one broad `GroundPlane3D`, then layer simple
  `Polygon3D` regions for roads, rivers, or district bands.
- Use `Line3D`, `Polyline3D`, and `Text3D` as world-space planning aids before
  introducing more geometry.
- Use `Box3D` for rectangular building massing and simple landmarks.

Best first reference for:

- Building a new flat world from scratch.
- Adding boxy buildings, map bands, borders, or coordinate labels.
- Replacing 2D map rectangles with retained 3D scene objects.

### `Animation/ported_demos/12_dearcygui_cpu_3d_map.py`

Primary classes:

- `Box3D`
- `CollisionWorld`
- `AabbFootprint`

What it builds:

- Demo 11 plus collision-safe movement around retained building boxes.

Reusable patterns:

- Derive one `AabbFootprint` from each `Box3D` that should block movement.
- Keep collision edits local by rebuilding only the footprint set when a box is
  added, removed, or resized.

Best first reference for:

- Revising an existing world so the player cannot pass through buildings.
- Explaining how scene geometry and collision proxies stay in sync.

### `Animation/ported_demos/14_dearcygui_cpu_3d_trees.py`

Primary classes:

- `Box3D`
- `Billboard3D`
- `AnimatedImageMaterial`
- `DrawStream3D`
- `ProjectionPipeline`
- `CollisionWorld`

What it builds:

- Demo 11 with collision-safe movement, animated billboard trees, a
  preprojected water overlay, and a world-linked hovering marker.

Reusable patterns:

- Use `Billboard3D` for thin vertical props such as trees, bushes, signs, or
  NPC stand-ins.
- Use `DrawStream3D` plus `ProjectionPipeline` when the effect is an animated
  overlay rather than retained solid geometry.
- Attach a persistent overlay stream to a moving object when the marker should
  track gameplay state without becoming real 3D geometry.

Best first reference for:

- Adding trees or other sprite-like world props.
- Adding decorative water motion or a hovering marker above a world object.
- Extending an existing world with camera-facing art and light animation.

### `Animation/ported_demos/15_engineering_mesh_roofs.py`

Primary classes:

- `GroundPlane3D`
- `Box3D`
- `TriangleMesh3D`
- `MeshEdgeStyle`

What it builds:

- A small settlement where each rectangular building body gets a separate mesh
  roof chosen from gable, hip, pyramid, or shed patterns.

Reusable patterns:

- Keep walls as `Box3D` massing and layer one `TriangleMesh3D` roof on top.
- Express roof families as small helper builders that accept center, footprint,
  and wall-top height.
- Use `MeshEdgeStyle` only when ridge and eave lines materially improve the
  silhouette.

Best first reference for:

- Editing a box building into a more specific roofed structure.
- Adding sloped roof geometry without inventing a full mesh workflow.
- Explaining the smallest safe `TriangleMesh3D` topology for building roofs.

## Supporting references

### `Animation/ported_demos/collision_two_boxes.py`

- Best for the smallest collision example with two blocking `Box3D` objects and
  textured faces.
- Use it when the request is specifically about collision tuning rather than
  broader world layout.

### `Animation/ported_demos/collision_sort_diagnostics.py`

- Best for comparing overlap-aware vs average-depth sorting while moving through
  the Demo 11 world.
- Use it when a revision request involves ordering artifacts, not new world
  composition.

### `Animation/ported_demos/16_triangle_transition_diagnostic.py`

- Diagnostic only, not a world-building starting point.
- Use it when the request is about outline artifacts on nearly edge-on mesh
  faces, especially roofs borrowed from Demo 15.

## Request router

| Request | Start here | Why |
|---|---|---|
| "Create a simple town map" | `11_dearcygui_cpu_3d_map.py` | It shows the base retained world recipe: ground, bands, labels, and box buildings. |
| "Add or resize rectangular buildings" | `11_dearcygui_cpu_3d_map.py` | `Box3D` massing is already the main structure pattern there. |
| "Make movement respect buildings" | `12_dearcygui_cpu_3d_map.py` | It is the smallest direct example of `Box3D` plus `CollisionWorld`. |
| "Add trees, bushes, signs, or figure stand-ins" | `14_dearcygui_cpu_3d_trees.py` | `Billboard3D` is used exactly for thin camera-facing props. |
| "Add animated water or a hovering marker" | `14_dearcygui_cpu_3d_trees.py` | It shows the narrow documented use of `DrawStream3D`. |
| "Add a gable, hip, pyramid, or shed roof" | `15_engineering_mesh_roofs.py` | Each roof family is isolated as a small reusable `TriangleMesh3D` builder. |
| "Debug ordering or collision side effects while editing the world" | `collision_sort_diagnostics.py` | It exposes the sorter and collision choices separately. |
| "Investigate edge-on roof outline spikes" | `16_triangle_transition_diagnostic.py` | That diagnostic exists specifically for the Demo 15 outline artifact. |

## Revision guidance

- For greenfield world creation, begin with Demo 11 unless the request is
  explicitly about roofs or billboards.
- For edits to an existing world, route first by the affected class: `Box3D`
  and ground surfaces usually point to Demos 11 or 12, `Billboard3D` and
  `DrawStream3D` point to Demo 14, and `TriangleMesh3D` roof work points to
  Demo 15.
- When a request mixes multiple patterns, compose from the smallest proven
  references in this order: Demo 11 base layout, Demo 12 collision rules, Demo
  14 prop overlays, Demo 15 roof geometry.

## Example gaps to call out honestly

- No strong demo yet for curved roads, spline fences, or other non-linear path
  authoring.
- No settled example for sloped terrain, embankments, cliffs, or cutout ground
  beyond simple planar mesh patches.
- No combined town scene yet that merges collision, billboard foliage, and mesh
  roofs into one larger authored settlement.
- No example for collision proxies attached to `TriangleMesh3D` or
  `Billboard3D`; current collision guidance is box-footprint driven.
- No mature workflow for interiors, multistory floor plans, or enterable
  buildings.