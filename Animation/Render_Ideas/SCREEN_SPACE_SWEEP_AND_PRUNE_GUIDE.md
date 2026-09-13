# Screen-Space Sweep-and-Prune Guide

## Purpose

This guide describes a focused first Python optimization for
`OverlapDepthSorter`: **screen-space sweep-and-prune with cached AABBs**.

The goal is to reduce how many polygon pairs reach the expensive exact overlap
and depth calculations while preserving the current painter-ordering behavior.
It requires no Cython extension and no public renderer API change.

## Terminology

### Screen space

Screen space is the two-dimensional coordinate system after world geometry has
been transformed by the camera and projected into the viewport.

A world-space point such as `(100, 125, 34)` becomes a screen-space point such
as `(612, 248)`. `ProjectedRenderEntry.points` already contains these projected
2D points.

The broad phase should use these final projected points because two objects only
need an occlusion relationship when their visible screen projections overlap.
World-space distance alone does not answer that question reliably under camera
rotation and perspective.

### AABB

**AABB** means **axis-aligned bounding box**. The plural is **AABBs**.

For a projected polygon, its screen-space AABB is the smallest rectangle aligned
with the screen's x and y axes that contains every polygon vertex:

```text
min_x = minimum x coordinate
min_y = minimum y coordinate
max_x = maximum x coordinate
max_y = maximum y coordinate
```

For example, a projected triangle with points:

```text
(10, 20), (30, 15), (25, 40)
```

has this AABB:

```text
min_x = 10
min_y = 15
max_x = 30
max_y = 40
```

An AABB is cheaper to compare than the polygon it surrounds. If two AABBs are
disjoint, their polygons cannot overlap. If two AABBs overlap, their polygons
might overlap, so the existing exact polygon test is still required.

```text
AABB overlap is necessary for polygon overlap, but it is not sufficient.
```

This makes AABBs a conservative broad-phase filter:

- false positives are allowed and continue to exact testing;
- false negatives are not allowed because they could produce incorrect draw
  order.

### Cached AABBs

"Cached" means each entry's AABB is calculated once per sort operation and
stored for reuse.

Without caching, calculating bounds inside the nested pair loop repeatedly
scans the same polygon vertices. With caching, each polygon's points are scanned
once, and pair checks compare four stored numbers.

The cache is per rendered frame because camera yaw, pitch, zoom, clipping, and
viewport size can change projected points.

### Sweep-and-prune

Sweep-and-prune is a broad-phase candidate-generation algorithm.

1. Sort polygon AABBs by their left edge, `min_x`.
2. Sweep from left to right across the screen.
3. Keep an active collection of earlier AABBs whose right edge, `max_x`, still
   reaches the current AABB.
4. Remove active AABBs that end before the current AABB begins.
5. Compare the current AABB only with the remaining active AABBs.
6. Reject active candidates whose y intervals do not overlap.
7. Send only x-and-y-overlapping candidates to the existing exact polygon test.

"Prune" refers to removing entries that can no longer overlap anything farther
to the right.

## Why This Reduces Pair Work

The current sorter visits every unordered pair. For `n` entries, that is:

$$
\frac{n(n-1)}{2}
$$

With sweep-and-prune, entries separated along the x axis never become candidate
pairs. Entries overlapping in x but separated in y are rejected by the cheap y
interval check. Only entries whose AABBs overlap on both axes reach
`overlapping_polygon_depths()`.

The expected cost for spatially distributed geometry is approximately:

$$
O(n \log n + k)
$$

where sorting costs $O(n \log n)$ and $k$ is the number of pairs active during
the sweep. The exact geometry cost depends on the smaller set of candidates
whose x and y bounds overlap.

The worst case remains $O(n^2)$. If every projected polygon spans most of the
viewport, every AABB remains active and overlaps in y. This optimization is
intended to improve common map scenes, not eliminate the dense-overlap worst
case.

## Relationship to the Existing Exact Test

