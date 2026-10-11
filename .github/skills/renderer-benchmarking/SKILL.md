---
name: renderer-benchmarking
description: "Use when running, explaining, or interpreting benchmark_pipeline.py or benchmark_overlap_sort.py; profiling CPU renderer stages; comparing sweep-and-prune with all-pairs; investigating silent benchmark runs; or collecting repeatable rendering performance evidence."
---

# Renderer Benchmarking

## Choose the benchmark

These are opt-in, headless CPU benchmarks, not interactive profilers or GPU/display benchmarks.

| Question | Tool |
| --- | --- |
| Where does a synthetic scene rebuild spend its time? | [benchmark_pipeline.py](../../../Animation/ported_demos/benchmark_pipeline.py) |
| How do all-pairs and sweep-and-prune compare across overlap patterns? | [benchmark_overlap_sort.py](../../../Animation/ported_demos/benchmark_overlap_sort.py) |
| Does a sorter change preserve ordering on the benchmark inputs? | Overlap-sort benchmark: checks strategy agreement before timing |
| How does sorting behave on demo 11 at different camera angles? | Overlap-sort benchmark with `--include-target` |
| What is interactive town frame latency, GPU time, or display FPS? | Neither script answers this |

The pipeline runner uses the production collection, projection, sorter, line-occlusion, emission, and publication boundaries. The overlap runner isolates the complete sorter call on already-projected entries. It does not measure scene traversal, projection, line occlusion, or drawing-node creation.

## Safe execution workflow

1. Work from the repository root. Use the workspace interpreter; the commands below assume Windows PowerShell and `.\.venv\Scripts\python.exe`. Do not assume a global Python has DearCyGui.
2. If options may have changed, run each script with `--help` before constructing commands.
3. Begin with a smoke test unless the user explicitly requests an established longer run. A single sample verifies execution and report shape, not reliable performance.
4. Explain the expected scope and silent behavior before starting. In particular, do not casually launch the overlap runner's 100-sample defaults.
5. Run benchmarks sequentially, with no concurrent tests, builds, other benchmarks, or interactive rendering when collecting performance evidence. Concurrent activity makes results unsuitable as a clean baseline.
6. Store reports under the gitignored `profiling-output\` directory. Use distinct run subfolders or filenames to preserve comparisons; existing output files are overwritten.
7. Use a tracked long-running command with a generous wait. If it continues in the background, retain its session ID and retrieve its eventual result; do not launch duplicates because it is silent. Never terminate processes by name.
8. Verify the exit status and newly written reports. Check timestamps when reusing paths: old reports do not prove the latest run succeeded.
9. Report the exact command, interpreter, scope, samples, warmups, output location, workload counters, timing units, and limitations. Distinguish a smoke check from performance evidence.

No visible GUI is opened. The pipeline still creates real DearCyGui drawing nodes and publishes/deletes drawing layers; headless does not mean a mock backend or no DearCyGui dependency.

### Silent-run warning

Both scripts finish their benchmark work before creating their requested output directory and writing reports. Neither checkpoints completed fixtures.

- Pipeline: prints its median/P95 table only after the whole run finishes; JSON is written only with `--output`.
- Overlap-sort: prints no progress or completion table; writes JSON and Markdown only after all requested cases finish.
- Missing folders and no console output during execution are therefore expected, not proof of a hang.
- CPU activity alone is not proof of success either. Verify completion and report contents.
- An interruption or exception before report writing leaves no new report of completed fixtures. Do not describe partial work as a completed benchmark.

## Pipeline CLI

Entry point: [benchmark_pipeline.py](../../../Animation/ported_demos/benchmark_pipeline.py).

| Option | Default | Meaning |
| --- | --- | --- |
| `-h`, `--help` | N/A | Print usage and exit |
| `--counts N [N ...]` | `100 500 2000 10000` | Select from these four supported face counts |
| `--samples N` | `5` | Measured samples per count; must be at least 1 |
| `--warmups N` | `1` | Unmeasured rebuilds per count; must be nonnegative |
| `--strategy NAME` | `sweep_and_prune` | `sweep_and_prune` or `all_pairs`; one strategy per run |
| `--no-lines` | Off | Omit the eight fixture lines; does not omit polygons |
| `--output PATH` | None | JSON file path; parent directories created at completion |

The 10,000-face fixture rejects `all_pairs` to avoid materializing 49,995,000 candidate pairs. To compare strategies, explicitly select counts no greater than 2,000. Do not remove the guard to obtain a comparison.

### Commands

Small smoke test:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 --samples 1 --warmups 0 --output profiling-output\pipeline-smoke.json
```

