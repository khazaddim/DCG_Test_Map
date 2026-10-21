# DCG_Test_Map

Testing a zooming tabletop game map with my DearCyGui fork.

## Repo layout

- `Demos/` is a git submodule pointing at `https://github.com/khazaddim/Demos.git`
- `examples/` contains small standalone DearCyGui scripts focused on drawing containers

Initialize the submodule after cloning:

```bash
git submodule update --init --recursive
```

## Running the examples

These examples are meant to be used with your DearCyGui fork, including the branch
that contains your multi-controller work.

```bash
python /absolute/path/to/examples/01_draw_in_window_world.py
python /absolute/path/to/examples/02_draw_in_plot_zoom_levels.py
python /absolute/path/to/examples/03_draw_stream_animation.py
python /absolute/path/to/examples/04_draw_stream_arrow_keys.py
python /absolute/path/to/examples/05_drawing_scale_basics.py
python /absolute/path/to/examples/06_pan_camera_edge_band.py
python /absolute/path/to/examples/07_pan_camera_perspective_tilt.py
python /absolute/path/to/examples/08_Camera_tilt_simple.py
python /absolute/path/to/examples/09_pan_camera_perspective_fullscreen.py
python /absolute/path/to/examples/10_pan_camera_perspective_rotation.py
python /absolute/path/to/examples/11_dearcygui_cpu_3d_map.py
```

## What the examples cover

- `01_draw_in_window_world.py` explores `DrawInWindow`, `DrawingScale`, and `DrawingList`
- `02_draw_in_plot_zoom_levels.py` explores `DrawInPlot`, `DrawingClip`, and zoom-based culling
- `03_draw_stream_animation.py` explores `DrawStream` for frame-based character animation
- `04_draw_stream_arrow_keys.py` explores `DrawStream` plus `KeyDownHandler`-driven movement
- `05_drawing_scale_basics.py` explores `DrawingScale` transform fundamentals (`origin` + `scales`)
- `06_pan_camera_edge_band.py` explores camera panning with edge-band/dead-zone behavior
- `07_pan_camera_perspective_tilt.py` introduces projective tilt and source-space clipping
- `08_Camera_tilt_simple.py` isolates the basic rectangle-to-trapezoid transform
- `09_pan_camera_perspective_fullscreen.py` fills the viewport and reveals more world depth with inclination
- `10_pan_camera_perspective_rotation.py` combines centered inclination, world rotation, inverse-projected camera tracking, and flicker-free double buffering
- `11_dearcygui_cpu_3d_map.py` implements a true CPU-side 3D camera, raised box meshes, clipping, culling, shading, and painter-sorted faces using only DearCyGui drawing primitives

## Perspective map learning path

Start with `05` for affine coordinates, then read `07`, `09`, and `10` in that
order. Demo `10` contains a ground-up lesson in its module docstring and is the
canonical reference for a rotating game map with moving pieces.

The central lessons are:

1. Keep game state in world space and convert it to source and screen space only
	for drawing or screen interaction.
2. Transform order matters. Rotate the world around the camera focus before
	applying camera scaling and perspective.
3. Inclination and rotation must share one central anchor. Normalize the
	homography scale there to avoid focus drift and rotation-dependent stretching.
4. Clip geometry in source space before applying the homography.
5. Never clear and rebuild the visible projected layer. Build a hidden back
	layer, then swap complete layers under their common parent mutex. This avoids
	intermittent black frames from rendering a partially rebuilt scene.

The repository-local
[`dcg-perspective-map-patterns`](.github/skills/perspective_map_patterns/SKILL.md)
skill contains the reusable formulas, implementation patterns, anti-patterns,
and cheap numerical validation checks behind these demos.

Demo `11` is the next architectural step when map objects need real height. It
stores geometry as `(x, y, z)`, projects it through a pinhole camera, and gives
DearCyGui the resulting 2D faces. Its painter ordering is intended for separated
convex tabletop objects; intersecting meshes would require face splitting or a
renderer with a per-pixel depth buffer.

For the larger reference demo, inspect `Demos/main_demo/drawings.py`.

## Interactive town CPU profiling