Sweep-and-prune does not replace:

- `convex_screen_polygons_overlap()`;
- `_convex_polygon_intersection()`;
- overlap-area testing;
- `ray_plane_depth()`; or
- ordering-edge construction.

It changes only which pairs are sent to those operations.

```text
projected polygons
    -> cached screen-space AABBs
    -> sweep by min_x
    -> prune separated x intervals
    -> reject separated y intervals
    -> existing exact polygon overlap/depth test
    -> existing ordering graph
    -> existing topological sort
```

## Recommended First Implementation

### Bounds representation

Use a private immutable tuple or dataclass:

```python
@dataclass(frozen=True)
class _ScreenBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
```

Calculate one bound per polygon entry:

```python
def _screen_bounds(points: Sequence[Vec2]) -> _ScreenBounds:
    first_x, first_y = points[0]
    min_x = max_x = first_x
    min_y = max_y = first_y
    for x, y in points[1:]:
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
    return _ScreenBounds(min_x, min_y, max_x, max_y)
```

Entries with fewer than three points should not enter polygon candidate
generation.

### Candidate generation

The initial implementation can use a Python list for the active collection:

```python
def _sweep_candidate_pairs(
    entries: Sequence[ProjectedRenderEntry],
) -> Iterable[tuple[int, int]]:
    polygon_indices = [
        index
        for index, entry in enumerate(entries)
        if entry.kind == "polygon" and len(entry.points) >= 3
    ]
    bounds = {
        index: _screen_bounds(entries[index].points)
        for index in polygon_indices
    }
    sweep_order = sorted(
        polygon_indices,
        key=lambda index: (bounds[index].min_x, index),
    )

    active: list[int] = []
    for current_index in sweep_order:
        current = bounds[current_index]
        active = [
            other_index
            for other_index in active
            if bounds[other_index].max_x >= current.min_x
        ]

        for other_index in active:
            other = bounds[other_index]
            if current.max_y < other.min_y or other.max_y < current.min_y:
                continue
            yield min(other_index, current_index), max(other_index, current_index)

        active.append(current_index)
```

The canonical `(smaller_index, larger_index)` result makes pair identity clear
and deterministic. This implementation naturally emits each pair once because
each current entry is compared only with earlier active entries.

### Exact testing and graph construction

Replace only the nested all-pairs loop in `OverlapDepthSorter.sort()`:

```python
for first_index, second_index in _sweep_candidate_pairs(ordered_entries):
    depths = overlapping_polygon_depths(
        ordered_entries[first_index],
        ordered_entries[second_index],
        frame,
        overlap_area_epsilon=self.overlap_area_epsilon,
    )
    if depths is None or abs(depths[0] - depths[1]) <= self.depth_epsilon:
        continue

    farther = first_index if depths[0] > depths[1] else second_index
    nearer = second_index if farther == first_index else first_index
    if nearer not in successors[farther]:
        successors[farther].add(nearer)
        indegree[nearer] += 1
```

The existing graph, heap-based topological sort, stable-index tie breaking, and
cycle fallback remain unchanged.

## Boundary and Epsilon Rules

A first implementation should treat touching AABBs as candidates. Use strict
separation checks:

```text
first.max_x < second.min_x
first.max_y < second.min_y
```

Do not use `<=` for separation, because shared boundaries may correspond to
real polygon contact after floating-point projection.

If projection noise later causes a demonstrated false rejection, introduce a
separate screen-space bounds tolerance:

```text
first.max_x + bounds_epsilon < second.min_x
```

Do not reuse `overlap_area_epsilon` or `depth_epsilon`:

- `bounds_epsilon` would be a linear screen-coordinate distance;
- `overlap_area_epsilon` is an area in squared screen units; and
- `depth_epsilon` is a camera-depth difference.

These quantities have different units and meanings.

## Metrics to Add First

Instrumentation should be added before changing candidate generation. Record
these values per sort:

