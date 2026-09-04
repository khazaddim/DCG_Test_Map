## Milestone 0: Feasibility Spikes
- [x] 0.1 Verify `dcg.DrawInWindow` supports Python subclass construction with context-manager use
- [x] 0.2 Verify two child `DrawingList` objects can be swapped by toggling `show` under a mutex
- [x] 0.3 Subclassing succeeded; wrapper fallback not needed and Phase 0 notes document why
- [x] 0.4 Minimal `DrawInWindow3D` displays and atomically replaces a single polygon (exit criterion)

## Milestone 1: Pure Math Baseline
- [x] 1.1 Extract `Camera3D` dataclass with `eye()`, `world_to_camera()`, `camera_to_screen()`, `ground_from_screen()`
- [x] 1.2 Extract `Viewport` dataclass
- [x] 1.3 Implement near-plane polygon clipping (camera-space `depth >= near_plane`)
- [x] 1.4 Implement near-plane line clipping
- [x] 1.5 Implement screen-space viewport polygon clipping
- [x] 1.6 Implement screen-space viewport line clipping
- [x] 1.7 Implement polygon cleanup: duplicate removal, collinear vertex removal, zero-area rejection (epsilon=1e-5)
- [x] 1.8 Implement `ProjectionPipeline.project_polygon()` combining steps 1.3–1.7
- [x] 1.9 Implement `ProjectionPipeline.project_line()`
- [x] 1.10 Implement `ProjectionPipeline.project_complete_quad()` (strict; returns None if any corner clips)
- [x] 1.11 Implement back-face culling utility
- [x] 1.12 Implement directional shading utility (face normal dot light)
- [x] 1.13 Write unit tests: camera eye position and world-to-camera rotation order
- [x] 1.14 Write unit tests: screen projection and reverse ground-plane ray intersection
- [x] 1.15 Write unit tests: near-plane polygon and line clipping edge cases
- [x] 1.16 Write unit tests: viewport clipping and degenerate polygon cleanup
- [x] 1.17 Write unit tests: back-face culling
- [x] 1.18 Verify tests reproduce demo 11 projection results without importing DearCyGui

## Milestone 2: Solid Scene Renderer
- [x] 2.1 Define `Renderable3D` protocol with `visible` and `collect()` method
- [x] 2.2 Implement `Scene3D` with `add()`, `remove()`, `ObjectHandle` management
- [x] 2.3 Define `WorldRenderPacket` and `ProjectedRenderEntry` dataclasses
- [x] 2.4 Define `Material3D` protocol and `SolidMaterial` (fill, outline, thickness, shading, blend mode)
- [x] 2.5 Implement `Box3D` renderable (six axis-aligned faces, back-face culled, shaded)
- [x] 2.6 Implement `GroundPlane3D` renderable
- [x] 2.7 Implement `Line3D` and `Polyline3D` renderables
- [x] 2.8 Implement `Polygon3D` renderable (arbitrary planar polygon)
- [x] 2.9 Implement `Text3D` renderable (projected label with perspective-scaled size)
- [x] 2.10 Implement `AverageDepthSorter` with stable-index tie breaking
- [x] 2.11 Implement `CpuRenderer3D.render()` lifecycle: collect → project → sort → emit
- [x] 2.12 Implement DearCyGui draw-command emission (DrawPolygon, DrawLine, DrawText)
- [x] 2.13 Implement `FramePublisher` for atomic front/back `DrawingList` swap
- [x] 2.14 Implement `DrawInWindow3D` widget with scene, camera, renderer ownership
- [x] 2.15 Implement `invalidate()` and `render_if_needed()` dirty-flag coalescing
- [x] 2.16 Implement `render_now()` for synchronous single-frame rendering
- [x] 2.17 Implement `set_camera()`, `orbit()`, `pan_world()`, `zoom_by()`, `focus_on()` camera helpers
- [x] 2.18 Implement `world_to_screen()` and `screen_to_ground()` query methods
- [x] 2.19 Implement `EdgeBandFollowController` for camera auto-follow
- [x] 2.20 Port demo 11 to the framework under `Animation/ported_demos/` (preserve arrow-key movement, clipping, camera follow, shading, ordering)
- [x] 2.21 Write integration tests: widget construction, resize, layer publication
- [ ] 2.22 Deferred: final demo 11 appearance/control parity verification after known ordering and occlusion issues are addressed in 3.14-3.16

## Milestone 3: Collision and Accurate Ordering

### Sub-milestone 3A: AABB Collision (independent)
- [x] 3.1 Implement `CollisionShape2D` protocol and `AabbFootprint` shape (complexity: Low)
- [x] 3.2 Implement `CollisionWorld.first_blocker()` with configurable gap (complexity: Low)
- [x] 3.3 Implement candidate-first AABB validation (demo 12 ordering: clamp → test → commit)  (complexity: Low)

