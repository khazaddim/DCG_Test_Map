"""Framework demo 15: buildings with mesh-based roof geometry."""

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
    GroundPlane3D,
    MeshEdgeStyle,
    Scene3D,
    SolidMaterial,
    TriangleMesh3D,
)


VIEW_W = 980
VIEW_H = 620
WORLD_W = 1300.0
WORLD_H = 850.0

WALL_MATERIAL = SolidMaterial(fill=(146, 154, 150), outline=(54, 62, 66), thickness=-1.0)
GROUND_MATERIAL = SolidMaterial(fill=(73, 103, 83), outline=None, thickness=-1.0, shaded=False, line_occluder=False)
ROAD_MATERIAL = SolidMaterial(fill=(92, 88, 78), outline=None, thickness=-1.0, shaded=False, line_occluder=False)
EDGE_STYLE = MeshEdgeStyle(color=(34, 38, 40, 155), thickness=-1.0)


def add_box_building(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], height: float) -> float:
    # Keep the wall mass rectangular and let the roof silhouette come from a separate mesh.
    scene.add(
        Box3D(
            center=(center[0], center[1], 0.0),
            size=(size[0], size[1], height),
            material=WALL_MATERIAL,
        )
    )
    return height


def add_gable_roof(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], base_z: float) -> None:
    width, depth = size
    x0 = center[0] - width * 0.5
    x1 = center[0] + width * 0.5
    y0 = center[1] - depth * 0.5
    y1 = center[1] + depth * 0.5
    ridge_y = center[1]
    ridge_z = base_z + 64.0
    # Two ridge points plus the wall corners give a minimal six-vertex gable roof.
    vertices = (
        (x0, y0, base_z), (x1, y0, base_z), (x1, y1, base_z), (x0, y1, base_z),
        (x0, ridge_y, ridge_z), (x1, ridge_y, ridge_z),
    )
    scene.add(
        TriangleMesh3D(
            vertices=vertices,
            triangles=((0, 1, 5), (0, 5, 4), (3, 5, 2), (3, 4, 5), (0, 4, 3), (1, 2, 5)),
            material=SolidMaterial(fill=(178, 76, 54), outline=(74, 43, 36), thickness=-1.0),
            edges=EDGE_STYLE,
        )
    )


def add_hip_roof(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], base_z: float) -> None:
    width, depth = size
    x0 = center[0] - width * 0.5
    x1 = center[0] + width * 0.5
    y0 = center[1] - depth * 0.5
    y1 = center[1] + depth * 0.5
    ridge_z = base_z + 58.0
    # A shortened ridge makes the roof slope down on all four sides.
    vertices = (
        (x0, y0, base_z), (x1, y0, base_z), (x1, y1, base_z), (x0, y1, base_z),
        (center[0] - width * 0.22, center[1], ridge_z),
        (center[0] + width * 0.22, center[1], ridge_z),
    )
    scene.add(
        TriangleMesh3D(
            vertices=vertices,
            triangles=((0, 1, 5), (0, 5, 4), (1, 2, 5), (2, 3, 4), (2, 4, 5), (3, 0, 4)),
            material=SolidMaterial(fill=(67, 112, 139), outline=(27, 50, 65), thickness=-1.0),
            edges=EDGE_STYLE,
        )
    )


def add_pyramid_roof(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], base_z: float) -> None:
    width, depth = size
    x0 = center[0] - width * 0.5
    x1 = center[0] + width * 0.5
    y0 = center[1] - depth * 0.5
    y1 = center[1] + depth * 0.5
    # One apex over the rectangle corners is the smallest pyramid roof pattern.
    vertices = (
        (x0, y0, base_z), (x1, y0, base_z), (x1, y1, base_z), (x0, y1, base_z),
        (center[0], center[1], base_z + 92.0),
    )
    scene.add(
        TriangleMesh3D(
            vertices=vertices,
            triangles=((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)),
            material=SolidMaterial(fill=(196, 146, 65), outline=(82, 59, 27), thickness=-1.0),
            edges=EDGE_STYLE,
        )
    )


