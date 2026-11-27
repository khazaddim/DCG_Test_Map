## Context

The shared hot-reload host creates the sorter, and all seven interactive profiling launchers enter through the same profiling host. The existing Taichi evaluator consumes already-projected entries and candidate pairs and returns results in candidate order.

## Goals / Non-Goals

- Make the backend selectable at the shared exact-test stage, then compare exact-stage and total rebuild timings across profiling worlds using matching camera and scene inputs.
- Do not change projection, broad-phase settings, coplanar filtering, graph ordering, line occlusion, or drawing. Do not automatically enable Taichi for any launch.

## Decisions

- Give `OverlapDepthSorter` an optional exact-stage backend at `test_overlaps`, used by both profiled and unprofiled rebuilds when configured. Keep the backend contract and default Python path independent of Taichi imports and lifecycle. Preserve candidate order and the existing overlap-area and depth tolerances.
- Parse `--taichi-exact-tests` once in the shared profiling entry point and pass the backend through the existing host/UI construction path. Keep world modules and wrapper launchers free of backend-specific logic.
- Reuse the CPU `float64` evaluator synchronously. Start with one Taichi thread, which won at the Organic Frozen Temple default view; defer automatic thread selection and workload thresholds until there is evidence across worlds.
- Own the Taichi runtime in the opt-in launch process, not in the reloadable world. Initialize once on the render-owning thread, keep it across world reloads, and report first-use cost separately from warm measurements. Do not modify DearCyGui state from kernel workers.
- Keep the evaluator's per-pair Python fallback for unsupported inputs. On a recognized optional dependency or backend runtime failure, warn, discard incomplete accelerated output, and use Python for the full batch and subsequent rebuilds. Do not relabel fallback as Taichi or swallow unexpected application errors.
- Keep the existing logical exact-test count and timing boundary. In the profiler and its exports, distinguish Python, Taichi, and mixed batches, with Taichi plus Python pair counts matching executed exact pairs.

## Risks / Trade-offs

- A different world or camera could cross a numerical boundary not covered by the headless trial. Compare directed edges, stable order, and cycle state on real inputs from each profiling world, including wider views for the temples. Hold candidate settings fixed between backends; separately verify coexistence with the experimental coplanar filter.
- Import, initialization, and compilation costs can make the first launch slower. Report those separately and compare warm exact-stage and full rebuild times; do not infer FPS from isolated timings.
- Taichi initialization is process-global. Keep lifecycle ownership outside the generic renderer and do not reset another caller's runtime from a world reload.

## Migration Plan

Launch without `--taichi-exact-tests` to return to the existing Python path. No scene data migration is needed.
