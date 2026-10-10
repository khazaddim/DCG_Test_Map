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
explicitly for large fixtures; **the production sorter default is unchanged**.
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
