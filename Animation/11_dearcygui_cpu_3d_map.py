"""A small CPU-side 3D game-map renderer drawn entirely with DearCyGui.

DearCyGui receives only final 2D polygons. This file owns the 3D work:

    world (x, y, z)
      -> camera yaw and pitch
      -> near-plane clipping
      -> perspective division
      -> viewport clipping
      -> depth ordering
      -> dcg.DrawPolygon / dcg.DrawLine

The renderer intentionally targets tabletop geometry: a ground plane, convex
rectangular towers, and a movable box-shaped piece. It uses back-face culling
and a painter's algorithm rather than a depth buffer. That is sufficient for
separated convex objects, but intersecting meshes would need face splitting or
a renderer with a real per-pixel depth buffer.

Ground labels use real `(x, y, z)` anchor points and perspective-scaled sizes,
but the text itself remains screen-upright so coordinates and names stay easy
to read while the map rotates and tilts. They are drawn before solid faces, so
towers naturally cover labels behind their footprints.

The follow camera projects the player's ground contact into screen space. When
it leaves the central edge band, `ground_world_from_screen` casts the desired
band-boundary pixel back onto the `z=0` plane. Moving the camera target by that
exact world-space difference keeps tracking correct through yaw, pitch, and
zoom. The vertical band is slightly wider because pixels above the horizon do
not have a forward intersection with the ground plane at low camera angles.

The front/back DrawingList swap from demo 10 remains important. Camera changes
rebuild many projected faces, so the hidden back layer is completed before one
mutex-protected visibility swap prevents partially rendered frames.
"""

from dataclasses import dataclass
import math

import dearcygui as dcg


VIEW_W = 900
VIEW_H = 600
WORLD_W = 2200.0
WORLD_H = 1500.0
MOVE_STEP = 35.0
PIECE_SIZE = 70.0
EDGE_BAND_X = 150.0
EDGE_BAND_Y = 200.0
FOV_Y_DEG = 58.0
NEAR_PLANE = 25.0
ZOOM_MIN = 0.35
ZOOM_MAX = 2.0
GROUND_PAD = 7000.0

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class Camera:
    target_x: float
    target_y: float
    yaw_deg: float
    pitch_deg: float
    zoom: float

    @property
    def focal_length(self) -> float:
        return VIEW_H * 0.5 / math.tan(math.radians(FOV_Y_DEG) * 0.5)

    @property
    def distance(self) -> float:
        return self.focal_length / self.zoom


@dataclass(frozen=True)
class Box:
    center_x: float
    center_y: float
    width: float
    depth: float
    height: float
    color: Color
    name: str


@dataclass(frozen=True)
class Face:
    points: tuple[Vec3, ...]
    normal: Vec3
    color: Color


@dataclass(frozen=True)
class GroundLabel:
    position: Vec3
    text: str
    size: float
    color: Color


@dataclass
class World3D:
    boxes: list[Box]
    labels: list[GroundLabel]


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def subtract(a: Vec3, b: Vec3) -> Vec3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def normalized(vector: Vec3) -> Vec3:
    length = math.sqrt(dot(vector, vector))
    if length <= 1e-12:
        return 0.0, 0.0, 0.0
    return vector[0] / length, vector[1] / length, vector[2] / length


def camera_eye(camera: Camera) -> Vec3:
    yaw = math.radians(camera.yaw_deg)
    pitch = math.radians(camera.pitch_deg)
    horizontal = camera.distance * math.sin(pitch)
    return (
        camera.target_x + math.sin(yaw) * horizontal,
        camera.target_y + math.cos(yaw) * horizontal,
        camera.distance * math.cos(pitch),
    )


def world_to_camera(point: Vec3, camera: Camera) -> Vec3:
    """Return camera right, screen-down, and forward-depth coordinates."""
    dx = point[0] - camera.target_x
    dy = point[1] - camera.target_y
    dz = point[2]

    yaw = math.radians(camera.yaw_deg)
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    rotated_x = cos_yaw * dx - sin_yaw * dy
    rotated_y = sin_yaw * dx + cos_yaw * dy

    pitch = math.radians(camera.pitch_deg)
    cos_pitch = math.cos(pitch)
    sin_pitch = math.sin(pitch)
    screen_down = cos_pitch * rotated_y - sin_pitch * dz
    forward_depth = (camera.distance - sin_pitch * rotated_y
                     - cos_pitch * dz)
    return rotated_x, screen_down, forward_depth


