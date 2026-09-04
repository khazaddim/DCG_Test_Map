"""Framework-backed port of demo 11's CPU-side 3D map renderer."""

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
    Polygon3D,
    Polyline3D,
    Scene3D,
    SolidMaterial,
    Text3D,
)


VIEW_W = 900
VIEW_H = 600
WORLD_W = 2200.0
WORLD_H = 1500.0
MOVE_STEP = 35.0
PIECE_SIZE = 70.0
PIECE_HEIGHT = 115.0
EDGE_BAND_X = 150.0
EDGE_BAND_Y = 200.0
ZOOM_MIN = 0.35
ZOOM_MAX = 2.0
GROUND_PAD = 7000.0
GRID_LINE_Z = 0.5
BORDER_LINE_Z = 0.5


def build_scene() -> tuple[Scene3D, Box3D]:
    scene = Scene3D(background=(19, 24, 31))
    # Base terrain that sits under the whole map.
    scene.add(
        GroundPlane3D(
            bounds=(-GROUND_PAD, -GROUND_PAD, WORLD_W + GROUND_PAD, WORLD_H + GROUND_PAD),
            z=0.0,
            material=SolidMaterial(fill=(42, 66, 47), outline=None, thickness=-1.0, shaded=False),
        )
    )
    # Horizontal blue band across the map.
    scene.add(
        Polygon3D(
            points=((0.0, 620.0, 1.0), (WORLD_W, 620.0, 1.0), (WORLD_W, 710.0, 1.0), (0.0, 710.0, 1.0)),
            material=SolidMaterial(fill=(68, 116, 168), outline=None, thickness=-1.0, shaded=False, line_occluder=False),
            cull_back_face=False,
        )
    )
    # Vertical brown band that cuts through the map.
    scene.add(
        Polygon3D(
            points=((910.0, 0.0, 2.0), (995.0, 0.0, 2.0), (995.0, WORLD_H, 2.0), (910.0, WORLD_H, 2.0)),
            material=SolidMaterial(fill=(130, 116, 91), outline=None, thickness=-1.0, shaded=False, line_occluder=False),
            cull_back_face=False,
        )
    )

    for grid_x in range(0, int(WORLD_W) + 1, 100):
        # Vertical grid line for map measurement.
        scene.add(
            Line3D(
                start=(float(grid_x), 0.0, GRID_LINE_Z),
                end=(float(grid_x), WORLD_H, GRID_LINE_Z),
                color=(65, 91, 68),
                thickness=-1.0,
            )
        )
    for grid_y in range(0, int(WORLD_H) + 1, 100):
        # Horizontal grid line for map measurement.
        scene.add(
            Line3D(
                start=(0.0, float(grid_y), GRID_LINE_Z),
                end=(WORLD_W, float(grid_y), GRID_LINE_Z),
                color=(65, 91, 68),
                thickness=-1.0,
            )
        )

    # Outer boundary of the playable world.
    scene.add(
        Polyline3D(
            points=((0.0, 0.0, BORDER_LINE_Z), (WORLD_W, 0.0, BORDER_LINE_Z), (WORLD_W, WORLD_H, BORDER_LINE_Z), (0.0, WORLD_H, BORDER_LINE_Z)),
            color=(235, 214, 116),
            thickness=-3.0,
            closed=True,
        )
    )

    for grid_x in range(0, int(WORLD_W) + 1, 200):
        for grid_y in range(0, int(WORLD_H) + 1, 200):
            # Coordinate label placed on the ground at this grid intersection.
            scene.add(
                Text3D(
                    position=(float(grid_x + 5), float(grid_y + 4), 6.0),
                    text=f"{grid_x},{grid_y}",
                    size=13.0,
                    color=(132, 164, 137),
                )
            )

    boxes = [
        (440.0, 400.0, 210.0, 180.0, 320.0, (175, 105, 72), "watch tower"),
        (820.0, 980.0, 260.0, 220.0, 180.0, (93, 136, 170), "storehouse"),
        (1450.0, 430.0, 180.0, 180.0, 420.0, (154, 126, 72), "high tower"),
        (1760.0, 1080.0, 340.0, 240.0, 140.0, (113, 145, 91), "hall"),
    ]
    for center_x, center_y, width, depth, height, color, name in boxes:
        # Rectangular building footprint and its height in the world.
        scene.add(
            Box3D(
                center=(center_x, center_y, 0.0),
                size=(width, depth, height),
                material=SolidMaterial(fill=color, outline=(24, 27, 25), thickness=-2.0, shaded=True),
            )
        )
        # Name label anchored just outside the building footprint.
        scene.add(
            Text3D(
                position=(center_x - width * 0.5, center_y + depth * 0.5 + 28.0, 6.0),
                text=name,
                size=16.0,
                color=(218, 207, 151),
            )
        )

    # Movable player piece that the arrow keys control.
    player = Box3D(
        center=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0),
        size=(PIECE_SIZE, PIECE_SIZE, PIECE_HEIGHT),
        material=SolidMaterial(fill=(245, 194, 67), outline=(24, 27, 25), thickness=-2.0, shaded=True),
    )
    scene.add(player)
    return scene, player


