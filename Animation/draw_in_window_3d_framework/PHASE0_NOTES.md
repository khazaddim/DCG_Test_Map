# DrawInWindow3D Phase 0 Notes

## Result

- `DrawInWindow3D` can subclass `dcg.DrawInWindow` directly.
- The subclass works with normal context-manager construction: `with DrawInWindow3D(...) as viewport:`.
- Two child `DrawingList` objects can be atomically published by building into the hidden list, then toggling `show` under the owning layer mutex.
- The wrapper fallback from the design remains unnecessary for this codebase because the subclass spike succeeded.

## Minimal implementation

- `widget.py` contains the phase-0 `DrawInWindow3D` subclass and a reusable `FramePublisher`.
- `phase0_demo.py` publishes one polygon, then lets the user swap to another polygon with a button or the space bar.
- Each swap rebuilds the hidden layer and flips visibility under the layer mutex, matching the publication pattern proven in demo 11.

## Validation

- Focused pytest coverage: `pytest tests/test_draw_in_window_3d_phase0.py`
- Manual smoke demo: `python Animation/draw_in_window_3d_framework/phase0_demo.py`