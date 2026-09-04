## ADDED Requirements

### Requirement: Camera and Projection Math
The system SHALL provide a pure-Python camera and projection layer with no DearCyGui dependency that transforms 3D world coordinates into 2D screen coordinates using a yaw-then-pitch rotation, screen-down Y convention, and configurable focal length.

#### Scenario: Camera eye position computation
- **WHEN** a Camera3D is configured with target, yaw, pitch, and zoom
- **THEN** `eye()` returns the world-space camera position derived from yaw-then-pitch rotation at the configured distance

#### Scenario: World-to-screen projection
- **WHEN** a world point is transformed through `world_to_camera()` then `camera_to_screen()`
- **THEN** the result matches the screen position computed by demo 11's equivalent projection

#### Scenario: Ground ray intersection
- **WHEN** `ground_from_screen()` is called with a screen coordinate and ground plane z
- **THEN** the returned world point lies on the ground plane and projects back to the original screen coordinate (within floating-point tolerance)

### Requirement: Near-Plane and Viewport Clipping
The system SHALL clip geometry in the correct order: near-plane clipping in camera space before perspective division, then viewport clipping in screen space, then polygon cleanup.

#### Scenario: Polygon partially behind near plane
- **WHEN** a polygon has some vertices behind the near plane
- **THEN** the polygon is clipped to only the portion at depth >= near_plane before projection

#### Scenario: Line partially behind near plane
- **WHEN** a line segment has one endpoint behind the near plane
- **THEN** the line is clipped to the visible segment

#### Scenario: Polygon extends beyond viewport
- **WHEN** a projected polygon extends outside the viewport rectangle
- **THEN** it is clipped to the viewport boundary

#### Scenario: Degenerate polygon cleanup
- **WHEN** clipping produces adjacent duplicate vertices, collinear sequences, or zero-area polygons
- **THEN** duplicates and collinear vertices are removed; zero-area polygons are rejected

### Requirement: Scene Model
The system SHALL provide a retained scene model (`Scene3D`) that stores world objects without drawing them, where each object implements the `Renderable3D` protocol and emits world-space render packets.

#### Scenario: Add and remove objects
- **WHEN** an object is added via `scene.add()`
- **THEN** it returns a stable `ObjectHandle` and the object participates in future renders until removed

#### Scenario: Object visibility
- **WHEN** a renderable's `visible` property is False
- **THEN** its `collect()` method is not called during rendering

#### Scenario: Object handle stability
- **WHEN** unrelated objects are added or removed from the scene
- **THEN** previously returned handles remain valid and refer to the same objects

### Requirement: Built-in Scene Object Types
The system SHALL provide these renderable object types: `Box3D`, `Polygon3D`, `Line3D`, `Polyline3D`, `Text3D`, `Billboard3D`, `GroundPlane3D`, `TriangleMesh3D`, and `TetrahedralMesh3D`.

#### Scenario: New primitive occlusion review
- **WHEN** a new renderable primitive type is added to the framework, such as circles, ellipses, arcs, sprites, or other non-polygon primitives
- **THEN** its visibility and occlusion behavior against existing primitive families is evaluated explicitly and any required clipping, splitting, or approximation rule is documented before the primitive is considered complete

#### Scenario: Box3D rendering
- **WHEN** a `Box3D` is collected
- **THEN** it emits up to six back-face-culled polygon packets for its axis-aligned faces with directional shading

#### Scenario: Billboard3D facing
- **WHEN** a `Billboard3D` with `CAMERA_YAW` facing is collected
- **THEN** it emits a quad oriented toward the camera's yaw angle

#### Scenario: TriangleMesh3D efficiency
- **WHEN** a `TriangleMesh3D` with N triangles is in the scene
- **THEN** it emits N triangle packets from one retained object, not N separate scene objects

#### Scenario: TetrahedralMesh3D exterior extraction
- **WHEN** a `TetrahedralMesh3D` is rendered
- **THEN** only exterior faces (occurring once among all cells) are emitted with outward-oriented winding

### Requirement: Render Ordering Strategies
The system SHALL provide selectable ordering strategies for depth-sorting projected render entries, with `OverlapDepthSorter` as the default for small scenes and `AverageDepthSorter` as an explicit fallback.

