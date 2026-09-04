# Change: Add DrawInWindow 3D Framework

## Why
Demos 11 through 14 each copy and extend a full scene renderer to add one visual capability (textures, collision, overlap sorting, billboards). Adding any new object type requires copying hundreds of lines and expanding argument lists. A reusable framework eliminates this duplication and lets each demo become a thin configuration of shared components.

## What Changes
- Extract camera transforms, clipping, projection, and polygon cleanup into a testable pure-math layer
- Introduce `Scene3D` as a retained world model with composable `Renderable3D` objects
- Implement `CpuRenderer3D` that projects, orders, and emits DearCyGui draw commands from scene packets
- Create `DrawInWindow3D` widget integrating the renderer with atomic front/back layer publication
- Provide selectable ordering strategies: `AverageDepthSorter` (simple) and `OverlapDepthSorter` (topological, default for small scenes)
- Support solid faces, textured faces, labels, lines, billboards, ground planes, indexed triangle meshes, and tetrahedral mesh exterior surfaces
- Add optional collision and camera-follow controllers composed outside the renderer
- Support thread-safe async updates for CAE/solver workflows
- Provide three `DrawStream` animation ownership policies: persistent overlay, preprojected non-occludable, and preprojected occludable
- Preserve the original numbered `Animation/` demos as historical references and place framework-backed demo ports under `Animation/ported_demos/`
- Track deferred line-vs-face partial occlusion so line primitives do not bleed through nearer solid faces at some camera angles

## Impact
- Affected specs: draw-in-window-3d (new capability)
- Affected code: new `draw_in_window_3d/` package; framework-backed demo ports under `Animation/ported_demos/`
- No breaking changes to existing standalone numbered demo files; legacy `Animation/11_*` through `Animation/14_*` remain preserved as references
