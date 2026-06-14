---
name: dcg-perspective-map-patterns
description: 'DearCyGui (dcg) projective 2D map rendering patterns. Use when building perspective-tilted maps, pseudo-3D top-down/world canvases, vanishing-point grid views, runtime inclination/zoom sliders, homography transforms, full-screen perspective fill without dark wedges, source-trapezoid clipping, polygon/line clipping, DrawPolygon triangulation safety, or edge-band cameras combined with non-affine projection. Builds on dcg-animation-patterns Pattern 6.'
---

# DearCyGui Perspective Map Patterns

Use this skill when `DrawingScale` is not enough because the view needs a true
projective transform: parallel world lines should visually converge, tilt should
change at runtime, or the full viewport should be filled by a perspective map.

This skill is a focused companion to `dcg-animation-patterns`. Load that skill
first when you need the broader animation/camera catalog; use this one for the
homography and clipping machinery in the perspective examples.

## Reference Examples

| File | Role | Notes |
|---|---|---|
| [07_pan_camera_perspective_tilt.py](../../../Animation/07_pan_camera_perspective_tilt.py) | First perspective map with tilt + zoom | Maps viewport rect to an output trapezoid. Good for learning the pipeline, but it naturally leaves dark corner wedges outside the trapezoid. |
| [08_Camera_tilt_simple.py](../../../Animation/08_Camera_tilt_simple.py) | Simpler tilt branch | Same core rect-to-trapezoid homography idea without the later fullscreen-fill refinement. |
| [09_pan_camera_perspective_fullscreen.py](../../../Animation/09_pan_camera_perspective_fullscreen.py) | Canonical fullscreen perspective map | Clips to the source trapezoid (preimage of the viewport) and extends ground so the entire viewport fills with map content. Prefer this for new work. |

## Core Mental Model

DCG draw trees support affine transforms (`DrawingScale`), not projective
homographies. For perspective maps, store the world as plain Python data and
rebuild projected draw items when state changes.

Pipeline:

```text
world_xy -- camera pan / zoom --> source_xy -- homography --> viewport_xy
```

Then create `dcg.DrawLine`, `dcg.DrawPolygon`, and `dcg.DrawText` in a
pixel-space `dcg.DrawingList` under `dcg.DrawInWindow`.

HUD overlays such as edge bands, dead-zone outlines, borders, and status text
stay parented directly to the canvas so they do not tilt or pan.

## Homography Used By The Examples

The perspective parameter is `a in [0, 0.5)`, typically derived from a slider:

```python
a = MAX_A * math.sin(math.radians(angle_deg))
```

Forward projection from source viewport pixels `(x, y)` to output pixels:

```python
u = x / VIEW_W
v = y / VIEW_H
denom = 1.0 - 2.0 * a * v
sx = VIEW_W * ((1.0 - 2.0 * a) * u - a * v + a) / denom
sy = VIEW_H * ((1.0 - 2.0 * a) * v) / denom
```

This preserves straight lines, so grid lines remain straight and converge.
Circles do not remain circles; approximate them with `DrawPolygon` using a
small regular polygon (the examples use `CIRCLE_SEGMENTS = 24`).

## Rect-To-Trapezoid vs Fullscreen Fill

### Rect-To-Trapezoid (`07`, `08`)

Clip world geometry to `[0, VIEW_W] x [0, VIEW_H]` in source space, then project.
The output is a trapezoid. This is simple and useful for explaining the math,
but the viewport corners outside the trapezoid stay blank/dark.

Use when:
- You want a clear visual demonstration of a tilted plane.
- Dark wedges are acceptable or even helpful for teaching.
- Simplicity matters more than filling the entire draw window.

### Fullscreen Fill (`09`, canonical)

Instead of clipping to the source rect, clip to the source trapezoid that maps
to the full output viewport. At tilt `a`, the source trapezoid has:

```text
bottom edge: (0, H) -> (W, H)
top edge:    (-a*W/(1-2a), 0) -> ((1-a)*W/(1-2a), 0)
```

