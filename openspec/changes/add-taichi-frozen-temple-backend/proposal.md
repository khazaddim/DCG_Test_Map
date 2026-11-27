## Why

The [headless experiment](../experiment-taichi-exact-tests/design.md) found that Taichi CPU accelerated exact overlap tests on Organic Frozen Temple inputs without changing the tested ordering. The interactive Frozen Temple profiler can test whether that gain carries over to its own world and actual rebuilds.

## What Changes

- Add an explicit `--taichi-exact-tests` launch option to the Frozen Temple profiling launcher on the experimental branch.
- Reuse the existing `float64` Taichi CPU evaluator for exact candidate-pair tests only. Preserve Python as the default and fallback.
- Expose the actual backend and pair counts in profiling so fallback cannot be mistaken for acceleration.

## Capabilities

### New Capabilities

- `frozen-temple-taichi-exact-tests`: Opt-in interactive evaluation of Taichi exact tests in the Frozen Temple profiler.

### Modified Capabilities

- None.

## Impact

- Affects the Frozen Temple profiling launcher, its shared host wiring, and exact-stage diagnostics. Other launchers retain their current behavior.
- Depends on the branch's existing headless evaluator. Taichi remains optional and does not become a default dependency.
