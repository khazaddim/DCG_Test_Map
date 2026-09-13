# Occlusion Ordering Performance Spec

## Status

Draft design specification for improving the performance of the retained CPU
renderer without changing its public scene-authoring model.

## Problem

`CpuRenderer3D` currently projects visible scene packets into
`ProjectedRenderEntry` values and passes the occludable entries to
`OverlapDepthSorter`. The sorter constructs a directed ordering graph by
examining every unordered pair of entries:

```text
for first in entries:
    for second after first in entries:
        test projected polygon overlap
        if the polygons overlap:
            calculate depth at an overlap sample
            add a farther -> nearer ordering edge
```

For `n` projected entries, the pair count is:

$$
\frac{n(n-1)}{2} = O(n^2)
$$

The exact pair test is also relatively expensive. It may perform:

- convex polygon separation checks;
- polygon clipping/intersection;
- overlap-area calculation;
- camera-space plane reconstruction; and
- ray-plane depth calculation.

Camera yaw and pitch invalidate the viewport. The current event-driven render
path then reprojects and resorts the complete visible scene synchronously.
Consequently, a scene with more visible faces can produce noticeable input
latency even when the scene itself has not changed structurally.

The optimization target is the overlap-ordering stage, not DearCyGui texture
animation or the persistent front/back publication mechanism.

## Goals

1. Preserve the current `RenderSorter` and `CpuRenderer3D` public interfaces.
2. Preserve exact overlap-aware ordering for candidate pairs that may overlap.
3. Avoid running exact polygon geometry for pairs that cannot overlap.
4. Reduce the number of candidate pairs visited by the exact pair stage when
   the scene is spatially distributed on screen.
5. Keep `AverageDepthSorter` available as a low-cost approximate fallback.
6. Keep a pure-Python implementation available when an optional accelerator is
   unavailable.
7. Add diagnostics that make pair reduction and render cost measurable.
8. Keep deterministic stable-index ordering and cycle fallback behavior.

## Non-goals

- A complete GPU depth-buffer renderer.
- A general-purpose spatial database for world objects.
- Changing the visual ordering semantics of `OverlapDepthSorter`.
- Making intersecting or cyclic geometry mathematically sortable when no valid
  painter ordering exists.
- Replacing the retained scene graph or DearCyGui draw-list publication model.

## Current Ordering Contract

`OverlapDepthSorter` receives projected entries and a `FrameContext`. For each
pair of entries, `overlapping_polygon_depths()` first rejects non-polygons,
then tests projected polygon overlap. If the overlap has sufficient area, it
samples the overlap and calculates each polygon's camera-space depth. The
farther polygon receives an ordering edge toward the nearer polygon.

The resulting graph is topologically sorted with a heap keyed by:

1. negative average depth;
2. stable index; and
3. internal entry index as a deterministic tie breaker.

If the graph contains a cycle, the sorter returns stable average-depth order and
sets `cycle_detected=True`.

These behaviors must remain unchanged after optimization.

## Improvement Paths

The work is intentionally partitioned into a Python-first path and a later
optional Cython path. The Python path should be completed and benchmarked
before introducing a compiled extension. It addresses the algorithmic waste
first, keeps the renderer easy to run from source, and gives the Cython work a
stable reference implementation for differential testing.

### Python-First Path

Everything in this section can be implemented with the existing Python
runtime, dataclasses, tuples, lists, dictionaries, sets, and standard library.
No compiler or binary packaging is required.

#### Python Step 1: Instrument the existing sorter

Add counters and timing around the current implementation without changing its
ordering algorithm. Measure:

- projected entry count;
- total possible pair count;
- exact overlap-test count;
- accepted ordering-edge count;
- cycle count; and
- sorter duration.

This establishes whether the town demo is dominated by pair enumeration,
polygon geometry, graph construction, or topological sorting.

#### Python Step 2: Add a screen-space bounding-box broad phase

Compute a conservative axis-aligned bounding box for every projected polygon:

```text
min_x = minimum projected x
max_x = maximum projected x
min_y = minimum projected y
max_y = maximum projected y
```

