## 1. Interactive integration

- [ ] 1.1 Route the Frozen Temple launcher option through the shared profiling host to an optional exact-test backend; leave the no-option path unchanged.
- [ ] 1.2 Reuse the Taichi evaluator with launch-owned CPU initialization, per-pair fallback, and explicit handling of recognized backend failures.
- [ ] 1.3 Report actual backend pair counts and fallback diagnostics in the profiler and export without changing the existing timing boundary.

## 2. Validation

- [ ] 2.1 Test no-option behavior without Taichi, successful opt-in, mixed and failed batches, and runtime reuse across rebuilds and world reload.
- [ ] 2.2 Compare Python and Taichi directed edges, stable order, and cycle behavior on the Frozen Temple default and wide views, with the same inputs and settings.
- [ ] 2.3 Smoke-test the interactive launcher and compare first-use and warm exact-stage and total rebuild timings where a display is available; record any verification that could not be run.
- [ ] 2.4 Document the launch command, profiling indicators, fallback, and how to return to Python.
