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
    Box3D,
    Camera3D,
    DrawInWindow3D,
    EdgeBandFollowController,
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
WORLD_W = 150.0
WORLD_H = 150.0
GRID_STEP = 5
MAJOR_GRID_STEP = 25
MOVE_STEP = GRID_STEP
PITCH_MIN = 0.0
PITCH_MAX = 78.0
ZOOM_MIN = 0.75
ZOOM_MAX = 16.0
ZOOM_DEFAULT = 3.5
AVATAR_SIZE = 5.0
AVATAR_HEIGHT = 6.0
GROUND_PAD = 200.0
CONTROLS_HEIGHT = 220.0


def build_scene() -> tuple[Scene3D, Box3D]:
    scene = Scene3D(background=(135, 195, 230))
    scene.add(
        GroundPlane3D(
            bounds=(
                -GROUND_PAD,
                -GROUND_PAD,
                WORLD_W + GROUND_PAD,
                WORLD_H + GROUND_PAD,
            ),
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

    # Label only major 25 ft intersections to keep the scene responsive.
    for x_coordinate in range(0, int(WORLD_W) + 1, MAJOR_GRID_STEP):
        for y_coordinate in range(0, int(WORLD_H) + 1, MAJOR_GRID_STEP):
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

    avatar = Box3D(
        center=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0),
        size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT),
        material=SolidMaterial(
            fill=(245, 194, 67),
            outline=(35, 45, 30),
            thickness=-2.0,
            shaded=True,
        ),
    )
    scene.add(avatar)
    return scene, avatar


class TownGridController:
    def __init__(self, viewport: DrawInWindow3D, avatar: Box3D, status: dcg.Text) -> None:
        self.viewport = viewport
        self.avatar = avatar
        self.status = status
        self.follow = EdgeBandFollowController(
            viewport=viewport,
            band_x=VIEW_W * 0.2,
            band_y=VIEW_H * 0.2,
            world_bounds=(0.0, 0.0, WORLD_W, WORLD_H),
        )
        self._update_status()

    def on_resize(self, *_: object) -> None:
        self.viewport.invalidate()
        self.viewport.render_now()

    def move_left(self, *_):
        self._move(-MOVE_STEP, 0.0)

    def move_right(self, *_):
        self._move(MOVE_STEP, 0.0)

    def move_up(self, *_):
        self._move(0.0, -MOVE_STEP)

    def move_down(self, *_):
        self._move(0.0, MOVE_STEP)

    def set_pitch(self, sender, *_):
        self._set_camera(pitch_deg=float(sender.value))

    def set_yaw(self, sender, *_):
        self._set_camera(yaw_deg=float(sender.value))

    def set_zoom(self, sender, *_):
        self._set_camera(zoom=float(sender.value))

    def reset_view(self, *_):
        self.avatar.center = (WORLD_W * 0.5, WORLD_H * 0.5, 0.0)
        self._set_camera(target=self.avatar.center, yaw_deg=0.0, pitch_deg=52.0, zoom=ZOOM_DEFAULT)

    def _move(self, dx: float, dy: float) -> None:
        half_size = AVATAR_SIZE * 0.5
        next_center = (
            max(half_size, min(WORLD_W - half_size, self.avatar.center[0] + dx)),
            max(half_size, min(WORLD_H - half_size, self.avatar.center[1] + dy)),
            self.avatar.center[2],
        )
        self.avatar.center = next_center
        self.follow.update(next_center)
        self.viewport.invalidate()
        self.viewport.render_now()
        self._update_status()

    def _set_camera(self, **changes: object) -> None:
        self.viewport.set_camera(replace(self.viewport.camera, **changes))
        self.viewport.render_now()
        self._update_status()

    def _update_status(self) -> None:
        camera = self.viewport.camera
        self.status.value = (
            f"avatar=({self.avatar.center[0]:.0f}, {self.avatar.center[1]:.0f})   "
            f"target=({camera.target[0]:.0f}, {camera.target[1]:.0f})   "
            f"pitch={camera.pitch_deg:.1f} deg   yaw={camera.yaw_deg:.1f} deg   "
            f"zoom={camera.zoom:.2f}x   world={WORLD_W:.0f} x {WORLD_H:.0f}"
        )


def build_ui(context: dcg.Context) -> None:
    scene, avatar = build_scene()
    initial_camera = Camera3D(
        target=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=ZOOM_DEFAULT,
    )

    with dcg.Window(
        context,
        label="Town planning grid",
        width="fillx",
        height="filly",
        primary=True,
    ) as window:
        with dcg.VerticalLayout(context, parent=window) as content:
            dcg.Text(context, parent=content, value="Town planning canvas")
            with dcg.ChildWindow(
                context,
                parent=content,
                width="fillx",
                height=f"window.height-{CONTROLS_HEIGHT:.0f}",
                no_scrollbar=True,
            ) as viewport_area:
                viewport = DrawInWindow3D(
                    context,
                    parent=viewport_area,
                    width="fillx",
                    height="filly",
                    scene=scene,
                    camera=initial_camera,
                )

            with dcg.ChildWindow(
                context,
                parent=content,
                width="fillx",
                height=CONTROLS_HEIGHT,
                no_scrollbar=True,
            ) as controls:
                status = dcg.Text(context, parent=controls, value="")
                controller = TownGridController(viewport, avatar, status)
                dcg.Slider(
                    context,
                    parent=controls,
                    label="Camera pitch from overhead (degrees)",
                    min_value=PITCH_MIN,
                    max_value=PITCH_MAX,
                    value=initial_camera.pitch_deg,
                    width="fillx",
                    callback=controller.set_pitch,
                )
                dcg.Slider(
                    context,
                    parent=controls,
                    label="Camera yaw (degrees)",
                    min_value=-180.0,
                    max_value=180.0,
                    value=initial_camera.yaw_deg,
                    width="fillx",
                    callback=controller.set_yaw,
                )
                dcg.Slider(
                    context,
                    parent=controls,
                    label="Camera zoom",
                    min_value=ZOOM_MIN,
                    max_value=ZOOM_MAX,
                    value=initial_camera.zoom,
                    width="fillx",
                    callback=controller.set_zoom,
                )
                dcg.Button(context, parent=controls, label="Reset view", callback=controller.reset_view)

            viewport.handlers += [
                dcg.ResizeHandler(context, callback=controller.on_resize),
            ]

        window.handlers += [
            dcg.KeyPressHandler(context, key=dcg.Key.LEFTARROW, repeat=False, callback=controller.move_left),
            dcg.KeyPressHandler(context, key=dcg.Key.RIGHTARROW, repeat=False, callback=controller.move_right),
            dcg.KeyPressHandler(context, key=dcg.Key.UPARROW, repeat=False, callback=controller.move_up),
            dcg.KeyPressHandler(context, key=dcg.Key.DOWNARROW, repeat=False, callback=controller.move_down),
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