"""AABB collision demo with tessellated image materials on selected box faces."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Box3D,
    Camera3D,
    CollisionWorld,
    DrawInWindow3D,
    GroundPlane3D,
    ImageMaterial,
    Scene3D,
    SolidMaterial,
)


VIEW_WIDTH = 640
VIEW_HEIGHT = 420
WORLD_WIDTH = 600.0
BOX_SIZE = 100.0
MOVE_STEP = 20.0
COLLISION_GAP = 10.0
ZOOM_MIN = 0.35
ZOOM_MAX = 2.0
CONTROLS_HEIGHT = 200.0
TEXTURE_TESSELLATION = 10


def create_box_texture(context: dcg.Context) -> dcg.Texture:
    """Create a compact checker-and-cross texture for the projected box faces."""
    size = 48
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            checker = ((x // 8) + (y // 8)) % 2
            color = (237, 200, 69) if checker else (45, 136, 169)
            if abs(x - size // 2) <= 2 or abs(y - size // 2) <= 2:
                color = (242, 245, 228)
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes((*color, 255))
    texture = dcg.Texture(context)
    texture.nearest_neighbor_upsampling = True
    texture.set_value(memoryview(pixels).cast("B", shape=(size, size, 4)))
    return texture


def footprint_for(box: Box3D) -> AabbFootprint:
    return AabbFootprint.from_center(
        box.center[0], box.center[1], box.size[0], box.size[1]
    )


class TwoBoxController:
    def __init__(
        self,
        viewport: DrawInWindow3D,
        player: Box3D,
        collisions: CollisionWorld,
        status: dcg.Text,
    ) -> None:
        self.viewport = viewport
        self.player = player
        self.collisions = collisions
        self.status = status
        self.blocked_by: object | None = None

    def on_resize(self, *_: object) -> None:
        self.repaint()

    def set_pitch(self, sender, *_: object) -> None:
        self.viewport.set_camera(
            replace(self.viewport.camera, pitch_deg=float(sender.value))
        )
        self.repaint()

    def set_yaw(self, sender, *_: object) -> None:
        self.viewport.set_camera(
            replace(self.viewport.camera, yaw_deg=float(sender.value))
        )
        self.repaint()

    def set_zoom(self, sender, *_: object) -> None:
        requested_zoom = max(ZOOM_MIN, min(ZOOM_MAX, float(sender.value)))
        self.viewport.set_camera(
            replace(self.viewport.camera, zoom=requested_zoom)
        )
        self.repaint()

    def move_left(self, *_: object) -> None:
        self._move(-MOVE_STEP)

    def move_right(self, *_: object) -> None:
        self._move(MOVE_STEP)

    def _move(self, dx: float) -> None:
        half_width = self.player.size[0] * 0.5
        candidate_x = max(
            half_width,
            min(WORLD_WIDTH - half_width, self.player.center[0] + dx),
        )
        candidate_center = (candidate_x, self.player.center[1], self.player.center[2])
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
            self.blocked_by = None
        else:
            self.blocked_by = blocker.owner
        self.repaint()

    def repaint(self) -> None:
        self.viewport.invalidate()
        self.viewport.render_now()
        outcome = f"blocked by {self.blocked_by}" if self.blocked_by else "movement accepted"
        self.status.value = f"player x = {self.player.center[0]:.0f}; {outcome}"


def build_ui(context: dcg.Context) -> TwoBoxController:
    scene = Scene3D(background=(28, 38, 48))
    texture = create_box_texture(context)
    textured_faces = ImageMaterial(
        texture=texture,
        tessellation=TEXTURE_TESSELLATION,
        fill=(88, 130, 139),
        outline=(24, 27, 25),
    )
    scene.add(
        GroundPlane3D(
            bounds=(0.0, 0.0, WORLD_WIDTH, 240.0),
            z=0.0,
            material=SolidMaterial(fill=(65, 88, 68), outline=None, shaded=False),
        )
    )
    obstacle = Box3D(
        center=(420.0, 120.0, 0.0),
        size=(BOX_SIZE, BOX_SIZE, 150.0),
        material=SolidMaterial(fill=(179, 93, 74)),
        face_materials=(None, textured_faces, textured_faces, None, None, None),
    )
    player = Box3D(
        center=(120.0, 120.0, 0.0),
        size=(BOX_SIZE, BOX_SIZE, 100.0),
        material=SolidMaterial(fill=(244, 191, 62)),
        face_materials=(None, textured_faces, textured_faces, None, None, None),
    )
    scene.add(obstacle)
    scene.add(player)
    collisions = CollisionWorld(gap=COLLISION_GAP)
    collisions.add("red box", footprint_for(obstacle))
    camera = Camera3D(
        target=(WORLD_WIDTH * 0.5, 120.0, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=0.72,
    )

    with dcg.Window(context, label="Two-box AABB collision", width='fillx', height='filly', primary=True) as window:
        with dcg.VerticalLayout(context, parent=window) as content:
            with dcg.ChildWindow(
                context,
                parent=content,
                width='fillx',
                height=f'window.height-{CONTROLS_HEIGHT:.0f}',
                no_scrollbar=True,
            ) as viewport_area:
                viewport = DrawInWindow3D(
                    context,
                    parent=viewport_area,
                    width='fillx',
                    height='filly',
                    scene=scene,
                    camera=camera,
                )

            with dcg.ChildWindow(
                context,
                parent=content,
                width='fillx',
                height=CONTROLS_HEIGHT-10, # added -10 to fix scroll bar tolerance issue
                no_scrollbar=True,
            ) as controls:
                dcg.Text(context, parent=controls, value=f"Textured faces: {TEXTURE_TESSELLATION} x {TEXTURE_TESSELLATION} image cells")
                status = dcg.Text(context, parent=controls, value="")
                controller = TwoBoxController(viewport, player, collisions, status)
                dcg.Slider(
                    context,
                    parent=controls,
                    label="Camera inclination",
                    min_value=0.0,
                    max_value=78.0,
                    value=camera.pitch_deg,
                    width="fillx",
                    callback=controller.set_pitch,
                )
                dcg.Slider(
                    context,
                    parent=controls,
                    label="Camera rotation",
                    min_value=-180.0,
                    max_value=180.0,
                    value=camera.yaw_deg,
                    width="fillx",
                    callback=controller.set_yaw,
                )
                dcg.Slider(
                    context,
                    parent=controls,
                    label="Camera zoom",
                    min_value=ZOOM_MIN,
                    max_value=ZOOM_MAX,
                    value=camera.zoom,
                    width="fillx",
                    callback=controller.set_zoom,
                )
            viewport.handlers += [
                dcg.ResizeHandler(context, callback=controller.on_resize),
            ]
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
        ]
    return controller


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="Two-box textured AABB collision", width=VIEW_WIDTH + 70, height=VIEW_HEIGHT + 140)
    controller = build_ui(context)
    context.viewport.render_frame()
    controller.repaint()
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()