Then forward-project the clipped geometry. The result fills `[0,W] x [0,H]`
with no dark corner wedges.

Use when:
- The perspective map should fill the whole canvas.
- You do not want the user to see the projection's empty corners.
- You are building a game/map surface rather than a math demonstration.

## Clipping Rules

Always clip before projection. Do not clamp vertices independently.

Why: per-vertex clamping can pile multiple polygon vertices onto one corner,
which creates degenerate polygons. DCG's `DrawPolygon` triangulator can raise
`RuntimeError: not triangulation` on those shapes.

Recommended clipping by example:

- Rect-to-trapezoid: use Sutherland-Hodgman polygon clipping against the source
  viewport rect and Liang-Barsky clipping for lines.
- Fullscreen-fill: use half-plane polygon clipping and Cyrus-Beck line clipping
  against the source trapezoid.

After projection, defensively remove near-duplicate consecutive vertices and
skip polygons with fewer than 3 vertices.

## World Model Pattern

Represent world contents as data, not as long-lived DCG draw items:

```python
class WorldModel:
    def __init__(self) -> None:
        self.rects = []
        self.lines = []
        self.circles = []
        self.texts = []
```

`render_perspective(...)` clears the projected drawing layer, clips/projects the
model, and creates the current frame's `Draw*` items. This is intentionally a
rebuild-on-input-change model, not a per-frame animation loop.

Use a plain `dcg.DrawingList` under `DrawInWindow` as the projected layer:

```python
with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
    persp_layer = dcg.DrawingList(context, parent=canvas)
```

## Camera + Zoom With Edge Band

Keep the edge-band controller from `dcg-animation-patterns`, but run the band
test in viewport-pixel space after zoom:

```python
screen_x = (avatar_x - cam_x) * zoom
screen_y = (avatar_y - cam_y) * zoom
```

When panning the camera in response to edge-band pressure, convert back to
world units:

```python
cam_x += delta_pixels / zoom
cam_y += delta_pixels / zoom
```

Camera clamp also depends on zoom:

```python
max_cam_x = max(0.0, WORLD_W - VIEW_W / zoom)
max_cam_y = max(0.0, WORLD_H - VIEW_H / zoom)
```

When the zoom slider changes, recenter the camera around the avatar before
clamping. That keeps the avatar visually anchored and avoids surprising jumps.

## Runtime Sliders

The perspective examples use regular `dcg.Slider` callbacks. The callbacks
mutate controller state and call `repaint()`.

```python
dcg.Slider(context, label="Inclination angle (degrees)",
           min_value=0.0, max_value=80.0,
           value=controller.angle_deg,
           width=VIEW_W,
           callback=controller.set_angle)

dcg.Slider(context, label="Zoom (x world units per viewport pixel)",
           min_value=ZOOM_MIN, max_value=ZOOM_MAX,
           value=controller.zoom,
           width=VIEW_W,
           callback=controller.set_zoom)
```

## Fullscreen Fill Details

For full viewport coverage, extend the ground beyond the actual world bounds:

```python
GROUND_PAD = 50_000.0
m.rects.append((
    (-GROUND_PAD, -GROUND_PAD),
    (WORLD_W + GROUND_PAD, WORLD_H + GROUND_PAD),
    ground_color, 0, -1,
))
```

Keep the actual world border as separate line segments. This makes the map fill
the whole canvas while still showing where the real world bounds are.

## Anti-Patterns

- Using `DrawingScale` alone for vanishing-point perspective. It is affine; it
  cannot make parallel lines converge.
- Rebuilding every render frame when the geometry only changes on input. Repaint
  on slider/key changes instead.
- Clipping after projection unless you have a specific reason. Clip source-space
  geometry first.
- Per-vertex clamping polygon points to the viewport rectangle. Use proper
  polygon clipping to avoid degenerate shapes.
- Drawing circles directly when you need them transformed by a homography.
  Approximate with `DrawPolygon`.
- Letting the homography parameter reach `0.5`. The denominator can collapse at
  the bottom edge. Keep `MAX_A` below 0.5.