All supported sizes, sweep-and-prune:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 500 2000 10000 --samples 5 --warmups 1 --output profiling-output\pipeline-sweep.json
```

Small paired strategy comparison; run sequentially and compare identical counts/settings:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 500 --samples 5 --warmups 1 --strategy sweep_and_prune --output profiling-output\pipeline-compare-sweep.json
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 500 --samples 5 --warmups 1 --strategy all_pairs --output profiling-output\pipeline-compare-all-pairs.json
```

### Fixture and workload checks

The fixtures contain valid world-space retained polygons, constructed to project into predictable screen-space overlap groups. Pair counts are computed by the real sorter, not injected.

- Four mutually overlapping quads per cell; cells are separated.
- Fixed 4096 x 4096 viewport and zero-yaw/zero-pitch camera.
- Depths within a cell: 80, 100, 120, 140.
- All scaling-fixture faces survive projection; these runs do not stress clipping.
- Eight world lines, unless disabled, each yield two visible fragments.

For face count `F` and line count `L` (8 or 0), expected counters are:

| Counter | Expected |
| --- | --- |
| `packet_count`, `projected_count` | `F + L` |
| `polygon_count` | `F` |
| `clipped_count` | `0` |
| `possible_polygon_pairs` | `F * (F - 1) / 2` |
| Sweep `candidate_pairs`, `exact_tests` | `3 * F / 2` |
| All-pairs `candidate_pairs`, `exact_tests` | `F * (F - 1) / 2` |
| `accepted_edges` | `3 * F / 2` |
| `cycle_detected` | `false` |
| `line_fragments` | `2 * L` |
| `emitted_count` | `1 + F + 2 * L` (includes background) |

Sweep candidate counts for 100/500/2,000/10,000 faces are 150/750/3,000/15,000. The runner validates expected counters and repeat consistency outside the timed region. A mismatch is a failed workload validation, not a usable speed result.

### Read the pipeline report

JSON contains:

- `metadata`: schema/fixture versions, nanosecond timing unit, interpreter, platform, GC state, sample/warmup counts, camera, viewport, and measurement scope.
- `rows`: one record per face count/sample, including `strategy`, `durations_ns`, and `counters`.
- `summary`: per-count/per-stage `median_ms` and `p95_ms`.

| Stage | Work included |
| --- | --- |
| `scene_collection` | Materialized scene traversal and packet collection |
| `projection_clipping` | Projection and clipping/rejection |
| `broad_phase` | Candidate-pair generation |
| `exact_tests` | Exact overlap/depth tests producing ordering constraints |
| `topological_ordering` | Graph construction, ordering, and cycle fallback |
| `line_occlusion` | Visible line-fragment preparation |
| `node_creation` | Emission, including background and prepared geometry; emission also clears its target |
| `back_layer_cleanup` | Preparing/clearing the hidden drawing layer before rebuilding |
| `publication_cleanup` | Publishing the new layer and deleting obsolete nodes |
| `total_rebuild` | Full measured interval through publication/cleanup |
| `unaccounted` | Total minus the sum of the nine exclusive stages |

Timing uses `perf_counter_ns()` and rejects nested regions. Never add inclusive sorter time on top of the exclusive sorting stages. The accounting identity applies per sample; the sum of stage medians need not equal the median total.

Setup, fixture construction, warmups, validation, report construction, and file I/O are excluded. Even with zero warmups, a frame is seeded before measuring so publication cleans up a populated obsolete frame.

The runner retains intermediate results and orchestrates a polygon-and-line workload. It is not an uninstrumented latency baseline and does not exercise all normal-rendering branches, such as persistent overlays and background streams.

## Overlap-sort CLI

Entry point: [benchmark_overlap_sort.py](../../../Animation/ported_demos/benchmark_overlap_sort.py).

| Option | Default | Meaning |
| --- | --- | --- |
| `-h`, `--help` | N/A | Print usage and exit |
| `--samples N` | `100` | Measured sorts per strategy per fixture |
| `--warmup N` | `5` | Warmup sorts per strategy per fixture; singular spelling |
| `--include-target` | Off | Add demo 11 at 12 camera orientations |
| `--output-dir PATH` | Required | Directory for JSON and Markdown reports |

Use positive sample counts and nonnegative warmups; do not rely on this older runner to reject invalid values cleanly. There is no CLI count selector, fixture selector, or strategy selector: every run includes all synthetic cases and both strategies, even though sweep is the framework default.

### Commands and runtime expectations

Smoke test, all 20 synthetic cases, no target scene:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_overlap_sort.py --samples 1 --warmup 0 --output-dir profiling-output\overlap-sort-smoke
```

Add target-scene coverage with the same reduced sampling:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_overlap_sort.py --samples 1 --warmup 0 --include-target --output-dir profiling-output\overlap-sort-target-smoke
```

