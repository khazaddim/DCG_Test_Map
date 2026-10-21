Review the **13 files** in this order: establish the intended behavior, follow the instrumentation through the renderer, then inspect reload safety, UI integration, and tests.

### 1. Requirements and user-facing behavior

1. **`tasks.md`**  
   Marks **5.5.8–5.5.16** complete. No scope changes; the subsequent validation and performance-evidence tasks remain unchecked.

2. **`README.md`**  
   Adds launch instructions, feature-switch descriptions, telemetry/control semantics, capture/export formats, and a reproducible comparison workflow. This is the quickest overview of how the implementation should behave.

### 2. Core telemetry and renderer integration

3. **`profiling.py — new`**  
   Implements exclusive stage timing, total/unaccounted time, bounded 120-sample history, latest/mean/P95 statistics, failure tracking, configuration identity, CSV/JSON exports, and rebuild-only `cProfile` capture.  
   **Main review focus:** timing accounting, window-reset rules, and capture/save lifecycle.

4. **`scene.py`**  
   Adds optional measurements to overlap sorting. Times candidate generation, exact overlap tests, and graph ordering separately without changing the sorting algorithm.

5. **`renderer.py`**  
   Wires timing into actual collection, projection, sorting, line occlusion, and node emission. Preserves the uninstrumented path and avoids double-counting the overlap sorter’s internal stages.

6. **`widget.py`**  
   Connects telemetry to real viewport rebuilds, including back-layer preparation and publication/cleanup. Supplies camera, viewport, and strategy context; idle calls do not generate samples.  
   **Main review focus:** successful-publication boundaries and preservation of normal rendering behavior.

7. **`benchmark_pipeline.py`**  
   Removes its private timing helper and imports the shared implementation. Existing fixtures and benchmark behavior remain intact.

### 3. World configuration and safe reloads

8. **`town_hot_reload_world.py`**  
   Adds independent switches for houses, roads, grids, border, mesh edges, and windmill animation. Connects switches to geometry, collisions, terrain, and texture creation, and reports effective dependent flags. Existing defaults are preserved.

9. **`town_hot_reload.py`**  
   Introduces a complete candidate-world bundle and isolated source loading instead of mutating the active module with `importlib.reload()`. Prepares candidate state before replacement, preserves active state on failure, tracks generation/configuration, and serializes world operations with a lock. Also adds optional profiling-host layout parameters.  
   **Main review focus:** this is the most significant behavioral change—especially failure preservation and resource ownership.

### 4. Panel and runnable demo

10. **`profiling_panel.py — new`**  
    Provides ranked timing bars, statistics, counters, configuration/status displays, and queued telemetry/capture/export controls. Refreshes at most 5 Hz without touching scene invalidation and visibly reports save failures.

11. **`town_hot_reload_profiling.py — new`**  
    Assembles the shared town host and profiling panel side by side. Processes profiling actions outside rebuilds, preserves once-per-loop rendering, reports rebuild errors, and saves pending captures on shutdown.

12. **`init.py`**  
    Exports the new telemetry, timing, and panel classes through the framework package. Small API-exposure change.

### 5. Verification

13. **`test_draw_in_window_3d_profiling.py — new`**  
    Adds **30 test cases** covering timing/output equivalence, history/statistics, idle/failure handling, exports, capture scope and `pstats` readability, panel throttling, feature switches, reload preservation, resources, and original-host defaults.

**If review time is limited:** prioritize items **3, 6, 9, and 13**. Those contain the timing contract, publication boundary, reload-safety changes, and their verification.