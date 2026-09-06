"""Configurable collision and ordering example for the retained CPU 3D framework."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    AverageDepthSorter,
    Box3D,
    Camera3D,
    CollisionWorld,
    CpuRenderer3D,
    DrawInWindow3D,
    OverlapDepthSorter,
    RenderStats,
)


COLLISION_OPTIONS = ("enabled", "disabled")
SORTER_OPTIONS = ("overlap", "average")
COLLISION_GAP = 2.0


def load_demo_11():
    source = Path(__file__).with_name("11_dearcygui_cpu_3d_map.py")
    spec = importlib.util.spec_from_file_location("framework_demo_11_for_controls", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = load_demo_11()


def build_sorter(mode: str):
    normalized = str(mode).strip().lower()
    if normalized == "average":
        return AverageDepthSorter()
    return OverlapDepthSorter()


def footprint_for(box: Box3D) -> AabbFootprint:
    return AabbFootprint.from_center(
        box.center[0],
        box.center[1],
        box.size[0],
        box.size[1],
    )


def build_collision_world(scene, player: Box3D) -> CollisionWorld:
    collisions = CollisionWorld(gap=COLLISION_GAP)
    building_index = 1
    for item in scene.iter_visible():
        # Reuse the visible building boxes as the diagnostic collision footprint set.
        if isinstance(item, Box3D) and item is not player:
            collisions.add(f"building {building_index}", footprint_for(item))
            building_index += 1
    return collisions


def build_status_text(
    player: Box3D,
    camera: Camera3D,
    viewport_size: tuple[float, float],
    stats: RenderStats,
    *,
    collision_enabled: bool,
    sorter_mode: str,
    blocked_by: object | None,
) -> str:
    blocked_status = f"  blocked by={blocked_by}" if blocked_by is not None else ""
    cycle_status = "  occlusion cycle fallback" if stats.cycle_detected else ""
    return (
        f"piece=({player.center[0]:.0f},{player.center[1]:.0f},0)  "
        f"target=({camera.target[0]:.0f},{camera.target[1]:.0f})  "
        f"pitch={camera.pitch_deg:.1f} deg  yaw={camera.yaw_deg:.1f} deg  "
        f"zoom={camera.zoom:.2f}x  view=({viewport_size[0]:.0f}x{viewport_size[1]:.0f})  "
        f"collision={'on' if collision_enabled else 'off'}  sort={sorter_mode}  "
        f"projected={stats.projected_count}  clipped={stats.clipped_count}"
        f"{blocked_status}{cycle_status}"
    )


class ConfigurableCollisionSortController(demo.FrameworkDemoController):
    def __init__(self, viewport: DrawInWindow3D, player: Box3D, status: dcg.Text, collisions: CollisionWorld) -> None:
        self.collisions = collisions
        self.collision_enabled = True
        self.sorter_mode = "overlap"
        self.blocked_by: object | None = None
        super().__init__(viewport, player, status)

    def set_collision_mode(self, sender, *_: object) -> None:
        self.collision_enabled = str(sender.value).strip().lower() != "disabled"
        self.blocked_by = None
        self.repaint()

    def set_sorter_mode(self, sender, *_: object) -> None:
        self.sorter_mode = str(sender.value).strip().lower()
        self.viewport.renderer.sorter = build_sorter(self.sorter_mode)
        self.repaint()

    def _move(self, dx: float, dy: float) -> None:
        half_width = self.player.size[0] * 0.5
        half_depth = self.player.size[1] * 0.5
        candidate_center = (
            max(half_width, min(demo.WORLD_W - half_width, self.player.center[0] + dx)),
            max(half_depth, min(demo.WORLD_H - half_depth, self.player.center[1] + dy)),
            self.player.center[2],
        )
        blocker = None
        if self.collision_enabled:
            blocker = self.collisions.first_blocker(
                AabbFootprint.from_center(
                    candidate_center[0],
                    candidate_center[1],
                    self.player.size[0],
                    self.player.size[1],
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
        self.viewport.invalidate()
        stats = self.viewport.render_now()
        self.status.value = build_status_text(
            self.player,
            self.viewport.camera,
            (self.viewport.viewport.width, self.viewport.viewport.height),
            stats,
            collision_enabled=self.collision_enabled,
            sorter_mode=self.sorter_mode,
            blocked_by=self.blocked_by,
        )


def build_ui(context: dcg.Context) -> ConfigurableCollisionSortController:
    scene, player = demo.build_scene()
    collisions = build_collision_world(scene, player)
    camera = Camera3D(
        target=(demo.WORLD_W * 0.5, demo.WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=0.72,
    )
    # Swap sorters on the same scene to compare ordering behavior without changing world content.
    renderer = CpuRenderer3D(sorter=build_sorter("overlap"))

    with dcg.Window(
        context,
        label="DearCyGui CPU 3D map - Collision and ordering diagnostics",
        width=demo.VIEW_W + 40,
        height=demo.VIEW_H + 360,
    ) as window:
        dcg.Text(
            context,
            value=(
                "Arrow keys move the gold 3D piece. Toggle collision independently from "
                "average-depth vs overlap-aware sorting and watch the diagnostics line."
            ),
            wrap=demo.VIEW_W,
        )
        status = dcg.Text(context, value="")
        with DrawInWindow3D(
            context,
            width=demo.VIEW_W,
            height=demo.VIEW_H,
            scene=scene,
            camera=camera,
            renderer=renderer,
        ) as viewport:
            band_color = (245, 205, 83, 35)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(demo.VIEW_W, demo.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, demo.VIEW_H - demo.EDGE_BAND_Y), pmax=(demo.VIEW_W, demo.VIEW_H), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, demo.EDGE_BAND_Y), pmax=(demo.EDGE_BAND_X, demo.VIEW_H - demo.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(demo.VIEW_W - demo.EDGE_BAND_X, demo.EDGE_BAND_Y), pmax=(demo.VIEW_W, demo.VIEW_H - demo.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            # Keep the familiar edge-band overlay so camera-follow behavior stays comparable to Demo 11.
            dcg.DrawRect(context, parent=viewport, pmin=(demo.EDGE_BAND_X, demo.EDGE_BAND_Y), pmax=(demo.VIEW_W - demo.EDGE_BAND_X, demo.VIEW_H - demo.EDGE_BAND_Y), color=(245, 205, 83, 115), thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(demo.VIEW_W, demo.VIEW_H), color=(112, 132, 155), thickness=-2)

        controller = ConfigurableCollisionSortController(viewport, player, status, collisions)
        dcg.Combo(
            context,
            label="Collision",
            items=list(COLLISION_OPTIONS),
            value="enabled",
            width=demo.VIEW_W,
            callback=controller.set_collision_mode,
        )
        dcg.Combo(
            context,
            label="Ordering strategy",
            items=list(SORTER_OPTIONS),
            value="overlap",
            width=demo.VIEW_W,
            callback=controller.set_sorter_mode,
        )
        dcg.Slider(context, label="Camera pitch from overhead (degrees)", min_value=0.0, max_value=78.0, value=controller.viewport.camera.pitch_deg, width=demo.VIEW_W, callback=controller.set_pitch)
        dcg.Slider(context, label="Camera yaw (degrees)", min_value=-180.0, max_value=180.0, value=controller.viewport.camera.yaw_deg, width=demo.VIEW_W, callback=controller.set_yaw)
        dcg.Slider(context, label="Camera zoom", min_value=demo.ZOOM_MIN, max_value=demo.ZOOM_MAX, value=controller.viewport.camera.zoom, width=demo.VIEW_W, callback=controller.set_zoom)
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW, callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW, callback=controller.move_down),
        ]
    return controller


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - collision and ordering diagnostics",
        width=demo.VIEW_W + 80,
        height=demo.VIEW_H + 400,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()