Deliberate long comparison run, only after agreeing the runtime budget:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_overlap_sort.py --samples 100 --warmup 5 --include-target --output-dir profiling-output\overlap-sort-full
```

Even the smoke test is not instantaneous: each fixture runs an initial correctness sort for each strategy in addition to measured sorts. With `S` samples and `W` warmups, each fixture performs `2 * (1 + W + S)` sort calls.

The dense 512-polygon fixture has 130,816 overlapping pairs for each strategy. One local smoke run measured about 4.7 seconds per sort; at that rate, defaults take roughly 16-17 minutes for this fixture alone, before other fixtures and target views. This is an illustrative observation, not a runtime guarantee or formal baseline. Measure on the current machine before extrapolating.

### Workloads

All synthetic arrangements use 32, 64, 128, 256, and 512 polygons: 4 arrangements x 5 sizes = 20 cases.

| Fixture prefix | Purpose |
| --- | --- |
| `distributed` | Groups of four overlapping polygons, separated across the screen |
| `x_separated` | Early rejection along the sweep axis |
| `y_separated` | X-active pairs rejected by Y bounds; exposes active-set overhead |
| `dense` | All polygons overlap; pruning cannot eliminate genuine candidate pairs |

With `--include-target`, geometry comes from [demo 11](../../../Animation/ported_demos/11_dearcygui_cpu_3d_map.py), not the hot-reload town world. It is collected/projected before timing at yaw 0/45/90/135 and pitch 25/55/80 degrees. This adds 12 cases, for 32 total. It measures repeated sorting of fixed projected geometry, not a moving-camera frame loop.

### Read the overlap-sort reports

The output directory contains:

- `overlap_sort_benchmark.md`: fixture/strategy rows with exact-test counts and median/P95 milliseconds.
- `overlap_sort_benchmark.json`: fixture version, Python version, sample/warmup settings, and `results`.
- Each result includes `fixture_id`, `sample_count`, `raw_samples`, and `summary` keyed by strategy.
- Each raw sample has `outer_duration_ns` and `sort_stats`. `sort_stats.sort_duration_seconds` is an inner, inclusive measurement in seconds; do not add it to the outer duration.
- Summary `counters` come from the first sample, including that sample's inner duration; this duration is not a median.

Before warmups, the runner compares both strategies' stable-index output order and cycle flag. It alternates timing order in blocks of five samples, and checks structural counter consistency across samples. This is finite-input differential coverage, not a proof of equivalence for every scene.

Interpret sorter counters:

- `possible_polygon_pair_count`: all possible polygon pairs.
- `x_active_pair_count`: pairs active along X; a large value can explain broad-phase work even if Y rejects most pairs.
- `bounds_candidate_pair_count`: candidates passed to exact testing.
- `exact_test_count`: pair tests actually executed.
- `accepted_edge_count`: distinct ordering constraints, not necessarily the number of geometric overlaps (equal-depth pairs may add no edge).
- `cycle_detected`: ordering required fallback; do not equate fallback output with a fully satisfied dependency graph.

Compare the two strategies within the same fixture. Speedup is `all_pairs median / sweep median`; greater than 1 favors sweep. Candidate reduction and elapsed-time reduction are different metrics. Dense cases may show little benefit or overhead because pruning cannot reduce the pair set.

## Interpretation and reporting rules

- Both scripts use nearest-rank P95: sorted sample at `ceil(0.95 * N) - 1`. With one sample median and P95 are identical; with five samples P95 is the maximum. Small-sample P95 is not strong tail-latency evidence.
- These are elapsed wall-clock timings of CPU-side work, not CPU utilization or hardware cycle counts.
- Compare matching fixture versions, counts, strategies, camera settings, line settings, interpreter, and machine conditions. Record revision and exact command separately; reports do not automatically capture every provenance detail.
- Do not compare absolute milliseconds across the two runners as if their geometry, sizes, and measured scope were identical.
- For the pipeline, identify the largest stages and inspect per-sample fractions of total time. If emission dominates, faster projection alone has limited potential benefit.
- For the sorter, inspect pruning effectiveness and dense-case behavior, not just the fastest sparse case.
- A successful smoke run proves execution and the runner's checked invariants only. Do not claim reliable performance gates, instrumentation overhead budgets, interactive-town speedups, or a justified CUDA/Taichi/Cython choice from it.
- Do not promise a duration, claim a command was tested, or report success without direct evidence. On failure, retain the exact error and distinguish it from normal silent execution.
- Keep generated reports out of version control unless explicitly requested. See [README profiling guidance](../../../README.md) and [.gitignore](../../../.gitignore).
