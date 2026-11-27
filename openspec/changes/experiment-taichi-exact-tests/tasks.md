## 1. Headless prototype

- [x] 1.1 Preflight the existing Taichi environment and leave production code unchanged.
- [x] 1.2 Implement `float64` CPU batching, exact overlap/depth evaluation, and counted per-pair Python fallback.
- [x] 1.3 Add differential tests for numerical boundaries, geometry and clipping, batch boundaries, and a real cycle.

## 2. Measurement and verification

- [x] 2.1 Add a headless Python / single-thread Taichi / multithread Taichi comparison for fixed temple and synthetic workloads.
- [x] 2.2 Smoke-test execution, measurement shape, and exact parity.
- [x] 2.3 Run the full comparison and record workload timing and actual backend counts.
- [x] 2.4 Run relevant sorter, profiling, and temple regressions.
- [x] 2.5 Document the command, limits, and outcome; keep runtime adoption separate.
