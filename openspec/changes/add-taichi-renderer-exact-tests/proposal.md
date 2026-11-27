## Why

The [headless experiment](../experiment-taichi-exact-tests/design.md) found that Taichi CPU accelerated exact overlap tests on Organic Frozen Temple inputs without changing the tested ordering. A shared renderer backend lets all profiling examples test whether that gain carries over to other worlds and actual rebuilds.

## What Changes

- Add an optional backend at the renderer's shared exact-test stage and expose it via `--taichi-exact-tests` in all profiling launchers on the experimental branch.
- Reuse the existing `float64` Taichi CPU evaluator for exact candidate-pair tests only. Preserve Python as the default and fallback, including for non-profiling launches that do not explicitly select a backend.
- Expose the actual backend and pair counts in profiling so fallback cannot be mistaken for acceleration.

## Capabilities

### New Capabilities

- `renderer-taichi-exact-tests`: Opt-in Taichi exact tests at the shared renderer stage, available in all profiling examples.

### Modified Capabilities

- None.

## Impact

- Affects the shared overlap sorter, profiling host, and exact-stage diagnostics. Town, Cave, Complex Cave, Trippy Cave, Volcano Cave, Frozen Temple, and Organic Frozen Temple use the same launch option.
- Depends on the branch's existing headless evaluator. Taichi remains optional and does not become a default dependency.
