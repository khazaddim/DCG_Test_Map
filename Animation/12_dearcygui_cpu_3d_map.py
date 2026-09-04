"""Demo 12: collision-safe CPU-side 3D map rendering with DearCyGui.

Demo 11 sorts complete projected faces with a painter's algorithm. That model
cannot reliably order intersecting or coplanar faces because each face has only
one average-depth value. This revision keeps solid box footprints disjoint:
candidate player movement is rejected before world state changes when it would
overlap or come within ``COLLISION_GAP`` of a static box.

The separation invariant deliberately avoids polygon subtraction and face
splitting. It is appropriate for this tabletop world of axis-aligned boxes,
but arbitrary intersecting meshes would still require a depth buffer or a more
capable polygon-splitting renderer.
"""

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg


COLLISION_GAP = 2.0


def load_demo_11():
    source = Path(__file__).with_name("11_dearcygui_cpu_3d_map.py")
    spec = importlib.util.spec_from_file_location("dcg_demo_11_for_12", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = load_demo_11()


@dataclass(frozen=True)
class Footprint:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


def box_footprint(box) -> Footprint:
    half_width = box.width * 0.5
    half_depth = box.depth * 0.5
    return Footprint(
        box.center_x - half_width,
        box.center_y - half_depth,
        box.center_x + half_width,
        box.center_y + half_depth,
    )


def player_footprint(center_x: float, center_y: float) -> Footprint:
    half_size = demo.PIECE_SIZE * 0.5
    return Footprint(
        center_x - half_size,
        center_y - half_size,
        center_x + half_size,
        center_y + half_size,
    )


def footprints_conflict(first: Footprint, second: Footprint,
                        gap: float = COLLISION_GAP) -> bool:
    """Return whether two closed footprints overlap or violate their gap."""
    return not (
        first.max_x <= second.min_x - gap
        or first.min_x >= second.max_x + gap
        or first.max_y <= second.min_y - gap
        or first.min_y >= second.max_y + gap
    )


def blocking_box(world, center_x: float, center_y: float):
    candidate = player_footprint(center_x, center_y)
    return next(
        (box for box in world.boxes
         if footprints_conflict(candidate, box_footprint(box))),
        None,
    )


def render_scene(context, parent, world, camera, piece_x, piece_y):
    demo.clear_layer(parent)

    demo.draw_ground_polygon(context, parent, (
        (-demo.GROUND_PAD, -demo.GROUND_PAD, 0.0),
        (demo.WORLD_W + demo.GROUND_PAD, -demo.GROUND_PAD, 0.0),
        (demo.WORLD_W + demo.GROUND_PAD,
         demo.WORLD_H + demo.GROUND_PAD, 0.0),
        (-demo.GROUND_PAD, demo.WORLD_H + demo.GROUND_PAD, 0.0),
    ), camera, (42, 66, 47))

    demo.draw_ground_polygon(context, parent, (
        (0.0, 620.0, 1.0), (demo.WORLD_W, 620.0, 1.0),
        (demo.WORLD_W, 710.0, 1.0), (0.0, 710.0, 1.0),
    ), camera, (68, 116, 168))
    demo.draw_ground_polygon(context, parent, (
        (910.0, 0.0, 2.0), (995.0, 0.0, 2.0),
        (995.0, demo.WORLD_H, 2.0), (910.0, demo.WORLD_H, 2.0),
    ), camera, (130, 116, 91))

    for grid_x in range(0, int(demo.WORLD_W) + 1, 100):
        line = demo.project_world_line(
            (float(grid_x), 0.0, 3.0),
            (float(grid_x), demo.WORLD_H, 3.0), camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=(65, 91, 68), thickness=-1)
    for grid_y in range(0, int(demo.WORLD_H) + 1, 100):
        line = demo.project_world_line(
            (0.0, float(grid_y), 3.0),
            (demo.WORLD_W, float(grid_y), 3.0), camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=(65, 91, 68), thickness=-1)

    border_color = (235, 214, 116)
    border_points = (
        (0.0, 0.0, 5.0), (demo.WORLD_W, 0.0, 5.0),
        (demo.WORLD_W, demo.WORLD_H, 5.0),
        (0.0, demo.WORLD_H, 5.0),
    )
    for index in range(4):
        line = demo.project_world_line(
            border_points[index], border_points[(index + 1) % 4], camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=border_color, thickness=-3)

    for label in world.labels:
        projected_label = demo.project_ground_label(label, camera)
        if projected_label is None:
            continue
        screen, screen_size = projected_label
        dcg.DrawText(context, parent=parent, pos=screen, text=label.text,
                     size=-screen_size, color=label.color)

    piece = demo.Box(
        piece_x, piece_y, demo.PIECE_SIZE, demo.PIECE_SIZE, 115.0,
        (245, 194, 67), "player",
    )
    eye = demo.camera_eye(camera)
    render_faces = []
    for object_index, box in enumerate([*world.boxes, piece]):
        for face_index, face in enumerate(demo.box_faces(box)):
            if not demo.face_is_visible(face, eye):
                continue
            projected = demo.project_world_polygon(face.points, camera)
            if projected is None:
                continue
            screen_points, average_depth = projected
            render_faces.append((
                average_depth,
                -object_index,
                -face_index,
                screen_points,
                demo.shade_color(face.color, face.normal),
            ))

    render_faces.sort(key=lambda item: item[:3], reverse=True)
    for _, _, _, screen_points, fill in render_faces:
        dcg.DrawPolygon(context, parent=parent, points=screen_points,
                        fill=fill, color=(24, 27, 25), thickness=-2)


class CollisionCpu3DController(demo.Cpu3DController):
    def __init__(self, context, layer, world, status):
        self.blocked_by = None
        super().__init__(context, layer, world, status)

    def _move(self, dx: float, dy: float) -> None:
        half_size = demo.PIECE_SIZE * 0.5
        candidate_x = max(
            half_size,
            min(demo.WORLD_W - half_size, self.piece_x + dx),
        )
        candidate_y = max(
            half_size,
            min(demo.WORLD_H - half_size, self.piece_y + dy),
        )
        blocker = blocking_box(self.world, candidate_x, candidate_y)
        if blocker is None:
            self.piece_x = candidate_x
            self.piece_y = candidate_y
            self.blocked_by = None
            self._pan_for_piece()
        else:
            self.blocked_by = blocker.name
        self.repaint()

    def repaint(self) -> None:
        camera = self.camera()
        render_scene(
            self.context, self.back_layer, self.world, camera,
            self.piece_x, self.piece_y,
        )
        with self.layer.mutex:
            self.displayed_layer.show = False
            self.back_layer.show = True
            self.displayed_layer, self.back_layer = (
                self.back_layer, self.displayed_layer)
        blocked_status = (
            f"  blocked by={self.blocked_by}" if self.blocked_by else ""
        )
        self.status.value = (
            f"piece=({self.piece_x:.0f},{self.piece_y:.0f},0)  "
            f"target=({self.target_x:.0f},{self.target_y:.0f})  "
            f"pitch={self.pitch_deg:.1f} deg  yaw={self.yaw_deg:.1f} deg  "
            f"zoom={self.zoom:.2f}x  camera distance={camera.distance:.0f}"
            f"{blocked_status}"
        )


def build_ui(context: dcg.Context) -> None:
    world = demo.build_world()
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 12",
                    width=demo.VIEW_W + 40,
                    height=demo.VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="Arrow keys move the gold 3D piece. Solid footprints keep "
                "a small separation so painter-ordered faces do not "
                "intersect.",
            wrap=demo.VIEW_W,
        )
        status = dcg.Text(context, value="")
        with dcg.DrawInWindow(
                context, width=demo.VIEW_W, height=demo.VIEW_H) as canvas:
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.VIEW_H), fill=(19, 24, 31),
                color=0, thickness=-1,
            )
            scene_layer = dcg.DrawingList(context, parent=canvas)
            band_color = (245, 205, 83, 35)
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.EDGE_BAND_Y), fill=band_color,
                color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas,
                pmin=(0, demo.VIEW_H - demo.EDGE_BAND_Y),
                pmax=(demo.VIEW_W, demo.VIEW_H), fill=band_color,
                color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, demo.EDGE_BAND_Y),
                pmax=(demo.EDGE_BAND_X,
                      demo.VIEW_H - demo.EDGE_BAND_Y),
                fill=band_color, color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas,
                pmin=(demo.VIEW_W - demo.EDGE_BAND_X, demo.EDGE_BAND_Y),
                pmax=(demo.VIEW_W, demo.VIEW_H - demo.EDGE_BAND_Y),
                fill=band_color, color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas,
                pmin=(demo.EDGE_BAND_X, demo.EDGE_BAND_Y),
                pmax=(demo.VIEW_W - demo.EDGE_BAND_X,
                      demo.VIEW_H - demo.EDGE_BAND_Y),
                color=(245, 205, 83, 115), thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.VIEW_H), color=(112, 132, 155),
                thickness=-2,
            )

        controller = CollisionCpu3DController(
            context, scene_layer, world, status)
        dcg.Slider(
            context, label="Camera pitch from overhead (degrees)",
            min_value=0.0, max_value=78.0, value=controller.pitch_deg,
            width=demo.VIEW_W, callback=controller.set_pitch,
        )
        dcg.Slider(
            context, label="Camera yaw (degrees)",
            min_value=-180.0, max_value=180.0,
            value=controller.yaw_deg, width=demo.VIEW_W,
            callback=controller.set_yaw,
        )
        dcg.Slider(
            context, label="Camera zoom", min_value=demo.ZOOM_MIN,
            max_value=demo.ZOOM_MAX, value=controller.zoom,
            width=demo.VIEW_W, callback=controller.set_zoom,
        )
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW,
                               callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW,
                               callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW,
                               callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW,
                               callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Demo 12 collision-safe CPU 3D",
        width=demo.VIEW_W + 80,
        height=demo.VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()