def project_camera(point: Vec3, camera: Camera) -> Vec2:
    scale = camera.focal_length / point[2]
    return (
        VIEW_W * 0.5 + point[0] * scale,
        VIEW_H * 0.5 + point[1] * scale,
    )


def ground_world_from_screen(screen: Vec2, camera: Camera) -> Vec2 | None:
    """Intersect a screen ray with z=0 and return its world position."""
    normalized_x = (screen[0] - VIEW_W * 0.5) / camera.focal_length
    normalized_y = (screen[1] - VIEW_H * 0.5) / camera.focal_length
    pitch = math.radians(camera.pitch_deg)
    cos_pitch = math.cos(pitch)
    sin_pitch = math.sin(pitch)
    denominator = cos_pitch + normalized_y * sin_pitch
    if denominator <= 1e-8:
        return None

    rotated_y = normalized_y * camera.distance / denominator
    depth = camera.distance - sin_pitch * rotated_y
    if depth < NEAR_PLANE:
        return None
    rotated_x = normalized_x * depth

    yaw = math.radians(camera.yaw_deg)
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    offset_x = cos_yaw * rotated_x + sin_yaw * rotated_y
    offset_y = -sin_yaw * rotated_x + cos_yaw * rotated_y
    return camera.target_x + offset_x, camera.target_y + offset_y


def clip_polygon_near(points: list[Vec3]) -> list[Vec3]:
    """Clip a camera-space polygon against depth >= NEAR_PLANE."""
    if not points:
        return []
    output: list[Vec3] = []
    previous = points[-1]
    previous_inside = previous[2] >= NEAR_PLANE
    for current in points:
        current_inside = current[2] >= NEAR_PLANE
        if current_inside != previous_inside:
            denominator = current[2] - previous[2]
            t = (NEAR_PLANE - previous[2]) / denominator
            output.append((
                previous[0] + t * (current[0] - previous[0]),
                previous[1] + t * (current[1] - previous[1]),
                NEAR_PLANE,
            ))
        if current_inside:
            output.append(current)
        previous = current
        previous_inside = current_inside
    return output


def clip_line_near(p0: Vec3, p1: Vec3) -> tuple[Vec3, Vec3] | None:
    inside_0 = p0[2] >= NEAR_PLANE
    inside_1 = p1[2] >= NEAR_PLANE
    if not inside_0 and not inside_1:
        return None
    if inside_0 and inside_1:
        return p0, p1
    t = (NEAR_PLANE - p0[2]) / (p1[2] - p0[2])
    intersection = (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
        NEAR_PLANE,
    )
    return (p0, intersection) if inside_0 else (intersection, p1)


def clip_polygon_screen(points: list[Vec2]) -> list[Vec2]:
    """Clip a convex projected polygon to the canvas rectangle."""
    polygon = points
    boundaries = (
        (0, 0.0, True),
        (0, float(VIEW_W), False),
        (1, 0.0, True),
        (1, float(VIEW_H), False),
    )
    for axis, boundary, keep_greater in boundaries:
        if not polygon:
            return []
        output: list[Vec2] = []
        previous = polygon[-1]
        previous_inside = (previous[axis] >= boundary
                           if keep_greater else previous[axis] <= boundary)
        for current in polygon:
            current_inside = (current[axis] >= boundary
                              if keep_greater else current[axis] <= boundary)
            if current_inside != previous_inside:
                delta = current[axis] - previous[axis]
                t = (boundary - previous[axis]) / delta
                output.append((
                    previous[0] + t * (current[0] - previous[0]),
                    previous[1] + t * (current[1] - previous[1]),
                ))
            if current_inside:
                output.append(current)
            previous = current
            previous_inside = current_inside
        polygon = output
    return polygon


