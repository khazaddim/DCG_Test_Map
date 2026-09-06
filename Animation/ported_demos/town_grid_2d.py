"""Framework-backed 2D town-planning scene.

The world deliberately contains only a flat ground plane, a measurement grid,
and a border. It is a clean authoring surface for adding town geometry later.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import (
    Camera3D,
    DrawInWindow3D,
    GroundPlane3D,
    Line3D,
    LineRenderLayer,
    Polyline3D,
    Scene3D,
    SolidMaterial,
    Text3D,
)


VIEW_W = 900
VIEW_H = 600
WORLD_W = 100.0
WORLD_H = 100.0
GRID_STEP = 5
MAJOR_GRID_STEP = 25
MOVE_STEP = GRID_STEP
PITCH_MIN = 0.0
PITCH_MAX = 78.0
ZOOM_MIN = 0.75
ZOOM_MAX = 8.0
ZOOM_DEFAULT = 3.5


def build_scene() -> Scene3D:
    scene = Scene3D(background=(135, 195, 230))
    scene.add(
        GroundPlane3D(
            bounds=(0.0, 0.0, WORLD_W, WORLD_H),
            z=0.0,
            material=SolidMaterial(
                fill=(74, 128, 68),
                outline=None,
                thickness=-1.0,
                shaded=False,
                line_occluder=False,
            ),
        )
    )

    for coordinate in range(0, int(WORLD_W) + 1, GRID_STEP):
        major = coordinate % MAJOR_GRID_STEP == 0
        scene.add(
            Line3D(
                start=(float(coordinate), 0.0, 0.5),
                end=(float(coordinate), WORLD_H, 0.5),
                color=(156, 177, 116) if major else (105, 145, 91),
                thickness=-2.0 if major else -1.0,
                render_layer=LineRenderLayer.UTILITY,
            )
        )

    for coordinate in range(0, int(WORLD_H) + 1, GRID_STEP):
        major = coordinate % MAJOR_GRID_STEP == 0
        scene.add(
            Line3D(
                start=(0.0, float(coordinate), 0.5),
                end=(WORLD_W, float(coordinate), 0.5),
                color=(156, 177, 116) if major else (105, 145, 91),
                thickness=-2.0 if major else -1.0,
                render_layer=LineRenderLayer.UTILITY,
            )
        )

    # Label every 5 ft intersection with an ordered pair in world feet.
    for x_coordinate in range(0, int(WORLD_W) + 1, GRID_STEP):
        for y_coordinate in range(0, int(WORLD_H) + 1, GRID_STEP):
            scene.add(
                Text3D(
                    position=(float(x_coordinate + 1), float(y_coordinate + 1), 1.0),
                    text=f"({x_coordinate}, {y_coordinate})",
                    size=10.0,
                    color=(35, 67, 38),
                    min_size=7.0,
                    max_size=12.0,
                )
            )

    scene.add(
        Polyline3D(
            points=(
                (0.0, 0.0, 0.7),
                (WORLD_W, 0.0, 0.7),
                (WORLD_W, WORLD_H, 0.7),
                (0.0, WORLD_H, 0.7),
            ),
            color=(224, 205, 133),
            thickness=-3.0,
            closed=True,
            render_layer=LineRenderLayer.UTILITY,
        )
    )
    return scene


class TownGridController:
    def __init__(self, viewport: DrawInWindow3D, status: dcg.Text) -> None:
        self.viewport = viewport
        self.status = status
        self._update_status()

    def move_left(self, *_):
        self._pan(-MOVE_STEP, 0.0)

    def move_right(self, *_):
        self._pan(MOVE_STEP, 0.0)

    def move_up(self, *_):
        self._pan(0.0, -MOVE_STEP)

    def move_down(self, *_):
        self._pan(0.0, MOVE_STEP)

    def set_pitch(self, sender, *_):
        self._set_camera(pitch_deg=float(sender.value))

    def set_yaw(self, sender, *_):
        self._set_camera(yaw_deg=float(sender.value))

    def set_zoom(self, sender, *_):
        self._set_camera(zoom=float(sender.value))

    def reset_view(self, *_):
        self._set_camera(target=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0), yaw_deg=0.0, pitch_deg=52.0, zoom=ZOOM_DEFAULT)

    def _pan(self, dx: float, dy: float) -> None:
        target = self.viewport.camera.target
        next_target = (
            max(0.0, min(WORLD_W, target[0] + dx)),
            max(0.0, min(WORLD_H, target[1] + dy)),
            target[2],
        )
        self._set_camera(target=next_target)

    def _set_camera(self, **changes: object) -> None:
        self.viewport.set_camera(replace(self.viewport.camera, **changes))
        self.viewport.render_now()
        self._update_status()

    def _update_status(self) -> None:
        camera = self.viewport.camera
        self.status.value = (
            f"target=({camera.target[0]:.0f}, {camera.target[1]:.0f})   "
            f"pitch={camera.pitch_deg:.1f} deg   yaw={camera.yaw_deg:.1f} deg   "
            f"zoom={camera.zoom:.2f}x   world={WORLD_W:.0f} x {WORLD_H:.0f}"
        )


def build_ui(context: dcg.Context) -> None:
    scene = build_scene()
    initial_camera = Camera3D(
        target=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=ZOOM_DEFAULT,
    )

    with dcg.Window(
        context,
        label="Town planning grid",
        width=VIEW_W + 40,
        height=VIEW_H + 300,
    ) as window:
        dcg.Text(context, value="Town planning canvas", wrap=VIEW_W)
        status = dcg.Text(context, value="")
        with DrawInWindow3D(
            context,
            width=VIEW_W,
            height=VIEW_H,
            scene=scene,
            camera=initial_camera,
        ) as viewport:
            dcg.DrawRect(
                context,
                parent=viewport,
                pmin=(0, 0),
                pmax=(VIEW_W, VIEW_H),
                color=(130, 151, 133),
                thickness=-2,
            )

        controller = TownGridController(viewport, status)
        dcg.Slider(
            context,
            label="Camera pitch from overhead (degrees)",
            min_value=PITCH_MIN,
            max_value=PITCH_MAX,
            value=initial_camera.pitch_deg,
            width=VIEW_W,
            callback=controller.set_pitch,
        )
        dcg.Slider(
            context,
            label="Camera yaw (degrees)",
            min_value=-180.0,
            max_value=180.0,
            value=initial_camera.yaw_deg,
            width=VIEW_W,
            callback=controller.set_yaw,
        )
        dcg.Slider(
            context,
            label="Camera zoom",
            min_value=ZOOM_MIN,
            max_value=ZOOM_MAX,
            value=initial_camera.zoom,
            width=VIEW_W,
            callback=controller.set_zoom,
        )
        dcg.Button(context, label="Reset view", callback=controller.reset_view)
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW, callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW, callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Town planning grid",
        width=VIEW_W + 80,
        height=VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()