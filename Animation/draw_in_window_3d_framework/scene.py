from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import heapq
from typing import Any, Callable, Iterable, Literal, Protocol, Sequence, TypeAlias, runtime_checkable

from .math3d import DEFAULT_LIGHT_DIRECTION, Camera3D, Color, Vec2, Vec3, Viewport, cross, dot, subtract


ColorValue: TypeAlias = Color | int
PacketKind: TypeAlias = Literal["polygon", "line", "text", "stream"]
StreamFrameBuilder: TypeAlias = Callable[[Any, Any, "FrameContext", int], None]


class AnimationProjection(Enum):
    PERSISTENT_OVERLAY = "persistent_overlay"
    PREPROJECTED_BACKGROUND = "preprojected_background"
    OCCLUDABLE_WORLD = "occludable_world"


class LineRenderLayer(Enum):
    WORLD = "world"
    UTILITY = "utility"


class BillboardFacing(Enum):
    CAMERA_YAW = "camera_yaw"


class FieldAssociation(Enum):
    CELL = "cell"
    NODE = "node"


class OutOfRangePolicy(Enum):
    CLAMP = "clamp"
    TRANSPARENT = "transparent"


@dataclass(frozen=True)
class FrameContext:
    camera: Camera3D
    viewport: Viewport
    light_direction: Vec3 = DEFAULT_LIGHT_DIRECTION
    eye: Vec3 = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "eye", self.camera.eye(self.viewport))


@runtime_checkable
class Material3D(Protocol):
    fill: ColorValue | None
    outline: ColorValue | None
    thickness: float
    shaded: bool
    blend_mode: str | None
    line_occluder: bool


@dataclass(frozen=True)
class SolidMaterial:
    """Flat or shaded fill/outline material used by retained solid world primitives."""

    fill: ColorValue | None
    outline: ColorValue | None = (24, 27, 25)
    thickness: float = -2.0
    shaded: bool = True
    blend_mode: str | None = None
    line_occluder: bool = True


ColorMap: TypeAlias = Callable[[float], ColorValue]


def grayscale_color_map(amount: float) -> Color:
    channel = int(round(max(0.0, min(1.0, amount)) * 255.0))
    return channel, channel, channel


def turbo_color_map(amount: float) -> Color:
    amount = max(0.0, min(1.0, amount))
    red = int(round(34.0 + 221.0 * min(1.0, max(0.0, amount * 1.7))))
    green = int(round(48.0 + 207.0 * (1.0 - abs(amount - 0.5) * 2.0)))
    blue = int(round(180.0 * max(0.0, 1.0 - amount * 1.25)))
    return red, green, blue


@dataclass(frozen=True)
class ScalarFieldMaterial:
    values: tuple[float, ...]
    association: FieldAssociation = FieldAssociation.CELL
    color_map: ColorMap = turbo_color_map
    value_range: tuple[float, float] | None = None
    out_of_range: OutOfRangePolicy = OutOfRangePolicy.CLAMP
    outline: ColorValue | None = None
    thickness: float = -1.0
    shaded: bool = True
    blend_mode: str | None = None
    line_occluder: bool = True
    fill: ColorValue | None = None

    def color_for_value(self, value: float) -> ColorValue | None:
        value_min, value_max = self.resolved_range()
        if value_max <= value_min:
            amount = 0.0
        else:
            amount = (value - value_min) / (value_max - value_min)
        if amount < 0.0 or amount > 1.0:
            if self.out_of_range is OutOfRangePolicy.TRANSPARENT:
                return None
            amount = max(0.0, min(1.0, amount))
        return self.color_map(amount)

    def resolved_range(self) -> tuple[float, float]:
        if self.value_range is not None:
            return self.value_range
        if not self.values:
            return 0.0, 1.0
        return min(self.values), max(self.values)