def clean_screen_polygon(points: list[Vec2]) -> list[Vec2]:
    """Remove clipping artifacts that make polygon triangulation degenerate."""
    epsilon = 1e-5
    cleaned: list[Vec2] = []
    for point in points:
        if (not cleaned
                or abs(point[0] - cleaned[-1][0]) > epsilon
                or abs(point[1] - cleaned[-1][1]) > epsilon):
            cleaned.append(point)
    if (len(cleaned) >= 2
            and abs(cleaned[0][0] - cleaned[-1][0]) <= epsilon
            and abs(cleaned[0][1] - cleaned[-1][1]) <= epsilon):
        cleaned.pop()

    changed = True
    while changed and len(cleaned) >= 3:
        changed = False
        output: list[Vec2] = []
        count = len(cleaned)
        for index, current in enumerate(cleaned):
            previous = cleaned[(index - 1) % count]
            following = cleaned[(index + 1) % count]
            twice_area = ((current[0] - previous[0])
                          * (following[1] - current[1])
                          - (current[1] - previous[1])
                          * (following[0] - current[0]))
            if abs(twice_area) <= epsilon:
                changed = True
            else:
                output.append(current)
        cleaned = output

    if len(cleaned) < 3:
        return []
    signed_area = sum(
        cleaned[index][0] * cleaned[(index + 1) % len(cleaned)][1]
        - cleaned[(index + 1) % len(cleaned)][0] * cleaned[index][1]
        for index in range(len(cleaned))
    )
    return cleaned if abs(signed_area) > epsilon else []


def clip_line_screen(p0: Vec2, p1: Vec2) -> tuple[Vec2, Vec2] | None:
    """Liang-Barsky clipping against the canvas rectangle."""
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    t_enter = 0.0
    t_leave = 1.0
    for direction, distance in (
        (-dx, p0[0]),
        (dx, VIEW_W - p0[0]),
        (-dy, p0[1]),
        (dy, VIEW_H - p0[1]),
    ):
        if abs(direction) < 1e-12:
            if distance < 0.0:
                return None
            continue
        ratio = distance / direction
        if direction < 0.0:
            t_enter = max(t_enter, ratio)
        else:
            t_leave = min(t_leave, ratio)
        if t_enter > t_leave:
            return None
    return (
        (p0[0] + t_enter * dx, p0[1] + t_enter * dy),
        (p0[0] + t_leave * dx, p0[1] + t_leave * dy),
    )


def box_faces(box: Box) -> list[Face]:
    x0 = box.center_x - box.width * 0.5
    x1 = box.center_x + box.width * 0.5
    y0 = box.center_y - box.depth * 0.5
    y1 = box.center_y + box.depth * 0.5
    z1 = box.height
    vertices: tuple[Vec3, ...] = (
        (x0, y0, 0.0), (x1, y0, 0.0),
        (x1, y1, 0.0), (x0, y1, 0.0),
        (x0, y0, z1), (x1, y0, z1),
        (x1, y1, z1), (x0, y1, z1),
    )
    definitions = (
        ((4, 5, 6, 7), (0.0, 0.0, 1.0)),
        ((0, 1, 5, 4), (0.0, -1.0, 0.0)),
        ((1, 2, 6, 5), (1.0, 0.0, 0.0)),
        ((2, 3, 7, 6), (0.0, 1.0, 0.0)),
        ((3, 0, 4, 7), (-1.0, 0.0, 0.0)),
    )
    return [
        Face(tuple(vertices[index] for index in indices), normal, box.color)
        for indices, normal in definitions
    ]


def face_center(face: Face) -> Vec3:
    count = float(len(face.points))
    return (
        sum(point[0] for point in face.points) / count,
        sum(point[1] for point in face.points) / count,
        sum(point[2] for point in face.points) / count,
    )


def face_is_visible(face: Face, eye: Vec3) -> bool:
    return dot(face.normal, subtract(eye, face_center(face))) > 1e-6


def shade_color(color: Color, normal: Vec3) -> Color:
    light_to_surface = normalized((-0.45, -0.65, 1.0))
    brightness = 0.35 + 0.65 * max(0.0, dot(normal, light_to_surface))
    return tuple(min(255, round(channel * brightness)) for channel in color)


