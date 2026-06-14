---
name: dcg-animation-patterns
description: 'DearCyGui (dcg) 2D animation, drawing-coordinate, and camera-control patterns. Use when building maps, sprite-like avatars, walk cycles, panning/zooming canvases, level-of-detail overlays, arrow-key controllers, or anything that mixes pixel space with a world coordinate system using DrawInWindow, DrawInPlot, DrawingScale, DrawingClip, DrawStream, or KeyDownHandler. For perspective/homography/fullscreen tilted maps, also load dcg-perspective-map-patterns.'
---

# DearCyGui Animation & Drawing Patterns

Reusable patterns extracted from the `Animation/` examples. Each pattern names
the DCG primitives, when to reach for it, and the canonical example file.

For non-affine perspective maps (vanishing points, runtime inclination sliders,
source-trapezoid clipping, fullscreen map fill), load the companion skill
`dcg-perspective-map-patterns`. This skill stays as the higher-level chooser.

## Coordinate model (mental model first)

DCG drawing uses a tree of affine frames:

```
Window
  DrawInWindow   <- pixel space, origin top-left, +y DOWN
    DrawingScale <- screen = origin + scales * local
      DrawingScale ...  (nest for world -> region -> token)
        Draw* primitives
  -- or --
  Plot
    DrawInPlot   <- world space, built-in pan/zoom
      DrawingClip <- LOD gate keyed off current zoom
        Draw* primitives
```

Two non-negotiable rules:
1. `DrawingScale.origin` is in the **parent**'s units, `scales` converts **child** units to parent units.
2. dcg's +y points **down**. Use `scales=(sx, -sy)` plus an `origin` placed at the bottom of the cell to get math y-up. See [05_drawing_scale_basics.py](../../../Animation/05_drawing_scale_basics.py).

## Pattern catalog

| # | Pattern | Use when | Reference |
|---|---------|----------|-----------|
| 1 | `DrawInWindow` + nested `DrawingScale` | You own the camera math; want world / region / token frames inside fixed pixel canvas | [01_draw_in_window_world.py](../../../Animation/01_draw_in_window_world.py) |
| 2 | `DrawInPlot` + `DrawingClip` | Built-in pan/zoom and zoom-gated level of detail | [02_draw_in_plot_zoom_levels.py](../../../Animation/02_draw_in_plot_zoom_levels.py) |
| 3 | `dcg.utils.DrawStream` | Frame-cycled vector animation (walk/attack cycles, sprite swaps) | [03_draw_stream_animation.py](../../../Animation/03_draw_stream_animation.py) |
| 4 | `DrawStream` pose + arrow-key transform | Animated pose whose **position** is driven by input | [04_draw_stream_arrow_keys.py](../../../Animation/04_draw_stream_arrow_keys.py) |
| 5 | `DrawingScale` parameter cheat-sheet | Need to reason about `origin`, `scales`, y-flip, units | [05_drawing_scale_basics.py](../../../Animation/05_drawing_scale_basics.py) |
| 6 | Pan camera via `DrawingScale.origin = (-cx,-cy)` with edge-band dead zone | World larger than viewport; want smooth follow-cam with hard world-edge clamp | [06_pan_camera_edge_band.py](../../../Animation/06_pan_camera_edge_band.py) |
| 7 | Perspective tilt with homography | Need parallel world lines to visually converge and tilt to change at runtime | [07_pan_camera_perspective_tilt.py](../../../Animation/07_pan_camera_perspective_tilt.py), [08_Camera_tilt_simple.py](../../../Animation/08_Camera_tilt_simple.py) |
| 8 | Fullscreen perspective map fill | Need a tilted map to fill the entire viewport with no dark wedges | [09_pan_camera_perspective_fullscreen.py](../../../Animation/09_pan_camera_perspective_fullscreen.py) |

## Idioms used across the examples

### App skeleton

Every example uses the same shape — replicate it verbatim:

```python
def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="...", width=W, height=H)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()
```

`build_ui(context)` is where all widgets and draw items are constructed. The
render loop is dumb — state changes flow through handler callbacks.

### Pose vs position separation

A `DrawStream` of `DrawingList` frames defines the **pose** in local
coordinates centered on `(0, 0)`. Wrap it in a `DrawingScale` whose `origin`
is the world position. Move the avatar by mutating `scale.origin`, never by
rebuilding the stream. See `build_walker_pose_stream` + `mover` in
[04_draw_stream_arrow_keys.py](../../../Animation/04_draw_stream_arrow_keys.py).

### Controller class owning DCG node refs

