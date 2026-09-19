# Terrain Surface and Hill Traversal Guide

## Purpose

This document explains the terrain work added for Milestone 5.25.

The goal of the change was to let the framework answer questions like:

- What is the support height at world-space `(x, y)`?
- What surface normal is under the actor?
- If the user clicks or points at the viewport, where does that screen point land on uneven terrain?
- Can a moving actor stand on this surface, or is it too steep or out of bounds?

The town hot-reload hill is the main example used to drive and test the feature.

## Big Picture

Before this work, the framework assumed a flat world for interaction and movement:

- `screen_to_ground()` resolved onto one constant `ground_z` plane.
- Movement kept the actor's `z` fixed.
- Collision treated every collider as a blocker.
- Camera follow logic assumed the focus point lived on a flat surface.

After this work, the framework can still do flat-ground movement, but it also supports a terrain-following mode:

- mesh triangles can act as a terrain surface;
- collision roles distinguish walkable support from blocking boundaries;
- actor `z` can be derived from terrain height;
- camera and widget queries can resolve against terrain instead of a plane.

## Main Files

### Core terrain surface logic

- `Animation/draw_in_window_3d_framework/terrain.py`

This file introduced the terrain abstraction layer.

Important types:

- `TerrainSample`
  - Holds `position`, optional `normal`, and optional `source_id`.
  - `height` is exposed as a convenience property.
- `TerrainSurface`
  - Protocol with two operations:
    - `sample(x, y)` for support-height lookup in world space.
    - `intersect_ray(origin, direction)` for viewport picking and screen queries.
- `MeshTerrainSurface`
  - Concrete implementation backed by triangle meshes.
  - Compiles triangles once, then answers repeated queries efficiently.

### Traversal and collision policy

- `Animation/draw_in_window_3d_framework/collision.py`

This file now owns the first terrain-aware traversal contract.

Important additions:

- `TraversalRole`
  - `LEGACY`: old behavior, acts like a normal blocker.
  - `BOUNDARY`: explicit blocker.
  - `TRAVERSABLE`: contributes support height, but is not a blocker by default.
- `TerrainMode`
  - `FLAT`
  - `FOLLOW_SURFACE`
- `OutOfBoundsPolicy`
  - `USE_FALLBACK_GROUND`
  - `REJECT`
- `TraversalSettings`
  - Controls flat-vs-terrain mode, fallback ground height, steep-slope limit, and out-of-bounds handling.
- `TraversalResolution`
  - The result of a movement/support query.
  - Carries the accepted position plus blocker/support/rejection details.

The main new behavior is in `CollisionWorld.resolve_movement(...)`.

That method now performs movement resolution in this order:

1. Check for blocking colliders with `first_blocker(...)`.
2. If blocked, reject movement.
3. If the mode is `FLAT`, return `(x, y, fallback_ground_z)`.
4. Otherwise, find the best traversable support surface with `support_sample(...)`.
5. Apply the configured out-of-bounds policy if no support exists.
6. If support exists and a max slope is configured, reject surfaces steeper than the limit.
7. Return the accepted terrain-aligned `(x, y, z)` position.

### Screen-to-surface queries

- `Animation/draw_in_window_3d_framework/math3d.py`
- `Animation/draw_in_window_3d_framework/widget.py`

`Camera3D` gained `ray_from_screen(...)`.

That method converts a screen-space point into:

- the camera eye position, and
- a normalized world-space ray direction.

`DrawInWindow3D` still keeps the older flat-plane method:

- `screen_to_ground(screen, ground_z=...)`

But it now also exposes:

- `screen_to_surface(screen, terrain=..., ground_z=...)`

Behavior:

- If terrain is available, it casts a ray into the terrain surface.
- If the ray hits, it returns the terrain hit point.
- If there is no hit, it can optionally fall back to `screen_to_ground(...)`.
- If `ground_z=None`, the query becomes terrain-only with no flat fallback.

### Terrain-aware camera follow

- `Animation/draw_in_window_3d_framework/controllers.py`

`EdgeBandFollowController` gained an optional `terrain` field.

In flat mode, it still behaves like the older version.

In terrain mode, it changes two things:

1. The focus point is treated as a real 3D terrain point instead of `(x, y, ground_z)`.
2. The controller uses `screen_to_surface(...)` to compute the retargeted point when the actor leaves the dead zone.

One subtle fix matters here:

