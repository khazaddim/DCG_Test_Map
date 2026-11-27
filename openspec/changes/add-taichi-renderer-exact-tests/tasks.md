## 1. Interactive integration

- [ ] 1.1 Add an optional backend at the shared renderer exact-test stage and route `--taichi-exact-tests` through the common profiling entry point for all seven launchers; leave the no-option path unchanged.
- [ ] 1.2 Reuse the Taichi evaluator with launch-owned CPU initialization, per-pair fallback, and explicit handling of recognized backend failures.
- [ ] 1.3 Report actual backend pair counts and fallback diagnostics in the profiler and export without changing the existing timing boundary.

## 2. Validation

- [ ] 2.1 Verify the shared option reaches all seven launchers. Test no-option behavior without Taichi, successful opt-in, mixed and failed batches, and runtime reuse across rebuilds and world reload.
- [ ] 2.2 Compare Python and Taichi directed edges, stable order, and cycle behavior at representative cameras in each profiling world, including default and wide temple views. Hold inputs and settings fixed and verify compatibility with the coplanar filter separately.
- [ ] 2.3 Smoke-test representative interactive launchers and compare first-use and warm exact-stage and total rebuild timings where a display is available; record any verification that could not be run.
- [ ] 2.4 Document the shared launch option, profiling indicators, fallback, and how to return to Python.
