"""Framework-backed port of demo 14 using the retained 3D renderer."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import math
from pathlib import Path
import sys
import time

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    AnimatedImageMaterial,
    AnimationProjection,
    Billboard3D,
    BillboardFacing,
    Box3D,
    Camera3D,
    CollisionWorld,
    DrawInWindow3D,
    DrawStream3D,
    EdgeBandFollowController,
    ImageMaterial,
    ProjectionPipeline,
    Scene3D,
)


def load_demo(module_name: str, filename: str):
    source = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo11 = load_demo("framework_demo_11_for_14", "11_dearcygui_cpu_3d_map.py")


MARKER_WORLD_SIZE = 72.0
MARKER_HEIGHT = 185.0
MARKER_BITMAP_SIZE = 48
MARKER_FRAME_COUNT = 12
MARKER_LOOP_SECONDS = 1.2
WATER_FRAME_COUNT = 12
WATER_LOOP_SECONDS = 1.8
WATER_DASH_SPACING = 260.0
TREE_BITMAP_W = 64
TREE_BITMAP_H = 96
TREE_FRAME_COUNT = 8
TREE_LOOP_SECONDS = 1.25
COLLISION_GAP = 2.0
MOVE_REPEAT_INTERVAL = 1.0 / 30.0
MOVE_REPEAT_GRACE = 0.09


def create_player_bitmap(context: dcg.Context) -> dcg.Texture:
    size = 48
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            checker = ((x // 8) + (y // 8)) % 2
            color = (238, 72, 54) if checker else (250, 202, 62)
            if abs(x - size // 2) <= 2 or abs(y - size // 2) <= 2:
                color = (34, 214, 220)
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes((*color, 255))
    texture = dcg.Texture(context)
    texture.nearest_neighbor_upsampling = True
    texture.set_value(memoryview(pixels).cast("B", shape=(size, size, 4)))
    return texture


def create_star_sprite(context: dcg.Context) -> dcg.Texture:
    center = (MARKER_BITMAP_SIZE - 1) * 0.5
    pixels = bytearray(MARKER_BITMAP_SIZE * MARKER_BITMAP_SIZE * 4)
    for y in range(MARKER_BITMAP_SIZE):
        for x in range(MARKER_BITMAP_SIZE):
            dx = abs(x - center)
            dy = abs(y - center)
            distance = dx + dy
            if distance > center:
                continue
            if distance < center * 0.42:
                color = (255, 249, 178, 255)
            elif distance < center * 0.76:
                color = (255, 210, 54, 255)
            else:
                color = (236, 112, 36, 255)
            offset = (y * MARKER_BITMAP_SIZE + x) * 4
            pixels[offset:offset + 4] = bytes(color)
    texture = dcg.Texture(context)
    texture.nearest_neighbor_upsampling = True
    texture.set_value(memoryview(pixels).cast("B", shape=(MARKER_BITMAP_SIZE, MARKER_BITMAP_SIZE, 4)))
    return texture


def create_tree_textures(context: dcg.Context) -> tuple[dcg.Texture, ...]:
    textures: list[dcg.Texture] = []
    for frame_index in range(TREE_FRAME_COUNT):
        phase = frame_index * 2.0 * math.pi / TREE_FRAME_COUNT
        pixels = bytearray(TREE_BITMAP_W * TREE_BITMAP_H * 4)
        for y in range(TREE_BITMAP_H):
            for x in range(TREE_BITMAP_W):
                color = None
                if y >= 53 and abs(x - TREE_BITMAP_W * 0.5) <= 4:
                    color = (103, 66, 35, 255)
                canopy_y = (y - 36.0) / 34.0
                sway = math.sin(phase + y * 0.18) * 3.0
                canopy_x = (x - TREE_BITMAP_W * 0.5 - sway) / 29.0
                lobe = math.sin((x + y * 0.4) * 0.38 + phase) * 0.10
                if canopy_x * canopy_x + canopy_y * canopy_y < 0.92 + lobe:
                    shade = int(18 * math.sin(x * 0.33 + y * 0.17))
                    color = (45 + shade, 122 + shade, 57 + shade, 255)
                if color is not None:
                    offset = (y * TREE_BITMAP_W + x) * 4
                    pixels[offset:offset + 4] = bytes(color)
        texture = dcg.Texture(context)
        texture.nearest_neighbor_upsampling = True
        texture.set_value(memoryview(pixels).cast("B", shape=(TREE_BITMAP_H, TREE_BITMAP_W, 4)))
        textures.append(texture)
    return tuple(textures)


def build_marker_frame_builder(texture: dcg.Texture):
    def build_frame(context: dcg.Context, parent: dcg.DrawingList, frame, frame_index: int) -> None:
        phase = frame_index / MARKER_FRAME_COUNT
        pulse = 1.0 + 0.12 * math.sin(phase * 2.0 * math.pi)
        rotation = phase * 0.5 * math.pi
        dcg.DrawImage(
            context,
            parent=parent,
            texture=texture,
            center=(0.0, 0.0),
            width=pulse,
            height=pulse,
            direction=rotation,
        )

    return build_frame


def build_water_frame(context: dcg.Context, parent: dcg.DrawingList, frame, frame_index: int) -> None:
    pipeline = ProjectionPipeline(frame.camera, frame.viewport)
    phase = frame_index / WATER_FRAME_COUNT
    lanes = (
        (634.0, 72.0, 0.00),
        (653.0, 108.0, 0.38),
        (677.0, 84.0, 0.71),
        (697.0, 118.0, 0.19),
    )
    for lane_index, (world_y, dash_length, lane_phase) in enumerate(lanes):
        offset = ((phase + lane_phase) % 1.0) * WATER_DASH_SPACING
        world_x = offset - WATER_DASH_SPACING
        while world_x < demo11.WORLD_W:
            wave = 3.0 * math.sin(world_x * 0.012 + phase * 2.0 * math.pi)
            line = pipeline.project_line(
                (world_x, world_y + wave, 4.0),
                (world_x + dash_length, world_y - wave, 4.0),
            )
            if line is not None:
                alpha = 105 if lane_index % 2 == 0 else 75
                dcg.DrawLine(
                    context,
                    parent=parent,
                    p1=line.p0,
                    p2=line.p1,
                    color=(176, 224, 240, alpha),
                    thickness=-2,
                )
            world_x += WATER_DASH_SPACING


def footprint_for(box: Box3D) -> AabbFootprint:
    return AabbFootprint.from_center(
        box.center[0],
        box.center[1],
        box.size[0],
        box.size[1],
    )


def build_collision_world(scene: Scene3D, player: Box3D) -> CollisionWorld:
    collisions = CollisionWorld(gap=COLLISION_GAP)
    building_index = 1
    for item in scene.iter_visible():
        if isinstance(item, Box3D) and item is not player:
            collisions.add(f"building {building_index}", footprint_for(item))
            building_index += 1
    return collisions


def build_scene(context: dcg.Context) -> tuple[Scene3D, Box3D, DrawStream3D]:
    scene, player = demo11.build_scene()
    player_texture = create_player_bitmap(context)
    marker_texture = create_star_sprite(context)
    tree_textures = create_tree_textures(context)

    player.face_materials = (
        None,
        None,
        None,
        None,
        ImageMaterial(texture=player_texture, tessellation=12),
        None,
    )

    scene.add(
        DrawStream3D(
            projection_policy=AnimationProjection.PREPROJECTED_BACKGROUND,
            frame_count=WATER_FRAME_COUNT,
            loop_seconds=WATER_LOOP_SECONDS,
            frame_builder=build_water_frame,
        )
    )

    marker = DrawStream3D(
        projection_policy=AnimationProjection.PERSISTENT_OVERLAY,
        frame_count=MARKER_FRAME_COUNT,
        loop_seconds=MARKER_LOOP_SECONDS,
        frame_builder=build_marker_frame_builder(marker_texture),
        anchor=(player.center[0], player.center[1], MARKER_HEIGHT),
        world_size=(MARKER_WORLD_SIZE, MARKER_WORLD_SIZE),
    )
    scene.add(marker)

    trees = (
        ((655.0, 540.0, 0.0), (150.0, 255.0), 0),
        ((1260.0, 650.0, 0.0), (185.0, 285.0), 4),
    )
    for anchor, world_size, frame_offset in trees:
        scene.add(
            Billboard3D(
                anchor=anchor,
                world_size=world_size,
                facing=BillboardFacing.CAMERA_YAW,
                material=AnimatedImageMaterial(
                    frames=tree_textures,
                    loop_seconds=TREE_LOOP_SECONDS,
                    frame_offset=frame_offset,
                    projection_policy=AnimationProjection.OCCLUDABLE_WORLD,
                    tessellation=1,
                ),
            )
        )

    return scene, player, marker


class FrameworkDemo14Controller:
    def __init__(
        self,
        viewport: DrawInWindow3D,
        player: Box3D,
        marker: DrawStream3D,
        status: dcg.Text,
        collisions: CollisionWorld,
    ) -> None:
        self.viewport = viewport
        self.player = player
        self.marker = marker
        self.status = status
        self.collisions = collisions
        self.blocked_by: object | None = None
        self._move_until: dict[str, float] = {
            "left": 0.0,
            "right": 0.0,
            "up": 0.0,
            "down": 0.0,
        }
        self._next_move_time = 0.0
        self.follow = EdgeBandFollowController(
            viewport=viewport,
            band_x=demo11.EDGE_BAND_X,
            band_y=demo11.EDGE_BAND_Y,
            world_bounds=(0.0, 0.0, demo11.WORLD_W, demo11.WORLD_H),
        )
        self.repaint()

    def move_left(self, *_):
        self._queue_move("left")

    def move_right(self, *_):
        self._queue_move("right")

    def move_up(self, *_):
        self._queue_move("up")

    def move_down(self, *_):
        self._queue_move("down")

    def set_pitch(self, sender, target, value) -> None:
        self.viewport.set_camera(replace(self.viewport.camera, pitch_deg=float(sender.value)))

    def set_yaw(self, sender, target, value) -> None:
        self.viewport.set_camera(replace(self.viewport.camera, yaw_deg=float(sender.value)))

    def set_zoom(self, sender, target, value) -> None:
        requested_zoom = max(demo11.ZOOM_MIN, min(demo11.ZOOM_MAX, float(sender.value)))
        self.viewport.set_camera(replace(self.viewport.camera, zoom=requested_zoom))

    def _queue_move(self, direction: str, *, now: float | None = None) -> None:
        now = time.perf_counter() if now is None else now
        self._move_until[direction] = now + MOVE_REPEAT_GRACE
        self._next_move_time = min(self._next_move_time, now)
        self.viewport.invalidate()

    def tick(self, now: float | None = None) -> bool:
        now = time.perf_counter() if now is None else now
        dx = 0.0
        dy = 0.0
        if now <= self._move_until["left"]:
            dx -= demo11.MOVE_STEP
        if now <= self._move_until["right"]:
            dx += demo11.MOVE_STEP
        if now <= self._move_until["up"]:
            dy -= demo11.MOVE_STEP
        if now <= self._move_until["down"]:
            dy += demo11.MOVE_STEP
        if dx == 0.0 and dy == 0.0:
            return False
        if now < self._next_move_time:
            return False
        self._apply_move(dx, dy)
        self._next_move_time = now + MOVE_REPEAT_INTERVAL
        return True

    def _apply_move(self, dx: float, dy: float) -> None:
        half_width = self.player.size[0] * 0.5
        half_depth = self.player.size[1] * 0.5
        candidate_center = (
            max(half_width, min(demo11.WORLD_W - half_width, self.player.center[0] + dx)),
            max(half_depth, min(demo11.WORLD_H - half_depth, self.player.center[1] + dy)),
            self.player.center[2],
        )
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
            self.marker.anchor = (candidate_center[0], candidate_center[1], MARKER_HEIGHT)
            self.follow.update(candidate_center)
            self.blocked_by = None
        else:
            self.blocked_by = blocker.owner
        self.viewport.invalidate()

    def render_if_needed(self) -> None:
        stats = self.viewport.render_if_needed()
        if stats is not None:
            self._update_status(stats)

    def repaint(self) -> None:
        self.viewport.invalidate()
        stats = self.viewport.render_now()
        self._update_status(stats)

    def _update_status(self, stats) -> None:
        camera = self.viewport.camera
        self.status.value = (
            f"piece=({self.player.center[0]:.0f},{self.player.center[1]:.0f},0)  "
            f"target=({camera.target[0]:.0f},{camera.target[1]:.0f})  "
            f"pitch={camera.pitch_deg:.1f} deg  yaw={camera.yaw_deg:.1f} deg  "
            f"zoom={camera.zoom:.2f}x  packets={stats.packet_count}  trees + water + overlay"
        )
        if self.blocked_by is not None:
            self.status.value += f"  blocked by={self.blocked_by}"


def build_ui(context: dcg.Context) -> None:
    scene, player, marker = build_scene(context)
    collisions = build_collision_world(scene, player)
    initial_camera = Camera3D(
        target=(demo11.WORLD_W * 0.5, demo11.WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=0.72,
    )
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 14", width=demo11.VIEW_W + 40, height=demo11.VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="Arrow keys move the textured player; the river shimmers, the marker persists, and trees sort with the buildings.",
            wrap=demo11.VIEW_W,
        )
        status = dcg.Text(context, value="")
        with DrawInWindow3D(context, width=demo11.VIEW_W, height=demo11.VIEW_H, scene=scene, camera=initial_camera) as viewport:
            band_color = (245, 205, 83, 35)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(demo11.VIEW_W, demo11.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, demo11.VIEW_H - demo11.EDGE_BAND_Y), pmax=(demo11.VIEW_W, demo11.VIEW_H), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, demo11.EDGE_BAND_Y), pmax=(demo11.EDGE_BAND_X, demo11.VIEW_H - demo11.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(demo11.VIEW_W - demo11.EDGE_BAND_X, demo11.EDGE_BAND_Y), pmax=(demo11.VIEW_W, demo11.VIEW_H - demo11.EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(demo11.EDGE_BAND_X, demo11.EDGE_BAND_Y), pmax=(demo11.VIEW_W - demo11.EDGE_BAND_X, demo11.VIEW_H - demo11.EDGE_BAND_Y), color=(245, 205, 83, 115), thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(demo11.VIEW_W, demo11.VIEW_H), color=(112, 132, 155), thickness=-2)

        controller = FrameworkDemo14Controller(viewport, player, marker, status, collisions)
        dcg.Slider(
            context,
            label="Camera pitch from overhead (degrees)",
            min_value=0.0,
            max_value=78.0,
            value=controller.viewport.camera.pitch_deg,
            width=demo11.VIEW_W,
            callback=controller.set_pitch,
        )
        dcg.Slider(
            context,
            label="Camera yaw (degrees)",
            min_value=-180.0,
            max_value=180.0,
            value=controller.viewport.camera.yaw_deg,
            width=demo11.VIEW_W,
            callback=controller.set_yaw,
        )
        dcg.Slider(
            context,
            label="Camera zoom",
            min_value=demo11.ZOOM_MIN,
            max_value=demo11.ZOOM_MAX,
            value=controller.viewport.camera.zoom,
            width=demo11.VIEW_W,
            callback=controller.set_zoom,
        )
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW, callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW, callback=controller.move_down),
        ]
    return controller


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - Framework Demo 14", width=demo11.VIEW_W + 80, height=demo11.VIEW_H + 340)
    controller = build_ui(context)
    while context.running:
        controller.tick()
        controller.render_if_needed()
        context.viewport.render_frame()


if __name__ == "__main__":
    main()