For each pair, reject it before exact polygon testing when either axis is
separated:

```text
if first.max_x < second.min_x or second.max_x < first.min_x:
    reject pair
if first.max_y < second.min_y or second.max_y < first.min_y:
    reject pair
```

This test is conservative. Non-overlapping bounding boxes prove that the
polygons cannot overlap. Overlapping boxes do not prove that the polygons
overlap, so those pairs continue to the current exact test.

#### What the Python broad phase improves

Stage 1 does **not** remove the nested loop. It still visits every pair, so the
worst-case complexity remains $O(n^2)$. It reduces the expensive work performed
inside that loop:

```text
all pairs -> cheap bounding-box test -> exact polygon test only for candidates
```

For spread-out map geometry, most pairs should be rejected by the broad phase.
For a dense scene where every polygon overlaps every other polygon, the benefit
will be small.

#### Data representation

Bounding boxes should be computed once per projected entry and stored in a
compact internal structure or parallel arrays. They must not be recomputed
inside the pair loop.

A Python implementation may initially use a private tuple or dataclass. The
accelerated implementation should use contiguous numeric arrays or typed
memoryviews.

#### Python Step 3: Generate candidate pairs with a uniform grid

Stage 2 changes the pair-generation structure so the exact loop does not visit
all possible pairs. The recommended first implementation is a uniform
screen-space grid.

##### Uniform screen-space grid

1. Choose a cell size based on viewport dimensions and a configurable target
   number of cells per axis.
2. Insert each projected polygon into every grid cell touched by its bounding
   box.
3. For each cell, enumerate the entries assigned to it.
4. Generate unique candidate pairs from those cell memberships.
5. Run the exact overlap test only for those candidate pairs.

An entry must be inserted into every touched cell, not only the cell containing
its center. This prevents missed overlaps for large polygons.

Pairs found in multiple cells must be deduplicated before exact testing. A
canonical pair key `(min_index, max_index)` is sufficient for a first version.

The grid is a broad-phase acceleration structure, not an ordering structure.
The existing exact overlap test remains authoritative for candidate pairs.

##### Alternative: sweep and prune

A sweep-and-prune implementation can sort entries by `min_x` and maintain an
active interval set while scanning from left to right. Only entries with
intersecting x intervals are compared, followed by the y bounding-box test.
This avoids cell tuning and can work well for scenes with coherent projected
positions, but it is more complex to implement deterministically.

The first implementation should prefer the uniform grid unless profiling shows
that cell duplication or pair-set allocation is a problem.

##### Complexity expectations

The grid does not guarantee a better worst-case bound. If all entries occupy the
same cells, candidate generation can still approach $O(n^2)$. In ordinary
spatially distributed scenes, the expected candidate count should be much lower
than the total pair count.

The optimization should report both values:

```text
total_pairs = n * (n - 1) / 2
candidate_pairs = unique pairs emitted by the broad phase
exact_tests = candidate pairs sent to polygon geometry
```

#### Python Step 4: Add a simple Python policy threshold

The accelerated Python candidate path should not be forced on tiny scenes if
its setup cost exceeds the saved pair work. A configurable policy can choose:

- all-pairs with exact tests for small entry counts;
- bounding-box or grid candidates for medium and large scenes; and
- `AverageDepthSorter` for an explicitly selected approximate-performance mode.

The threshold must be based on measured timings, not a guessed universal value.
It should be configurable on `OverlapDepthSorter` or `CpuRenderer3D` and
reported in diagnostics.

#### Python Step 5: Keep exact geometry and ordering in Python

The first implementation should leave `overlapping_polygon_depths()`, graph
construction, and heap-based topological ordering in Python. This makes the
optimized path easy to compare against the current implementation and avoids
changing correctness semantics while the broad phase is being validated.

#### Python Step 6: Add differential and performance tests

Run the original all-pairs sorter and each Python optimization against the same
projected entries. Verify identical ordered stable indices and cycle state,
then measure candidate and exact-test reduction. Test distributed scenes,
dense scenes, clipped polygons, billboards, and cyclic geometry.

### Cython-Required Path

