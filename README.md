# DCG_Test_Map

Testing a zooming tabletop game map with my DearCyGui fork.

## Repo layout

- `Demos/` is a git submodule pointing at `https://github.com/khazaddim/Demos.git`
- `examples/` contains small standalone DearCyGui scripts focused on drawing containers

Initialize the submodule after cloning:

```bash
git submodule update --init --recursive
```

## Running the examples

These examples are meant to be used with your DearCyGui fork, including the branch
that contains your multi-controller work.

```bash
python /absolute/path/to/examples/01_draw_in_window_world.py
python /absolute/path/to/examples/02_draw_in_plot_zoom_levels.py
python /absolute/path/to/examples/03_draw_stream_animation.py
python /absolute/path/to/examples/04_draw_stream_arrow_keys.py
python /absolute/path/to/examples/05_drawing_scale_basics.py
python /absolute/path/to/examples/06_pan_camera_edge_band.py
python /absolute/path/to/examples/07_pan_camera_perspective_tilt.py
python /absolute/path/to/examples/08_Camera_tilt_simple.py
python /absolute/path/to/examples/09_pan_camera_perspective_fullscreen.py
python /absolute/path/to/examples/10_pan_camera_perspective_rotation.py
```

## What the examples cover

- `01_draw_in_window_world.py` explores `DrawInWindow`, `DrawingScale`, and `DrawingList`
- `02_draw_in_plot_zoom_levels.py` explores `DrawInPlot`, `DrawingClip`, and zoom-based culling
- `03_draw_stream_animation.py` explores `DrawStream` for frame-based character animation
- `04_draw_stream_arrow_keys.py` explores `DrawStream` plus `KeyDownHandler`-driven movement
- `05_drawing_scale_basics.py` explores `DrawingScale` transform fundamentals (`origin` + `scales`)
- `06_pan_camera_edge_band.py` explores camera panning with edge-band/dead-zone behavior
- `07_pan_camera_perspective_tilt.py` introduces projective tilt and source-space clipping
- `08_Camera_tilt_simple.py` isolates the basic rectangle-to-trapezoid transform
- `09_pan_camera_perspective_fullscreen.py` fills the viewport and reveals more world depth with inclination
- `10_pan_camera_perspective_rotation.py` combines centered inclination, world rotation, inverse-projected camera tracking, and flicker-free double buffering

## Perspective map learning path

Start with `05` for affine coordinates, then read `07`, `09`, and `10` in that
order. Demo `10` contains a ground-up lesson in its module docstring and is the
canonical reference for a rotating game map with moving pieces.

The central lessons are:

1. Keep game state in world space and convert it to source and screen space only
	for drawing or screen interaction.
2. Transform order matters. Rotate the world around the camera focus before
	applying camera scaling and perspective.
3. Inclination and rotation must share one central anchor. Normalize the
	homography scale there to avoid focus drift and rotation-dependent stretching.
4. Clip geometry in source space before applying the homography.
5. Never clear and rebuild the visible projected layer. Build a hidden back
	layer, then swap complete layers under their common parent mutex. This avoids
	intermittent black frames from rendering a partially rebuilt scene.

The repository-local
[`dcg-perspective-map-patterns`](.github/skills/perspective_map_patterns/SKILL.md)
skill contains the reusable formulas, implementation patterns, anti-patterns,
and cheap numerical validation checks behind these demos.

For the larger reference demo, inspect `Demos/main_demo/drawings.py`.