#### Scenario: Average depth ordering
- **WHEN** `AverageDepthSorter` is configured
- **THEN** entries are ordered by average camera-space depth with stable-index tie breaking

#### Scenario: Overlap-aware topological ordering
- **WHEN** `OverlapDepthSorter` is configured and projected faces overlap on screen
- **THEN** depth is sampled at overlap points and a topological sort determines back-to-front order

#### Scenario: Cycle detection fallback
- **WHEN** the overlap graph contains a cycle
- **THEN** `SortResult.cycle_detected` is True and cycle participants fall back to stable average-depth order

### Requirement: Line vs Face Partial Occlusion
The system SHALL support occlusion of `Line3D` and `Polyline3D` segments by nearer solid polygon faces so partially hidden linework does not bleed through buildings or other occluders, while allowing specific packet or material roles to opt polygon surfaces out of line-fragment depth tests.

#### Scenario: Grid line behind a building side
- **WHEN** a projected line segment passes behind a nearer visible polygon face for only part of its length
- **THEN** only the visible fragment remains drawn in front of the face and the hidden fragment is clipped or split away

#### Scenario: Average-depth ordering is insufficient for a line segment
- **WHEN** one portion of a line segment is nearer than a face and another portion is farther away
- **THEN** the renderer does not rely on one average depth for the whole line segment to determine visibility

#### Scenario: Decorative surface remains in polygon ordering but does not clip linework
- **WHEN** a polygon packet or its material is marked as non-occluding for line tests
- **THEN** the polygon still participates in normal polygon ordering, but the line-occlusion pass excludes it from line-fragment depth comparisons

### Requirement: CPU Renderer Pipeline
The system SHALL provide `CpuRenderer3D` that executes the render lifecycle: collect world packets from visible scene objects, project through `ProjectionPipeline`, assign stable indices, order with the configured sorter, and emit DearCyGui draw commands into a hidden layer.

#### Scenario: Render lifecycle
- **WHEN** `render()` is called with a scene, camera, and viewport
- **THEN** it produces draw commands in sorted back-to-front order in the target `DrawingList`

#### Scenario: Textured quad clipping fallback
- **WHEN** a textured quad fails `project_complete_quad()` (corners clipped)
- **THEN** the renderer emits the clipped solid polygon with the material's shaded fallback color

#### Scenario: Render statistics
- **WHEN** rendering completes
- **THEN** `RenderStats` reports packet counts, clipped counts, and cycle state

### Requirement: DrawInWindow3D Widget
The system SHALL provide a `DrawInWindow3D` widget that owns DearCyGui drawing resources, integrates the renderer, and provides atomic front/back layer publication so partially rebuilt scenes are never displayed.

#### Scenario: Atomic publication
- **WHEN** `render_if_needed()` rebuilds the back layer
- **THEN** the front/back swap is atomic (toggle `show` flags under mutex) and no intermediate state is visible

#### Scenario: Dirty coalescing
- **WHEN** multiple mutations occur before the next render opportunity
- **THEN** only one render pass executes

#### Scenario: Camera helpers
- **WHEN** `orbit()`, `pan_world()`, `zoom_by()`, or `focus_on()` is called
- **THEN** the camera is replaced, camera-dependent state is invalidated, and the accepted camera is returned

#### Scenario: Coordinate queries
- **WHEN** `world_to_screen()` is called with a visible world point
- **THEN** it returns the current projected screen coordinate

### Requirement: DrawStream Animation Policies
The system SHALL support three `DrawStream` animation ownership policies with distinct invalidation and ordering semantics.

#### Scenario: Persistent overlay stream
- **WHEN** an animation uses `PERSISTENT_OVERLAY` policy
- **THEN** it lives outside cleared scene layers, survives scene rebuilds, and only its parent transform updates on camera change

#### Scenario: Preprojected non-occludable stream
- **WHEN** an animation uses `PREPROJECTED_BACKGROUND` policy
- **THEN** it is built in the back layer for one camera state, does not enter face ordering, and is recreated on camera/scene invalidation