Run the [profiling town](Animation/ported_demos/town_hot_reload_profiling.py):

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\town_hot_reload_profiling.py
```

It reuses the [original host](Animation/ported_demos/town_hot_reload.py) and
[world module](Animation/ported_demos/town_hot_reload_world.py); the original
host still starts without instrumentation. Both retain yaw/pitch/zoom sliders,
arrow-key movement, terrain following, reset, and the startup
`USE_SWEEP_AND_PRUNE` switch. Move/resize the profiling window as needed.

### Comparing world features

Edit world constants, save, and press **Reload world**. Existing feature flags
are retained. New independently editable switches default to `True`:

| Switch | What it removes when false |
| --- | --- |
| `HOUSES_ENABLED` | House walls/roofs and their collision blockers |
| `ROAD_ENABLED` | Road geometry; independent of `ROAD_TEXTURE_ENABLED` |
| `FLAT_GRID_ENABLED` | Flat utility grid lines |
| `HILL_GRID_ENABLED` | Hill grid lines, not the hill mesh or support surface |
| `BORDER_ENABLED` | Decorative border, not world movement bounds |
| `MESH_EDGES_ENABLED` | Explicit mesh-edge overlays, not meshes or material face outlines |
| `WINDMILL_ENABLED` | Animated tower billboard and its textures, not the tower |

`HILL_ENABLED` controls geometry and support; `TERRAIN_FOLLOWING_ENABLED`
controls traversal policy. Effective flags show dependent features as off when
their parent is absent (for example, no tower means no windmill). The ground and
controllable avatar remain present. Road geometry is decorative and retains its
original non-blocking, non-support collision behavior.

Reload reads fresh source into an isolated candidate module, then builds
resources, scene, collisions, terrain, traversal settings, avatar support, and
configuration before replacing active references. The active module retains its
textures. A failed candidate leaves the previous module, world, resources,
configuration, and measurement history intact, with a visible error and traceback.
The panel displays the last successful configuration and scene generation.

### Panel and timing semantics

- **Enable / disable telemetry** starts/stops recording; disabled is the default.
  **Pause / resume** suspends sampling without changing scene interaction.
  Both preserve existing samples. **Reset** clears samples and failure diagnostics,
  not the scene or a running detailed capture.
- The rolling window contains the last **120 successful published rebuilds**,
  not GUI frames. Idle frames add nothing; instrumented failures increment a
  separate counter and preserve the last published frame.
- Bars rank exclusive stage means; values are latest/mean/P95 **milliseconds**.
  P95 uses nearest rank, `sorted[ceil(0.95 * N) - 1]`. Skipped stages are zero.
  Total spans back-layer preparation through publication/obsolete-node cleanup.
  `unaccounted = total - sum(exclusive stages)` includes orchestration overhead.
  Sorting stages are not counted again as an inclusive parent duration.
- Collection, projection/clipping, broad phase, exact tests, ordering, line
  occlusion, node creation, and both cleanup regions are measured on the real
  rendering path, including streams and persistent overlay synchronization.
  For average/custom sorters, the complete sort is charged to ordering and the
  overlap-specific regions remain zero. Counters retain `RenderStats` semantics:
  projected count excludes utility/background/persistent-overlay entries routed
  around sorting; emitted count includes the background and regular draw nodes,
  but not persistent-overlay nodes managed separately.
- Successful reloads reset the window. Changes in viewport size, strategy, or
  baseline/capture mode start a new window at the next successful sampled rebuild.
  Ordinary camera rotations and movement stay in one window; camera, viewport,
  strategy, effective flags, configuration hash, and generation accompany each sample.
- The panel refreshes at most **5 Hz**, outside rebuild timing. Its previous update
  cost is displayed separately. Controls only change state or enqueue actions;
  panel updates never invalidate the scene or force an extra render.

### Detailed captures and exports

**Start capture** / **Stop and save** records `cProfile` only while executing
actual rebuilds on the render thread. It excludes idle waits, panel refreshes,
world/resource construction, and file writing. It works independently of telemetry
enable/pause; telemetry sampled during capture is marked `cprofile`, never mixed
with baseline samples. Closing the host attempts to save any pending capture.
An empty capture reports that no rebuilds occurred instead of creating an invalid
profile. Save failures remain visible and retain capture data for retry; shutdown
errors also print a traceback.

Files are written with unique names under gitignored `profiling-output\town\`:

- **Export JSON:** schema version 1, integer nanosecond durations, bounded raw
  samples, workload counters, failure diagnostics, and configuration context.
- **Export CSV:** one successful sample per row, schema version and units in
  each row, stage-duration columns, and JSON-encoded camera/viewport/flags/counters
  cells. An empty window produces a header-only CSV.
- **Detailed `.prof`:** readable by `pstats` and SnakeViz, whose timing units
  are seconds. The adjacent `.prof.json` includes schema, render-thread ID,
  total attempt count, and the last 120 attempt contexts (including failures,
  workload counters on success, and an explicit omitted-context count).
  The profile aggregates the entire capture even when context history is bounded.

With SnakeViz installed in the chosen environment:

```powershell
.\.venv\Scripts\python.exe -m snakeviz profiling-output\town\<capture-name>.prof
```

For reproducible comparisons, fix viewport dimensions and sorter; use reset
and the same camera path (for example yaw 0/30/60/90, pitch 35/52/65, zoom 3.5).
Change one feature, reload, warm up once, reset telemetry, and replay the same
path. Keep initial/reload resource setup and detailed captures out of baseline
latency comparisons. Compare counters as well as durations. These are CPU-side
elapsed timings including synchronous native calls, **not GPU timings or
time-to-display**. Automated correctness tests do not establish an instrumentation
overhead budget or representative performance evidence; those remain separate
Milestone 5.5 validation/evidence tasks.

## CPU 3D pipeline profiling fixtures

The opt-in [pipeline benchmark](Animation/ported_demos/benchmark_pipeline.py)
measures the pure-Python framework's stages separately, including real DearCyGui
node creation and atomic publication. It constructs drawing lists on the calling
thread without opening a viewport or running a display/event loop.

From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 500 2000 10000 --samples 5 --warmups 1 --output profiling-output\pipeline.json
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 500 --strategy all_pairs --output profiling-output\all-pairs.json
```