### Sub-milestone 3B: Overlap Depth Ordering (independent)
- [x] 3.4 Implement convex screen-polygon overlap detection (separating-axis test) (complexity: High)
- [x] 3.5 Implement ray-plane depth comparison for overlapping projected faces (complexity: High)
- [x] 3.6 Implement topological sort of overlap constraints (complexity: High)
- [x] 3.7 Implement cycle detection with stable average-depth fallback (complexity: High)
- [x] 3.8 Implement `OverlapDepthSorter` combining steps 3.4–3.7 (complexity: High)
- [x] 3.9 Report cycle state through `SortResult.cycle_detected` (complexity: High)

### Sub-milestone 3C: Integration, Diagnostics, and Line Occlusion (depends on 3A and 3B)
- [x] 3.10 Write unit tests: AABB collision boundaries and configured gaps (complexity: Moderate - high)
- [x] 3.11 Write unit tests: convex overlap detection, ray-plane depth, topological order, cycles (complexity: Moderate - high)
- [x] 3.12 Create example selecting collision and either ordering strategy independently (complexity: Moderate - high)
- [x] 3.13 Verify cycle fallback is visible in diagnostics (complexity: Moderate - high)
- [x] 3.14 Implement line vs face partial occlusion for `Line3D` and `Polyline3D` (complexity: Moderate - high)
- [x] 3.15 Write tests covering partially occluded grid or border lines against solid faces (complexity: Moderate - high)
- [x] 3.16 Document the chosen approach for line splitting/clipping vs thin-polygon substitution (complexity: Moderate - high)

### Sub-milestone 3D: Surface-Role Line Occlusion (depends on 3C)
- [x] 3.17 Define a packet/material line-occlusion policy, with solid faces
      occluding lines by default.
- [x] 3.18 Propagate the policy from `SolidMaterial` through projected polygon
      entries to the line-occlusion pass.
- [x] 3.19 Exclude non-occluding decorative surfaces from line-fragment depth
      tests while retaining normal polygon ordering.
- [x] 3.20 Mark the demo road and water surfaces as non-occluding decoration.
- [x] 3.21 Add rotation tests proving building faces clip grid/border lines while
      road and water surfaces do not.
- [x] 3.22 Document how material/surface roles interact with face ordering and
      line occlusion.

## Milestone 4: Materials and Animation

### Sub-milestone 4A: Image Materials and Animation Core (continuous GPT-5.6 Terra implementation)
- [x] 4.1 Implement `ImageMaterial` with UV coordinates and tessellation policy
- [x] 4.2 Implement tessellated texture mapping (subdivision-based approximation)
- [x] 4.3 Implement textured-quad clipping fallback (solid shaded fill when `project_complete_quad()` returns None)
- [x] 4.4 Implement `AnimatedImageMaterial` with frame source, loop timing, and frame offset

### Sub-milestone 4B: 4A Review and Compatibility Gate (GPT-5.4; depends on 4A)
- [x] 4B.1 Review the complete 4A implementation against existing material, projection, and draw-command contracts
- [x] 4B.2 Review UV correspondence, tessellation edge cases, clipped-quad fallback, animation timing, and resource ownership
- [x] 4B.3 Add or correct focused tests and resolve review findings before starting 4C

### Sub-milestone 4C: Projection Policies, Streams, Billboards, and Integration (continuous GPT-5.4 implementation; depends on 4B)
- [x] 4.5 Define `AnimationProjection` enum: PERSISTENT_OVERLAY, PREPROJECTED_BACKGROUND, OCCLUDABLE_WORLD
- [x] 4.6 Implement persistent overlay `DrawStream` policy (outside cleared scene layers, transform-only updates)
- [x] 4.7 Implement preprojected non-occludable `DrawStream` policy (rebuilt in back layer, not sorted)
- [x] 4.8 Implement preprojected occludable `DrawStream` policy (sorted with faces, viewport-clipped)
- [x] 4.9 Implement `Billboard3D` renderable (camera-facing quad with image/animation command)
- [x] 4.10 Implement `BillboardFacing.CAMERA_YAW` orientation
- [x] 4.11 Ensure texture lifetime survives layer clears (shared textures outside scene layers)
- [x] 4.12 Verify camera/viewport change invalidates preprojected streams but preserves persistent overlays
- [x] 4.13 Port demo 14 features: solid boxes, textured player, animated water, overlay marker, occludable trees
- [x] 4.14 Write integration tests: stream continuity, rebuild on camera change, overlay survival
- [x] 4.15 Verify all object types coexist through the common packet API

