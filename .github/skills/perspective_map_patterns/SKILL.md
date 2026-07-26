---
name: dcg-perspective-map-patterns
description: 'DearCyGui (dcg) projective 2D game-map rendering patterns. Use when building perspective-tilted or rotating maps, camera yaw, centered inclination, runtime rotation/inclination/zoom sliders, homography transforms, inverse projection, full-screen fill without dark wedges, source-trapezoid clipping, polygon safety, edge-band cameras, scene-graph double buffering, or diagnosing black flicker during draw-list rebuilds. Builds on dcg-animation-patterns Pattern 6.'
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
| [07_pan_camera_perspective_tilt.py](../../../examples/07_pan_camera_perspective_tilt.py) | First perspective map with tilt + zoom | Maps viewport rect to an output trapezoid. Good for learning the pipeline, but it naturally leaves dark corner wedges outside the trapezoid. |
| [08_Camera_tilt_simple.py](../../../examples/08_Camera_tilt_simple.py) | Simpler tilt branch | Same core rect-to-trapezoid homography idea without the later fullscreen-fill refinement. |
| [09_pan_camera_perspective_fullscreen.py](../../../examples/09_pan_camera_perspective_fullscreen.py) | Fullscreen perspective map | Clips to the source trapezoid and extends ground so the entire viewport fills with map content. |
| [10_pan_camera_perspective_rotation.py](../../../examples/10_pan_camera_perspective_rotation.py) | Canonical game-map version | Adds centered world rotation, locally normalized inclination, inverse-projected edge tracking, and atomic front/back drawing buffers. Prefer this when pieces move on a rotating map. |

## Beginner Foundations

A coordinate is only meaningful together with its coordinate space. These
examples use three spaces:

1. **World space** stores durable game state. A piece at `(1100, 750)` stays at
  that world position regardless of camera settings.
2. **Source space** is the input plane for the perspective formula. It resembles
  viewport pixels, but may extend outside the viewport rectangle.
3. **Screen space** contains the final pixels inside `DrawInWindow`.

A transform converts coordinates from one space to the next. A transform does
not move the actual game object; it computes where that object should be drawn.
Keep simulation and collision logic in world space. Project only for rendering
and screen-space interaction.

Transform order matters because transforms generally do not commute. Rotating
an already depth-compressed map rotates its compressed axis and causes shearing.
For a stable game map, rotate in world space before camera/depth/perspective
work. Terrain and every moving piece must use the same complete pipeline.

## Core Mental Model

DCG draw trees support affine transforms (`DrawingScale`), not projective
homographies. For perspective maps, store the world as plain Python data and
rebuild projected draw items when state changes.

Basic fullscreen pipeline (`09`):

```text
world_xy -- camera pan / zoom --> source_xy -- homography --> viewport_xy
```

Centered rotating game-map pipeline (`10`):

```text
world_xy
  -- rotate around camera focus
  -- camera pan / zoom
  -- center and scale normalization
  --> source_xy
  -- source clipping
  -- homography
  --> screen_xy
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

The inverse homography is also useful. Edge-band tracking in a perspective view
should inspect a piece after projection in actual screen pixels, move the desired
screen position to the band boundary, then unproject that target back into
source space. Do not compare source coordinates directly with screen-space HUD
boundaries once perspective is active.

## Shared Central Anchor (`10`)

The center of the source rectangle is not the source point that the homography
maps to screen center. For the homography above, the true source preimage of
screen center is:

```python
center_source_x = VIEW_W * 0.5
center_source_y = VIEW_H / (2.0 * (1.0 - a))
```

Use one camera focus for both world rotation and inclination. Normalize source
offsets by the homography's local center scale:

```python
horizontal_center_scale = 1.0 - a
vertical_center_scale = (1.0 - a) ** 2 / (1.0 - 2.0 * a)

