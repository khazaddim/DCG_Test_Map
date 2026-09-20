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

### Screen-space sweep-and-prune broad phase
- Decision: `OverlapDepthSorter` SHALL use a pure-Python screen-space sweep-and-prune broad phase with per-sort cached AABBs to reduce the polygon pairs sent to `overlapping_polygon_depths()`. Only projected polygon entries with at least three points participate. Their bounds are computed from final `ProjectedRenderEntry.points`, sorted deterministically by `(min_x, entry_index)`, pruned on the x axis, and filtered on the y axis before exact testing.
- Rationale: Camera changes invalidate projected geometry, so bounds must be cheap frame-local data rather than persistent world-space state. Sweep-and-prune avoids tuning grid cell sizes and avoids visiting x-separated pairs in spatially distributed map scenes while preserving the existing exact overlap, depth, graph, topological-sort, and cycle-fallback semantics.
- Boundary rule: Touching AABBs remain candidates. An interval is rejected only under strict separation (`max_x < min_x` or `max_y < min_y`). Any future screen-space bounds tolerance must be a separate linear-distance setting rather than reusing area or depth epsilon values.
- Complexity: Expected candidate generation is approximately $O(n \log n + k)$ for the sort and active comparisons, where $k$ is the number of x-active pairs. Dense projected geometry remains $O(n^2)$ in the worst case.
- Evaluation switch: Preserve the current all-pairs candidate generator as a separate implementation and add sweep-and-prune alongside it. `OverlapDepthSorter` accepts a startup-time `use_sweep_and_prune: bool`, initially defaulting to `False`, and the target demo exposes a top-level `USE_SWEEP_AND_PRUNE` constant that is passed when constructing the sorter. The value is selected before launch; runtime UI switching and mid-frame mutation are out of scope.
- Shared pipeline: The boolean selects only candidate-pair generation. Both paths feed the same `overlapping_polygon_depths()`, ordering-edge construction, heap-based topological sort, stable-index tie breaking, and cycle fallback so comparisons isolate the broad-phase change.
- Rollout: Instrument the unchanged all-pairs path first, then add sweep-and-prune without deleting or rewriting the baseline generator. Keep both implementations available for visual, differential, and performance evaluation. Make sweep-and-prune the constructor default only after both paths produce identical stable-index order and cycle state across representative fixtures and distributed-scene timings show a meaningful improvement; preserve the boolean escape hatch afterward and do not introduce a permanent face-count threshold without measurements.
- Diagnostics: Per-sort metrics SHALL report total entries, eligible polygons, possible polygon pairs, x-active pairs, AABB candidates, exact tests, accepted graph edges, cycle state, duration, and selected candidate strategy. Metrics reset for each sort and do not change the public renderer API unless later profiling demonstrates a need to expose them.
- Alternatives considered:
  - Uniform screen-space grid: deferred because it requires cell-size policy, inserts large polygons into multiple cells, and requires pair deduplication. Reconsider only if sweep active-list costs dominate measured workloads.
  - Cached AABB rejection inside the existing nested loop: useful as an intermediate measurement step, but insufficient as the final candidate generator because it still enumerates every unordered pair.
  - Cython or another compiled kernel: deferred until the pure-Python algorithm is correct and profiling identifies remaining numeric hot spots.

### Milestone 5.4 fixture implementation handoff

This is the fixture design for Terra to implement during tasks 5.4.10-5.4.15,
including 5.4.11.1. It is not a record of passing tests or measured performance.
Keep `use_sweep_and_prune=False` and the demo startup constant unchanged until
the gates below have been evaluated. Do not mark implementation tasks complete
on the strength of this design alone.

#### Scope and implementation homes

- Extend `tests/test_draw_in_window_3d_milestone3.py`, which already owns bounds,
  sweep, selector, exact-depth, and cycle tests. Parameterize or strengthen those
  tests instead of duplicating them in a new milestone test module.
- Add one opt-in benchmark runner under `Animation/ported_demos/`, provisionally
  `benchmark_overlap_sort.py`. Put reusable benchmark fixture builders there;
  it must be import-safe, with no UI construction, asset loading, measurements,
  or file writes at import time. Tests may import its builders using the existing
  demo-loading convention. Do not import the test suite from the runner.
- Reuse `make_sort_frame`, `make_camera_space_polygon_entry`, and the existing
  cycle/selector probes. `make_projected_entry` is suitable for bounds-only tests:
  its screen and camera coordinates are not a perspective-consistent pair.