- the camera target's `z` is anchored to the focus surface height,
- but the camera follow still computes the dead-zone correction only from the x/y retargeting logic.

That avoids a bad case where a ray landing on a different hill height could push camera target `z` below the actor's support height.

## How Mesh Terrain Sampling Works

`MeshTerrainSurface` is intentionally narrow. It does not try to reuse the whole render pipeline. It just treats selected triangles as a geometric support surface.

### 1. Triangle compilation

When the mesh terrain is created, each triangle is compiled into a cached internal form containing:

- the three triangle vertices;
- an upward-pointing normal;
- the source id;
- a precomputed x/y bounding box;
- a precomputed barycentric denominator.

Triangles are skipped if they are:

- degenerate;
- missing valid indices;
- vertical enough that they do not define a useful support height.

### 2. Height queries with `sample(x, y)`

`sample(x, y)` works like this:

1. Reject triangles whose x/y bounds do not contain the point.
2. Use barycentric coordinates in the triangle's projected x/y plane.
3. If the point lies inside the triangle, interpolate `z` from the triangle vertices.
4. If more than one triangle matches, keep the highest sample.

Keeping the highest sample is important because terrain can overlap in projection. The support surface should be the topmost traversable one at that `(x, y)`.

### 3. Screen picking with `intersect_ray(...)`

For viewport queries, `intersect_ray(...)` tests a ray against all compiled triangles and returns the nearest valid hit.

This is what allows `screen_to_surface(...)` to answer terrain-aware click/pick queries.

## The Traversal Contract

The traversal-role split is the main semantic change.

### Legacy behavior remains available

If you never opt into terrain mode:

- leave movement in `TerrainMode.FLAT`;
- use legacy/boundary colliders;
- do not attach a `TerrainSurface`.

Then movement behaves like the earlier flat-world demos.

### Boundary vs traversable

The new contract separates two concerns that used to be fused together:

- Blocking geometry: should stop movement.
- Support geometry: should provide standing height.

That is why a traversable hill is now registered as:

- an `AabbFootprint` for cheap candidate coverage; plus
- a `MeshTerrainSurface` for actual height/normal lookup; plus
- `TraversalRole.TRAVERSABLE` so it does not act like a wall.

This lets the actor stand on the hill without the hill blocking horizontal movement.

### Slope rejection

Slope rejection uses the terrain sample's normal.

The code converts the normal into a slope angle relative to straight up. A surface is rejected when:

$$
\text{slope angle} > \text{max slope degrees}
$$

So:

- a flat normal near `(0, 0, 1)` is accepted;
- a steeply tilted normal is rejected if it exceeds the configured threshold.

## Town Hill Example

The example terrain lives in:

- `Animation/ported_demos/town_hot_reload_world.py`
- `Animation/ported_demos/town_hot_reload.py`

### Geometry generation

The hill shape is defined by:

- `HILL_CORNER`
- `HILL_EXTENT`
- `HILL_HEIGHT`

`generate_rolling_hill_geometry(...)` builds the actual vertex and triangle arrays.

The height field is a decaying exponential based on distance from the hill corner, so the peak is highest near the corner and falls off smoothly.

That same geometry is reused in two places:

1. `add_rolling_hill(...)`
   - Adds the visible `TriangleMesh3D` and decorative contour/grid lines to the scene.
2. `build_terrain_surface()`
   - Builds a `MeshTerrainSurface` from the same hill mesh for movement and picking.

This is one of the more important design choices in the change:

```text
rendered hill geometry and traversed hill geometry come from the same source
```

That keeps visuals and traversal consistent.

### Collision registration

`build_collision_world()` still registers houses, towers, boulders, and other blockers the usual way.

It now also registers the hill footprint as a traversable collider:

- footprint bounds cover the hill's x/y area;
- role is `TraversalRole.TRAVERSABLE`;
- terrain is the `MeshTerrainSurface` built from the hill mesh.

### Traversal settings

`build_traversal_settings()` controls whether the world uses flat movement or hill-following movement.

Current terrain-follow configuration:

- `mode=TerrainMode.FOLLOW_SURFACE`
- `fallback_ground_z=0.0`
- `max_slope_degrees=HILL_MAX_SLOPE_DEGREES`
- `out_of_bounds_policy=OutOfBoundsPolicy.USE_FALLBACK_GROUND`

That means:

- the actor follows terrain when standing on the hill;
- if movement leaves the terrain footprint, the actor falls back to `z=0.0` instead of being rejected.