```text
sort_entry_count
polygon_entry_count
possible_polygon_pair_count
x_active_pair_count
bounds_candidate_pair_count
exact_test_count
accepted_edge_count
cycle_detected
sort_duration_seconds
candidate_strategy              # all_pairs or sweep_and_prune
```

Definitions:

- `sort_entry_count`: all entries passed to the sorter.
- `polygon_entry_count`: entries eligible for polygon overlap testing.
- `possible_polygon_pair_count`: $p(p-1)/2$, where `p` is polygon entry count.
- `x_active_pair_count`: pairs compared after x-axis pruning.
- `bounds_candidate_pair_count`: pairs overlapping on both x and y.
- `exact_test_count`: calls to `overlapping_polygon_depths()`.
- `accepted_edge_count`: unique farther-to-nearer edges added to the graph.

For this strategy, `bounds_candidate_pair_count` and `exact_test_count` should
normally match. Keeping both counters makes later filters measurable.

## Correctness Requirements

1. Every pair accepted by the old all-pairs sorter must either:
   - be rejected only because its AABBs are provably disjoint; or
   - reach the unchanged exact overlap/depth function.
2. The optimized and baseline sorters must return identical stable-index order
   and identical `cycle_detected` state for the same entries and frame.
3. Candidate enumeration must be deterministic.
4. Non-polygon entries must remain in the final ordering input where required,
   but must not enter polygon overlap testing.
5. The existing `frame is None` fallback to `AverageDepthSorter` must remain
   unchanged.
6. Degenerate projected polygons must not create candidates or ordering edges.

## Testing Plan

### Unit tests

1. Two x-separated AABBs produce no candidate pair.
2. Two x-overlapping but y-separated AABBs produce no candidate pair.
3. Two AABBs overlapping on both axes produce one candidate pair.
4. Touching AABBs remain candidates.
5. Three mutually overlapping AABBs produce exactly three unique pairs.
6. Sweep order remains deterministic when `min_x` values are equal.
7. Non-polygon and degenerate entries are excluded from candidate generation.

### Differential tests

Run the existing all-pairs implementation and sweep-and-prune implementation on
the same data. Compare:

- ordered stable indices;
- cycle state;
- accepted graph edges, when exposed; and
- exact overlap/depth results for every sweep candidate.

Include:

- spread-out boxes;
- overlapping houses and tower meshes;
- camera-facing billboards;
- near-plane and viewport-clipped polygons;
- coplanar faces;
- equal-depth faces;
- cyclic/intersecting geometry; and
- randomized convex polygons with deterministic seeds.

### Performance tests

Measure at least 32, 64, 128, 256, and 512 projected polygons in two scene
families:

- **distributed:** small polygons spread across the viewport;
- **dense:** large polygons overlapping much of the viewport.

Report median and 95th-percentile sort duration together with all pair counters.
The distributed fixture should show a meaningful drop in exact tests. The dense
fixture should document the remaining worst case.

Do not select a permanent strategy threshold until these measurements exist.

## Suggested Rollout

1. Add metrics to the unchanged all-pairs implementation.
2. Add `_ScreenBounds` and unit tests.
3. Add `_sweep_candidate_pairs()` and candidate tests.
4. Add a private strategy switch for differential testing.
5. Run baseline and sweep implementations against identical fixtures.
6. Make sweep-and-prune the overlap sorter's default only if correctness tests
   match and target-scene yaw/pitch latency improves.
7. Keep all-pairs temporarily available as a reference path.
8. Consider a more advanced active structure, a grid, or Cython only after
   profiling the simple Python implementation.

## Expected Outcome

For the town-style scene, most small projected building faces should occupy
limited screen regions. Sweep-and-prune should prevent widely separated faces
from reaching exact overlap tests, improving yaw and pitch responsiveness.

The implementation remains pure Python, retains exact overlap-aware ordering
for candidate pairs, and provides a measured baseline for deciding whether a
later grid, compiled kernel, or approximate sorter is necessary.
