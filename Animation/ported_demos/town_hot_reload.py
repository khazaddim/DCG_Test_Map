"""DearCyGui town scene host with a reloadable world-definition module.

Edit ``town_hot_reload_world.py`` while this application is running, then use
Reload world to replace the retained scene without rebuilding the UI.
"""

from __future__ import annotations

from dataclasses import replace
import importlib
from pathlib import Path
import sys
import traceback
from types import ModuleType

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import Camera3D, DrawInWindow3D, EdgeBandFollowController
import Animation.ported_demos.town_hot_reload_world as world


VIEW_W = 900
VIEW_H = 600
PITCH_MIN = 0.0
PITCH_MAX = 78.0
ZOOM_MIN = 0.75
ZOOM_MAX = 16.0
ZOOM_DEFAULT = 3.5
CONTROLS_HEIGHT = 250.0


class HotReloadTownController:
    def __init__(
        self,
        viewport: DrawInWindow3D,
        avatar,
        world_module: ModuleType,
        status: dcg.Text,
        reload_status: dcg.Text,
    ) -> None:
        self.viewport = viewport
        self.avatar = avatar
        self.world_module = world_module
        self.status = status
        self.reload_status = reload_status
        self._configure_follow()
        self._update_status()

    def on_resize(self, *_: object) -> None:
        self.viewport.invalidate()
        self.viewport.render_now()

    def move_left(self, *_: object) -> None:
        self._move(-self.world_module.GRID_STEP, 0.0)

    def move_right(self, *_: object) -> None:
        self._move(self.world_module.GRID_STEP, 0.0)

    def move_up(self, *_: object) -> None:
        self._move(0.0, -self.world_module.GRID_STEP)

    def move_down(self, *_: object) -> None:
        self._move(0.0, self.world_module.GRID_STEP)

    def set_pitch(self, sender, *_: object) -> None:
        self._set_camera(pitch_deg=float(sender.value))

    def set_yaw(self, sender, *_: object) -> None:
        self._set_camera(yaw_deg=float(sender.value))

    def set_zoom(self, sender, *_: object) -> None:
        self._set_camera(zoom=float(sender.value))

    def reset_view(self, *_: object) -> None:
        self.avatar.center = self._world_center()
        self._set_camera(target=self.avatar.center, yaw_deg=0.0, pitch_deg=52.0, zoom=ZOOM_DEFAULT)

    def reload_world(self, *_: object) -> None:
        """Replace the scene only after the edited world module builds cleanly."""
        try:
            importlib.invalidate_caches()
            candidate_module = importlib.reload(self.world_module)
            candidate_scene, candidate_avatar = candidate_module.build_scene()
        except Exception as error:
            self.reload_status.value = f"Reload failed: {type(error).__name__}: {error}"
            traceback.print_exc()
            return

        self.world_module = candidate_module
        self.viewport.scene = candidate_scene
        self.avatar = candidate_avatar
        self._configure_follow()
        self._set_camera(target=self._clamped_target(self.viewport.camera.target))
        self.reload_status.value = "Reloaded world definition."

    def _move(self, dx: float, dy: float) -> None:
        half_size = self.world_module.AVATAR_SIZE * 0.5
        next_center = (
            max(half_size, min(self.world_module.WORLD_W - half_size, self.avatar.center[0] + dx)),
            max(half_size, min(self.world_module.WORLD_H - half_size, self.avatar.center[1] + dy)),
            self.avatar.center[2],
        )
        self.avatar.center = next_center
        self.follow.update(next_center)
        self.viewport.invalidate()
        self.viewport.render_now()
        self._update_status()

    def _configure_follow(self) -> None:
        self.follow = EdgeBandFollowController(
            viewport=self.viewport,
            band_x=self.viewport.viewport.width * 0.2,
            band_y=self.viewport.viewport.height * 0.2,
            world_bounds=(0.0, 0.0, self.world_module.WORLD_W, self.world_module.WORLD_H),
        )

    def _world_center(self) -> tuple[float, float, float]:
        return self.world_module.WORLD_W * 0.5, self.world_module.WORLD_H * 0.5, 0.0

    def _clamped_target(self, target: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            max(0.0, min(self.world_module.WORLD_W, target[0])),
            max(0.0, min(self.world_module.WORLD_H, target[1])),
            target[2],
        )

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
            f"zoom={camera.zoom:.2f}x   world={self.world_module.WORLD_W:.0f} x {self.world_module.WORLD_H:.0f}"
        )


def build_ui(context: dcg.Context) -> HotReloadTownController:
    scene, avatar = world.build_scene()
    initial_camera = Camera3D(
        target=avatar.center,
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=ZOOM_DEFAULT,
    )

    with dcg.Window(context, label="Town hot-reload experiment", width="fillx", height="filly", primary=True) as window:
        with dcg.VerticalLayout(context, parent=window) as content:
            dcg.Text(context, parent=content, value="Edit town_hot_reload_world.py, then reload the world.")
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
                reload_status = dcg.Text(context, parent=controls, value="World definition loaded.")
                controller = HotReloadTownController(viewport, avatar, world, status, reload_status)
                dcg.Button(context, parent=controls, label="Reload world", callback=controller.reload_world)
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

            viewport.handlers += [dcg.ResizeHandler(context, callback=controller.on_resize)]

        window.handlers += [
            dcg.KeyPressHandler(context, key=dcg.Key.LEFTARROW, repeat=False, callback=controller.move_left),
            dcg.KeyPressHandler(context, key=dcg.Key.RIGHTARROW, repeat=False, callback=controller.move_right),
            dcg.KeyPressHandler(context, key=dcg.Key.UPARROW, repeat=False, callback=controller.move_up),
            dcg.KeyPressHandler(context, key=dcg.Key.DOWNARROW, repeat=False, callback=controller.move_down),
        ]
    return controller


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Town hot reload",
        width=VIEW_W + 80,
        height=VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