def add_shed_roof(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], base_z: float) -> None:
    width, depth = size
    x0 = center[0] - width * 0.5
    x1 = center[0] + width * 0.5
    y0 = center[1] - depth * 0.5
    y1 = center[1] + depth * 0.5
    # Two raised back corners turn one quad into a single-slope shed roof.
    vertices = (
        (x0, y0, base_z), (x1, y0, base_z),
        (x1, y1, base_z + 54.0), (x0, y1, base_z + 54.0),
    )
    scene.add(
        TriangleMesh3D(
            vertices=vertices,
            triangles=((0, 1, 2), (0, 2, 3)),
            material=SolidMaterial(fill=(94, 130, 94), outline=(39, 65, 43), thickness=-1.0),
            edges=EDGE_STYLE,
            cull_back_faces=False,
        )
    )


def build_scene() -> Scene3D:
    scene = Scene3D(background=(23, 29, 34))
    scene.add(GroundPlane3D(bounds=(0.0, 0.0, WORLD_W, WORLD_H), z=0.0, material=GROUND_MATERIAL))
    scene.add(
        # A flat two-triangle strip is enough for roads that do not need curb geometry.
        TriangleMesh3D(
            vertices=((0.0, 360.0, 1.0), (WORLD_W, 360.0, 1.0), (WORLD_W, 500.0, 1.0), (0.0, 500.0, 1.0)),
            triangles=((0, 1, 2), (0, 2, 3)),
            material=ROAD_MATERIAL,
            cull_back_faces=False,
        )
    )

    specs = (
        ((250.0, 255.0), (190.0, 150.0), 118.0, add_gable_roof),
        ((560.0, 245.0), (210.0, 170.0), 136.0, add_hip_roof),
        ((850.0, 270.0), (155.0, 155.0), 165.0, add_pyramid_roof),
        ((365.0, 595.0), (230.0, 135.0), 108.0, add_shed_roof),
        ((735.0, 585.0), (185.0, 185.0), 128.0, add_gable_roof),
    )
    for center, size, height, roof_builder in specs:
        # This table-driven pair is the reusable settlement pattern: one wall box, one roof mesh.
        base_z = add_box_building(scene, center, size, height)
        roof_builder(scene, center, size, base_z)
    return scene


class Demo15Controller:
    def __init__(self, viewport: DrawInWindow3D, status: dcg.Text) -> None:
        self.viewport = viewport
        self.status = status
        self.repaint()

    def set_pitch(self, sender, target, value) -> None:
        del target, value
        self.viewport.set_camera(replace(self.viewport.camera, pitch_deg=float(sender.value)))
        self.repaint()

    def set_yaw(self, sender, target, value) -> None:
        del target, value
        self.viewport.set_camera(replace(self.viewport.camera, yaw_deg=float(sender.value)))
        self.repaint()

    def set_zoom(self, sender, target, value) -> None:
        del target, value
        self.viewport.set_camera(replace(self.viewport.camera, zoom=float(sender.value)))
        self.repaint()

    def repaint(self) -> None:
        stats = self.viewport.render_now()
        self.status.value = f"mesh roof packets={stats.packet_count}  projected={stats.projected_count}  cycle={stats.cycle_detected}"


def build_ui(context: dcg.Context) -> Demo15Controller:
    scene = build_scene()
    camera = Camera3D(target=(WORLD_W * 0.5, WORLD_H * 0.48, 40.0), yaw_deg=-28.0, pitch_deg=54.0, zoom=0.64)
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 15", width=VIEW_W + 40, height=VIEW_H + 180):
        dcg.Text(context, value="Mesh roof demo: one retained TriangleMesh3D per roof, with optional edge packets.")
        status = dcg.Text(context, value="")
        with DrawInWindow3D(context, width=VIEW_W, height=VIEW_H, scene=scene, camera=camera) as viewport:
            dcg.DrawRect(context, parent=viewport, pmin=(0, 0), pmax=(VIEW_W, VIEW_H), color=(126, 142, 150), thickness=-2)
        controller = Demo15Controller(viewport, status)
        dcg.Slider(context, label="Camera pitch", min_value=12.0, max_value=76.0, value=camera.pitch_deg, width=VIEW_W, callback=controller.set_pitch)
        dcg.Slider(context, label="Camera yaw", min_value=-180.0, max_value=180.0, value=camera.yaw_deg, width=VIEW_W, callback=controller.set_yaw)
        dcg.Slider(context, label="Camera zoom", min_value=0.35, max_value=1.6, value=camera.zoom, width=VIEW_W, callback=controller.set_zoom)
    return controller


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - Framework Demo 15", width=VIEW_W + 80, height=VIEW_H + 220)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()