The runner prints per-stage median/P95 milliseconds and optionally writes JSON
with raw integer nanoseconds, counters, camera, viewport, interpreter, platform,
GC policy, sample/warmup counts, and fixture/schema versions. P95 is nearest-rank:
sort the samples and select `ceil(0.95 * N) - 1`. Five samples are a smoke run,
not a statistically strong baseline; use more samples and fresh processes for
performance conclusions. Errors abort the run with an explicit exception; failed
rebuilds are never serialized as successful measurements.

### Repeatable workloads

`build_fixture()` creates exactly **100, 500, 2000, or 10000 polygon faces**,
one retained `Polygon3D` per face. These are not box counts or mesh-vertex counts.
Four 24-by-24 screen-pixel quads per cell overlap locally, offset by six pixels
at camera depths 80/100/120/140. Cells have 64-pixel spacing in a fixed
4096-by-4096 viewport with zero yaw/pitch. The existing screen-plane fixture
helper is reused to construct perspective-consistent world geometry.

Every face survives projection. Each four-face cell produces six exact ordering
edges, so sweep-and-prune must produce `1.5 * face_count` candidates and edges.
Eight retained world lines at depth 160 cross the first eight cells; each is
partly hidden by solid faces and leaves two visible fragments. `--no-lines`
removes these lines without changing the faces. This isolates linework cost
without presenting an empty line-occlusion workload as representative.

The all-pairs option preserves the production comparison path, but the runner
rejects it at 10000 faces (49,995,000 materialized pairs). Sweep is selected
for fixtures and is also the default for `OverlapDepthSorter()` and the default
`CpuRenderer3D`. The town and collision diagnostic hosts enable their startup
`USE_SWEEP_AND_PRUNE` switches by default. To opt out, construct
`OverlapDepthSorter(use_sweep_and_prune=False)` or set the host's switch to
`False`. Explicit all-pairs regression tests and comparison benchmarks remain.
The [existing sorting benchmark](Animation/ported_demos/benchmark_overlap_sort.py)
remains the source for dense, separated, and other worst-case sort workloads.
The new [stage tests](tests/test_draw_in_window_3d_milestone5_5.py) also exercise
near-plane and viewport clipping, complete rejection, and cyclic graph fallback.
The all-visible scaling fixture alone is not a clipping-heavy or dense-scene
performance claim.

### Callable stages and timing accounting

| Region | Callable boundary |
| --- | --- |
| Retained traversal and packet construction | `CpuRenderer3D.collect_packets` |
| Projection, clipping, material resolution | `CpuRenderer3D.project_packets` |
| Bounds and selected candidate generation | `OverlapDepthSorter.generate_candidates` |
| Polygon intersection, ray-plane depths, directed constraints | `OverlapDepthSorter.test_overlaps` |
| Graph allocation, edge deduplication, heap sort, cycle fallback | `OverlapDepthSorter.order_entries` |
| Line/face tests and visible-fragment preparation | `CpuRenderer3D.prepare_line_occlusion` |
| DCG nodes, background, and optional persistent overlays | `CpuRenderer3D.emit_entries` |
| Hidden-layer preparation | `FramePublisher.prepare_back_layer` |
| Mutex-protected swap and obsolete-node deletion | `FramePublisher.publish_back_layer` |

These are the same boundaries used by the normal renderer/publisher, and can be
called independently with prepared inputs. Collection and projection return
materialized values: timing generator creation alone would omit the real work.
Emission consumes precomputed line fragments and does not repeat occlusion.
Existing rendering order, utility-line bypass, streams, and render statistics
are preserved.

`measure_fixture()` runs those boundaries sequentially for the synthetic solid
polygon/world-line workload. `total_rebuild` starts before hidden-layer
preparation and ends after publication and obsolete-node cleanup. Scene/resource
construction, context allocation, initial frame seeding, warmups, reporting, and
file writing are outside measured samples. One initial frame is always seeded,
even with zero warmups, so publication measures deletion of a populated old
frame rather than an empty startup layer.

All stage durations are exclusive. `unaccounted = total_rebuild - sum(stages)`
retains orchestration, timing-dispatch, and other gaps instead of attributing
them to numeric kernels. Uncalled regions are zero; invoked regions include
their real work even for empty inputs. The three DCG regions may be summed for
comparison, but that aggregate must not be added again to the stage total.
Likewise, inclusive `SortStats.sort_duration_seconds` is **not** another
exclusive stage. The measurement helper rejects nested regions.

These are CPU elapsed times, including synchronous native DCG calls, not GPU
execution or time-to-display. The staged fixture retains intermediate outputs
for validation; it is not an uninstrumented town-host latency baseline. Actual
rebuild telemetry, interactive panels, detailed captures, overhead budgets, and
town comparison evidence remain later Milestone 5.5 tasks.