- For differential fixtures, use actual projected geometry. The existing
  `project_scene_entries` helper sorts before returning; add a local option or
  unsorted collection helper so neither strategy receives pre-sorted input.
  Capture entries immediately after `_collect_packets` and `_project_packet`,
  before sorting, line-fragment processing, or DCG emission.
- No production API expansion, new dependencies, broad renderer refactor,
  general Milestone 5.5 profiler, or optimization of the baseline is required.

#### Correctness hypothesis and independent checks

The hypothesis is that sweep changes only the set of exact-test calls: every
pair capable of producing an ordering edge remains present, so graph edges,
stable-index order, and cycle state are unchanged. Final-order equality alone
cannot prove this: a missing edge can agree accidentally with average depth.
Use three layers of checks:

1. Independently enumerate eligible input positions with nested loops. Compute
   scalar minima/maxima directly from final screen points, without calling
   production bounds, overlap, or candidate helpers. Retain an unordered pair
   when both closed intervals intersect. Compare this set exactly with sweep
   candidates; independently count x-interval intersections for x-active metrics.
2. For each differential fixture, enumerate all eligible pairs through the real
   `overlapping_polygon_depths` outside any timed region. Apply the configured
   depth epsilon to derive directed edges, keyed by input positions. Check every
   edge-producing pair is a sweep candidate and compare complete directed edge
   sets obtained from each candidate list. This is an oracle for broad-phase
   equivalence, not independent verification of the exact geometry algorithm.
3. Sort the identical immutable entry tuple with both flags; require identical
   ordered stable-index tuples, entry identity/multiplicity, cycle flags, and
   accepted-edge counts. Add analytical expected orders for the simple depth
   and cycle fixtures, so two equally wrong paths cannot satisfy all checks.

Use unique stable indices unrelated to input positions (for example 41, 7, 23).
Repeat with original, reversed, and fixed-seed shuffled input, retaining each
entry's stable index. Compare strategies on each permutation; require invariant
output across permutations when stable indices are unique. Candidate sequence
determinism applies to a fixed input tuple, not across permutations.

#### Candidate matrix: task 5.4.10

Represent a bounds rectangle as `(min_x, min_y, max_x, max_y)` and expand it to
four points. Unless stated otherwise, entry positions are 0, 1, 2, and the base
rectangle is `(0, 0, 10, 10)`. Check exact pair sequence, canonical indices
`first < second`, no duplicates, independent oracle equality, and both counters.

| Case | Other bounds or input | Expected pairs in emission order | x-active / candidates |
| --- | --- | --- | --- |
| Empty / singleton | Zero entries / base only | `()` | 0 / 0 |
| Strict x separation | `(11, 0, 21, 10)` | `()` | 0 / 0 |
| Strict y separation | `(0, 11, 10, 21)` | `()` | 1 / 0 |
| Positive overlap | `(5, 5, 15, 15)` | `((0, 1),)` | 1 / 1 |
| Containment | `(2, 2, 8, 8)` | `((0, 1),)` | 1 / 1 |
| Touch x edge | `(10, 0, 20, 10)` | `((0, 1),)` | 1 / 1 |
| Touch y edge | `(0, 10, 10, 20)` | `((0, 1),)` | 1 / 1 |
| Touch corner | `(10, 10, 20, 20)` | `((0, 1),)` | 1 / 1 |
| Equal minima / identical | Three copies of base; scrambled stable indices | `((0, 1), (0, 2), (1, 2))` | 3 / 3 |
| Three-way, non-index sweep order | Index 0: `(4, 0, 14, 10)`; 1: base; 2: `(2, 0, 12, 10)` | `((1, 2), (0, 1), (0, 2))` | 3 / 3 |
| Expiration with long-lived entry | Base; `(2, 0, 3, 10)`; `(4, 0, 5, 10)` | `((0, 1), (0, 2))` | 2 / 2 |

- Repeat edge tests with the separating coordinate set to
  `math.nextafter(10.0, math.inf)` and `math.nextafter(10.0, -math.inf)`.
  The first must prune and the second must retain. Repeat on y. Do not borrow
  area/depth epsilon for a linear bounds tolerance.
- Include negative and translated coordinates, reversed vertex winding, and
  noncontiguous eligible positions separated by line/text entries and polygons
  with zero, one, or two points. Expected pairs refer to original input positions.
- A three-point collinear polygon is still eligible under the present contract;
  test that distinction explicitly. Its degenerate plane cannot produce an edge.
  Do not silently broaden eligibility filtering as part of this test work.
