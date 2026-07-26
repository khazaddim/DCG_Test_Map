# Drawing container examples

These scripts are intentionally small and standalone so you can compare root-level
container choices for the map prototype.

## Files

- `01_draw_in_window_world.py`
  - Uses `DrawInWindow` as the root canvas
  - Adds `DrawingScale` so child drawings can live in world coordinates
  - Nests `DrawingList` containers for terrain, a city, and a party token

- `02_draw_in_plot_zoom_levels.py`
  - Uses `DrawInPlot` as the root canvas
  - Leans on plot pan/zoom instead of custom camera math
  - Uses `DrawingClip` to hide finer-detail content until the user zooms in

- `03_draw_stream_animation.py`
  - Uses `dcg.utils.DrawStream` to cycle animation frames
  - Keeps the example vector-only so it has no extra asset dependencies
  - Can be adapted later to swap `DrawingList` frames for SVG- or bitmap-based frames

- `10_pan_camera_perspective_rotation.py`
  - Adds map rotation around the viewport center to the full-screen perspective map
  - Combines rotation, inclination-dependent view depth, zoom, and edge-band panning
  - Uses a rotation slider spanning -180 to 180 degrees

- `11_dearcygui_cpu_3d_map.py`
  - Replaces the planar homography with a true CPU-side 3D pinhole camera
  - Projects raised box meshes with near-plane clipping, back-face culling, face shading, and painter ordering
  - Uses only DearCyGui 2D polygons and lines; no ModernGL or other GPU renderer
  - Retains atomic front/back drawing buffers while pitch, yaw, zoom, or the player piece changes

## Suggested comparison

If the game map wants built-in panning and zooming, start with `02_draw_in_plot_zoom_levels.py`.
If you want total control over transforms and interaction, start with
`01_draw_in_window_world.py`.

`03_draw_stream_animation.py` is meant to answer the animation question separately,
so you can combine the same frame-cycling idea with either root container.