def project_world_polygon(points: tuple[Vec3, ...] | list[Vec3],
                          camera: Camera) -> tuple[list[Vec2], float] | None:
    camera_points = [world_to_camera(point, camera) for point in points]
    clipped_camera = clip_polygon_near(camera_points)
    if len(clipped_camera) < 3:
        return None
    projected = [project_camera(point, camera) for point in clipped_camera]
    clipped_screen = clean_screen_polygon(clip_polygon_screen(projected))
    if len(clipped_screen) < 3:
        return None
    average_depth = sum(point[2] for point in clipped_camera) / len(clipped_camera)
    return clipped_screen, average_depth


def project_world_line(p0: Vec3, p1: Vec3,
                       camera: Camera) -> tuple[Vec2, Vec2] | None:
    clipped_camera = clip_line_near(
        world_to_camera(p0, camera), world_to_camera(p1, camera))
    if clipped_camera is None:
        return None
    screen_0 = project_camera(clipped_camera[0], camera)
    screen_1 = project_camera(clipped_camera[1], camera)
    return clip_line_screen(screen_0, screen_1)


def project_ground_label(label: GroundLabel,
                         camera: Camera) -> tuple[Vec2, float] | None:
    camera_point = world_to_camera(label.position, camera)
    if camera_point[2] < NEAR_PLANE:
        return None
    screen = project_camera(camera_point, camera)
    if not (0.0 <= screen[0] <= VIEW_W and 0.0 <= screen[1] <= VIEW_H):
        return None
    apparent_scale = camera.focal_length / camera_point[2]
    screen_size = max(8.0, min(18.0, label.size * apparent_scale))
    return screen, screen_size


def build_world() -> World3D:
    boxes = [
        Box(440.0, 400.0, 210.0, 180.0, 320.0,
            (175, 105, 72), "watch tower"),
        Box(820.0, 980.0, 260.0, 220.0, 180.0,
            (93, 136, 170), "storehouse"),
        Box(1450.0, 430.0, 180.0, 180.0, 420.0,
            (154, 126, 72), "high tower"),
        Box(1760.0, 1080.0, 340.0, 240.0, 140.0,
            (113, 145, 91), "hall"),
    ]
    labels = [
        GroundLabel(
            (float(grid_x + 5), float(grid_y + 4), 6.0),
            f"{grid_x},{grid_y}", 13.0, (132, 164, 137),
        )
        for grid_x in range(0, int(WORLD_W) + 1, 200)
        for grid_y in range(0, int(WORLD_H) + 1, 200)
    ]
    labels.extend(
        GroundLabel(
            (box.center_x - box.width * 0.5,
             box.center_y + box.depth * 0.5 + 28.0, 6.0),
            box.name, 16.0, (218, 207, 151),
        )
        for box in boxes
    )
    return World3D(boxes=boxes, labels=labels)


def clear_layer(parent: dcg.DrawingList) -> None:
    for child in list(parent.children):
        child.delete_item()


def draw_ground_polygon(context: dcg.Context, parent: dcg.DrawingList,
                        points: tuple[Vec3, ...], camera: Camera,
                        fill: Color) -> None:
    projected = project_world_polygon(points, camera)
    if projected is not None:
        dcg.DrawPolygon(context, parent=parent, points=projected[0],
                        fill=fill, color=0, thickness=-1)


