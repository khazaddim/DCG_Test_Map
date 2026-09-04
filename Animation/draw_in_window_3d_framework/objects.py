from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .math3d import Vec3, cross, normalized, subtract
from .scene import FrameContext, Material3D, SolidMaterial, WorldRenderPacket


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
    visible: bool = True

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        yield WorldRenderPacket(
            kind="line",
            points=(self.start, self.end),
            material=SolidMaterial(fill=None, outline=self.color, thickness=self.thickness, shaded=False),
        )


@dataclass
class Polyline3D:
    points: tuple[Vec3, ...]
    color: tuple[int, int, int] | tuple[int, int, int, int] | int
    thickness: float = -1.0
    closed: bool = False
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