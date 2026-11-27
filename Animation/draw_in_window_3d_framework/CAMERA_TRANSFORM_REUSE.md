# Camera transform reuse in the 3D renderer

This note explains the rendering phases and how polygon coordinates move
through them. The optimization avoids repeating a calculation; it does not
change the camera or the intended picture.

## The rendering flow

When a frame is rebuilt, the CPU renderer takes a 3D scene and prepares 2D
drawing instructions for DearCyGui. In simplified form, the phases are:

1. **Scene collection:** Gather the scene's drawable pieces into *render
   packets*. A polygon packet contains its vertices in world coordinates,
   along with its material and other drawing information.
2. **Projection and clipping:** Decide which pieces can be seen, transform
   their coordinates relative to the camera, and convert the visible parts to
   screen coordinates. Clipping removes the parts too close to the camera or
   outside the viewport.
3. **Sorting:** Determine a drawing order for overlapping pieces using their
   projected shapes and depth information.
4. **Line occlusion:** Work out which portions of world lines should be hidden
   by polygons.
5. **Emission and publication:** Create DearCyGui drawing nodes and publish
   the completed drawing layer.

The optimization described here affects the polygon work in phase 2. Sorting,
line handling, drawing-node creation, and publication still happen afterward.
The [renderer](renderer.py) starts these phases in `CpuRenderer3D.render`;
the [math helpers](math3d.py) implement the coordinate and clipping operations.

## Three coordinate spaces

- **World space** describes where a point is in the scene, independently of
  the camera. For example, a wall vertex stays at the same world location when
  the camera moves.
- **Camera space** describes that point relative to the current camera. Its
  third coordinate is forward depth. `Camera3D.world_to_camera` uses the camera
  and viewport to calculate this position.
- **Screen space** is the resulting 2D position in the viewport. The
  `camera_to_screen` perspective calculation divides by depth, so more distant
  objects appear smaller.

These are different representations of the same geometry, not three separate
objects in the world. The near-plane clip is performed in camera space before
the perspective calculation; viewport clipping is performed afterward in 2D.
Clipping can create new intersection points, so the final visible screen
polygon can have different vertices from the original world polygon.

## Before: calculate the same camera coordinates again

For each polygon that passed back-face culling, the renderer first transformed
its world-space vertices to camera space. It needed these coordinates to check
the near plane and later retain depth information. However, it then passed the
original **world-space** vertices to projection helpers, which transformed
them again:

```text
world vertices
    |-- world_to_camera --> camera vertices for checks / retained depth
    |-- project_polygon(world vertices)
    |       `-- world_to_camera again --> clip --> project --> screen polygon
    `-- project_complete_quad(world vertices), for some image polygons
            `-- world_to_camera again --> check/project image quad
```

In the repeated-transform path, a solid polygon typically transforms each
vertex twice. Some image and near-clipping cases perform additional passes.
The results of those repeated calculations describe the same polygon from the
same camera.

## Now: pass camera coordinates to the helpers

The renderer still begins with the polygon's world-space vertices, but it
calculates `raw_camera_points` once and passes those coordinates to the
camera-space helpers:

```text
world vertices
    `-- world_to_camera --> raw_camera_points
            |-- near-plane check
            |-- _project_camera_polygon --> near clip --> screen projection
            |                              --> viewport clip --> cleanup
            |-- _project_camera_complete_quad, for applicable image polygons
            `-- ProjectedRenderEntry.camera_points
```

In [`CpuRenderer3D._project_packet`](renderer.py), the same tuple is used for
the relevant image checks, normal polygon projection, and the retained entry.
The complete-quad helper is used when an image polygon must fit entirely in the
viewport. For viewport-clipped images that are fully in front of the camera,
the original camera-space quad also supplies the image's screen-space corners.
When an image cannot use its image path, the existing solid-material fallback
is retained.

The projection helper clips a **separate** camera-space polygon against the
near plane, projects it to screen, clips it to the viewport, and cleans it up.
Its visible screen vertices and average depth go into the projected entry.
The entry's `camera_points` instead retain the **original, unclipped** camera
vertices. Later code uses those vertices for depth comparisons and line
occlusion, and for tessellating applicable image quads. This distinction
matters when a polygon crosses the near plane.

The existing `ProjectionPipeline.project_polygon` and `project_complete_quad`
methods still accept world-space vertices; they transform them and delegate to
the new internal camera-space helpers. Existing callers therefore do not need
to change.

This reuse is **per polygon, per rebuild**, not a cache across frames or a
single transform for the whole scene. Shared vertices in different packets can
still be transformed separately. Lines, text, and streams follow their own
paths. It also does not combine camera transformations into a new matrix:
the existing `world_to_camera` calculation is simply performed fewer times.

## Default and comparison switch

Reuse is on by default in `CpuRenderer3D` and in the profiling launchers. To
compare the previous repeated-transform path, restart a profiling launcher with
`--no-reuse-camera-transforms`; omit it to use the default. The profiling panel
and exported counters report the selected mode. See the [README comparison
instructions](../../README.md#comparing-camera-transform-reuse) for an example.

The focused [projection tests](../../tests/test_draw_in_window_3d_milestone3.py)
compare both modes for solid polygons, image cases, and clipping, and check
Organic Frozen Temple's projected entries and sorting. This is a calculation
reduction in one stage, so the overall frame-time improvement depends on the
scene and on how much time the other phases take.
