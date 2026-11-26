## Why

The organic frozen temple generates thousands of projected polygon-pair candidates, including many floor pairs that lie on the same plane and produce no ordering constraint. An experiment can determine whether recognizing such pairs reduces sorting work without changing the rendered result.

## What Changes

- Experiment with automatically identifying provably coplanar polygon pairs without requiring floor flags or changes to world definitions.
- Skip detailed pair testing only when the existing ordering behavior can be preserved; retain the existing path for uncertain cases.
- Compare the experimental and baseline sorters on representative temple views and focused correctness cases before considering default use.

## Capabilities

### New Capabilities

- `coplanar-overlap-optimization`: Conservative, measurable avoidance of redundant polygon-ordering tests.

### Modified Capabilities

- None.

## Impact

- Affects the CPU renderer's overlap sorter, its diagnostics, and focused tests.
- Adds no dependencies and does not change movement collision detection or require scene-author annotations.
- The experiment remains isolated on its branch; it is not a decision to merge or enable the optimization by default.
