## 1. Interactive integration

- [x] 1.1 Add an optional backend at the shared renderer exact-test stage and route `--taichi-exact-tests` through the common profiling entry point for all seven launchers; leave the no-option path unchanged.
- [x] 1.2 Reuse the Taichi evaluator with launch-owned CPU initialization, per-pair fallback, and explicit handling of recognized backend failures.
- [x] 1.3 Report actual backend pair counts and fallback diagnostics in the profiler and export without changing the existing timing boundary.

## 2. Validation

- [x] 2.1 Verify the shared option reaches all seven launchers. Test no-option behavior without Taichi, successful opt-in, mixed and failed batches, and runtime reuse across rebuilds and world reload.
- [x] 2.2 Compare Python and Taichi directed edges, stable order, and cycle behavior at representative cameras in each profiling world, including default and wide temple views. Hold inputs and settings fixed and verify compatibility with the coplanar filter separately.
- [ ] 2.3 Smoke-test representative interactive launchers and compare first-use and warm exact-stage and total rebuild timings where a display is available; record any verification that could not be run.
- [x] 2.4 Document the shared launch option, profiling indicators, fallback, and how to return to Python.

## Verification notes

- The Taichi-enabled focused suite in `.venv-taichi` passed 112 tests, including the parity matrix for all seven profiling worlds, both temple views, and both coplanar-filter settings. Two unrelated test cases were deselected after their assertions failed in the system-Python run.
- All seven launchers' `--help` output includes `--taichi-exact-tests`. A headless exact-stage smoke on `temple-yaw0-zoom3.5` (2,760 pairs, one measured sample) reported Taichi single-thread first use at 929.7 ms and warm exact-stage median at 4.94 ms; Python measured 39.74 ms. The single sample is smoke evidence, not a performance baseline.
- A direct real-adapter smoke on the 100-face fixture matched Python ordering and cycle state; it reported 150 Taichi pairs, zero Python pairs, 1.73 s initialization, 1.08 s first exact-stage, and 2.09 ms warm exact-stage.
- Interactive total-rebuild timings were not collected. They remain pending for a user-run profiling window; opted-in telemetry starts enabled so its initial cold rebuild is captured.
