from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TypeAlias


Vec2: TypeAlias = tuple[float, float]
Vec3: TypeAlias = tuple[float, float, float]
Color: TypeAlias = tuple[int, int, int] | tuple[int, int, int, int]


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


def length(vector: Vec3) -> float:
    return math.sqrt(dot(vector, vector))


def normalized(vector: Vec3) -> Vec3:
    vector_length = length(vector)
    if vector_length <= 1e-12:
        return 0.0, 0.0, 0.0
    return (
        vector[0] / vector_length,
        vector[1] / vector_length,
        vector[2] / vector_length,
    )


DEFAULT_LIGHT_DIRECTION: Vec3 = normalized((-0.45, -0.65, 1.0))


@dataclass(frozen=True)
class Viewport:
    width: float
    height: float

    @property
    def center(self) -> Vec2:
        return self.width * 0.5, self.height * 0.5

    def contains(self, point: Vec2) -> bool:
        return 0.0 <= point[0] <= self.width and 0.0 <= point[1] <= self.height


@dataclass(frozen=True)
class Camera3D:
    target: Vec3
    yaw_deg: float
    pitch_deg: float
    zoom: float
    fov_y_deg: float = 58.0
    near_plane: float = 25.0

    def focal_length(self, viewport: Viewport) -> float:
        return viewport.height * 0.5 / math.tan(math.radians(self.fov_y_deg) * 0.5)

    def distance(self, viewport: Viewport) -> float:
        return self.focal_length(viewport) / self.zoom

    def eye(self, viewport: Viewport) -> Vec3:
        yaw = math.radians(self.yaw_deg)
        pitch = math.radians(self.pitch_deg)
        horizontal = self.distance(viewport) * math.sin(pitch)
        return (
            self.target[0] + math.sin(yaw) * horizontal,
            self.target[1] + math.cos(yaw) * horizontal,
            self.target[2] + self.distance(viewport) * math.cos(pitch),
        )

    def world_to_camera(self, point: Vec3, viewport: Viewport) -> Vec3:
        dx = point[0] - self.target[0]
        dy = point[1] - self.target[1]
        dz = point[2] - self.target[2]

        yaw = math.radians(self.yaw_deg)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        rotated_x = cos_yaw * dx - sin_yaw * dy
        rotated_y = sin_yaw * dx + cos_yaw * dy

        pitch = math.radians(self.pitch_deg)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        screen_down = cos_pitch * rotated_y - sin_pitch * dz
        forward_depth = (
            self.distance(viewport) - sin_pitch * rotated_y - cos_pitch * dz
        )
        return rotated_x, screen_down, forward_depth

    def camera_to_screen(self, point: Vec3, viewport: Viewport) -> Vec2:
        scale = self.focal_length(viewport) / point[2]
        center_x, center_y = viewport.center
        return center_x + point[0] * scale, center_y + point[1] * scale

    def ground_from_screen(
        self,
        screen: Vec2,
        viewport: Viewport,
        ground_z: float = 0.0,
    ) -> Vec3 | None:
        focal_length = self.focal_length(viewport)
        center_x, center_y = viewport.center
        normalized_x = (screen[0] - center_x) / focal_length
        normalized_y = (screen[1] - center_y) / focal_length

        pitch = math.radians(self.pitch_deg)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        denominator = cos_pitch + normalized_y * sin_pitch
        if denominator <= 1e-8:
            return None

        dz = ground_z - self.target[2]
        rotated_y = (
            normalized_y * self.distance(viewport)
            + dz * (sin_pitch - normalized_y * cos_pitch)
        ) / denominator
        depth = self.distance(viewport) - sin_pitch * rotated_y - cos_pitch * dz
        if depth < self.near_plane:
            return None
        rotated_x = normalized_x * depth

        yaw = math.radians(self.yaw_deg)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        offset_x = cos_yaw * rotated_x + sin_yaw * rotated_y
        offset_y = -sin_yaw * rotated_x + cos_yaw * rotated_y
        return self.target[0] + offset_x, self.target[1] + offset_y, ground_z


