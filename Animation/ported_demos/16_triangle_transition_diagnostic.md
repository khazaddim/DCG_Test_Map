# DearCyGui Edge-On Outline Diagnostic

## Purpose

[`16_triangle_transition_diagnostic.py`](16_triangle_transition_diagnostic.py)
is a minimal visual reproduction of an outline artifact discovered in Demo 15.
It explains why the framework renders polygon fills and outlines as separate
DearCyGui primitives.

The artifact appeared as long, shaded spikes extending from roof faces while
the camera rotated. It occurred only as a face rotated into or out of view and
disappeared once the face was clearly front-facing or back-facing. This timing
initially made the problem look like incorrect 3D projection, clipping,
back-face culling, depth sorting, or stale frame publication.

The diagnostic isolates those possibilities from DearCyGui's 2D primitive
emission.

## Reproduction Environment

The issue was reproduced with:

- DearCyGui 0.1.7
- Python 3.14.0
- Windows 11 build 26200

Run the diagnostic from the repository root:

```powershell
& .\.venv\Scripts\python.exe .\Animation\ported_demos\16_triangle_transition_diagnostic.py
```

Move the yaw or pitch slider until the triangle becomes nearly edge-on. The
default camera starts close to such a transition.

## Expected Edge-On Projection

As a 3D face rotates edge-on, its projected 2D area approaches zero. Its
vertices become nearly collinear, and its signed area changes sign when its
winding reverses:

```text
Normal face        Nearly edge-on       Fully edge-on
    /\                  ______               ------
   /  \
  /____\
```

This is expected projection behavior. A nearly collinear triangle is still a
valid 2D triangle unless the drawing API documents a larger minimum-area
requirement.

At the default diagnostic camera, the real Demo 15 roof face projects to
approximately:

```text
(361.88, 126.11)  (426.91, 157.75)  (392.62, 141.08)
```

Its signed area is approximately `0.4010`. Every coordinate is finite and
inside the `980 x 620` projection viewport. The points move smoothly as the
camera rotates; none travels toward the distant tips of the visible spikes.

## Four Identical-Input Cases

The diagnostic recenters the same three projected points in four panels. It
changes only how those points are submitted to DearCyGui:

| Panel | DearCyGui primitives | Result near edge-on |
|---|---|---|
| Fill only | `DrawTriangle(fill=..., color=0)` | Correct thin fill |
| Integrated triangle outline | `DrawTriangle(fill=..., color=...)` | Produces spikes |
| Integrated polygon outline | `DrawPolygon(fill=..., color=...)` | Produces spikes |
| Separate fill and edges | Fill-only `DrawTriangle` plus three `DrawLine` items | Correct thin fill and edges |

The comparison bypasses the framework's scene traversal, clipping, sorter,
line-occlusion pass, and front/back frame publisher. All four panels receive
equivalent screen-space geometry during the same repaint.

## Likely Failure Mechanism

The exact DearCyGui native implementation was not inspected, so the following
mechanism is an inference rather than a confirmed internal call sequence.

A continuous polygon outline commonly offsets adjacent edges by the requested
stroke width and intersects those offset lines to form a corner join. When the
source edges become nearly parallel, their intersection can be very far from
the original corner:

```text
Nearly parallel offset edges
        \  /
         \/
         |
         |
         |  calculated join extends far beyond the face
```

That distant, internally generated join can create the lightning-shaped
geometry visible in the integrated-outline panels. Because it is emitted with
the outlined filled primitive, the artifact resembles a shaded 3D face rather
than a simple line error.

The first panel does not fail because fill tessellation remains bounded by the
three supplied vertices. The last panel does not fail because each independent
`DrawLine` needs only two finite endpoints; no shared polygon corner join is
constructed.

## Why This Appears To Be A DearCyGui Bug

The evidence points to the integrated outline path exposed by DearCyGui:

1. The three supplied coordinates are finite, viewport-bounded, and smoothly
   varying.
2. Identical coordinates render correctly with a fill-only `DrawTriangle`.
3. Identical coordinates produce spikes when an outline is enabled on either
   `DrawTriangle` or `DrawPolygon`.
4. Identical coordinates render correctly when the outline is represented by
   independent DearCyGui `DrawLine` items.
5. The failure reproduces without the framework's 3D sorting, clipping, or
   frame-publication code.

This makes malformed framework input an unlikely explanation and identifies
DearCyGui's public integrated-outline behavior as the failing boundary. The
defect may be implemented directly in DearCyGui or in a lower-level drawing or
stroke-tessellation backend used by DearCyGui. Without inspecting that native
code, it would be too strong to assign the fault to one internal layer.

## Framework Workaround

The CPU renderer avoids integrated outlines:

1. Emit fills with the most specific native DearCyGui primitive:
   `DrawTriangle` for three points, `DrawQuad` for four points, and
   `DrawPolygon` for clipped or general polygons.
2. Set the fill primitive's outline color to `0`.
3. When an outline is requested, emit each boundary edge as an independent
   native `DrawLine`.

This is still entirely DearCyGui-based rendering. The framework composes native
primitives rather than implementing a custom rasterizer. The cost is additional
retained draw nodes for outlined faces, which is acceptable for the intended
small CPU-rendered scenes.

## Regression Coverage

`tests/test_draw_in_window_3d_milestone5.py` verifies that a nearly collinear
outlined mesh triangle emits this node structure:

```text
DrawTriangle
DrawLine
DrawLine
DrawLine
```

The visual diagnostic remains useful because a structural unit test can prove
that the workaround is selected, but it cannot directly prove that a native
rasterization artifact is absent.

## Useful Upstream Bug Report Details

An upstream report can use this diagnostic as a standalone reproduction and
should include:

- DearCyGui, Python, operating-system, and graphics-backend versions.
- The three exact 2D coordinates displayed by the diagnostic.
- The outline color and `thickness=-1.0` setting.
- A screenshot showing all four panels at the same camera values.
- Expected behavior: a thin outlined triangle bounded by its supplied points.
- Actual behavior: distant filled or stroked spike geometry only when an
  integrated outline is enabled.