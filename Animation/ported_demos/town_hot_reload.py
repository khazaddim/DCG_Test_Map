"""DearCyGui town scene host with a reloadable world-definition module.

Edit ``town_hot_reload_world.py`` while this application is running, then use
Reload world to replace the retained scene without rebuilding the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import importlib.util
from pathlib import Path
import sys
import traceback
from types import ModuleType
from threading import RLock

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import Camera3D, CpuRenderer3D, DrawInWindow3D, EdgeBandFollowController, OverlapDepthSorter
from Animation.draw_in_window_3d_framework import Box3D, CollisionWorld, Scene3D, TerrainSurface, TraversalSettings
from Animation.draw_in_window_3d_framework.profiling import RenderTelemetry
import Animation.ported_demos.town_hot_reload_world as world


VIEW_W = 900
VIEW_H = 600
PITCH_MIN = 0.0
PITCH_MAX = 78.0
ZOOM_MIN = 0.75
ZOOM_MAX = 16.0
ZOOM_DEFAULT = 3.5
CONTROLS_HEIGHT = 250.0
USE_SWEEP_AND_PRUNE = True


@dataclass(frozen=True)
class TownWorld:
    module: ModuleType
    road_texture: dcg.Texture | None
    scene: Scene3D
    avatar: Box3D
    collisions: CollisionWorld
    terrain: TerrainSurface | None
    traversal: TraversalSettings
    flags: dict[str, bool]


def load_world_candidate(module: ModuleType) -> ModuleType:
    """Execute fresh source without mutating the active module's globals."""
    if module.__file__ is None:
        raise ValueError("Reloadable world must have a source file")
    path = Path(module.__file__)
    spec = importlib.util.spec_from_file_location(module.__name__, path)
    if spec is None:
        raise ImportError(f"Cannot load world source: {path}")
    candidate = importlib.util.module_from_spec(spec)
    # Read source directly so rapid same-size edits cannot reuse stale bytecode.
    exec(compile(path.read_bytes(), str(path), "exec"), candidate.__dict__)
    return candidate


def build_world(context: dcg.Context, module: ModuleType) -> TownWorld:
    texture = module.create_road_texture(context)
    scene, avatar = module.build_scene(texture)
    collisions = module.build_collision_world()
    terrain = module.build_terrain_surface()
    traversal = module.build_traversal_settings()
    flags = module.effective_world_flags()
    resolution = collisions.resolve_movement(
        module.AabbFootprint.from_center(
            avatar.center[0], avatar.center[1], module.AVATAR_SIZE, module.AVATAR_SIZE,
        ),
        x=avatar.center[0], y=avatar.center[1], settings=traversal,
    )
    if resolution.accepted:
        avatar.center = resolution.position
    return TownWorld(module, texture, scene, avatar, collisions, terrain, traversal, flags)