@dataclass(frozen=True)
class ProjectedPolygon:
    points: tuple[Vec2, ...]
    average_depth: float


@dataclass(frozen=True)
class ProjectedLine:
    p0: Vec2
    p1: Vec2
    average_depth: float
    camera_points: tuple[Vec3, Vec3]


@dataclass(frozen=True)
class ProjectedQuad:
    points: tuple[Vec2, Vec2, Vec2, Vec2]
    average_depth: float


def clip_polygon_near(points: list[Vec3], near_plane: float) -> list[Vec3]:
    if not points:
        return []
    output: list[Vec3] = []
    previous = points[-1]
    previous_inside = previous[2] >= near_plane
    for current in points:
        current_inside = current[2] >= near_plane
        if current_inside != previous_inside:
            denominator = current[2] - previous[2]
            t = (near_plane - previous[2]) / denominator
            output.append(
                (
                    previous[0] + t * (current[0] - previous[0]),
                    previous[1] + t * (current[1] - previous[1]),
                    near_plane,
                )
            )
        if current_inside:
            output.append(current)
        previous = current
        previous_inside = current_inside
    return output


def clip_line_near(p0: Vec3, p1: Vec3, near_plane: float) -> tuple[Vec3, Vec3] | None:
    inside_0 = p0[2] >= near_plane
    inside_1 = p1[2] >= near_plane
    if not inside_0 and not inside_1:
        return None
    if inside_0 and inside_1:
        return p0, p1
    t = (near_plane - p0[2]) / (p1[2] - p0[2])
    intersection = (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
        near_plane,
    )
    return (p0, intersection) if inside_0 else (intersection, p1)


def clip_polygon_to_viewport(points: list[Vec2], viewport: Viewport) -> list[Vec2]:
    polygon = points
    boundaries = (
        (0, 0.0, True),
        (0, viewport.width, False),
        (1, 0.0, True),
        (1, viewport.height, False),
    )
    for axis, boundary, keep_greater in boundaries:
        if not polygon:
            return []
        output: list[Vec2] = []
        previous = polygon[-1]
        previous_inside = (
            previous[axis] >= boundary if keep_greater else previous[axis] <= boundary
        )
        for current in polygon:
            current_inside = (
                current[axis] >= boundary if keep_greater else current[axis] <= boundary
            )
            if current_inside != previous_inside:
                delta = current[axis] - previous[axis]
                t = (boundary - previous[axis]) / delta
                output.append(
                    (
                        previous[0] + t * (current[0] - previous[0]),
                        previous[1] + t * (current[1] - previous[1]),
                    )
                )
            if current_inside:
                output.append(current)
            previous = current
            previous_inside = current_inside
        polygon = output
    return polygon


def clean_polygon(points: list[Vec2], epsilon: float = 1e-5) -> list[Vec2]:
    cleaned: list[Vec2] = []
    for point in points:
        if (
            not cleaned
            or abs(point[0] - cleaned[-1][0]) > epsilon
            or abs(point[1] - cleaned[-1][1]) > epsilon
        ):
            cleaned.append(point)
    if (
        len(cleaned) >= 2
        and abs(cleaned[0][0] - cleaned[-1][0]) <= epsilon
        and abs(cleaned[0][1] - cleaned[-1][1]) <= epsilon
    ):
        cleaned.pop()

    changed = True
    while changed and len(cleaned) >= 3:
        changed = False
        output: list[Vec2] = []
        count = len(cleaned)
        for index, current in enumerate(cleaned):
            previous = cleaned[(index - 1) % count]
            following = cleaned[(index + 1) % count]
            twice_area = (
                (current[0] - previous[0]) * (following[1] - current[1])
                - (current[1] - previous[1]) * (following[0] - current[0])
            )
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


