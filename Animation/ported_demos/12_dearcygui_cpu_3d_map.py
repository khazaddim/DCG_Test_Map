"""Framework-backed port of demo 12's collision-safe CPU-side 3D map."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import AabbFootprint, Box3D, CollisionWorld


def load_demo_11():
    source = Path(__file__).with_name("11_dearcygui_cpu_3d_map.py")
    spec = importlib.util.spec_from_file_location("framework_demo_11_for_12", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = load_demo_11()
COLLISION_GAP = 2.0


def footprint_for(box: Box3D) -> AabbFootprint:
    return AabbFootprint.from_center(
        box.center[0],
        box.center[1],
        box.size[0],
        box.size[1],
    )


class CollisionDemoController(demo.FrameworkDemoController):
    def __init__(self, viewport, player: Box3D, status: dcg.Text, collisions: CollisionWorld) -> None:
        self.collisions = collisions
        self.blocked_by: object | None = None
        super().__init__(viewport, player, status)

    def _move(self, dx: float, dy: float) -> None:
        half_width = self.player.size[0] * 0.5
        half_depth = self.player.size[1] * 0.5
        candidate_center = (
            max(half_width, min(demo.WORLD_W - half_width, self.player.center[0] + dx)),
            max(half_depth, min(demo.WORLD_H - half_depth, self.player.center[1] + dy)),
            self.player.center[2],
        )
        blocker = self.collisions.first_blocker(
            AabbFootprint.from_center(
                candidate_center[0], candidate_center[1], self.player.size[0], self.player.size[1]
            )
        )
        if blocker is None:
            self.player.center = candidate_center
            self.follow.update(candidate_center)
            self.blocked_by = None
        else:
            self.blocked_by = blocker.owner
        self.repaint()

    def repaint(self) -> None:
        super().repaint()
        if self.blocked_by is not None:
            self.status.value += f"  blocked by={self.blocked_by}"


def build_collision_world(scene, player: Box3D) -> CollisionWorld:
    collisions = CollisionWorld(gap=COLLISION_GAP)
    building_index = 1
    for item in scene.iter_visible():
        # Reuse every non-player Box3D footprint as the movement blocker set.
        if isinstance(item, Box3D) and item is not player:
            collisions.add(f"building {building_index}", footprint_for(item))
            building_index += 1
    return collisions


def build_ui(context: dcg.Context) -> None:
    scene, player = demo.build_scene()
    collisions = build_collision_world(scene, player)
    initial_camera = demo.Camera3D(
        target=(demo.WORLD_W * 0.5, demo.WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=0.72,
    )
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 12", width=demo.VIEW_W + 40, height=demo.VIEW_H + 300) as window:
        dcg.Text(context, value="Arrow keys move the gold 3D piece. Buildings keep a small separation.", wrap=demo.VIEW_W)
        status = dcg.Text(context, value="")
        with demo.DrawInWindow3D(context, width=demo.VIEW_W, height=demo.VIEW_H, scene=scene, camera=initial_camera) as viewport:
            band_color = (245, 205, 83, 35)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(demo.VIEW_W, demo.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, demo.VIEW_H - demo.EDGE_BAND_Y), pmax=(demo.VIEW_W, demo.VIEW_H), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, demo.EDGE_BAND_Y), pmax=(demo.EDGE_BAND_X, demo.VIEW_H - demo.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(demo.VIEW_W - demo.EDGE_BAND_X, demo.EDGE_BAND_Y), pmax=(demo.VIEW_W, demo.VIEW_H - demo.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(demo.EDGE_BAND_X, demo.EDGE_BAND_Y), pmax=(demo.VIEW_W - demo.EDGE_BAND_X, demo.VIEW_H - demo.EDGE_BAND_Y), color=(245, 205, 83, 115), thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(demo.VIEW_W, demo.VIEW_H), color=(112, 132, 155), thickness=-2)
        controller = CollisionDemoController(viewport, player, status, collisions)
        dcg.Slider(context, label="Camera pitch from overhead (degrees)", min_value=0.0, max_value=78.0, value=controller.viewport.camera.pitch_deg, width=demo.VIEW_W, callback=controller.set_pitch)
        dcg.Slider(context, label="Camera yaw (degrees)", min_value=-180.0, max_value=180.0, value=controller.viewport.camera.yaw_deg, width=demo.VIEW_W, callback=controller.set_yaw)
        dcg.Slider(context, label="Camera zoom", min_value=demo.ZOOM_MIN, max_value=demo.ZOOM_MAX, value=controller.viewport.camera.zoom, width=demo.VIEW_W, callback=controller.set_zoom)
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW, callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW, callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - Demo 12 collision-safe CPU 3D", width=demo.VIEW_W + 80, height=demo.VIEW_H + 340)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()