class HotReloadTownController:
    def __init__(
        self,
        viewport: DrawInWindow3D,
        avatar,
        context: dcg.Context,
        road_texture: dcg.Texture | None,
        world_module: ModuleType,
        collisions,
        status: dcg.Text,
        reload_status: dcg.Text,
        *,
        prepared_world: TownWorld | None = None,
    ) -> None:
        self._world_lock = RLock()
        self.viewport = viewport
        self.avatar = avatar
        self.context = context
        self.road_texture = road_texture
        self.world_module = world_module
        self.collisions = collisions
        self.terrain = prepared_world.terrain if prepared_world else world_module.build_terrain_surface()
        self.traversal_settings = prepared_world.traversal if prepared_world else world_module.build_traversal_settings()
        self.effective_flags = dict(prepared_world.flags if prepared_world else world_module.effective_world_flags())
        self.scene_generation = 1
        self.status = status
        self.reload_status = reload_status
        self.viewport.terrain = self.terrain
        self._anchor_avatar_to_support()
        self._configure_follow()
        self._update_status()
        if viewport.telemetry is not None:
            viewport.telemetry.set_scene(self.scene_generation, self.effective_flags)

    def on_resize(self, *_: object) -> None:
        with self._world_lock:
            self.viewport.invalidate()

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
        with self._world_lock:
            self.avatar.center = self._world_center()
            self._set_camera(target=self.avatar.center, yaw_deg=0.0, pitch_deg=52.0, zoom=ZOOM_DEFAULT)

    def reload_world(self, *_: object) -> None:
        """Replace the scene only after the edited world module builds cleanly."""
        with self._world_lock:
            self._reload_world()

    def _reload_world(self) -> None:
        try:
            candidate = build_world(self.context, load_world_candidate(self.world_module))
            follow = EdgeBandFollowController(
                viewport=self.viewport,
                band_x=self.viewport.viewport.width * 0.2,
                band_y=self.viewport.viewport.height * 0.2,
                world_bounds=(0.0, 0.0, candidate.module.WORLD_W, candidate.module.WORLD_H),
                terrain=candidate.terrain,
            )
            target = self.viewport.camera.target
            camera = replace(self.viewport.camera, target=(
                max(0.0, min(candidate.module.WORLD_W, target[0])),
                max(0.0, min(candidate.module.WORLD_H, target[1])),
                target[2],
            ))
        except Exception as error:
            self.reload_status.value = f"Reload failed: {type(error).__name__}: {error}"
            traceback.print_exc()
            return

        self.world_module = candidate.module
        self.viewport.scene = candidate.scene
        self.avatar = candidate.avatar
        self.road_texture = candidate.road_texture
        self.collisions = candidate.collisions
        self.terrain = candidate.terrain
        self.traversal_settings = candidate.traversal
        self.effective_flags = dict(candidate.flags)
        self.scene_generation += 1
        self.viewport.terrain = self.terrain
        self.follow = follow
        self.viewport.set_camera(camera)
        if self.viewport.telemetry is not None:
            self.viewport.telemetry.set_scene(self.scene_generation, self.effective_flags)
        self._update_status()
        self.reload_status.value = "Reloaded world definition."

    def _move(self, dx: float, dy: float) -> None:
        with self._world_lock:
            self._move_in_world(dx, dy)

    def _move_in_world(self, dx: float, dy: float) -> None:
        half_size = self.world_module.AVATAR_SIZE * 0.5
        candidate_xy = (
            max(half_size, min(self.world_module.WORLD_W - half_size, self.avatar.center[0] + dx)),
            max(half_size, min(self.world_module.WORLD_H - half_size, self.avatar.center[1] + dy)),
        )
        resolution = self.collisions.resolve_movement(
            self.world_module.AabbFootprint.from_center(
                candidate_xy[0],
                candidate_xy[1],
                self.world_module.AVATAR_SIZE,
                self.world_module.AVATAR_SIZE,
            ),
            x=candidate_xy[0],
            y=candidate_xy[1],
            settings=self.traversal_settings,
        )
        if not resolution.accepted:
            self._update_status()
            return
        self.avatar.center = resolution.position
        self.follow.update(resolution.position)
        self.viewport.invalidate()
        self._update_status()

    def _configure_follow(self) -> None:
        self.follow = EdgeBandFollowController(
            viewport=self.viewport,
            band_x=self.viewport.viewport.width * 0.2,
            band_y=self.viewport.viewport.height * 0.2,
            world_bounds=(0.0, 0.0, self.world_module.WORLD_W, self.world_module.WORLD_H),
            terrain=self.terrain,
        )

    def _world_center(self) -> tuple[float, float, float]:
        support = self.collisions.support_sample(self.avatar.center[0], self.avatar.center[1])
        return (
            self.world_module.WORLD_W * 0.5,
            self.world_module.WORLD_H * 0.5,
            0.0 if support is None else support.height,
        )

    def _clamped_target(self, target: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            max(0.0, min(self.world_module.WORLD_W, target[0])),
            max(0.0, min(self.world_module.WORLD_H, target[1])),
            target[2],
        )

    def _set_camera(self, **changes: object) -> None:
        with self._world_lock:
            self.viewport.set_camera(replace(self.viewport.camera, **changes))
            self._update_status()

    def _anchor_avatar_to_support(self) -> None:
        resolution = self.collisions.resolve_movement(
            self.world_module.AabbFootprint.from_center(
                self.avatar.center[0],
                self.avatar.center[1],
                self.world_module.AVATAR_SIZE,
                self.world_module.AVATAR_SIZE,
            ),
            x=self.avatar.center[0],
            y=self.avatar.center[1],
            settings=self.traversal_settings,
        )
        if resolution.accepted:
            self.avatar.center = resolution.position

    def render_if_needed(self) -> None:
        with self._world_lock:
            stats = self.viewport.render_if_needed()
            if stats is not None:
                self._update_status()

    def _update_status(self) -> None:
        camera = self.viewport.camera
        sort_stats = self.viewport.last_render_stats.sort_stats
        sort_status = "sort=average-depth"
        if sort_stats is not None:
            sort_status = (
                f"sort={sort_stats.candidate_strategy} "
                f"{sort_stats.sort_duration_seconds * 1000.0:.1f}ms "
                f"pairs={sort_stats.bounds_candidate_pair_count} "
                f"exact={sort_stats.exact_test_count}"
            )
        self.status.value = (
            f"avatar=({self.avatar.center[0]:.0f}, {self.avatar.center[1]:.0f}, {self.avatar.center[2]:.1f})   "
            f"target=({camera.target[0]:.0f}, {camera.target[1]:.0f}, {camera.target[2]:.1f})   "
            f"pitch={camera.pitch_deg:.1f} deg   yaw={camera.yaw_deg:.1f} deg   "
            f"zoom={camera.zoom:.2f}x   world={self.world_module.WORLD_W:.0f} x {self.world_module.WORLD_H:.0f}   "
            f"{sort_status}"
        )


