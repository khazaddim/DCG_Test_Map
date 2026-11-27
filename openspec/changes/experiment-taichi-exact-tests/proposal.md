# Change: Experiment with Taichi-accelerated exact overlap tests

## Why

The CPU overlap sorter currently evaluates candidate polygon pairs one at a time in `test_overlaps`. The exact test has independent screen-overlap and ray-plane work for each candidate pair, so it is a plausible target for parallel execution. A controlled Taichi experiment can determine whether parallel batch execution is fast enough to justify added complexity.

## What Changes

- Add a headless evaluation that compares Python, single-thread Taichi CPU, and multithread Taichi CPU on fixed projected inputs from the Organic Frozen Temple and synthetic fixtures.
- Check per-pair depth decisions, directed ordering edges, stable sort order, and cycle behavior. Report actual backend coverage and end-to-end exact-stage timing.
- Use `float64` and the existing `.venv-taichi` environment for the first experiment. Defer GPU, `float32`, and interactive integration.

## Capabilities

### New Capabilities

- `parallel-exact-pair-tests`: Execute independent polygon candidate-pair exact tests in a parallel implementation while preserving baseline output and fallback behavior.

### Modified Capabilities

- None.

## Impact

- Reuses `OverlapDepthSorter.test_overlaps` as the Python reference. Production sorter and demo code remain unchanged.
- Taichi is optional and required only for the evaluation. The experiment is not a decision to merge or enable Taichi.