- Retain the existing mixed touching/y-rejection test and its exact `5 / 2`
  counters. The whole candidate list is deterministic but is NOT required to be
  globally lexicographically sorted.
- Wrap `_screen_bounds` to count calls: one per eligible entry per sort for each
  strategy. Reuse stable IDs while changing points from separated to overlapping
  and back; verify counters and bounds recompute, without altering prior results.

#### Selector and statistics matrix: tasks 5.4.11 and 5.4.11.1

- Strengthen the existing selector test with asymmetric candidates: a separated
  two-polygon input produces one all-pairs exact call and zero sweep exact calls.
  Retain generator spies proving only the selected generator executes.
- Parameterize both flags over a new sorter with `frame=None`, a frame-backed
  sort followed by `frame=None` on the SAME instance, and frame-backed empty,
  singleton, non-polygon-only, and mixed-entry inputs. Exercise a one-shot input
  iterator as well as tuples to protect the iterable contract.
- For fallback, require exactly `AverageDepthSorter` ordering, including equal
  average depths with out-of-order stable indices; no candidate/exact calls;
  `cycle_detected=False`; result `sort_stats is None`; and
  `last_sort_stats is None`. The same-instance regression should fail before
  Terra implements the explicitly scoped 5.4.11.1 reset.
- For every frame-backed sort require a fresh statistics value, identity with
  `last_sort_stats`, a finite nonnegative duration, the correct strategy label,
  and result/statistics agreement on cycles. Prior result statistics must remain
  unchanged after later calls, including a cycle-to-acyclic transition.
- For eligible count `n`, require `possible_polygon_pair_count=n*(n-1)//2`.
  All-pairs reports x-active = bounds-candidate = exact = possible (the bounds
  field means emitted candidates here, not actual AABB intersections).
  Sweep reports `0 <= exact = bounds_candidate <= x_active <= possible`.
  Both report `0 <= accepted_edge_count <= exact_test_count` and the actual
  total entry count, including non-polygons.

#### Differential geometry matrix: task 5.4.12

Use the three-layer checks above on every row. Record a fixture ID, parameters,
camera, viewport, seed, permutation, and first mismatching pair on failure.
Assert each fixture actually exercises its named property; an empty projection
or an all-disjoint scene is not evidence of clipping or overlapping depth order.

| Family | Construction and required discriminator |
| --- | --- |
| Distributed boxes | A 4-by-4 grid of boxes, spacing 80, footprint 36-by-36, heights cycling 30/70/110. Include overlapping and separated projected pairs across the camera matrix; at least one view must produce edges and prune pairs. |
| Houses and towers | The same grid with alternating box heights 40/160 and gabled roof triangles above the shorter boxes. Use existing `Box3D` and `TriangleMesh3D` packet conventions. Assert roof triangles and tall walls survive projection and generate at least one overlap edge. |
| Billboards | Three yaw-facing `Billboard3D` objects interleaved with two solid boxes; use placeholder image resources without draw-node emission. Include a fully visible image quad and a viewport-clipped quad. Verify polygon eligibility and compare actual projected entries; do not fabricate a new `billboard` entry kind. |
| Clipping | Separate witnesses for near-plane clipping, each viewport boundary, simultaneous near/viewport clipping, and full rejection. Use real projection; assert surviving points lie inside the viewport, camera depths satisfy near-plane rules, and output geometry actually changed or vanished as intended. Pair each survivor with an overlapping face. Bounds must match final points, not the original packet. |
| Ties and thresholds | Overlapping coplanar faces, disconnected equal-average-depth faces, and parallel planes at depth differences 0, 0.5 and 2 times `depth_epsilon`; use non-default epsilon values as well. Test overlap areas 0, half and twice `overlap_area_epsilon` with wide numerical margins. Touching is a candidate but creates no real exact edge. |
| Exact rejection despite AABBs | Two disjoint triangles whose AABBs overlap: `((0,0),(10,0),(0,10))` and `((10,10),(10,6),(6,10))`. Translate into the viewport and lift to planes. Require one candidate, one exact call, zero edges. |
| Depth beats average | Reuse the current two-face reversed-average-depth regression under both flags; expected order is farther plane first, not average-depth order. This deliberately overridden average is a sorter unit probe, not a performance fixture. |
| Cycles | Parameterize the existing mocked three-edge cycle under both flags, plus a real geometric cycle described below. Add one disconnected farther face so fallback must replace the entire ordering, not merely append unresolved nodes. |
| Mixed stream of entries | Interleave valid polygons, lines, text, and fewer-than-three-point polygons with tied depths. Non-polygons remain in sorted output but never become broad-phase candidates. |
| Deterministic random convex faces | Seeds 54010, 54012, 54013, 54014; counts 8, 32, 64; both sparse and clustered layouts. Generate triangles/quads/hexagons as affine transforms of regular polygons, not arbitrary radius-jittered points that may be concave. Lift to valid planes, assert convexity/planarity, and run all three input permutations. |