class FrameworkDemoController:
    def __init__(self, viewport: DrawInWindow3D, player: Box3D, status: dcg.Text) -> None:
        self.viewport = viewport
        self.player = player
        self.status = status
        self.follow = EdgeBandFollowController(
            viewport=viewport,
            band_x=EDGE_BAND_X,
            band_y=EDGE_BAND_Y,
            world_bounds=(0.0, 0.0, WORLD_W, WORLD_H),
        )
        self.repaint()

    def move_left(self, *_):
        self._move(-MOVE_STEP, 0.0)

    def move_right(self, *_):
        self._move(MOVE_STEP, 0.0)

    def move_up(self, *_):
        self._move(0.0, -MOVE_STEP)

    def move_down(self, *_):
        self._move(0.0, MOVE_STEP)

    def set_pitch(self, sender, target, value) -> None:
        self.viewport.set_camera(replace(self.viewport.camera, pitch_deg=float(sender.value)))
        self.repaint()

    def set_yaw(self, sender, target, value) -> None:
        self.viewport.set_camera(replace(self.viewport.camera, yaw_deg=float(sender.value)))
        self.repaint()

    def set_zoom(self, sender, target, value) -> None:
        requested_zoom = max(ZOOM_MIN, min(ZOOM_MAX, float(sender.value)))
        self.viewport.set_camera(replace(self.viewport.camera, zoom=requested_zoom))
        self.repaint()

    def _move(self, dx: float, dy: float) -> None:
        half_size = PIECE_SIZE * 0.5
        next_center = (
            max(half_size, min(WORLD_W - half_size, self.player.center[0] + dx)),
            max(half_size, min(WORLD_H - half_size, self.player.center[1] + dy)),
            self.player.center[2],
        )
        self.player.center = next_center
        self.follow.update(next_center)
        self.repaint()

    def repaint(self) -> None:
        self.viewport.invalidate()
        self.viewport.render_now()
        camera = self.viewport.camera
        self.status.value = (
            f"piece=({self.player.center[0]:.0f},{self.player.center[1]:.0f},0)  "
            f"target=({camera.target[0]:.0f},{camera.target[1]:.0f})  "
            f"pitch={camera.pitch_deg:.1f} deg  yaw={camera.yaw_deg:.1f} deg  "
            f"zoom={camera.zoom:.2f}x  camera distance={camera.distance(self.viewport.viewport):.0f}"
        )


def build_ui(context: dcg.Context) -> None:
    scene, player = build_scene()
    initial_camera = Camera3D(
        target=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=0.72,
    )
    with dcg.Window(context, label="DearCyGui CPU 3D map", width=VIEW_W + 40, height=VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="Arrow keys move the gold 3D piece; the camera follows when it enters an edge band.",
            wrap=VIEW_W,
        )
        status = dcg.Text(context, value="")
        with DrawInWindow3D(context, width=VIEW_W, height=VIEW_H, scene=scene, camera=initial_camera) as viewport:
            band_color = (245, 205, 83, 35)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(VIEW_W, EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, VIEW_H - EDGE_BAND_Y), pmax=(VIEW_W, VIEW_H), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, EDGE_BAND_Y), pmax=(EDGE_BAND_X, VIEW_H - EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(VIEW_W - EDGE_BAND_X, EDGE_BAND_Y), pmax=(VIEW_W, VIEW_H - EDGE_BAND_Y), fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(EDGE_BAND_X, EDGE_BAND_Y), pmax=(VIEW_W - EDGE_BAND_X, VIEW_H - EDGE_BAND_Y), color=(245, 205, 83, 115), thickness=-1)
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(VIEW_W, VIEW_H), color=(112, 132, 155), thickness=-2)

        controller = FrameworkDemoController(viewport, player, status)
        dcg.Slider(
            context,
            label="Camera pitch from overhead (degrees)",
            min_value=0.0,
            max_value=78.0,
            value=controller.viewport.camera.pitch_deg,
            width=VIEW_W,
            callback=controller.set_pitch,
        )
        dcg.Slider(
            context,
            label="Camera yaw (degrees)",
            min_value=-180.0,
            max_value=180.0,
            value=controller.viewport.camera.yaw_deg,
            width=VIEW_W,
            callback=controller.set_yaw,
        )
        dcg.Slider(
            context,
            label="Camera zoom",
            min_value=ZOOM_MIN,
            max_value=ZOOM_MAX,
            value=controller.viewport.camera.zoom,
            width=VIEW_W,
            callback=controller.set_zoom,
        )
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW, callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW, callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - CPU 3D environment", width=VIEW_W + 80, height=VIEW_H + 340)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()