def render_scene(context: dcg.Context, parent: dcg.DrawingList,
                 world: World3D, camera: Camera,
                 piece_x: float, piece_y: float) -> None:
    clear_layer(parent)

    draw_ground_polygon(context, parent, (
        (-GROUND_PAD, -GROUND_PAD, 0.0),
        (WORLD_W + GROUND_PAD, -GROUND_PAD, 0.0),
        (WORLD_W + GROUND_PAD, WORLD_H + GROUND_PAD, 0.0),
        (-GROUND_PAD, WORLD_H + GROUND_PAD, 0.0),
    ), camera, (42, 66, 47))

    draw_ground_polygon(context, parent, (
        (0.0, 620.0, 1.0), (WORLD_W, 620.0, 1.0),
        (WORLD_W, 710.0, 1.0), (0.0, 710.0, 1.0),
    ), camera, (68, 116, 168))
    draw_ground_polygon(context, parent, (
        (910.0, 0.0, 2.0), (995.0, 0.0, 2.0),
        (995.0, WORLD_H, 2.0), (910.0, WORLD_H, 2.0),
    ), camera, (130, 116, 91))

    for grid_x in range(0, int(WORLD_W) + 1, 100):
        line = project_world_line(
            (float(grid_x), 0.0, 3.0),
            (float(grid_x), WORLD_H, 3.0), camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=(65, 91, 68), thickness=-1)
    for grid_y in range(0, int(WORLD_H) + 1, 100):
        line = project_world_line(
            (0.0, float(grid_y), 3.0),
            (WORLD_W, float(grid_y), 3.0), camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=(65, 91, 68), thickness=-1)

    border_color = (235, 214, 116)
    border_points = (
        (0.0, 0.0, 5.0), (WORLD_W, 0.0, 5.0),
        (WORLD_W, WORLD_H, 5.0), (0.0, WORLD_H, 5.0),
    )
    for index in range(4):
        line = project_world_line(
            border_points[index], border_points[(index + 1) % 4], camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=border_color, thickness=-3)

    for label in world.labels:
        projected_label = project_ground_label(label, camera)
        if projected_label is None:
            continue
        screen, screen_size = projected_label
        dcg.DrawText(context, parent=parent, pos=screen, text=label.text,
                     size=-screen_size, color=label.color)

    piece = Box(piece_x, piece_y, PIECE_SIZE, PIECE_SIZE, 115.0,
                (245, 194, 67), "player")
    eye = camera_eye(camera)
    render_faces: list[tuple[float, list[Vec2], Color]] = []
    for box in [*world.boxes, piece]:
        for face in box_faces(box):
            if not face_is_visible(face, eye):
                continue
            projected = project_world_polygon(face.points, camera)
            if projected is None:
                continue
            screen_points, average_depth = projected
            render_faces.append((
                average_depth,
                screen_points,
                shade_color(face.color, face.normal),
            ))

    render_faces.sort(key=lambda item: item[0], reverse=True)
    for _, screen_points, fill in render_faces:
        dcg.DrawPolygon(context, parent=parent, points=screen_points,
                        fill=fill, color=(24, 27, 25), thickness=-2)


class Cpu3DController:
    def __init__(self, context: dcg.Context, layer: dcg.DrawingList,
                 world: World3D, status: dcg.Text) -> None:
        self.context = context
        self.layer = layer
        self.displayed_layer = dcg.DrawingList(context, parent=layer)
        self.back_layer = dcg.DrawingList(context, parent=layer, show=False)
        self.world = world
        self.status = status
        self.target_x = WORLD_W * 0.5
        self.target_y = WORLD_H * 0.5
        self.piece_x = WORLD_W * 0.5
        self.piece_y = WORLD_H * 0.5
        self.pitch_deg = 52.0
        self.yaw_deg = 0.0
        self.zoom = 0.72
        self.repaint()

    def move_left(self, *_):  self._move(-MOVE_STEP, 0.0)
    def move_right(self, *_): self._move(MOVE_STEP, 0.0)
    def move_up(self, *_):    self._move(0.0, -MOVE_STEP)
    def move_down(self, *_):  self._move(0.0, MOVE_STEP)

    def set_pitch(self, sender, target, value) -> None:
        self.pitch_deg = float(sender.value)
        self.repaint()

    def set_yaw(self, sender, target, value) -> None:
        self.yaw_deg = float(sender.value)
        self.repaint()

    def set_zoom(self, sender, target, value) -> None:
        self.zoom = float(sender.value)
        self.repaint()

    def _move(self, dx: float, dy: float) -> None:
        self.piece_x = max(PIECE_SIZE * 0.5,
                           min(WORLD_W - PIECE_SIZE * 0.5,
                               self.piece_x + dx))
        self.piece_y = max(PIECE_SIZE * 0.5,
                           min(WORLD_H - PIECE_SIZE * 0.5,
                               self.piece_y + dy))
        self._pan_for_piece()
        self.repaint()

    def _pan_for_piece(self) -> None:
        camera = self.camera()
        camera_point = world_to_camera(
            (self.piece_x, self.piece_y, 0.0), camera)
        if camera_point[2] < NEAR_PLANE:
            return
        screen_x, screen_y = project_camera(camera_point, camera)
        target_screen = (
            max(EDGE_BAND_X, min(VIEW_W - EDGE_BAND_X, screen_x)),
            max(EDGE_BAND_Y, min(VIEW_H - EDGE_BAND_Y, screen_y)),
        )
        if target_screen == (screen_x, screen_y):
            return
        target_ground = ground_world_from_screen(target_screen, camera)
        if target_ground is None:
            return
        offset_x = target_ground[0] - camera.target_x
        offset_y = target_ground[1] - camera.target_y
        self.target_x = max(
            0.0, min(WORLD_W, self.piece_x - offset_x))
        self.target_y = max(
            0.0, min(WORLD_H, self.piece_y - offset_y))

    def camera(self) -> Camera:
        return Camera(
            self.target_x, self.target_y,
            self.yaw_deg, self.pitch_deg, self.zoom,
        )

    def repaint(self) -> None:
        camera = self.camera()
        render_scene(
            self.context, self.back_layer, self.world, camera,
            self.piece_x, self.piece_y)
        with self.layer.mutex:
            self.displayed_layer.show = False
            self.back_layer.show = True
            self.displayed_layer, self.back_layer = (
                self.back_layer, self.displayed_layer)
        self.status.value = (
            f"piece=({self.piece_x:.0f},{self.piece_y:.0f},0)  "
            f"target=({self.target_x:.0f},{self.target_y:.0f})  "
            f"pitch={self.pitch_deg:.1f} deg  yaw={self.yaw_deg:.1f} deg  "
            f"zoom={self.zoom:.2f}x  camera distance={camera.distance:.0f}"
        )