## Milestone 5: Engineering Mesh Support
- [ ] 5.1 Implement `TriangleMesh3D` with indexed vertices and triangular faces
- [ ] 5.2 Implement efficient packet emission (one retained renderable, not per-face objects)
- [ ] 5.3 Implement `TetrahedralMesh3D` with cell topology storage
- [ ] 5.4 Implement exterior-face extraction (face keyed by sorted vertex indices, occurs once = exterior)
- [ ] 5.5 Implement outward winding orientation (normal away from opposite vertex)
- [ ] 5.6 Cache extracted exterior faces; invalidate only on topology change
- [ ] 5.7 Implement per-cell to per-triangle scalar field mapping via source cell back-reference
- [ ] 5.8 Implement `ScalarFieldMaterial` with color map, value range, and out-of-range policy
- [ ] 5.9 Implement `source_id` propagation from mesh triangle back to original cell
- [ ] 5.10 Implement `MeshEdgeStyle` for optional triangle edge rendering
- [ ] 5.11 Implement double-sided emission for translucent alpha materials
- [ ] 5.12 Document mesh-size limit for pairwise overlap sorter; provide guidance on when to use average-depth
- [ ] 5.13 Implement `update_object()` for vertex replacement (reuse topology cache)
- [ ] 5.14 Implement `update_object()` for field/material replacement (reuse geometry cache)
- [ ] 5.15 Write unit tests: face deduplication, exterior extraction, outward winding
- [ ] 5.16 Write unit tests: per-cell scalar range handling, color mapping, source-ID preservation
- [ ] 5.17 Write unit tests: degenerate and inverted tetrahedra handling
- [ ] 5.18 Write integration test: tetrahedral fixture renders only exterior faces with correct colors and pickable source IDs
- [ ] 5.19 Write integration test: no tetrahedron represented as individual scene object

## Milestone 5.5: Performance Profiling Fixtures
- [ ] 5.5.1 Ensure each pipeline stage (projection/clipping, broad-phase, overlap tests, topological sort, DCG node creation) is a separate callable boundary
- [ ] 5.5.2 Create synthetic scene generators at documented face counts (100, 500, 2000, 10000 faces)
- [ ] 5.5.3 Write profiling fixture: projection/clipping stage wall-clock time per face count
- [ ] 5.5.4 Write profiling fixture: broad-phase candidate generation (once spatial acceleration exists)
- [ ] 5.5.5 Write profiling fixture: exact overlap intersection and ray-plane depth tests
- [ ] 5.5.6 Write profiling fixture: topological ordering (graph build + sort + cycle detection)
- [ ] 5.5.7 Write profiling fixture: DCG draw-node creation and front/back publication
- [ ] 5.5.8 Produce baseline timing table for pure-Python implementation at each face count
- [ ] 5.5.9 Identify bottleneck stages from profiling results; document findings
- [ ] 5.5.10 If warranted by evidence, spike targeted acceleration (Cython, NumPy vectorization, or spatial indexing) on the identified bottleneck

## Milestone 6: Async Update Support
- [ ] 6.1 Implement thread-safe update inbox (bounded queue with backpressure policy)
- [ ] 6.2 Implement `SceneUpdate` with revision, operations tuple, and coalesce_key
- [ ] 6.3 Implement `ReplaceGeometry` and `ReplaceField` operation types
- [ ] 6.4 Implement `SceneSnapshot` for complete world replacement
- [ ] 6.5 Implement `UpdateTicket` with status query and exception reporting
- [ ] 6.6 Implement `submit_update()` (non-rendering, thread-safe enqueue)
- [ ] 6.7 Implement `submit_snapshot()` (non-rendering, thread-safe enqueue)
- [ ] 6.8 Implement `render_if_needed()` draining: apply queued updates atomically, then render newest state
- [ ] 6.9 Implement coalescing: superseded updates sharing a key are dropped
- [ ] 6.10 Implement revision ordering: older slow completions cannot overwrite newer state
- [ ] 6.11 Implement atomic multi-operation application (geometry + field together or fail together)
- [ ] 6.12 Implement error handling: failed updates leave last published scene intact
- [ ] 6.13 Implement shutdown coordination: reject updates after context destruction
- [ ] 6.14 Write integration tests: worker submissions never mutate scene/DCG state before drain
- [ ] 6.15 Write integration tests: coalesced revisions apply newest, bounded queue does not grow
- [ ] 6.16 Write integration tests: failed/cancelled updates report through UpdateTicket

## Milestone 7: API Review and Demo Migration
- [ ] 7.1 Review and reduce accidental public API surface
- [ ] 7.2 Add type annotations on all public interfaces
- [ ] 7.3 Add lifecycle documentation for widget, scene, handles, and streams
- [ ] 7.3.1 Add a primitive-addition checklist requiring occlusion/visibility review against existing primitive families
- [ ] 7.4 Maintain demo 11 framework port under `Animation/ported_demos/` and preserve the legacy original in `Animation/`
- [ ] 7.5 Migrate demo 12 to a framework-backed port under `Animation/ported_demos/`
- [ ] 7.6 Migrate demo 13 to a framework-backed port under `Animation/ported_demos/`
- [ ] 7.7 Migrate demo 14 to a framework-backed port under `Animation/ported_demos/`
- [ ] 7.8 Verify each migrated demo is a thin configuration of shared components and close any deferred visual/control parity checks
- [ ] 7.9 Run full test suite against migrated demos
- [ ] 7.10 Final `openspec validate` confirming spec requirements met
