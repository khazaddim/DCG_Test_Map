## Context

The demos in `Animation/11_*` through `Animation/14_*` implement a CPU-side 3D rendering pipeline on DearCyGui's retained 2D drawing primitives. Each demo copies and extends the previous renderer. The framework extracts their shared logic into composable layers with stable public boundaries.

DearCyGui provides `DrawInWindow`, `DrawingList`, `DrawPolygon`, `DrawLine`, `DrawImage`, `DrawStream`, `DrawingScale`, and `DrawingClip`. All mutation of these objects must occur on the DCG thread. The framework adds 3D projection, scene management, and ordering above these primitives without replacing them.

### Stakeholders
- Application developers building 3D DearCyGui visualizations
- CAE/engineering users viewing tetrahedral solver results
- Demo authors who want to add object types without copying renderers
- Tabletop game creators that need to have a 2D world with 3D releif and sprite effects that can be rotated, zoomed, panned so players can see what is happening with avatars moving on the playing field

### Constraints
- CPU-only; no GPU shaders or depth buffer
- Convex planar faces for overlap sorting
- All DCG object mutation on the DCG thread
- DearCyGui screen-down Y convention preserved throughout

## Goals / Non-Goals

### Goals
1. One extensible render pipeline replacing per-demo copies
2. Testable pure-math layer with no DCG dependency
3. Selectable ordering strategies (average-depth, overlap-aware topological)
4. Support solid/textured/animated/mesh object types through a common packet interface
5. Atomic frame publication; no partial scenes displayed
6. Thread-safe async update path for solver/importer workflows
7. Optional collision and camera controllers composed outside the renderer
8. Engineering mesh support without one scene object per triangle

### Non-Goals
- Per-pixel depth buffer or triangle rasterizer
- GPU or shared-OpenGL rendering
- Arbitrary intersecting or concave geometry in the overlap sorter
- Perspective-correct texture interpolation without tessellation
- Physics engine, ECS, or asset pipeline
- True volumetric rendering or order-independent transparency
- Automatic continuous redraw (remains event-driven)
- Section planes, cutaways, or exploded-cell views of tetrahedral meshes

## Decisions

### Widget integration: subclass vs. wrapper
- Decision: Attempt `dcg.DrawInWindow` subclass first; fall back to wrapper if extension types cannot be safely subclassed.
- Rationale: Subclass gives natural DCG parenting. Phase 0 spike validates this.

### Immutable camera model
- Decision: `Camera3D` is a frozen dataclass. Mutations produce replacements via `set_camera()`.
- Rationale: Eliminates race conditions; camera changes atomically invalidate dependent state.

### Packet-based rendering
- Decision: Scene objects emit `WorldRenderPacket` values. The renderer projects, sorts, and draws them without type-switching on the object.
- Rationale: Adding a new visual type means implementing `collect()` and a material, not modifying the render loop.

### New primitive acceptance rule
- Decision: Every new primitive or render-packet shape added to the framework must be evaluated for partial occlusion behavior against existing primitive families before it is considered complete.
- Rationale: We have already encountered visibility artifacts from treating whole primitives as orderable units when only part of the primitive should be hidden. New primitive types such as circles, ellipses, arcs, thick polylines, billboards, or sprites may introduce the same issue with different overlap pairs unless occlusion behavior is reviewed up front.

### Default ordering strategy
- Decision: `OverlapDepthSorter` (demo 13 topological sort) is default for small scenes. `AverageDepthSorter` is the explicit fallback and performance option.
- Rationale: Average-depth painter ordering fails for overlapping coplanar geometry. Small-scene demos should show correct results by default.

### Mesh rendering strategy
- Decision: `TriangleMesh3D` and `TetrahedralMesh3D` are retained scene objects that emit triangle packets efficiently. They do NOT enter the pairwise overlap sorter without spatial acceleration or a documented face-count limit.
- Rationale: O(n²) pairwise overlap is unsuitable for thousands of triangles.

### Traversal-role policy
- Decision: Terrain-adjacent objects and collision participants SHALL expose a simple traversal-role policy so scene elements can be treated as traversable support surfaces, blocking boundaries, or legacy flat-ground colliders.
- Rationale: Uneven terrain movement needs a clear distinction between surfaces the actor may stand on and objects that should stop movement, while preserving the current flat-world collision behavior for existing demos.
- Alternatives considered:
  - Inferring traversal from renderable type alone: rejected because the same mesh or polygon family may represent either walkable terrain or a blocking wall.
  - Replacing the existing collision system wholesale: rejected because flat-ground AABB collision remains useful and should continue to work unchanged for simple scenes.

