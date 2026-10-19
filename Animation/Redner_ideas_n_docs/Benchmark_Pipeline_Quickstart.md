# Pipeline benchmark quickstart

**Question it answers:** Where does a synthetic scene rebuild spend its time?

[benchmark_pipeline.py](../ported_demos/benchmark_pipeline.py) measures scene
collection, projection/clipping, overlap sorting, line occlusion, drawing-node
creation, and publication/cleanup separately. It runs headlessly: no GUI opens,
but it still uses real DearCyGui drawing nodes.

## First run

Run in PowerShell from the repository root, using the existing workspace virtual
environment with the project dependencies installed:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 --samples 1 --warmups 0 --output profiling-output\pipeline-smoke.json
```

This measures one rebuild of 100 faces plus eight lines, using the default
**sweep-and-prune** sorter. The geometry is real world-space geometry arranged
into predictable overlap groups, not a town scene or injected overlap counts.

**While running:** no progress is printed. The output folder and report are
created only after all requested measurements finish.

## Expected output

- A terminal table with columns `Faces`, `Stage`, `Median ms`, and `P95 ms`.
- `profiling-output\pipeline-smoke.json`, containing:
  - `metadata`: interpreter, platform, camera, settings, and measurement scope.
  - `rows`: individual samples, raw `durations_ns`, and workload counters.
  - `summary`: per-stage median and P95 in milliseconds.
- No Markdown report is saved automatically. Without `--output`, only the
  terminal table is produced.

For this first run, expected counters include **100 polygons, 150 exact pair
tests, 16 visible line fragments, and 117 emitted nodes** (including background).
The runner checks workload counters; a mismatch raises an error.

## What to look at

1. Find `total_rebuild` for the full measured rebuild time.
2. Find the largest individual stages: these are the first optimization targets.
   Sorting is split into `broad_phase`, `exact_tests`, and
   `topological_ordering`.
3. `unaccounted` is time outside the nine named exclusive stages, not an extra
   rendering operation. Do not add `total_rebuild` to those stages.

Lower milliseconds means faster. With one sample, median and P95 are identical:
this is an execution check, not a reliable performance baseline. Stage medians
need not sum to the median total. These timings are not GPU time, FPS, or
interactive town frame latency.

## Next run and useful options

Try more samples and a second size:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_pipeline.py --counts 100 500 --samples 5 --warmups 1 --output profiling-output\pipeline-small.json
```

| Option | Meaning |
| --- | --- |
| `--counts` | Supported sizes: `100 500 2000 10000`; default is all four |
| `--samples` | Measured rebuilds per size; default `5`, minimum `1` |
| `--warmups` | Unmeasured rebuilds per size; default `1`, minimum `0` |
| `--strategy` | `sweep_and_prune` (default) or `all_pairs` |
| `--no-lines` | Omit the eight lines |
| `--output` | JSON **file** path |
| `--help` | Show command-line usage |

All-pairs requires counts no greater than 2,000; the 10,000-face case is blocked.
Compare strategies using identical settings and separate output filenames.
Run benchmarks sequentially without competing workloads. Output files are
overwritten if reused; `profiling-output` is gitignored.

See also: [overlap-sort quickstart](Benchmark_Overlap_Sort_Quickstart.md) for
isolated sorter comparisons, or the [full benchmarking guide](../../.github/skills/renderer-benchmarking/SKILL.md).
