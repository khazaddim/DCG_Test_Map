## ADDED Requirements

### Requirement: Shared exact-test backend selection

The renderer's overlap sorter SHALL support an optional Taichi CPU backend for exact candidate-pair tests. All profiling launchers SHALL expose the same `--taichi-exact-tests` startup option. Python SHALL remain the default.

#### Scenario: Launch without Taichi
- **WHEN** a profiling launcher runs without the option, or the renderer is constructed without an explicit backend
- **THEN** it uses the Python backend without importing or initializing Taichi

#### Scenario: Launch with Taichi
- **WHEN** any profiling example launches with the option and Taichi is available
- **THEN** its shared renderer exact stage uses Taichi for supported pairs without changing candidate generation, coplanar filtering, or graph ordering
- **AND THEN** the backend stays available across world reload without reinitializing per rebuild

### Requirement: Observable fallback and parity

The selected backend SHALL preserve accepted directed edges, stable order, and cycle behavior on the comparison inputs. Profiling SHALL identify actual backend usage alongside the existing exact-stage timing.

#### Scenario: Compare a profiling world
- **WHEN** Python and Taichi run on the same projected entries, candidate pairs, and thresholds
- **THEN** the compared directed edges, stable entry order, and cycle state match
- **AND THEN** the profiling panel and export show the actual backend and pair counts

#### Scenario: Mixed or failed backend
- **WHEN** a pair is unsupported or the backend cannot complete the batch
- **THEN** Python supplies the unsupported or failed work, and profiling reports actual Taichi and Python pair counts
- **AND THEN** a backend failure is reported without publishing partial accelerated results