def build_ui(
    context: dcg.Context, *, telemetry: RenderTelemetry | None = None,
    use_sweep_and_prune: bool | None = None,
    primary: bool = True,
) -> HotReloadTownController:
    prepared = build_world(context, world)
    road_texture, scene, avatar = prepared.road_texture, prepared.scene, prepared.avatar
    collisions, terrain = prepared.collisions, prepared.terrain
    initial_target = avatar.center if terrain is None else (avatar.center[0], avatar.center[1], avatar.center[2])
    initial_camera = Camera3D(
        target=initial_target,
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=ZOOM_DEFAULT,
    )
    renderer = CpuRenderer3D(
        sorter=OverlapDepthSorter(
            use_sweep_and_prune=USE_SWEEP_AND_PRUNE if use_sweep_and_prune is None else use_sweep_and_prune,
        )
    )

    with dcg.Window(
        context, label="Town hot-reload experiment",
        width="fillx" if primary else VIEW_W + 80, height="filly",
        primary=primary, x=0, y=0,
    ) as window:
        with dcg.VerticalLayout(context, parent=window) as content:
            dcg.Text(context, parent=content, value="Edit town_hot_reload_world.py, then reload the world.")
            with dcg.ChildWindow(
                context,
                parent=content,
                width="fillx",
                height=f"window.height-{CONTROLS_HEIGHT + (0.0 if primary else 65.0):.0f}",
                no_scrollbar=True,
            ) as viewport_area:
                viewport = DrawInWindow3D(
                    context,
                    parent=viewport_area,
                    width="fillx",
                    height="filly",
                    scene=scene,
                    camera=initial_camera,
                    renderer=renderer,
                    terrain=terrain,
                    telemetry=telemetry,
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
                controller = HotReloadTownController(
                    viewport, avatar, context, road_texture, world, collisions, status, reload_status,
                    prepared_world=prepared,
                )
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
    controller = build_ui(context)
    while context.running:
        controller.render_if_needed()
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