Camera coverage for boxes, houses, and billboards: yaw 0/45/90/135 degrees crossed
with pitch 25/55/80 degrees at zoom 1 and viewport 800-by-600. Add two targeted
views, not a full product: yaw 45/pitch 55 at zoom 0.6 with viewport 320-by-240,
and at zoom 1.8 with viewport 1280-by-360. Center the camera on the fixture and
choose/document a fixed fitting distance before freezing the fixture. Clipping
witnesses use separate deliberately selected cameras instead of depending on
chance clipping in this matrix.

For precise screen-space fixtures, lift screen points onto a plane using
`depth = 1 / (coefficient_x * screen_x + coefficient_y * screen_y + constant)`;
camera x/y are `(screen - viewport_center) * depth / focal_length`. This gives
perspective-consistent planar geometry. Require positive denominators and depths
in front of the near plane, then use `make_camera_space_polygon_entry`. Constant
denominators provide parallel planes; small slopes exercise ray-plane sampling.
For randomized faces, use screen radii 4-20 pixels, sparse centers in separated
cells and clustered centers in a 40-by-40 central patch. Choose a base depth in
80-160 and slopes bounded so inverse depth varies by at most 10% over each face.

Real cycle recipe in the 200-by-200 sort frame:

- A screen rectangle: `(40,40),(160,40),(160,60),(40,60)`; inverse depth `0.01`.
- B screen rectangle: `(140,40),(160,40),(160,160),(140,160)`; inverse depth
  `0.01 + 0.00001*(100-screen_y)`.
- C diagonal strip: `(40,50),(50,40),(160,150),(150,160)`; inverse depth
  `0.01 + 0.00001*(screen_x-100)`.

The separate positive-area pair overlaps give A farther than B, B farther than
C, and C farther than A; verify those three directed edges with the real exact
function before asserting cycle fallback. All three AABBs overlap. Use unique
scrambled stable indices and require the full `AverageDepthSorter` order. Keep
the mocked cycle test too: it isolates graph fallback from geometric sampling.

#### Performance fixture matrix: tasks 5.4.13 and 5.4.14

Build exactly 32, 64, 128, 256, and 512 eligible projected polygons for each
synthetic family. Count polygons, not objects or mesh vertices. Construct these
in screen space, lift to planes as above, and keep all points inside a fixed
2048-by-2048 viewport. Keep quad dimensions, depths, and layout rules fixed;
larger counts add occupied cells rather than shrinking faces. Timings must run
the real exact function and graph sort, with no monkeypatching.

| Family | Deterministic construction | Expected work / purpose |
| --- | --- | --- |
| Distributed local overlaps (primary) | Group four quads per cell; `ceil(sqrt(n/4))` columns, cell pitch 120, first cell origin `(40,40)`. Each quad is 24-by-24 with offsets `(0,0),(6,0),(0,6),(6,6)`, depths 80/100/120/140. | Six candidates per cell, so exact calls = `6*(n/4)`; accepted edges equal candidates. Proves pruning while retaining real local overlap and graph work. |
| All x-separated | 2-pixel-wide, 24-pixel-high quads at x pitch 3 starting at 40, shared y interval. | x-active = candidates = exact = 0. Isolates effective x pruning; not sufficient alone for the default gate. |
| X-active, y-separated | 24-pixel-wide, 2-pixel-high quads at y pitch 3 starting at 40, shared x interval. | x-active = possible, candidates = exact = 0. Exposes quadratic active-list comparisons despite eliminating exact work. |
| Dense positive overlaps | Identical screen quad `(900,900)-(1100,1100)`, depth `80 + 0.1*index`. | x-active = candidates = exact = accepted edges = possible; acyclic. Documents the quadratic worst case and candidate storage cost. |