The following work is optional and should begin only after the Python path has
reduced candidate counts and established a correct benchmark baseline. These
steps require a Cython build or another compiled extension strategy.

#### Cython Step 1: Pack projected entries into numeric buffers

After the Python broad phase is correct and measured, the candidate generation
and exact pair checks may be moved behind an optional Cython module.

The Cython boundary must not pass `ProjectedRenderEntry` objects through the
inner loop. Python object access, Python function calls, and Python set
operations inside the hot loop would preserve much of the current overhead.

##### Python-side packing

The renderer or sorter prepares compact data for each projected polygon:

- polygon vertex count;
- projected screen vertices;
- camera-space vertices;
- screen-space bounding box;
- average depth;
- stable index;
- optional flags for polygon eligibility.

The preferred representation is a set of contiguous arrays or typed memoryviews.
For example:

```text
screen_vertices: float64[entry, vertex, 2]
camera_vertices: float64[entry, vertex, 3]
vertex_counts: int32[entry]
bounds: float64[entry, 4]       # min_x, min_y, max_x, max_y
average_depth: float64[entry]
stable_indices: int32[entry]
```

Because entries may have different vertex counts, the implementation may use a
fixed maximum vertex width for the initial kernel or use flattened vertex arrays
plus offset/count arrays. The flattened representation is more general and
should be preferred if polygon sizes are expected to vary significantly.

##### Cython-side work

The accelerator should perform these operations without Python calls in the
inner loop:

1. broad-phase bounding-box rejection;
2. optional grid or sweep candidate generation;
3. convex polygon separation testing;
4. convex polygon intersection and overlap-area testing;
5. overlap sample calculation;
6. camera-space plane and ray depth calculation;
7. farther-to-nearer edge generation; and
8. deterministic topological ordering.

The result should be compact indices rather than Python entry objects:

```text
ordered_indices: int32[n]
cycle_detected: bool
candidate_pair_count: int
exact_test_count: int
accepted_edge_count: int
```

Python then maps `ordered_indices` back to the original
`ProjectedRenderEntry` tuple and constructs the existing `SortResult`.

##### Optional extension behavior

The Cython module must be optional. Import or build failure must select the pure
Python implementation without changing rendering behavior. The selected path
should be visible in diagnostics so performance comparisons are not ambiguous.

A possible internal shape is:

```python
try:
    from ._occlusion_kernel import sort_projected_polygons
except ImportError:
    sort_projected_polygons = None
```

The exact import and packaging mechanism should follow the repository's eventual
build system. This document does not require adding a build dependency before
the Python algorithm is validated.

#### Cython Step 2: Move the hot numeric loops into typed code

The compiled kernel may take ownership of:

1. bounding-box checks;
2. grid or sweep candidate generation;
3. convex polygon separation and clipping;
4. overlap-area and sample-depth calculations; and
5. ordering-edge generation.

It should not receive or return scene objects in the inner loop. Python should
pack once, call the kernel once, and map returned indices back to Python
entries once.

#### Cython Step 3: Decide whether topological sorting belongs in the kernel

Topological sorting can remain in Python initially. Moving it to Cython is
worthwhile only if profiling shows that graph traversal and Python set/heap
operations remain a significant part of total sort time after candidate
reduction. The graph algorithm is not automatically a Cython target merely
because the pair loop is expensive.

## Optimization Stages and Ownership

The earlier stages can be mapped directly to implementation ownership:

| Stage | Python possible | Requires Cython | Purpose |
| --- | --- | --- | --- |
| Baseline counters and timing | Yes | No | Establish cost model |
| Per-entry screen bounds | Yes | No | Avoid repeated bound calculation |
| All-pairs bounding-box rejection | Yes | No | Keep disjoint pairs out of exact geometry |
| Uniform screen-space grid | Yes | No | Reduce pairs visited by exact stage |
| Sweep-and-prune candidates | Yes | No | Alternative candidate generation |
| Small-scene policy threshold | Yes | No | Avoid acceleration setup overhead |
| Differential correctness tests | Yes | No | Protect ordering semantics |
| Packed flat numeric buffers | Yes, as preparation | No | Define stable kernel boundary |
| Typed numeric pair and geometry loop | No meaningful need | Yes | Reduce Python dispatch and object overhead |
| Typed topological sort | Not initially | Optional | Optimize only if profiling warrants it |