### Controller flow in the hot-reload app

`HotReloadTownController` in `town_hot_reload.py` is the main demo of terrain-aware movement.

The important flow is:

1. Load the scene.
2. Build `CollisionWorld`.
3. Build the terrain surface separately.
4. Store terrain on the viewport with `viewport.terrain = self.terrain`.
5. Anchor the avatar to terrain once with `_anchor_avatar_to_support()`.
6. During every move, call `collisions.resolve_movement(...)`.
7. If movement is accepted, set `avatar.center` to the returned terrain-aligned position.
8. Update the follow controller using that accepted terrain-aligned position.

That is the main structural change from the earlier flat demos.

## What Changed Conceptually

### Before

Interaction and movement assumed one infinite plane.

### After

Interaction and movement can use an explicit support surface.

The framework now has three separate concepts that used to be blurred together:

- rendered geometry;
- blocking geometry;
- traversable support geometry.

This separation is what makes hills possible without rewriting the renderer.

## What Stayed Intentionally Simple

This is the first terrain pass, not the final terrain system.

The current implementation keeps several constraints on purpose:

- support lookup is mesh-triangle based, not a full physics engine;
- blocking still uses 2D AABB footprints;
- no sliding or step resolution is attempted when a slope is too steep;
- traversable support is selected by topmost triangle at `(x, y)`;
- terrain picking is direct ray/triangle testing, not an acceleration structure.

Those constraints keep the change understandable and compatible with the existing demo architecture.

## Tests That Explain the Feature

The most useful learning-oriented tests are in:

- `tests/test_draw_in_window_3d_milestone5_25.py`

What each test proves:

- `test_mesh_terrain_surface_samples_height_and_normal`
  - Basic height and normal interpolation works.
- `test_mesh_terrain_surface_prefers_highest_overlapping_triangle`
  - The support surface chooses the topmost triangle when triangles overlap in x/y.
- `test_collision_world_roles_preserve_boundary_blockers_and_ignore_traversable_support`
  - Traversable terrain provides support without acting as a blocker.
- `test_collision_world_resolve_movement_rejects_steep_support_and_out_of_bounds`
  - Slope and out-of-bounds policies are enforced.
- `test_widget_screen_to_surface_resolves_town_hill_point`
  - Screen-space terrain resolution hits the expected hill point.
- `test_hot_reload_controller_anchors_avatar_to_hill_height_during_movement`
  - Movement updates actor `z` from terrain support.
- `test_edge_band_follow_controller_tracks_terrain_height`
  - Camera follow remains terrain-aware instead of flattening the focus point.

## How To Extend This Later

If you want to build on this terrain system, the next natural directions are:

1. Add spatial acceleration for terrain ray queries and support sampling.
2. Support multiple terrain patches with different priorities or materials.
3. Add richer traversal policies such as sliding, snapping, or jumping between support surfaces.
4. Extend the collision side from 2D AABB blocking toward terrain-aware volume tests if needed.
5. Allow terrain surfaces other than triangle meshes, as long as they satisfy the `TerrainSurface` protocol.

## Read This Code In Order

If you want to learn the feature by reading the code, this is the order I would use.

### 1. Start with the town world's hill geometry

Read `Animation/ported_demos/town_hot_reload_world.py` in this order:

- `HILL_CORNER`, `HILL_EXTENT`, `HILL_HEIGHT`, `HILL_MAX_SLOPE_DEGREES`
- `generate_rolling_hill_geometry(...)`
- `build_rolling_hill_mesh(...)`
- `build_terrain_surface()`
- `add_rolling_hill(...)`

Why start here:

- This is the concrete terrain data source.
- It shows that the visible hill mesh and the traversable hill surface come from the same generated triangle data.

When reading this part, focus on one key idea:

```text
terrain is not authored separately from rendering here; the same hill geometry feeds both
```

### 2. Read the terrain abstraction itself

Then read `Animation/draw_in_window_3d_framework/terrain.py` in this order:

- `TerrainSample`
- `TerrainSurface`
- `MeshTerrainSurface.from_triangle_mesh(...)`
- `MeshTerrainSurface.sample(...)`
- `MeshTerrainSurface.intersect_ray(...)`

What to look for:

- `sample(x, y)` is the support-height API used for movement.
- `intersect_ray(...)` is the picking/query API used for screen-to-surface resolution.
- `_compile_triangles(...)` shows the cached representation the runtime actually queries.