Additionally capture unsorted projected entry tuples from the existing
`collision_sort_diagnostics.py` scene (the demo with the startup selector).
Use its normal scene construction without UI emission; if construction is UI
coupled, reproduce its scene recipe in the benchmark module and document the
source, without refactoring production code just for benchmarking. Replay the
12 yaw/pitch combinations above at the demo's normal viewport, target, distance,
and zoom. Reproject separately for every view, then feed that view's identical
entry tuple to both sorters. Report actual eligible counts, never relabel them
as the synthetic size tiers. Include ground and decorative polygon packets that
really reach sorting, even if their large bounds hurt pruning. Line fragments,
projection, UI work, and redraw throttling are outside the sort latency claim.

Benchmark protocol:

1. Run correctness checks on every generated input before timing; abort the run
   on disagreement. Fixture construction, projection, shuffling, validation,
   logging, and serialization stay outside the timed region.
2. Use two long-lived sorter instances, identical tolerances, explicit opposite
   flags, and an immutable shared tuple. Each `sort()` must rebuild its own AABBs
   and candidate data. Never feed a previous sorted result into the next sample.
3. Warm each strategy for five calls per fixture. Collect 100 measured calls per
   strategy, grouped into 20 blocks of five paired calls. Alternate all-pairs
   then sweep / sweep then all-pairs order by block. No concurrent benchmark
   jobs or UI rendering. Leave garbage collection enabled for both paths.
4. Use an outer `perf_counter_ns()` measurement of the complete `sort()` call
   as the primary latency, and retain `sort_duration_seconds` as a secondary
   diagnostic. Their scopes differ; do not silently mix them. Save all raw
   samples. p95 is nearest-rank sorted sample `ceil(0.95 * sample_count)-1`;
   median is `statistics.median`. Report milliseconds, not rounded-to-zero seconds.
5. Repeat in three fresh processes on the same machine/environment. Summarize
   each run separately before aggregating ratios. Record Python executable and
   version, OS, CPU, revision and dirty state, fixture version/seed, viewport,
   camera, epsilon settings, GC policy, warmup/sample counts, and strategy order.
6. Emit machine-readable JSON and a compact Markdown table. Per sample preserve
   every `SortStats` field: `sort_entry_count`, `polygon_entry_count`,
   `possible_polygon_pair_count`, `x_active_pair_count`,
   `bounds_candidate_pair_count`, `exact_test_count`, `accepted_edge_count`,
   `cycle_detected`, `sort_duration_seconds`, and `candidate_strategy`, plus the
   outer duration and fixture/run/block identity. Assert deterministic counters
   across repeated samples. Tables show counters, median, p95, exact-reduction
   percentage, and baseline/sweep speedup. For zero possible pairs report the
   reduction ratio as not applicable. Keep raw generated outputs out of Git.

#### Predeclared decision gates: task 5.4.15

These are proposed acceptance thresholds for this milestone, not measurements
or general guarantees. Freeze them before collecting results; do not weaken
them retrospectively to obtain a passing default-switch decision.

- Correctness: all candidate, selector, statistics, analytical, and differential
  fixtures pass, including nonempty real cycles. Then run the existing complete
  test suite. Any mismatch blocks a default change regardless of timings.
- Work reduction: distributed local-overlap fixtures at 128/256/512 must reduce
  exact calls by at least 90%, matching the analytical counter formulas. Dense
  fixtures must retain every pair; the y-separated family must explicitly show
  that low exact counts do not imply subquadratic candidate generation.
- Synthetic latency: each 128/256/512 distributed tier must have at least 20%
  lower median complete-sort latency, with p95 no worse than baseline, in all
  three process runs. Report 32/64 too; a median regression above 10% at either
  small tier requires review before a global default change.
- Target-scene latency: at least 9 of the 12 yaw/pitch views must lower median
  sort latency by at least 10%, and the geometric mean of the 12 per-view
  baseline/sweep median ratios must be at least 1.20 in each process run.
  No target view may regress median or p95 by more than 10%. Give every view
  equal weight; do not pool raw samples across different geometry sizes.
- Dense cost: document pair counts `496, 2016, 8128, 32640, 130816` and timing
  growth at the five tiers; do not require speedup. A median or p95 regression
  above 15% at 128/256/512 is a default-switch review blocker. Do not claim a
  measured memory bound without a separate memory measurement.
- Noise or borderline results mean inconclusive, not pass. Preserve raw runs,
  investigate the environment, and repeat the same protocol; do not cherry-pick
  the fastest process or remove slow samples. Timings remain opt-in evidence,
  never hard wall-clock assertions in ordinary pytest runs.
- After numerical gates, compare the demo with both startup values on identical
  camera/player paths and check ordering, clipping, cycle diagnostics, and
  controls. This targeted comparison is not a claim to close deferred demo 11
  appearance parity. Report unperformed manual checks as outstanding.