#### Scenario: Preprojected occludable stream
- **WHEN** an animation uses `OCCLUDABLE_WORLD` policy
- **THEN** its world quad is sorted with other faces and the stream is emitted at its sorted position, viewport-clipped

### Requirement: Collision System
The system SHALL provide an optional world-space collision system independent of rendered geometry, using axis-aligned 2D footprints with a configurable separation gap.

#### Scenario: Movement validation
- **WHEN** a candidate footprint is tested against `CollisionWorld.first_blocker()`
- **THEN** it returns the first conflicting collider or None if the position is valid

#### Scenario: Configured gap enforcement
- **WHEN** a candidate footprint is within the configured gap distance of a collider
- **THEN** it is rejected as conflicting

#### Scenario: World-bound clamping
- **WHEN** a candidate position extends beyond configured world bounds
- **THEN** it is clamped before collision testing

### Requirement: Thread-Safe Async Updates
The system SHALL support thread-safe submission of immutable scene updates from worker threads, applied atomically on the DCG thread before the next render.

#### Scenario: Worker geometry submission
- **WHEN** a worker calls `submit_update()` with a `ReplaceGeometry` operation
- **THEN** the update is queued without touching the live scene or DearCyGui objects

#### Scenario: Atomic multi-operation application
- **WHEN** a `SceneUpdate` contains multiple operations (geometry + field)
- **THEN** all operations apply together or fail together; no partial state is published

#### Scenario: Coalescing by key
- **WHEN** multiple updates share the same `coalesce_key`
- **THEN** only the newest unapplied revision is retained and rendered

#### Scenario: Revision ordering
- **WHEN** an older slow computation completes after a newer one
- **THEN** the older result cannot overwrite the newer state

#### Scenario: Error isolation
- **WHEN** an update fails to apply
- **THEN** the last published scene remains intact and the error is reported through `UpdateTicket`

### Requirement: Engineering Mesh Scalar Fields
The system SHALL support per-cell and per-node scalar field visualization on triangle and tetrahedral meshes with configurable color mapping and value ranges.

#### Scenario: Per-cell coloring
- **WHEN** a `ScalarFieldMaterial` with `FieldAssociation.CELL` is applied to a `TetrahedralMesh3D`
- **THEN** each exterior triangle is colored by its owning cell's scalar value mapped through the color map

#### Scenario: Value range clamping
- **WHEN** a scalar value exceeds the configured `value_range`
- **THEN** it is handled according to the `out_of_range` policy (CLAMP or configured alternative)

#### Scenario: Field replacement without topology rebuild
- **WHEN** `update_object()` replaces only the material/field values
- **THEN** the cached exterior-face extraction is reused; only colors are recomputed

### Requirement: Pipeline Profiling Fixtures
The system SHALL expose each render pipeline stage as a separately callable boundary so profiling fixtures can measure per-stage wall-clock time independently at varying face counts, guiding evidence-based acceleration decisions.

#### Scenario: Stage isolation for profiling
- **WHEN** a profiling test targets one pipeline stage (projection/clipping, broad-phase candidate generation, exact overlap tests, topological ordering, or DCG node creation/publication)
- **THEN** that stage can be invoked and timed independently without executing the full render pipeline

#### Scenario: Synthetic scene scaling
- **WHEN** profiling fixtures generate scenes at documented face counts (100, 500, 2000, 10000)
- **THEN** per-stage timing results identify which stages dominate at each scale

#### Scenario: Acceleration justification
- **WHEN** profiling results show a stage consuming a disproportionate share of frame time
- **THEN** the framework documents the finding and targeted acceleration (Cython, NumPy vectorization, or spatial indexing) is applied only to that stage

### Requirement: Ported Demo Placement
The system SHALL keep the original numbered `Animation/` demos as preserved references and place framework-backed demo migrations in `Animation/ported_demos/`.

#### Scenario: Creating a framework-backed demo port
- **WHEN** a legacy demo is migrated to the shared framework
- **THEN** the framework-backed version is added under `Animation/ported_demos/` rather than overwriting the original numbered demo file

#### Scenario: Comparing a port against the legacy demo
- **WHEN** visual or behavioral parity is validated for a migrated demo
- **THEN** the original numbered demo remains available as the comparison baseline unless an explicit follow-up change requests its retirement