@dataclass(frozen=True)
class ImageMaterial:
    """Single texture material for billboard quads or selected box faces."""

    texture: object
    uv_coordinates: tuple[Vec2, Vec2, Vec2, Vec2] = (
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
    )
    tessellation: int = 12
    fill: ColorValue | None = (160, 160, 160)
    outline: ColorValue | None = (24, 27, 25)
    thickness: float = -2.0
    shaded: bool = True
    blend_mode: str | None = None
    line_occluder: bool = True

    def __post_init__(self) -> None:
        if self.tessellation < 1:
            raise ValueError("tessellation must be at least 1")

    def fallback_material(self) -> SolidMaterial:
        return SolidMaterial(
            fill=self.fill,
            outline=self.outline,
            thickness=self.thickness,
            shaded=self.shaded,
            blend_mode=self.blend_mode,
            line_occluder=self.line_occluder,
        )


@dataclass(frozen=True)
class AnimatedImageMaterial(ImageMaterial):
    """Frame-cycled texture material for billboards and other image-backed packets."""

    texture: object | None = None
    frames: tuple[object, ...] = ()
    loop_seconds: float = 1.0
    frame_offset: int = 0
    projection_policy: AnimationProjection = AnimationProjection.OCCLUDABLE_WORLD

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("frames must contain at least one texture")
        if self.texture is None:
            object.__setattr__(self, "texture", self.frames[0])
        super().__post_init__()
        if self.loop_seconds <= 0.0:
            raise ValueError("loop_seconds must be positive")

    def frame_texture(self, frame_index: int) -> object:
        return self.frames[(frame_index + self.frame_offset) % len(self.frames)]

    def frame_end_time(self, frame_index: int) -> float:
        return (frame_index + 1) * self.loop_seconds / len(self.frames)


@dataclass(frozen=True)
class WorldRenderPacket:
    kind: PacketKind
    points: tuple[Vec3, ...]
    material: Material3D | None = None
    animation_projection: AnimationProjection | None = None
    line_render_layer: LineRenderLayer = LineRenderLayer.WORLD
    line_occluder: bool | None = None
    normal: Vec3 | None = None
    cull_back_face: bool = False
    image_clip_to_viewport: bool = False
    text: str = ""
    text_size: float = 0.0
    text_min_size: float = 0.0
    text_max_size: float = float("inf")
    text_color: ColorValue = (255, 255, 255)
    stream_frame_count: int = 0
    stream_loop_seconds: float = 0.0
    stream_frame_builder: StreamFrameBuilder | None = None
    cache_key: object | None = None
    world_size: tuple[float, float] | None = None
    billboard: bool = False
    source_id: int | None = None


@dataclass(frozen=True)
class ProjectedRenderEntry:
    kind: PacketKind
    stable_index: int
    average_depth: float
    points: tuple[Vec2, ...]
    camera_points: tuple[Vec3, ...] = ()
    material: Material3D | None = None
    animation_projection: AnimationProjection | None = None
    line_render_layer: LineRenderLayer = LineRenderLayer.WORLD
    line_occluder: bool = True
    image_points: tuple[Vec2, ...] = ()
    image_clip_to_viewport: bool = False
    text: str = ""
    text_size: float = 0.0
    text_color: ColorValue = (255, 255, 255)
    stream_frame_count: int = 0
    stream_loop_seconds: float = 0.0
    stream_frame_builder: StreamFrameBuilder | None = None
    cache_key: object | None = None
    overlay_origin: Vec2 | None = None
    overlay_scale: tuple[float, float] = (1.0, 1.0)
    visible: bool = True
    billboard: bool = False
    source_id: int | None = None


@dataclass(frozen=True)
class ObjectHandle:
    object_id: int


@runtime_checkable
class Renderable3D(Protocol):
    visible: bool

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        ...


@dataclass
class Scene3D:
    """Retained container of visible 3D objects composed into one world scene."""

    background: ColorValue = (19, 24, 31)
    _objects: dict[int, Renderable3D] = field(default_factory=dict, init=False, repr=False)
    _next_object_id: int = field(default=1, init=False, repr=False)

    def add(self, item: Renderable3D) -> ObjectHandle:
        handle = ObjectHandle(self._next_object_id)
        self._objects[handle.object_id] = item
        self._next_object_id += 1
        return handle

    def get(self, handle: ObjectHandle) -> Renderable3D:
        return self._objects[handle.object_id]

    def remove(self, handle: ObjectHandle) -> None:
        del self._objects[handle.object_id]

    def update_object(self, handle: ObjectHandle, **changes: object) -> None:
        item = self.get(handle)
        updater = getattr(item, "update_object", None)
        if updater is None:
            for name, value in changes.items():
                if not hasattr(item, name):
                    raise AttributeError(f"{type(item).__name__} has no field {name!r}")
                setattr(item, name, value)
            return
        updater(**changes)

    def iter_visible(self) -> Iterable[Renderable3D]:
        for item in self._objects.values():
            if item.visible:
                yield item

    @property
    def object_count(self) -> int:
        return len(self._objects)