- Record the gate table, environment, ratios, failures, and a default decision
  in this change's design notes. If any gate is unmet or unverified, retain
  `False`, document why, and leave the default-flip task deferred. Do not invent
  an automatic face-count threshold. If gates pass and the review approves the
  switch, change the constructor default, align the demo's documented normal
  setting, test the no-argument constructor, and retain explicit `False` tests
  and the startup constant as rollback paths.

Implementation sequence: candidate/oracle tests; selector regression and scoped
statistics reset; analytical and projected differential families; benchmark
builders with deterministic counter smoke tests; opt-in measurements and report;
default review. Validate the touched tests after each slice. Completion evidence
must map back to 5.4.10, 5.4.11, 5.4.11.1, 5.4.12, 5.4.13, 5.4.14, and 5.4.15
individually; fixture implementation does not itself complete evaluation.

Design-time validation: a one-off workspace-interpreter probe confirmed the real
cycle's three directed edges and average-depth fallback under both flags. It
also confirmed the four synthetic families' candidate-count formulas at all five
sizes, and their exact accepted-edge counts at 32 polygons. These probes are not
committed tests, full differential coverage, or benchmark evidence. Terra must
implement and run the specified fixtures; all performance gates remain unevaluated.

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
- **Overlap sorter scalability** — Sweep-and-prune reduces candidate work for spatially distributed polygons but remains O(n²) when most projected AABBs overlap. Mitigation: report candidate and exact-test counts, retain `AverageDepthSorter` as the explicit approximate option, and use Milestone 5.5 profiling before selecting further acceleration.
- **Broad-phase false negatives** — Incorrect bounds, boundary comparisons, or eligibility filtering could omit a real ordering edge. Mitigation: derive AABBs from final projected points, keep touching bounds as candidates, and require all-pairs differential tests over clipped, degenerate, cyclic, and randomized geometry.
- **Comparison-path drift** — Maintaining two candidate generators can allow the baseline and accelerated paths to diverge outside the intended broad-phase behavior. Mitigation: share all exact testing and graph-ordering code, limit the boolean branch to candidate generation, and run both paths through the same differential fixtures.
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

1. **Subclass vs. wrapper — resolved.** Phase 0 confirmed that `DrawInWindow3D` can subclass `dcg.DrawInWindow` and use normal context-manager construction. The wrapper fallback is not needed for this codebase.
2. **Mutable vs. immutable object transforms — partially resolved.** `Camera3D` is an immutable frozen dataclass and camera changes replace the value. Scene objects currently use mutable dataclasses with `update_object()`, so a uniform immutable-transform policy has not been adopted. Revisit this during the API review if hierarchy or undo/redo requirements justify it.
3. **Local-space-only vs. mixed world-point geometry — resolved for the initial API.** The framework intentionally supports both transformed primitives such as `Box3D` and explicit world-space geometry such as `Polygon3D`, `Line3D`, and `Polyline3D`. A future uniform local-space model remains an API evolution question, not an implementation blocker.
4. **Picking API scope — still deferred.** Mesh `source_id` values are propagated through render packets and projected entries, providing the minimum identity needed by future picking and diagnostics. The framework does not yet define scene picking, ray-object intersection, or a structured `MeshHit` result.
5. **Mesh ordering strategy for large face counts — partially resolved; final decision pending.** Meshes remain one retained renderable that emits triangle packets, and the documentation directs large meshes toward `AverageDepthSorter` because pairwise overlap sorting is still quadratic. Sweep-and-prune is implemented as an opt-in comparison path, but the performance evaluation and default-switch decision remain incomplete in tasks 5.4.14 and 5.4.15.
6. **Parent-child transform hierarchies — still deferred.** The scene model remains flat. DearCyGui parent/child relationships are used for drawing-layer ownership, not for scene-object transforms or local/world hierarchy semantics.
7. **Offscreen/image-export API — still out of scope.** `render_now()` renders a frame into DearCyGui drawing layers; it is not an image-export contract. Framebuffer, screenshot, and deterministic offscreen-rendering integration remain future work.
8. **Line-vs-face partial occlusion — resolved for the current implementation.** The renderer uses screen-space line splitting at polygon intersections, then depth-tests each subsegment against nearer occluding faces. It keeps lines as native line packets rather than converting them to thin polygons. World-space clipping and thin-polygon substitution remain alternatives for future primitive families, but are not the selected approach here.