The central distinction is that bounding boxes and candidate generation are
algorithmic improvements available in Python. Cython is primarily a constant
factor optimization for the remaining numeric work; it does not by itself
change the $O(n^2)$ worst case.

## Correctness Requirements

### Conservative broad phase

The broad phase must never reject a pair whose projected polygons have a
non-empty overlap larger than the configured epsilon. False positives are
acceptable and continue to exact testing. False negatives are not acceptable.

### Determinism

For identical input entries and camera state, optimized and fallback paths must
produce the same order, except where an explicit approximate sorter is selected.
Candidate pair insertion order must not affect the result.

Use canonical pair keys and stable-index tie breakers. Do not rely on hash-set
iteration order for final ordering.

### Cycles

A cycle in the overlap graph must preserve the existing behavior: return
average-depth order and set `cycle_detected=True`. The optimization must not
silently drop the cycle diagnostic.

### Degenerate geometry

Pairs with fewer than three projected points, zero-area polygons, invalid
near-plane geometry, or parallel depth planes must be treated as non-ordering
pairs, matching the current exact helper behavior.

### Non-polygon entries

Lines, text, utility lines, preprojected background streams, and persistent
overlay streams must not enter polygon overlap testing. The renderer already
separates several of these categories before sorting; the optimized sorter must
retain those boundaries.

## Proposed Internal API

The public sorter API remains:

```python
class RenderSorter(Protocol):
    def sort(
        self,
        entries: Iterable[ProjectedRenderEntry],
        frame: FrameContext | None = None,
    ) -> SortResult: ...
```

The implementation may add private helpers such as:

```python
@dataclass(frozen=True)
class _ProjectedBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


def _screen_bounds(points: Sequence[Vec2]) -> _ProjectedBounds: ...


def _bounds_overlap(first: _ProjectedBounds, second: _ProjectedBounds) -> bool: ...


def _candidate_pairs(entries: Sequence[ProjectedRenderEntry]) -> Iterable[tuple[int, int]]: ...
```

A future Cython boundary may use a private packed-data API rather than these
Python structures. No application or scene object should need to know whether
the optimized path is active.

## Diagnostics and Profiling

`RenderStats` currently reports packet, clipping, projection, emission, and
cycle information. The performance work should add optional sorter diagnostics,
without forcing applications to display them.

Recommended fields:

```text
sort_entry_count
sort_total_pair_count
sort_candidate_pair_count
sort_exact_test_count
sort_accepted_edge_count
sort_duration_seconds
sort_backend              # python, cython, or other
```

If changing `RenderStats` is too disruptive, expose a separate immutable
`SortStats` object on the sorter or renderer. The values must be reset per
render, not accumulated indefinitely.

The benchmark should measure at least:

- static camera render;
- yaw-only camera changes;
- pitch-only camera changes;
- zoom changes;
- distributed map geometry;
- densely overlapping geometry; and
- cyclic or intentionally intersecting geometry.

Report median and high-percentile render time, not only a single timing. Also
report total pairs, candidates, exact tests, and cycles so a speedup can be
attributed to fewer tests rather than guessed.

## Testing Plan

### Unit tests

1. Disjoint rectangles are rejected by the bounding-box broad phase.
2. Touching or epsilon-overlapping rectangles are retained conservatively.
3. A polygon pair with overlapping bounding boxes still reaches exact testing.
4. Grid cell duplication produces one canonical candidate pair.
5. Non-polygon entries never reach polygon exact testing.
6. Stable indices produce deterministic ordering regardless of candidate order.
7. Cycles still fall back to average depth and set `cycle_detected=True`.
8. Degenerate polygons do not create invalid ordering edges.

### Differential tests

For generated convex polygon sets and fixed camera frames:

