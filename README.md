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
```

## What the examples cover

- `01_draw_in_window_world.py` explores `DrawInWindow`, `DrawingScale`, and `DrawingList`
- `02_draw_in_plot_zoom_levels.py` explores `DrawInPlot`, `DrawingClip`, and zoom-based culling
- `03_draw_stream_animation.py` explores `DrawStream` for frame-based character animation
- `04_draw_stream_arrow_keys.py` explores `DrawStream` plus `KeyDownHandler`-driven movement
- `05_drawing_scale_basics.py` explores `DrawingScale` transform fundamentals (`origin` + `scales`)
- `06_pan_camera_edge_band.py` explores camera panning with edge-band/dead-zone behavior

For the larger reference demo, inspect `Demos/main_demo/drawings.py`.