def clip_line_to_viewport(p0: Vec2, p1: Vec2, viewport: Viewport) -> tuple[Vec2, Vec2] | None:
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    t_enter = 0.0
    t_leave = 1.0
    for direction, distance in (
        (-dx, p0[0]),
        (dx, viewport.width - p0[0]),
        (-dy, p0[1]),
        (dy, viewport.height - p0[1]),
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


def average_depth(points: tuple[Vec3, ...] | list[Vec3]) -> float:
    return sum(point[2] for point in points) / len(points)


def face_center(points: tuple[Vec3, ...] | list[Vec3]) -> Vec3:
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def is_face_visible(
    normal: Vec3,
    points: tuple[Vec3, ...] | list[Vec3],
    eye: Vec3,
    epsilon: float = 1e-6,
) -> bool:
    return dot(normal, subtract(eye, face_center(points))) > epsilon


def shade_directional(
    color: Color,
    normal: Vec3,
    light_direction: Vec3 = DEFAULT_LIGHT_DIRECTION,
    ambient: float = 0.35,
    diffuse: float = 0.65,
) -> Color:
    brightness = ambient + diffuse * max(0.0, dot(normalized(normal), normalized(light_direction)))
    shaded_rgb = tuple(min(255, round(channel * brightness)) for channel in color[:3])
    if len(color) == 4:
        return shaded_rgb + (color[3],)
    return shaded_rgb


class ProjectionPipeline:
    """Project world-space polygons and lines through the current camera and viewport."""

    def __init__(
        self,
        camera: Camera3D,
        viewport: Viewport,
        epsilon: float = 1e-5,
    ) -> None:
        self.camera = camera
        self.viewport = viewport
        self.epsilon = epsilon

    def project_polygon(self, points: tuple[Vec3, ...] | list[Vec3]) -> ProjectedPolygon | None:
        camera_points = [self.camera.world_to_camera(point, self.viewport) for point in points]
        clipped_camera = clip_polygon_near(camera_points, self.camera.near_plane)
        if len(clipped_camera) < 3:
            return None
        projected = [
            self.camera.camera_to_screen(point, self.viewport) for point in clipped_camera
        ]
        clipped_screen = clip_polygon_to_viewport(projected, self.viewport)
        cleaned = clean_polygon(clipped_screen, epsilon=self.epsilon)
        if len(cleaned) < 3:
            return None
        return ProjectedPolygon(tuple(cleaned), average_depth(clipped_camera))

    def project_line(self, start: Vec3, end: Vec3) -> ProjectedLine | None:
        start_camera = self.camera.world_to_camera(start, self.viewport)
        end_camera = self.camera.world_to_camera(end, self.viewport)
        clipped_camera = clip_line_near(start_camera, end_camera, self.camera.near_plane)
        if clipped_camera is None:
            return None
        screen_0 = self.camera.camera_to_screen(clipped_camera[0], self.viewport)
        screen_1 = self.camera.camera_to_screen(clipped_camera[1], self.viewport)
        clipped_screen = clip_line_to_viewport(screen_0, screen_1, self.viewport)
        if clipped_screen is None:
            return None
        return ProjectedLine(
            clipped_screen[0],
            clipped_screen[1],
            average_depth(list(clipped_camera)),
            clipped_camera,
        )

    def project_complete_quad(
        self,
        points: tuple[Vec3, Vec3, Vec3, Vec3] | list[Vec3],
    ) -> ProjectedQuad | None:
        if len(points) != 4:
            return None
        camera_points = [self.camera.world_to_camera(point, self.viewport) for point in points]
        if any(point[2] < self.camera.near_plane for point in camera_points):
            return None
        screen_points = [
            self.camera.camera_to_screen(point, self.viewport) for point in camera_points
        ]
        if any(not self.viewport.contains(point) for point in screen_points):
            return None
        return ProjectedQuad(
            (screen_points[0], screen_points[1], screen_points[2], screen_points[3]),
            average_depth(camera_points),
        )