1. Run the current pure exact sorter.
2. Run the broad-phase sorter.
3. Compare ordered stable indices and cycle state.
4. Permit only differences already allowed by the existing depth epsilon and
   fallback semantics.

The differential suite should include boxes, billboards, tower-like meshes,
partially clipped polygons, coplanar faces, and intentionally intersecting
faces.

### Performance tests

Use deterministic scenes with increasing visible entry counts. At minimum test
roughly 32, 64, 128, 256, and 512 projected entries. Capture:

- total pair count;
- candidate pair count;
- exact test count; and
- elapsed sort time.

The broad phase should demonstrate a lower exact-test count for distributed
scenes while preserving correctness. Dense-overlap tests should make the
remaining worst-case behavior explicit rather than hiding it.

## Rollout Plan

### Python Phases

#### Phase A: Instrumentation

Add timing and pair counters around the existing `OverlapDepthSorter` without
changing its algorithm. Establish a baseline from the town demo and synthetic
scenes.

#### Phase B: Python bounding-box broad phase

Add precomputed projected bounds and reject disjoint pairs before
`overlapping_polygon_depths()`. Differential tests must pass before proceeding.

#### Phase C: Python candidate generation

Add a uniform screen-space grid or sweep-and-prune candidate generator. Keep a
configuration switch to compare all-pairs and accelerated candidate generation.

### Cython Phase

#### Phase D: Optional Cython kernel

Pack projected data into numeric arrays, implement the candidate and exact
geometry kernel, and retain the pure-Python fallback. Differential and
performance tests must run against both backends.

### Policy Phase

#### Phase E: Default policy review

After measurements, decide whether:

- overlap-aware ordering remains the default for small scenes;
- the broad-phase overlap sorter becomes the default generally;
- large scenes automatically use average-depth ordering; or
- applications receive an explicit quality/performance configuration.

No automatic policy should be introduced without diagnostics and a documented
face-count or candidate-count threshold.

## Risks and Tradeoffs

### Broad phase false negatives

Incorrect bounds or clipping assumptions could omit a real overlap and produce
wrong painter order. Bounds must be calculated from the final projected points,
not from unprojected world extents.

### Large polygon duplication

A grid inserts large polygons into many cells. A maximum-cell threshold or a
separate large-entry list may be needed. Large entries must still be compared
against every cell candidate to avoid missed overlaps.

### Memory allocation

Per-frame dictionaries, sets, and packed arrays can offset the geometry savings
for small scenes. The implementation should use the simplest broad phase that
measurably helps the target workload and keep a threshold below which the
current all-pairs path is cheaper.

### Cython packaging

An optional extension introduces build, interpreter, and platform concerns.
The renderer must remain usable from a source checkout with no compiler by
falling back to Python.

### Painter-order limitations

Acceleration improves speed, not the fundamental correctness limits of a
painter algorithm. Intersecting geometry can still form cycles and will still
use the existing average-depth fallback.

## Acceptance Criteria

The implementation is ready for renderer integration when:

1. Existing renderer and scene tests pass unchanged.
2. Differential tests show no new ordering or cycle-state mismatches.
3. Distributed scenes show a substantial reduction in exact polygon tests.
4. Yaw and pitch changes remain event-driven and do not require host changes.
5. The fallback path works without Cython installed.
6. Diagnostics identify backend, total pairs, candidate pairs, exact tests, and
   sort duration.
7. Dense scenes document their remaining worst-case behavior.
8. The public `RenderSorter` contract and stable ordering semantics remain
   unchanged.

## Suggested OpenSpec Change Scope

A future OpenSpec change can use this document as the design basis and split
implementation into these tasks:

### Python-first tasks

1. Instrument `OverlapDepthSorter` and add sorter diagnostics.
2. Add conservative screen-space bounds and differential tests.
3. Add a Python candidate-pair generator with a configuration switch.
4. Add renderer benchmarks for distributed and dense scenes.
5. Define packed numeric kernel data structures without requiring Cython.

### Later Cython tasks

6. Prototype the optional Cython kernel behind the same private interface.
7. Compare Python and Cython outputs and timings.

### Final policy task

8. Decide and document the default performance policy.