@dataclass(frozen=True)
class SortResult:
    entries: tuple[ProjectedRenderEntry, ...]
    cycle_detected: bool = False


@dataclass(frozen=True)
class RenderStats:
    packet_count: int
    clipped_count: int
    projected_count: int
    emitted_count: int
    cycle_detected: bool = False


class RenderSorter(Protocol):
    def sort(
        self,
        entries: Iterable[ProjectedRenderEntry],
        frame: FrameContext | None = None,
    ) -> SortResult:
        ...


def _cross_2d(first: Vec2, second: Vec2) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _signed_polygon_area(points: Sequence[Vec2]) -> float:
    return 0.5 * sum(
        _cross_2d(points[index], points[(index + 1) % len(points)])
        for index in range(len(points))
    )


def convex_screen_polygons_overlap(
    first: Sequence[Vec2],
    second: Sequence[Vec2],
    epsilon: float = 1e-7,
) -> bool:
    if len(first) < 3 or len(second) < 3:
        return False
    for polygon in (first, second):
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            edge = (end[0] - start[0], end[1] - start[1])
            axis = (-edge[1], edge[0])
            first_min, first_max = _project_polygon_axis(first, axis)
            second_min, second_max = _project_polygon_axis(second, axis)
            if first_max < second_min + epsilon or second_max < first_min + epsilon:
                return False
    return True


def _project_polygon_axis(points: Sequence[Vec2], axis: Vec2) -> tuple[float, float]:
    projected = [point[0] * axis[0] + point[1] * axis[1] for point in points]
    return min(projected), max(projected)


def _line_intersection(
    segment_start: Vec2,
    segment_end: Vec2,
    clip_start: Vec2,
    clip_end: Vec2,
) -> Vec2:
    segment = (segment_end[0] - segment_start[0], segment_end[1] - segment_start[1])
    clip = (clip_end[0] - clip_start[0], clip_end[1] - clip_start[1])
    denominator = _cross_2d(segment, clip)
    if abs(denominator) <= 1e-12:
        return segment_end
    offset = (clip_start[0] - segment_start[0], clip_start[1] - segment_start[1])
    amount = _cross_2d(offset, clip) / denominator
    return (
        segment_start[0] + amount * segment[0],
        segment_start[1] + amount * segment[1],
    )


def _convex_polygon_intersection(subject: Sequence[Vec2], clip: Sequence[Vec2]) -> list[Vec2]:
    if len(subject) < 3 or len(clip) < 3:
        return []
    orientation = 1.0 if _signed_polygon_area(clip) >= 0.0 else -1.0
    output = list(subject)
    for clip_index, clip_start in enumerate(clip):
        if not output:
            return []
        clip_end = clip[(clip_index + 1) % len(clip)]
        edge = (clip_end[0] - clip_start[0], clip_end[1] - clip_start[1])

        def inside(point: Vec2) -> bool:
            offset = (point[0] - clip_start[0], point[1] - clip_start[1])
            return orientation * _cross_2d(edge, offset) >= -1e-7

        input_points = output
        output = []
        previous = input_points[-1]
        previous_inside = inside(previous)
        for current in input_points:
            current_inside = inside(current)
            if current_inside != previous_inside:
                output.append(_line_intersection(previous, current, clip_start, clip_end))
            if current_inside:
                output.append(current)
            previous = current
            previous_inside = current_inside
    return output


def _plane_from_camera_points(points: Sequence[Vec3]) -> tuple[Vec3, Vec3] | None:
    if len(points) < 3:
        return None
    origin = points[0]
    for second_index in range(1, len(points) - 1):
        for third_index in range(second_index + 1, len(points)):
            normal = cross(
                subtract(points[second_index], origin),
                subtract(points[third_index], origin),
            )
            if dot(normal, normal) > 1e-12:
                return origin, normal
    return None


