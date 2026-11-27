## ADDED Requirements

### Requirement: Headless exact-test comparison

The evaluation SHALL compare production Python, single-thread Taichi CPU, and multithread Taichi CPU using the same projected entries and candidate pairs without modifying production rendering.

#### Scenario: Temple and synthetic inputs
- **WHEN** the default comparison runs
- **THEN** it includes default and wide Organic Frozen Temple views and synthetic fixtures, holds broad-phase settings fixed, and opens no GUI

### Requirement: Exact-test result parity

The evaluation SHALL check per-pair depth presence and compare valid depths against Python with absolute tolerance `1e-9` and relative tolerance `1e-10`. Directed edges, stable order, and cycle state SHALL agree exactly.

#### Scenario: Finite supported geometry
- **WHEN** an input exercises separation, winding, clipping, near-plane or epsilon boundaries, depth ties, degeneracy, or a real ordering cycle
- **THEN** the evaluation applies the Python reference decisions, or fails parity with a workload diagnostic

#### Scenario: Unsupported pair or failed backend
- **WHEN** a pair exceeds the supported geometry or scratch capacity
- **THEN** only that pair uses Python and is counted separately
- **WHEN** backend startup or launch fails, or a nonempty workload is entirely Python fallback
- **THEN** the evaluation fails rather than reporting Taichi performance

### Requirement: Full exact-stage measurement

The evaluation SHALL report actual backend work, setup and first-call latency separately from warm timing, and raw samples, median, and nearest-rank P95 for the exact-test stage.

#### Scenario: Measured sample
- **WHEN** a comparison sample is timed
- **THEN** the stage includes packing, dispatch through synchronization, fallback, and edge collection, and excludes projection, candidate generation, parity validation, and drawing
