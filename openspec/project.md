# Project Context

## Purpose
A collection of DearCyGui (DCG) examples and demos, including an evolving CPU-side 3D rendering framework built on top of DearCyGui's immediate-mode drawing primitives. The framework extracts reusable camera, projection, scene, and ordering logic from a progression of animation demos (11–14) into a composable library.

## Tech Stack
- Python 3.11+
- DearCyGui (dcg) — immediate-mode GUI framework with retained drawing primitives
- NumPy — array math for mesh and field data
- pytest — unit and integration testing

## Project Conventions

### Code Style
- Python with type annotations on public API boundaries
- Frozen dataclasses for immutable value types (Camera3D, Viewport, render entries)
- Protocols for extensible interfaces (Renderable3D, RenderSorter, Material3D)
- snake_case for functions and variables, PascalCase for classes
- Keep modules focused: one concern per file

### Architecture Patterns
- Composition over inheritance: scene objects produce render packets; the renderer is not subclassed per object type
- Immutable camera and viewport: mutations produce replacements
- Event-driven invalidation: mutations mark dirty, render rebuilds only when needed
- Atomic front/back layer publication: never display a partially built scene
- Pure math layers have no DearCyGui dependency and are independently testable

### Testing Strategy
- Pure-Python unit tests for camera transforms, clipping, projection, ordering, and collision
- Integration tests for DCG widget construction, layer publication, and resize behavior
- Visual comparison at representative camera configurations from demos 11–14
- No GPU or display required for math-layer tests

### Git Workflow
- Feature branches per phase or milestone
- Commit messages describe behavioral change

## Domain Context
- DearCyGui uses screen-down Y axis; camera math preserves this convention
- Drawing primitives: DrawPolygon, DrawLine, DrawImage, DrawStream, DrawingList, DrawingScale, DrawingClip, DrawInWindow
- DrawStream provides frame-based animation owned by DCG's render loop
- Near-plane clipping must occur before perspective division
- Overlap-aware topological sorting handles non-intersecting convex planar faces
- Tetrahedral meshes derive exterior surfaces for rendering; internal faces are never submitted to the renderer

## Important Constraints
- No GPU shaders or shared-OpenGL rendering in this framework (CPU-only pipeline)
- No per-pixel depth buffer; ordering is polygon-level
- Convex planar faces assumed by the overlap sorter
- Textured quads that clip against the near plane fall back to solid shading
- Translucent mesh rendering is explicitly approximate (no order-independent transparency)
- All DearCyGui mutation must occur on the DCG thread; async producers submit immutable data only

## External Dependencies
- DearCyGui: the host GUI framework providing Context, Viewport, DrawInWindow, drawing primitives, and input handlers
- NumPy: indexed array storage for mesh vertices, cells, and scalar fields
