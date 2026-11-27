## Context

The sorter evaluates each candidate independently: separating axes reject screen-separated faces, convex intersection gives the overlap vertices, and the mean of those vertices supplies a screen-space point for the two ray-plane tests. The resulting directed edges feed the existing topological sorter. This experiment replaces only that pair evaluation in a standalone runner.

## Goals / Non-Goals

- Compare the production Python path, Taichi CPU with one thread, and Taichi CPU with multiple threads, in the same `.venv-taichi` interpreter.
- Use identical projected entries and sweep-and-prune candidates for all modes, with the coplanar edge filter disabled. Prioritize the Organic Frozen Temple at default and wide zoom; include other camera angles and synthetic scaling cases.
- Do not alter production sorting, projection, draw publication, or demo controls. Do not test GPU or `float32` in this first experiment.

## Decisions

- **Batch the independent pair tests.** Pack screen vertices and camera-plane coefficients once per measured call. Evaluate each pair in an independent Taichi loop iteration with disjoint output and clipping scratch storage. Bound scratch memory by processing chunks. Polygons with more than 16 screen or camera vertices, or clipping that would exceed 32 scratch vertices, use the Python reference for that pair.
- **Preserve decisions, not bit patterns.** Use `float64`, disable fast math, and preserve the baseline's inequalities and mean-of-vertices sample point. Per-pair depth presence must match; numeric depths must meet `abs_tol=1e-9` or `rel_tol=1e-10`. Directed edges must match exactly regardless of tolerance, and so must stable order and cycle behavior. Check depths in an untimed pass and check edges and ordering on every sample.
- **Count actual backend work.** Report Python and Taichi pair counts separately. Unsupported pairs can use Python, but a full fallback, initialization/launch failure, or parity mismatch fails the run rather than publishing successful timing.
- **Time the full exact stage.** Record preparation/packing, kernel dispatch through synchronization, fallback, and edge collection, as well as total exact-stage latency. CPU NumPy buffers are passed by reference; dispatch/sync is not isolated kernel compute. Separate runtime initialization and the first call (including JIT) from warm measurements. Exclude collection, projection, broad phase, parity checks, graph ordering, and drawing.

## Risks / Trade-offs

- Headless exact-stage gains do not imply interactive FPS or full-frame gains.
- Mixed geometry and Python packing can dominate small batches or limit thread scaling. Compare all three modes instead of attributing the Python-to-Taichi gain to parallelism.
- Finite fixtures are not a proof of parity for every scene. Roundoff near overlap and depth thresholds can change decisions; reject the benchmark if a mismatch appears.
- Sequential mode timings can drift with system load. Keep other work idle during measurement, and repeat before making adoption decisions.

## Experiment results

On Windows with Python 3.11.9 and Taichi 1.7.4, the headless runner evaluated
four temple views (900 x 600, pitch 52 degrees) and three synthetic workloads.
Each mode used 20 measured samples and two warmups after an initial parity
check. The local raw report is `profiling-output/taichi-exact-temple-20261126.json`.

| Workload | Candidate pairs | Python median (ms) | Taichi 1 thread (ms) | Taichi 8 threads (ms) |
| --- | ---: | ---: | ---: | ---: |
| Temple default zoom (3.5x) | 2,760 | 69.69 | 5.02 | 6.81 |
| Temple 1x | 25,631 | 773.90 | 57.64 | 35.65 |
| Temple wide (0.25x) | 35,823 | 1,155.52 | 107.43 | 38.00 |
| Temple yaw 90, 1x | 20,306 | 407.86 | 54.72 | 24.57 |
| Synthetic 100 faces | 150 | 6.91 | 2.94 | 1.55 |
| Synthetic 500 faces | 750 | 36.37 | 8.28 | 4.33 |
| Synthetic 2,000 faces | 3,000 | 156.19 | 29.39 | 14.24 |

Both Taichi modes matched Python, with zero fallback pairs across all timed
workloads. Single-thread Taichi already accounts for much of the gain; eight
threads helped most at the widest view (2.83x over one thread), but were slower
at default zoom in this run. Initialization was 279 ms and 595 ms for one and
eight threads respectively, and the respective first calls including JIT were
961 ms and 1,109 ms. These are exact-stage results from one sequential run,
not full-frame performance or a recommendation to change the default.

The sorter, profiling, and temple regression run had 183 passes (including
the four new differential tests) and the two previously documented failures:
demo 11's road line-occluder expectation and the selected open-room world-module
expectation.
