from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable, Sequence

from .math3d import Vec3, cross, normalized, subtract
from .scene import (
    AnimatedImageMaterial,
    AnimationProjection,
    BillboardFacing,
    FrameContext,
    ImageMaterial,
    LineRenderLayer,
    Material3D,
    SolidMaterial,
    StreamFrameBuilder,
    WorldRenderPacket,
)


def polygon_normal(points: Sequence[Vec3]) -> Vec3:
    if len(points) < 3:
        return 0.0, 0.0, 0.0
    return normalized(
        cross(
            subtract(points[1], points[0]),
            subtract(points[2], points[0]),
        )
    )


@dataclass
class Polygon3D:
    points: tuple[Vec3, ...]
    material: SolidMaterial
    cull_back_face: bool = True
    normal: Vec3 | None = None
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        normal = self.normal if self.normal is not None else polygon_normal(self.points)
        yield WorldRenderPacket(
            kind="polygon",
            points=self.points,
            material=self.material,
            normal=normal,
            cull_back_face=self.cull_back_face,
        )


@dataclass
class GroundPlane3D:
    bounds: tuple[float, float, float, float]
    z: float
    material: SolidMaterial
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        x0, y0, x1, y1 = self.bounds
        yield WorldRenderPacket(
            kind="polygon",
            points=((x0, y0, self.z), (x1, y0, self.z), (x1, y1, self.z), (x0, y1, self.z)),
            material=self.material,
            normal=(0.0, 0.0, 1.0),
            cull_back_face=False,
        )


@dataclass
class Line3D:
    start: Vec3
    end: Vec3
    color: tuple[int, int, int] | tuple[int, int, int, int] | int
    thickness: float = -1.0
    render_layer: LineRenderLayer = LineRenderLayer.WORLD
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        yield WorldRenderPacket(
            kind="line",
            points=(self.start, self.end),
            material=SolidMaterial(fill=None, outline=self.color, thickness=self.thickness, shaded=False),
            line_render_layer=self.render_layer,
        )


@dataclass
class Polyline3D:
    points: tuple[Vec3, ...]
    color: tuple[int, int, int] | tuple[int, int, int, int] | int
    thickness: float = -1.0
    closed: bool = False
    render_layer: LineRenderLayer = LineRenderLayer.WORLD
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        if len(self.points) < 2:
            return
        stop = len(self.points) if self.closed else len(self.points) - 1
        for index in range(stop):
            yield WorldRenderPacket(
                kind="line",
                points=(self.points[index], self.points[(index + 1) % len(self.points)]),
                material=SolidMaterial(fill=None, outline=self.color, thickness=self.thickness, shaded=False),
                line_render_layer=self.render_layer,
            )


@dataclass
class Text3D:
    position: Vec3
    text: str
    size: float
    color: tuple[int, int, int] | tuple[int, int, int, int] | int
    min_size: float = 8.0
    max_size: float = 18.0
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        yield WorldRenderPacket(
            kind="text",
            points=(self.position,),
            text=self.text,
            text_size=self.size,
            text_min_size=self.min_size,
            text_max_size=self.max_size,
            text_color=self.color,
        )


@dataclass
class Box3D:
    center: Vec3
    size: tuple[float, float, float]
    material: Material3D
    face_materials: tuple[Material3D | None, ...] = ()
    visible: bool = True
    _face_definitions: tuple[tuple[tuple[int, int, int, int], Vec3], ...] = field(
        default=(
            ((0, 3, 2, 1), (0.0, 0.0, -1.0)),
            ((4, 5, 6, 7), (0.0, 0.0, 1.0)),
            ((0, 1, 5, 4), (0.0, -1.0, 0.0)),
            ((1, 2, 6, 5), (1.0, 0.0, 0.0)),
            ((2, 3, 7, 6), (0.0, 1.0, 0.0)),
            ((3, 0, 4, 7), (-1.0, 0.0, 0.0)),
        ),
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.face_materials and len(self.face_materials) != len(self._face_definitions):
            raise ValueError("face_materials must contain one override per box face")

    def vertices(self) -> tuple[Vec3, ...]:
        center_x, center_y, base_z = self.center
        width, depth, height = self.size
        x0 = center_x - width * 0.5
        x1 = center_x + width * 0.5
        y0 = center_y - depth * 0.5
        y1 = center_y + depth * 0.5
        z0 = base_z
        z1 = base_z + height
        return (
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
        )

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        vertices = self.vertices()
        for face_index, (indices, normal) in enumerate(self._face_definitions):
            yield WorldRenderPacket(
                kind="polygon",
                points=tuple(vertices[index] for index in indices),
                material=self.face_materials[face_index] if self.face_materials and self.face_materials[face_index] is not None else self.material,
                normal=normal,
                cull_back_face=True,
            )


def billboard_quad(anchor: Vec3, world_size: tuple[float, float], yaw_deg: float) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    half_width = world_size[0] * 0.5
    yaw = math.radians(yaw_deg)
    right_x = math.cos(yaw) * half_width
    right_y = -math.sin(yaw) * half_width
    left = (anchor[0] - right_x, anchor[1] - right_y, anchor[2])
    right = (anchor[0] + right_x, anchor[1] + right_y, anchor[2])
    return (
        (left[0], left[1], anchor[2] + world_size[1]),
        (right[0], right[1], anchor[2] + world_size[1]),
        right,
        left,
    )


@dataclass
class Billboard3D:
    anchor: Vec3
    world_size: tuple[float, float]
    material: ImageMaterial | AnimatedImageMaterial
    facing: BillboardFacing = BillboardFacing.CAMERA_YAW
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        if self.facing is not BillboardFacing.CAMERA_YAW:
            raise ValueError(f"Unsupported billboard facing: {self.facing}")
        points = billboard_quad(self.anchor, self.world_size, frame.camera.yaw_deg)
        animation_projection = (
            self.material.projection_policy
            if isinstance(self.material, AnimatedImageMaterial)
            else None
        )
        yield WorldRenderPacket(
            kind="polygon",
            points=points,
            material=self.material,
            animation_projection=animation_projection,
            line_occluder=False,
            image_clip_to_viewport=animation_projection is AnimationProjection.OCCLUDABLE_WORLD,
            cache_key=self,
            world_size=self.world_size,
            billboard=True,
        )


@dataclass
class DrawStream3D:
    projection_policy: AnimationProjection
    frame_count: int
    loop_seconds: float
    frame_builder: StreamFrameBuilder
    anchor: Vec3 | None = None
    world_size: tuple[float, float] = (1.0, 1.0)
    visible: bool = True

    def __post_init__(self) -> None:
        if self.frame_count < 1:
            raise ValueError("frame_count must be at least 1")
        if self.loop_seconds <= 0.0:
            raise ValueError("loop_seconds must be positive")
        if self.projection_policy is AnimationProjection.PERSISTENT_OVERLAY and self.anchor is None:
            raise ValueError("persistent overlays require an anchor")

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        yield WorldRenderPacket(
            kind="stream",
            points=(self.anchor,) if self.anchor is not None else (),
            animation_projection=self.projection_policy,
            line_occluder=False,
            stream_frame_count=self.frame_count,
            stream_loop_seconds=self.loop_seconds,
            stream_frame_builder=self.frame_builder,
            cache_key=self,
            world_size=self.world_size,
        )