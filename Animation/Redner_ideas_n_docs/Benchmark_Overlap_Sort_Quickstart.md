# Overlap-sort benchmark quickstart

**Question it answers:** How do all-pairs and sweep-and-prune compare across
different overlap patterns?

[benchmark_overlap_sort.py](../ported_demos/benchmark_overlap_sort.py) runs
headlessly and times sorting of already-projected geometry. It does not time
scene collection, projection, line occlusion, or drawing-node creation.
It always compares **both strategies**, even though sweep is the renderer default.

## First run

Run in PowerShell from the repository root, using the existing workspace virtual
environment with the project dependencies installed:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_overlap_sort.py --samples 1 --warmup 0 --output-dir profiling-output\overlap-sort-smoke
```

**Important:** this script prints no progress or completion table. It creates
the output directory and writes reports only after every case finishes.
An interruption leaves no new partial report. Check successful completion and
new report timestamps rather than relying on CPU activity or old files.

Even this reduced run is not instantaneous. Avoid the defaults initially:
they use **100 samples and 5 warmups per strategy per case**. A previous local
run took about 4.7 seconds per sort for the dense 512-polygon case; at that rate,
defaults would spend roughly 16-17 minutes on that case alone. Your time will vary.

## Expected output

The specified directory receives two files:

- `overlap_sort_benchmark.md`: start here for a readable results table.
- `overlap_sort_benchmark.json`: raw samples, strategy summaries, counters, and
  Python/sample settings for deeper analysis.

The first run covers **20 fixtures**, with two strategy rows each: **40 table
rows**. There are four arrangements at 32, 64, 128, 256, and 512 polygons:

| Fixture prefix | What it tests |
| --- | --- |
| `distributed` | Separated groups of four overlapping polygons |
| `x_separated` | Easy rejection along the sweep axis |
| `y_separated` | Shared X range, but rejection along Y |
| `dense` | Every polygon overlaps; pruning cannot remove any pairs |

Before timing, the runner checks that both strategies agree on output order and
cycle status for each fixture.

## How to read the table

| Column | Meaning |
| --- | --- |
| `Fixture` | Arrangement and polygon count |
| `Strategy` | `all_pairs` or `sweep_and_prune` |
| `Exact tests` | Number of candidate pairs actually tested |
| `Median ms` | Middle measured sort duration; lower is better |
| `P95 ms` | Nearest-rank 95th percentile of measured durations |

Compare the two rows for the **same fixture**:

- At `distributed-512`, expect 130,816 exact tests for all-pairs versus 768
  for sweep. Fewer tests can reduce time, but not in the same proportion.
- At `dense-512`, both perform 130,816 exact tests. Little speedup, or some
  sweep overhead, is unsurprising because every pair remains a candidate.
- Speedup = all-pairs median / sweep median. A value above 1 favors sweep.

With one sample, median and P95 are identical. This checks execution, not stable
performance or tail latency. These are sorter timings, not FPS or whole-frame
render times.

## Next steps and useful options

To add demo 11's geometry at 12 camera orientations:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_overlap_sort.py --samples 1 --warmup 0 --include-target --output-dir profiling-output\overlap-sort-target-smoke
```

This produces **32 fixtures / 64 table rows**. The target is
[demo 11](../ported_demos/11_dearcygui_cpu_3d_map.py), not the hot-reload town.
Projection happens before timing; this is not a moving-camera render loop.

| Option | Meaning |
| --- | --- |
| `--samples` | Measured sorts per strategy/fixture; default `100`, use at least `1` |
| `--warmup` | Unmeasured sorts per strategy/fixture; default `5`, use at least `0` |
| `--include-target` | Add the 12 demo-11 views; off by default |
| `--output-dir` | Required report **directory** |
| `--help` | Show command-line usage |

There is no count, fixture, or strategy selector. Notice singular `--warmup`,
unlike the pipeline's `--warmups`. Increase samples only after checking the
smoke-run duration. Run benchmarks sequentially without competing workloads;
use a fresh output directory to preserve results. `profiling-output` is gitignored.

See also: [pipeline quickstart](Benchmark_Pipeline_Quickstart.md) for stage-by-stage
rebuild timings, or the [full benchmarking guide](../../.github/skills/renderer-benchmarking/SKILL.md).
