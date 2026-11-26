## ADDED Requirements

### Requirement: Conservative automatic pair filtering
The experimental sorter SHALL automatically skip detailed polygon-pair tests only when it can establish that doing so preserves baseline ordering behavior, without requiring scene authors to mark floors or coplanar groups.

#### Scenario: Proven coplanar floor tiles
- **WHEN** candidate floor polygons are proven to share a plane and skipping their test preserves baseline ordering
- **THEN** the experimental sorter avoids their detailed pair test while retaining both polygons for rendering

#### Scenario: Unsafe or uncertain pair
- **WHEN** polygons are folded, nearly coplanar, degenerate, or otherwise not provably safe to skip
- **THEN** the sorter uses the existing detailed test

#### Scenario: Baseline comparison
- **WHEN** the same scene and camera are sorted with the experimental and baseline paths
- **THEN** stable polygon order and cycle behavior match, including order-sensitive and clipped geometry

### Requirement: Measurable opt-in experiment
The experiment SHALL preserve an available baseline and report candidate, executed detailed-test, and skipped-pair counts separately.

#### Scenario: Representative performance comparison
- **WHEN** baseline and experimental sorting are measured with matching temple camera settings and a non-floor workload
- **THEN** the results report sample counts, workload counts, and timings without assuming that fewer tests guarantee a speedup