State that responds to input lives in a small class that holds references to
the DCG nodes it mutates plus a status `dcg.Text`. Methods are bound as key
callbacks:

```python
class Controller:
    def __init__(self, mover, status):
        self.mover, self.status = mover, status
        self.x = START_X
        self._apply()
    def move_left(self, *_):  self.x -= STEP; self._apply()
    def move_right(self, *_): self.x += STEP; self._apply()
    def _apply(self):
        self.mover.origin = (self.x, Y)
        self.status.value = f"x={self.x:.0f}"

window.handlers += [
    dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW,  callback=ctrl.move_left),
    dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=ctrl.move_right),
]
```

Callbacks accept `*args` because DCG passes handler metadata.

### Camera = `DrawingScale` with negated origin

`origin = (-cam_x, -cam_y)` makes the world point `(cam_x, cam_y)` land at the
viewport's top-left. Parent the world under this node; parent any HUD /
viewport-fixed overlay (edge bands, borders, status text) directly under the
**canvas** so it does not pan with the world.

### Edge-band / dead-zone follow camera

Inside the central dead zone the camera does not move; entering the band
pushes the camera just enough to put the avatar back at the band boundary.
Clamp camera to `[0, world - viewport]` on each axis so the world edge never
reveals empty space. Reference implementation: `PanCameraController._move`
in [06_pan_camera_edge_band.py](../../../Animation/06_pan_camera_edge_band.py).

### Non-affine perspective maps

`DrawingScale` cannot make parallel lines converge because it is affine. For
perspective maps, store world contents as plain data, project them into a
pixel-space `DrawingList`, and rebuild that layer when input changes. Use
[07_pan_camera_perspective_tilt.py](../../../Animation/07_pan_camera_perspective_tilt.py)
for the simpler rect-to-trapezoid version, and prefer
[09_pan_camera_perspective_fullscreen.py](../../../Animation/09_pan_camera_perspective_fullscreen.py)
when the map should fill the whole viewport. Load `dcg-perspective-map-patterns`
for the homography, clipping, zoom, and `DrawPolygon` triangulation details.

### Zoom-gated detail with `DrawingClip`

In `DrawInPlot`, wrap detail layers in `DrawingClip(pmin, pmax, scale_min=...,
clip_rendering=True)`. The layer is hidden until the user zooms in far enough
that one world unit covers `scale_min` pixels. Stack multiple clips with
increasing `scale_min` for coarse → fine LOD.

### `DrawStream` push contract

```python
stream = dcg.utils.DrawStream(context, parent=...)
stream.time_modulus = 1.6        # loop length in seconds
for frame in range(N):
    with dcg.DrawingList(context) as drawing:
        ...  # build this frame
    stream.push(drawing, (frame + 1) * stream.time_modulus / N)
```

The timestamp is the **end** time of the frame within the modulus window.

## When building a new animation example

Pick the smallest combination that satisfies the goal:

1. **Static diagram, fixed canvas** → Pattern 1.
2. **User-pannable / zoomable map** → Pattern 2. Reach for `DrawingClip` only when LOD matters.
3. **Looping vector animation, no input** → Pattern 3.
4. **Input-driven sprite on a fixed canvas** → Pattern 4 (DrawStream + DrawingScale + KeyDownHandler).
5. **World larger than viewport, input-driven** → Pattern 6.
6. **World larger than viewport, perspective tilt** → Pattern 7; load `dcg-perspective-map-patterns` before implementing.
7. **Perspective tilt that fills the whole draw window** → Pattern 8; prefer [09_pan_camera_perspective_fullscreen.py](../../../Animation/09_pan_camera_perspective_fullscreen.py) as the canonical reference.
8. Whenever any affine transform behavior feels confusing, re-read Pattern 5 — many bugs in this folder are a `DrawingScale` parent/units mistake.

## Anti-patterns observed

- Rebuilding a `DrawStream` on every key press instead of moving the parent `DrawingScale.origin`.
- Parenting HUD/overlay items under the camera `DrawingScale` (they pan with the world — almost never what you want).
- Using raw pixel coordinates for world content inside `DrawInPlot` — break the world units and zoom stops working sensibly.
- Forgetting to clamp camera offset, so panning reveals empty space past the world border.
- Assuming +y is up. It is not. Use `scales=(sx, -sy)` + bottom-aligned origin for y-up.
- Trying to implement vanishing-point perspective with only `DrawingScale`; use the `dcg-perspective-map-patterns` homography approach.
- Clamping perspective polygon vertices independently to the viewport; proper clipping is required to avoid degenerate `DrawPolygon` triangulation failures.

## Out of scope

This skill covers 2D CPU-side DCG drawing.
