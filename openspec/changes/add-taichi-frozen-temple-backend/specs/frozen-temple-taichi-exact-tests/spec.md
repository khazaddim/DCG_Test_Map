## ADDED Requirements

### Requirement: Explicit Frozen Temple opt-in

The Frozen Temple profiling launcher SHALL offer a startup option for Taichi CPU exact tests only. Python SHALL remain the default and other launchers SHALL retain their current behavior.

#### Scenario: Launch without Taichi
- **WHEN** Frozen Temple launches without the option
- **THEN** it uses the Python backend without importing or initializing Taichi

#### Scenario: Launch with Taichi
- **WHEN** Frozen Temple launches with the option and Taichi is available
- **THEN** its exact stage uses Taichi for supported pairs without changing candidate generation or graph ordering
- **AND THEN** the backend stays available across world reload without reinitializing per rebuild

### Requirement: Observable fallback and parity

The selected backend SHALL preserve accepted directed edges, stable order, and cycle behavior on the comparison inputs. Profiling SHALL identify actual backend usage alongside the existing exact-stage timing.

#### Scenario: Mixed or failed backend
- **WHEN** a pair is unsupported or the backend cannot complete the batch
- **THEN** Python supplies the unsupported or failed work, and profiling reports actual Taichi and Python pair counts
- **AND THEN** a backend failure is reported without publishing partial accelerated results
