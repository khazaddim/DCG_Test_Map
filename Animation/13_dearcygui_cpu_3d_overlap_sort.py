"""Demo 13: overlap-aware painter ordering for the CPU-side 3D map.

Demo 12 prevents solid boxes from intersecting, but sorting each complete face
by its average depth can still reverse visibility inside a small projected
overlap. This revision compares ray-plane depth inside every positive-area
face overlap and topologically sorts the resulting far-to-near constraints.

The collision invariant remains important: two intersecting faces could swap
depth order within one overlap and would require polygon splitting or a real
per-pixel depth buffer.
"""

from dataclasses import dataclass
import heapq
import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg


OVERLAP_AREA_EPSILON = 0.25
DEPTH_EPSILON = 1e-5


def load_demo_12():
    source = Path(__file__).with_name("12_dearcygui_cpu_3d_map.py")
    spec = importlib.util.spec_from_file_location("dcg_demo_12_for_13", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo12 = load_demo_12()
demo = demo12.demo


@dataclass
class RenderFace:
    world_points: tuple
    screen_points: list
    average_depth: float
    fill: tuple[int, int, int]
    stable_index: int


def cross_2d(first, second) -> float:
    return first[0] * second[1] - first[1] * second[0]


def signed_polygon_area(points) -> float:
    return 0.5 * sum(
        cross_2d(points[index], points[(index + 1) % len(points)])
        for index in range(len(points))
    )


def line_intersection(segment_start, segment_end, clip_start, clip_end):
    segment = (
        segment_end[0] - segment_start[0],
        segment_end[1] - segment_start[1],
    )
    clip = (clip_end[0] - clip_start[0], clip_end[1] - clip_start[1])
    denominator = cross_2d(segment, clip)
    if abs(denominator) <= 1e-12:
        return segment_end
    offset = (
        clip_start[0] - segment_start[0],
        clip_start[1] - segment_start[1],
    )
    amount = cross_2d(offset, clip) / denominator
    return (
        segment_start[0] + amount * segment[0],
        segment_start[1] + amount * segment[1],
    )


def convex_polygon_intersection(subject, clip):
    """Clip one convex screen polygon against another convex polygon."""
    if len(subject) < 3 or len(clip) < 3:
        return []
    orientation = 1.0 if signed_polygon_area(clip) >= 0.0 else -1.0
    output = list(subject)
    for clip_index, clip_start in enumerate(clip):
        if not output:
            return []
        clip_end = clip[(clip_index + 1) % len(clip)]
        edge = (clip_end[0] - clip_start[0],
                clip_end[1] - clip_start[1])

        def inside(point):
            offset = (point[0] - clip_start[0],
                      point[1] - clip_start[1])
            return orientation * cross_2d(edge, offset) >= -1e-7

        input_points = output
        output = []
        previous = input_points[-1]
        previous_inside = inside(previous)
        for current in input_points:
            current_inside = inside(current)
            if current_inside != previous_inside:
                output.append(line_intersection(
                    previous, current, clip_start, clip_end))
            if current_inside:
                output.append(current)
            previous = current
            previous_inside = current_inside
    return output


def ray_plane_depth(screen_point, world_points, camera):
    camera_points = [
        demo.world_to_camera(point, camera) for point in world_points[:3]
    ]
    first, second, third = camera_points
    first_edge = demo.subtract(second, first)
    second_edge = demo.subtract(third, first)
    normal = demo.cross(first_edge, second_edge)
    ray = (
        (screen_point[0] - demo.VIEW_W * 0.5) / camera.focal_length,
        (screen_point[1] - demo.VIEW_H * 0.5) / camera.focal_length,
        1.0,
    )
    denominator = demo.dot(normal, ray)
    if abs(denominator) <= 1e-12:
        return None
    depth = demo.dot(normal, first) / denominator
    return depth if depth >= demo.NEAR_PLANE else None


def overlap_depths(first: RenderFace, second: RenderFace, camera):
    overlap = convex_polygon_intersection(
        first.screen_points, second.screen_points)
    if (len(overlap) < 3
            or abs(signed_polygon_area(overlap)) <= OVERLAP_AREA_EPSILON):
        return None
    sample = (
        sum(point[0] for point in overlap) / len(overlap),
        sum(point[1] for point in overlap) / len(overlap),
    )
    first_depth = ray_plane_depth(sample, first.world_points, camera)
    second_depth = ray_plane_depth(sample, second.world_points, camera)
    if first_depth is None or second_depth is None:
        return None
    return first_depth, second_depth


def order_render_faces(render_faces, camera):
    """Return back-to-front faces and whether an occlusion cycle was found."""
    face_count = len(render_faces)
    successors = [set() for _ in render_faces]
    indegree = [0] * face_count
    for first_index in range(face_count):
        for second_index in range(first_index + 1, face_count):
            depths = overlap_depths(
                render_faces[first_index], render_faces[second_index], camera)
            if depths is None or abs(depths[0] - depths[1]) <= DEPTH_EPSILON:
                continue
            farther = first_index if depths[0] > depths[1] else second_index
            nearer = second_index if farther == first_index else first_index
            if nearer not in successors[farther]:
                successors[farther].add(nearer)
                indegree[nearer] += 1

    ready = []
    for index, face in enumerate(render_faces):
        if indegree[index] == 0:
            heapq.heappush(
                ready, (-face.average_depth, face.stable_index, index))

    ordered_indices = []
    while ready:
        _, _, index = heapq.heappop(ready)
        ordered_indices.append(index)
        for successor in successors[index]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                face = render_faces[successor]
                heapq.heappush(
                    ready,
                    (-face.average_depth, face.stable_index, successor),
                )

    if len(ordered_indices) != face_count:
        return sorted(
            render_faces,
            key=lambda face: (-face.average_depth, face.stable_index),
        ), True
    return [render_faces[index] for index in ordered_indices], False


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
    for box in [*world.boxes, piece]:
        for face in demo.box_faces(box):
            if not demo.face_is_visible(face, eye):
                continue
            projected = demo.project_world_polygon(face.points, camera)
            if projected is None:
                continue
            screen_points, average_depth = projected
            render_faces.append(RenderFace(
                world_points=face.points,
                screen_points=screen_points,
                average_depth=average_depth,
                fill=demo.shade_color(face.color, face.normal),
                stable_index=len(render_faces),
            ))

    ordered_faces, cycle_detected = order_render_faces(render_faces, camera)
    for face in ordered_faces:
        dcg.DrawPolygon(
            context, parent=parent, points=face.screen_points,
            fill=face.fill, color=(24, 27, 25), thickness=-2,
        )
    return cycle_detected


class OverlapCpu3DController(demo12.CollisionCpu3DController):
    def repaint(self) -> None:
        camera = self.camera()
        cycle_detected = render_scene(
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
        cycle_status = "  occlusion cycle fallback" if cycle_detected else ""
        self.status.value = (
            f"piece=({self.piece_x:.0f},{self.piece_y:.0f},0)  "
            f"target=({self.target_x:.0f},{self.target_y:.0f})  "
            f"pitch={self.pitch_deg:.1f} deg  yaw={self.yaw_deg:.1f} deg  "
            f"zoom={self.zoom:.2f}x  overlap sort"
            f"{blocked_status}{cycle_status}"
        )


def build_ui(context: dcg.Context) -> None:
    world = demo.build_world()
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 13",
                    width=demo.VIEW_W + 40,
                    height=demo.VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="Arrow keys move the gold 3D piece. Overlapping projected "
                "faces are ordered by ray depth inside their overlap.",
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

        controller = OverlapCpu3DController(
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
        title="DCG Test Map - Demo 13 overlap-aware CPU 3D",
        width=demo.VIEW_W + 80,
        height=demo.VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()