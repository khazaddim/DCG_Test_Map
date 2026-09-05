"""Isolate DearCyGui triangle behavior at a 3D face visibility transition.

See ``16_triangle_transition_diagnostic.md`` for the investigation, evidence,
and the framework workaround derived from this diagnostic.
"""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import sys

import dearcygui as dcg


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import Camera3D, Viewport
from Animation.draw_in_window_3d_framework.math3d import cross, dot, subtract


VIEW_W = 960
VIEW_H = 360
PANEL_W = VIEW_W / 4.0
FACE = (
    (155.0, 180.0, 118.0),
    (345.0, 180.0, 118.0),
    (345.0, 255.0, 182.0),
)
TARGET = (650.0, 346.8, 40.0)
FILL = (132, 49, 34)
OUTLINE = (74, 43, 36)


def signed_area(points: tuple[tuple[float, float], ...]) -> float:
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


class TriangleTransitionDiagnostic:
    def __init__(self, context: dcg.Context, canvas: dcg.DrawInWindow, status: dcg.Text) -> None:
        self.context = context
        self.canvas = canvas
        self.status = status
        self.camera = Camera3D(
            target=TARGET,
            yaw_deg=41.4,
            pitch_deg=45.104,
            zoom=0.64,
        )

        for index, label in enumerate((
            "DrawTriangle: fill only",
            "DrawTriangle: integrated outline",
            "DrawPolygon: integrated outline",
            "DrawTriangle + DrawLine edges",
        )):
            dcg.DrawText(
                context,
                parent=canvas,
                pos=(index * PANEL_W + 12.0, 12.0),
                text=label,
                size=-15.0,
                color=(222, 226, 229),
            )
            if index:
                dcg.DrawLine(
                    context,
                    parent=canvas,
                    p1=(index * PANEL_W, 0.0),
                    p2=(index * PANEL_W, VIEW_H),
                    color=(80, 88, 94),
                    thickness=-1.0,
                )

        initial = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
        self.fill_only = dcg.DrawTriangle(
            context,
            parent=canvas,
            p1=initial[0],
            p2=initial[1],
            p3=initial[2],
            fill=FILL,
            color=0,
            thickness=-1.0,
        )
        self.integrated_outline = dcg.DrawTriangle(
            context,
            parent=canvas,
            p1=initial[0],
            p2=initial[1],
            p3=initial[2],
            fill=FILL,
            color=OUTLINE,
            thickness=-1.0,
        )
        self.polygon = dcg.DrawPolygon(
            context,
            parent=canvas,
            points=initial,
            fill=FILL,
            color=OUTLINE,
            thickness=-1.0,
        )
        self.separate_fill = dcg.DrawTriangle(
            context,
            parent=canvas,
            p1=initial[0],
            p2=initial[1],
            p3=initial[2],
            fill=FILL,
            color=0,
            thickness=-1.0,
        )
        self.separate_edges = tuple(
            dcg.DrawLine(
                context,
                parent=canvas,
                p1=(0.0, 0.0),
                p2=(0.0, 0.0),
                color=OUTLINE,
                thickness=-1.0,
            )
            for _ in range(3)
        )
        self.repaint()

    def set_yaw(self, sender, target, value) -> None:
        del target, value
        self.camera = replace(self.camera, yaw_deg=float(sender.value))
        self.repaint()

    def set_pitch(self, sender, target, value) -> None:
        del target, value
        self.camera = replace(self.camera, pitch_deg=float(sender.value))
        self.repaint()

    def repaint(self) -> None:
        projection_viewport = Viewport(980.0, 620.0)
        projected = tuple(
            self.camera.camera_to_screen(
                self.camera.world_to_camera(point, projection_viewport),
                projection_viewport,
            )
            for point in FACE
        )
        centroid = (
            sum(point[0] for point in projected) / 3.0,
            sum(point[1] for point in projected) / 3.0,
        )
        panel_points = tuple(
            tuple(
                (
                    panel * PANEL_W + PANEL_W * 0.5 + point[0] - centroid[0],
                    190.0 + point[1] - centroid[1],
                )
                for point in projected
            )
            for panel in range(4)
        )

        for triangle, points in (
            (self.fill_only, panel_points[0]),
            (self.integrated_outline, panel_points[1]),
            (self.separate_fill, panel_points[3]),
        ):
            triangle.p1, triangle.p2, triangle.p3 = points
        self.polygon.points = panel_points[2]
        for index, edge in enumerate(self.separate_edges):
            edge.p1 = panel_points[3][index]
            edge.p2 = panel_points[3][(index + 1) % 3]

        normal = cross(subtract(FACE[1], FACE[0]), subtract(FACE[2], FACE[0]))
        center = tuple(sum(point[axis] for point in FACE) / 3.0 for axis in range(3))
        eye_vector = subtract(self.camera.eye(projection_viewport), center)
        visible = dot(normal, eye_vector) > 1e-6
        finite = all(math.isfinite(value) for point in projected for value in point)
        bounded = all(
            0.0 <= point[0] <= projection_viewport.width
            and 0.0 <= point[1] <= projection_viewport.height
            for point in projected
        )
        coordinates = "  ".join(f"({point[0]:.2f}, {point[1]:.2f})" for point in projected)
        self.status.value = (
            f"yaw={self.camera.yaw_deg:.3f}  pitch={self.camera.pitch_deg:.3f}  "
            f"signed area={signed_area(projected):.4f}  front-facing={visible}  "
            f"finite={finite}  in viewport={bounded}\npoints: {coordinates}"
        )


def build_ui(context: dcg.Context) -> TriangleTransitionDiagnostic:
    with dcg.Window(
        context,
        label="Triangle transition diagnostic",
        width=VIEW_W + 40,
        height=VIEW_H + 150,
    ):
        dcg.Text(
            context,
            value="One real Demo 15 roof face, drawn directly with 2D primitives. Culling is intentionally disabled.",
        )
        status = dcg.Text(context, value="")
        with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
            dcg.DrawRect(
                context,
                parent=canvas,
                pmin=(0.0, 0.0),
                pmax=(VIEW_W, VIEW_H),
                fill=(23, 29, 34),
                color=(126, 142, 150),
                thickness=-1.0,
            )
        diagnostic = TriangleTransitionDiagnostic(context, canvas, status)
        dcg.Slider(
            context,
            label="Camera yaw",
            min_value=35.0,
            max_value=48.0,
            value=diagnostic.camera.yaw_deg,
            width=VIEW_W,
            callback=diagnostic.set_yaw,
        )
        dcg.Slider(
            context,
            label="Camera pitch",
            min_value=35.0,
            max_value=55.0,
            value=diagnostic.camera.pitch_deg,
            width=VIEW_W,
            callback=diagnostic.set_pitch,
        )
    return diagnostic


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG triangle transition diagnostic",
        width=VIEW_W + 80,
        height=VIEW_H + 190,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()