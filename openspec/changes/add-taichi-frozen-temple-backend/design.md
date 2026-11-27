## Context

The shared hot-reload host creates the sorter, and the profiling host wraps its rebuild telemetry. The existing Taichi evaluator consumes already-projected entries and candidate pairs and returns results in candidate order.

## Goals / Non-Goals

- Compare exact-stage and total rebuild timings in interactive Frozen Temple using the same camera and scene inputs.
- Do not change projection, broad-phase settings, coplanar filtering, graph ordering, line occlusion, or drawing. Do not opt other launchers in.

## Decisions

- Pass an optional sorter or exact-stage backend through the existing host construction path. Keep the Taichi import out of the default path. Prefer this over changing the shared default or copying the profiler loop.
- Reuse the CPU `float64` evaluator and run it synchronously at the existing `test_overlaps` boundary. Use one thread for the initial interactive trial because it won at the Organic Frozen Temple default view; a multithread setting and workload thresholds can follow measurement on Frozen Temple.
- Own the Taichi runtime in the opt-in launch process, not in the reloadable world. Initialize once on the render-owning thread, keep it across world reloads, and report first-use cost separately from warm measurements. Do not modify DearCyGui state from kernel workers.
- Keep the evaluator's per-pair Python fallback for unsupported inputs. On a recognized optional dependency or backend runtime failure, warn, discard incomplete accelerated output, and use Python for the full batch and subsequent rebuilds. Do not relabel fallback as Taichi or swallow unexpected application errors.
- Keep the existing logical exact-test count and timing boundary. In the profiler and its exports, distinguish Python, Taichi, and mixed batches, with Taichi plus Python pair counts matching executed exact pairs.

## Risks / Trade-offs

- A different world or camera could cross a numerical boundary not covered by the headless trial. Compare directed edges, stable order, and cycle state on real Frozen Temple inputs before claiming parity.
- Import, initialization, and compilation costs can make the first launch slower. Report those separately and compare warm exact-stage and full rebuild times; do not infer FPS from isolated timings.
- Taichi initialization is process-global. Keep lifecycle ownership outside the generic renderer and do not reset another caller's runtime from a world reload.

## Migration Plan

Launch without `--taichi-exact-tests` to return to the existing Python path. No scene data migration is needed.