def ray_plane_depth(
    screen_point: Vec2,
    camera_points: Sequence[Vec3],
    frame: FrameContext,
) -> float | None:
    plane = _plane_from_camera_points(camera_points)
    if plane is None:
        return None
    origin, normal = plane
    center_x, center_y = frame.viewport.center
    focal_length = frame.camera.focal_length(frame.viewport)
    ray = (
        (screen_point[0] - center_x) / focal_length,
        (screen_point[1] - center_y) / focal_length,
        1.0,
    )
    denominator = dot(normal, ray)
    if abs(denominator) <= 1e-12:
        return None
    depth = dot(normal, origin) / denominator
    return depth if depth >= frame.camera.near_plane else None


def overlapping_polygon_depths(
    first: ProjectedRenderEntry,
    second: ProjectedRenderEntry,
    frame: FrameContext,
    overlap_area_epsilon: float = 0.25,
) -> tuple[float, float] | None:
    if first.kind != "polygon" or second.kind != "polygon":
        return None
    if not convex_screen_polygons_overlap(first.points, second.points):
        return None
    overlap = _convex_polygon_intersection(first.points, second.points)
    if len(overlap) < 3 or abs(_signed_polygon_area(overlap)) <= overlap_area_epsilon:
        return None
    sample = (
        sum(point[0] for point in overlap) / len(overlap),
        sum(point[1] for point in overlap) / len(overlap),
    )
    first_depth = ray_plane_depth(sample, first.camera_points, frame)
    second_depth = ray_plane_depth(sample, second.camera_points, frame)
    if first_depth is None or second_depth is None:
        return None
    return first_depth, second_depth


class AverageDepthSorter:
    def sort(self, entries: Iterable[ProjectedRenderEntry], frame: FrameContext | None = None) -> SortResult:
        ordered = tuple(
            sorted(
                entries,
                key=lambda entry: (-entry.average_depth, entry.stable_index),
            )
        )
        return SortResult(entries=ordered, cycle_detected=False)


class OverlapDepthSorter:
    def __init__(
        self,
        *,
        overlap_area_epsilon: float = 0.25,
        depth_epsilon: float = 1e-5,
    ) -> None:
        self.overlap_area_epsilon = overlap_area_epsilon
        self.depth_epsilon = depth_epsilon

    def sort(self, entries: Iterable[ProjectedRenderEntry], frame: FrameContext | None = None) -> SortResult:
        ordered_entries = tuple(entries)
        if frame is None:
            return AverageDepthSorter().sort(ordered_entries)

        entry_count = len(ordered_entries)
        successors: list[set[int]] = [set() for _ in ordered_entries]
        indegree = [0] * entry_count
        for first_index in range(entry_count):
            for second_index in range(first_index + 1, entry_count):
                depths = overlapping_polygon_depths(
                    ordered_entries[first_index],
                    ordered_entries[second_index],
                    frame,
                    overlap_area_epsilon=self.overlap_area_epsilon,
                )
                if depths is None or abs(depths[0] - depths[1]) <= self.depth_epsilon:
                    continue
                farther = first_index if depths[0] > depths[1] else second_index
                nearer = second_index if farther == first_index else first_index
                if nearer not in successors[farther]:
                    successors[farther].add(nearer)
                    indegree[nearer] += 1

        ready: list[tuple[float, int, int]] = []
        for index, entry in enumerate(ordered_entries):
            if indegree[index] == 0:
                heapq.heappush(ready, (-entry.average_depth, entry.stable_index, index))

        ordered_indices: list[int] = []
        while ready:
            _, _, index = heapq.heappop(ready)
            ordered_indices.append(index)
            for successor in successors[index]:
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    entry = ordered_entries[successor]
                    heapq.heappush(ready, (-entry.average_depth, entry.stable_index, successor))

        if len(ordered_indices) != entry_count:
            fallback = AverageDepthSorter().sort(ordered_entries).entries
            return SortResult(entries=fallback, cycle_detected=True)
        return SortResult(
            entries=tuple(ordered_entries[index] for index in ordered_indices),
            cycle_detected=False,
        )