### Performance profiling fixtures
- Decision: The renderer exposes named timing regions that profiling fixtures can measure independently. The initial pipeline stages are:
  1. **Projection/clipping** — camera transform, near-plane clip, viewport clip, polygon cleanup
  2. **Broad-phase candidate generation** — spatial acceleration structures (once added) that reduce pairwise overlap tests
  3. **Exact overlap and depth tests** — convex polygon intersection and ray-plane depth sampling
  4. **Topological ordering** — constraint graph construction and topological sort (including cycle detection)
  5. **DCG draw-node creation/publication** — DearCyGui object instantiation, property assignment, and front/back layer swap
- Rationale: Profiling fixtures let us measure each stage with representative scene sizes, identify the actual bottleneck, and justify targeted acceleration (Cython, NumPy vectorization, spatial indexing) with evidence rather than speculation. The framework ships pure-Python first; optimization follows measurement.
- Contract: Each stage boundary is a function or method call that a test harness can time independently. Profiling tests use synthetic scenes at documented face counts (e.g., 100, 500, 2000, 10000 faces) and report per-stage wall-clock time. Results guide decisions about which stages to accelerate and by what means.

### Async update contract
- Decision: Workers submit frozen/immutable arrays via `submit_update()`. The DCG thread drains and applies updates before the next render. Coalescing by key prevents stale intermediate renders.
- Rationale: Keeps DCG objects single-threaded while supporting concurrent computation.

### DrawStream animation policies
- Decision: Three explicit ownership modes — persistent overlay, preprojected non-occludable (background), and preprojected occludable (sorted with faces).
- Rationale: Each has different invalidation, clearing, and ordering semantics demonstrated in demos 11.1 and 14.

## Risks / Trade-offs

- **Subclass feasibility** — DCG extension types may not support Python subclassing cleanly. Mitigation: Phase 0 spike before any other work.
- **Overlap sorter scalability** — Pairwise comparison is O(n²). Mitigation: Document face-count guidance; mesh objects use separate ordering or spatial acceleration.
- **Translucent ordering artifacts** — Alpha-blended faces produce incorrect results when constraints cycle. Mitigation: Explicit approximate-preview designation; no correctness guarantee.
- **API surface creep** — Large design risks premature abstraction. Mitigation: Phase-gated extraction; each phase has a working demo before proceeding.
- **Texture clipping fallback** — UV-aware clipping deferred; clipped textured quads show solid fill. Mitigation: Acceptable visual degradation documented in the material contract.
- **Traversal policy sprawl** — Mixing terrain following with collision roles could create too many special cases. Mitigation: keep the first policy limited to a few explicit roles such as traversable, boundary, and legacy collider semantics.

## Known Limitation: Line vs Face Partial Occlusion

The demo 11 family exposes a separate ordering limitation for `Line3D` and
`Polyline3D`: a single projected line segment can be partly in front of a wall
and partly behind it. Ordering the entire segment by one average depth cannot
represent that mixed visibility state, so grid lines can appear to bleed through
building sides at some camera angles.

This is related to, but distinct from, the face-vs-face painter-order failure
addressed by demo 13's overlap-aware sorting. `OverlapDepthSorter` resolves
cases where two polygon faces overlap on screen and one whole face should be
ordered behind the other within the overlap region. It does not automatically
solve line-vs-face partial occlusion because a line segment may need to be
split into multiple visible fragments rather than reordered as one primitive.

Collision milestones do not address this issue. The root cause is rendering and
occlusion granularity, not world-space movement validation. Future work should
handle this by clipping or splitting projected line segments against nearer
polygon occluders, or by representing important linework as thin polygons when
they need to participate in polygon occlusion rules.

This should be treated as the baseline lesson for future primitives: if a
primitive can span both visible and hidden regions at once, then ordering the
whole primitive by one scalar depth is suspicious and must be investigated.

## Migration Plan

1. Framework developed in `Animation/draw_in_window_3d_framework/` as a new package.
2. Demos 11–14 remain unchanged until Phase 6.
3. Framework-backed demo ports live in `Animation/ported_demos/` and import from the framework while preserving visual behavior.
4. Original numbered demo files in `Animation/11_*` through `Animation/14_*` remain intact as historical references and behavior baselines.
5. Validation compares each ported demo in `Animation/ported_demos/` against its original counterpart before any decision to retire or redirect the legacy file.

## Open Questions

1. Subclass vs. wrapper — resolved by Phase 0 spike.
2. Mutable vs. immutable object transforms — Phase 2 decides based on usage patterns.
3. Local-space-only vs. mixed world-point geometry — Phase 2 initial API uses both forms as sketched.
4. Picking API scope — deferred past Phase 4; handle + source_id propagation is the minimum.
5. Mesh ordering strategy for large face counts — Phase 5 measures and decides.
6. Parent-child transform hierarchies — deferred; flat scene initially.
7. Offscreen/image-export API — not in scope for initial implementation.
8. Whether line-vs-face occlusion should split lines in screen space, clip in world space against occluder footprints, or convert selected linework into thin polygon packets.