This file is the heart of the feature. If this file makes sense, the rest is mostly plumbing.

### 3. Read the traversal policy next

Then move to `Animation/draw_in_window_3d_framework/collision.py`.

Read in this order:

- `TraversalRole`
- `TerrainMode`
- `OutOfBoundsPolicy`
- `TraversalSettings`
- `TraversalResolution`
- `Collider`
- `CollisionWorld.first_blocker(...)`
- `CollisionWorld.support_sample(...)`
- `CollisionWorld.resolve_movement(...)`

What to look for:

- `TRAVERSABLE` colliders are intentionally skipped by `first_blocker(...)`.
- `support_sample(...)` asks all traversable colliders for a support height and keeps the best one.
- `resolve_movement(...)` is where blocking, fallback, slope rejection, and accepted terrain-aligned movement get unified into one result.

This is where the feature stops being “just a mesh query” and becomes actual movement behavior.

### 4. Read how screen-space queries were extended

Then read these two methods:

- `Animation/draw_in_window_3d_framework/math3d.py`: `Camera3D.ray_from_screen(...)`
- `Animation/draw_in_window_3d_framework/widget.py`: `DrawInWindow3D.screen_to_surface(...)`

What to look for:

- `ray_from_screen(...)` creates a world-space ray from a 2D viewport point.
- `screen_to_surface(...)` tries terrain first and only falls back to the flat plane if needed.

This is the query path to understand if you want to support terrain-aware mouse interaction later.

### 5. Read the camera follow changes

After that, read `Animation/draw_in_window_3d_framework/controllers.py` and focus on `EdgeBandFollowController.update(...)`.

What to look for:

- the controller now treats the focus point as a true 3D terrain point when terrain is enabled;
- it retargets using `screen_to_surface(...)` instead of only `screen_to_ground(...)`;
- it keeps camera target `z` anchored to the actor's support height.

This file is small, but it explains how terrain support reaches camera behavior without needing a new controller class.

### 6. Read the town demo wiring

Now go back to `Animation/ported_demos/town_hot_reload_world.py` and `Animation/ported_demos/town_hot_reload.py` and read the integration points in this order:

- `build_traversal_settings()`
- `build_collision_world()`
- `HotReloadTownController.__init__(...)`
- `HotReloadTownController._anchor_avatar_to_support()`
- `HotReloadTownController._move(...)`
- `HotReloadTownController._configure_follow()`
- `build_ui(...)`

What to look for:

- the world decides whether terrain mode is enabled;
- the hill gets registered as a traversable collider with both a footprint and a terrain surface;
- the controller anchors the avatar to terrain once on startup/reload;
- every accepted move uses the position returned by `resolve_movement(...)`.

This is the best place to see the full feature assembled into something interactive.

### 7. Finish with the tests

End with `tests/test_draw_in_window_3d_milestone5_25.py`.

Recommended order:

- `test_mesh_terrain_surface_samples_height_and_normal`
- `test_mesh_terrain_surface_prefers_highest_overlapping_triangle`
- `test_collision_world_roles_preserve_boundary_blockers_and_ignore_traversable_support`
- `test_collision_world_resolve_movement_rejects_steep_support_and_out_of_bounds`
- `test_widget_screen_to_surface_resolves_town_hill_point`
- `test_hot_reload_controller_anchors_avatar_to_hill_height_during_movement`
- `test_edge_band_follow_controller_tracks_terrain_height`

Why end here:

- the tests act like executable examples;
- each one isolates one design claim from the implementation.

## Suggested Mental Model While Reading

If the code starts to feel spread across too many files, reduce it to this pipeline:

```text
hill triangle data
  -> terrain surface queries
  -> traversal policy
  -> widget/camera query support
  -> demo controller movement and follow
  -> tests proving each step
```

That reading strategy usually makes the design much easier to hold in your head.

## Short Summary

The terrain milestone worked by adding one narrow abstraction and then threading it through the existing movement/query path:

```text
triangle mesh
    -> MeshTerrainSurface
    -> CollisionWorld support sampling / resolve_movement
    -> DrawInWindow3D screen_to_surface
    -> EdgeBandFollowController terrain-aware follow
    -> town_hot_reload avatar and camera using terrain-aligned positions
```

That is the main idea to keep in mind when reading the code: the renderer did not become a terrain system. Instead, a dedicated terrain-support layer was added beside the existing renderer and collision pieces, and the town hill wires those pieces together.