def build_ui(context: dcg.Context) -> None:
    world = build_world()
    with dcg.Window(context, label="DearCyGui CPU 3D map",
                    width=VIEW_W + 40, height=VIEW_H + 300) as window:
        dcg.Text(context,
                 value="Arrow keys move the gold 3D piece; the camera follows "
                     "when it enters an edge band.",
                 wrap=VIEW_W)
        status = dcg.Text(context, value="")
        with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0),
                         pmax=(VIEW_W, VIEW_H), fill=(19, 24, 31),
                         color=0, thickness=-1)
            scene_layer = dcg.DrawingList(context, parent=canvas)
            band_color = (245, 205, 83, 35)
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0),
                     pmax=(VIEW_W, EDGE_BAND_Y), fill=band_color,
                         color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                     pmin=(0, VIEW_H - EDGE_BAND_Y),
                         pmax=(VIEW_W, VIEW_H), fill=band_color,
                         color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas, pmin=(0, EDGE_BAND_Y),
                     pmax=(EDGE_BAND_X, VIEW_H - EDGE_BAND_Y),
                         fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                     pmin=(VIEW_W - EDGE_BAND_X, EDGE_BAND_Y),
                     pmax=(VIEW_W, VIEW_H - EDGE_BAND_Y),
                         fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                     pmin=(EDGE_BAND_X, EDGE_BAND_Y),
                     pmax=(VIEW_W - EDGE_BAND_X,
                         VIEW_H - EDGE_BAND_Y),
                         color=(245, 205, 83, 115), thickness=-1)
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0),
                         pmax=(VIEW_W, VIEW_H), color=(112, 132, 155),
                         thickness=-2)

        controller = Cpu3DController(context, scene_layer, world, status)
        dcg.Slider(context, label="Camera pitch from overhead (degrees)",
                   min_value=0.0, max_value=78.0,
                   value=controller.pitch_deg, width=VIEW_W,
                   callback=controller.set_pitch)
        dcg.Slider(context, label="Camera yaw (degrees)",
                   min_value=-180.0, max_value=180.0,
                   value=controller.yaw_deg, width=VIEW_W,
                   callback=controller.set_yaw)
        dcg.Slider(context, label="Camera zoom",
                   min_value=ZOOM_MIN, max_value=ZOOM_MAX,
                   value=controller.zoom, width=VIEW_W,
                   callback=controller.set_zoom)
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
        title="DCG Test Map - CPU 3D environment",
        width=VIEW_W + 80, height=VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()