source_x = center_source_x + (base_x - VIEW_W * 0.5) / horizontal_center_scale
source_y = center_source_y + (base_y - VIEW_H * 0.5) / vertical_center_scale
```

This construction gives two important invariants:

- Changing inclination or rotation does not move the camera focus away from
  screen center.
- At the focus, horizontal and vertical scale both equal the selected zoom.

Perspective still compresses geometry toward the horizon. That changing scale
with distance is intentional. Rotation-dependent scale or focus drift is not.

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

`render_perspective(...)` clips/projects the model and creates the current
frame's `Draw*` items. This is intentionally a rebuild-on-input-change model,
not a per-frame animation loop.

Use a plain `dcg.DrawingList` under `DrawInWindow` as the projected layer:

```python
with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
  layer_container = dcg.DrawingList(context, parent=canvas)
```

Do not clear and rebuild the currently visible list. Use the double-buffering
pattern below.

## Camera + Zoom With Edge Band

For affine examples, keep the edge-band controller from
`dcg-animation-patterns` and run the band test after zoom. For a perspective
map, first project the piece into actual screen pixels:

```python
source_x, source_y = world_to_source(...)
screen_x, screen_y = project_xy(source_x, source_y, a)
```

Move that screen point to the desired band boundary, call `unproject_xy` on the
target, then invert center scaling, rotation, and zoom to obtain the camera
correction. Demo `10` contains the complete implementation.

## Atomic Drawing-List Double Buffering

DearCyGui can render on a separate thread. Clearing a visible `DrawingList` and
then adding replacement children one by one exposes intermediate scene states.
The rendering thread may observe an empty list, producing a random black frame,
or a partially rebuilt list. More expensive transforms make the timing window
larger, so flicker may appear only after rotation is added and may arrive in
bursts. This is a synchronization issue, not floating-point precision.

Keep two child drawing lists under one stable parent:

```python
displayed_layer = dcg.DrawingList(context, parent=layer_container)
back_layer = dcg.DrawingList(context, parent=layer_container, show=False)
```

Rebuild only the hidden back layer. When complete, exchange visibility while
holding their common parent's mutex, then exchange Python references:

```python
render_perspective(context, back_layer, ...)

with layer_container.mutex:
  displayed_layer.show = False
  back_layer.show = True
  displayed_layer, back_layer = back_layer, displayed_layer
```

The old complete frame remains visible while the new frame is built. The mutex
makes the two visibility writes one atomic scene-graph transition from the
renderer point of view. This is scene-graph double buffering; it is analogous
to front/back image buffers but stores draw items rather than pixels.

Holding the visible layer mutex for the entire rebuild also prevents partial
frames, but it stalls rendering while all geometry is constructed. Hidden back
buffer construction plus a short swap lock gives smoother interaction.

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
- Clearing and rebuilding a live visible `DrawingList`. Build a hidden back
  layer and atomically swap complete buffers to prevent black flicker.
- Applying rotation after depth compression. Rotate world coordinates around
  the camera focus before inclination/perspective transforms.
- Anchoring inclination at a near edge while rotation uses viewport center. Use
  one central camera focus and normalize the homography scale there.
- Testing perspective edge bands in source coordinates. Test the projected
  screen position and unproject the desired correction.
- Clipping after projection unless you have a specific reason. Clip source-space
  geometry first.
- Per-vertex clamping polygon points to the viewport rectangle. Use proper
  polygon clipping to avoid degenerate shapes.
- Drawing circles directly when you need them transformed by a homography.
  Approximate with `DrawPolygon`.
- Letting the homography parameter reach `0.5`. The denominator can collapse at
  the bottom edge. Keep `MAX_A` below 0.5.

## Cheap Validation Invariants

Before relying only on visual inspection, numerically verify:

- `unproject_xy(*project_xy(point, a), a)` returns the original source point.
- The camera focus projects to `(VIEW_W / 2, VIEW_H / 2)` for several
  inclinations and rotations.
- Small world-X and world-Y offsets at the focus have equal screen scale and
  match the selected zoom.
- After each repaint exactly one drawing buffer is visible and it contains a
  complete set of children.
- A rapid multi-frame inclination/rotation stress run produces no exceptions or
  incomplete visible buffers.
