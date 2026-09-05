from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from typing import Iterable, Sequence

from .math3d import Vec3, cross, dot, normalized, subtract
from .scene import (
    AnimatedImageMaterial,
    AnimationProjection,
    BillboardFacing,
    FieldAssociation,
    FrameContext,
    ImageMaterial,
    LineRenderLayer,
    Material3D,
    ScalarFieldMaterial,
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


def _color_has_translucent_alpha(color: object) -> bool:
    return isinstance(color, tuple) and len(color) == 4 and color[3] < 255


def _material_is_translucent(material: Material3D | ScalarFieldMaterial) -> bool:
    return material.blend_mode is not None or _color_has_translucent_alpha(material.fill)


def _oriented_away_from_opposite(
    vertices: tuple[Vec3, ...],
    face: tuple[int, int, int],
    opposite_index: int,
) -> tuple[int, int, int]:
    first, second, third = (vertices[index] for index in face)
    normal = cross(subtract(second, first), subtract(third, first))
    toward_opposite = subtract(vertices[opposite_index], first)
    if dot(normal, toward_opposite) > 0.0:
        return face[0], face[2], face[1]
    return face


@dataclass(frozen=True)
class MeshEdgeStyle:
    color: tuple[int, int, int] | tuple[int, int, int, int] | int = (24, 27, 25, 140)
    thickness: float = -1.0
    render_layer: LineRenderLayer = LineRenderLayer.WORLD


@dataclass(frozen=True)
class MeshTriangle:
    indices: tuple[int, int, int]
    source_id: int


@dataclass
class TriangleMesh3D:
    vertices: tuple[Vec3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    material: Material3D | ScalarFieldMaterial
    source_ids: tuple[int, ...] = ()
    edges: MeshEdgeStyle | None = None
    cull_back_faces: bool = True
    visible: bool = True

    def __post_init__(self) -> None:
        self.vertices = tuple(self.vertices)
        self.triangles = tuple(tuple(triangle) for triangle in self.triangles)  # type: ignore[assignment]
        if self.source_ids and len(self.source_ids) != len(self.triangles):
            raise ValueError("source_ids must contain one id per triangle")
        self._validate_indices()

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        del frame
        emitted_edges: set[tuple[int, int]] = set()
        for triangle_index, triangle in enumerate(self.triangles):
            source_id = self.source_ids[triangle_index] if self.source_ids else triangle_index
            packets = tuple(self._collect_triangle(MeshTriangle(triangle, source_id)))
            yield from packets
            if self.edges is not None and packets:
                yield from self._collect_new_edges(triangle, source_id, emitted_edges)

    def update_object(self, **changes: object) -> None:
        for name, value in changes.items():
            if name == "vertices":
                self.vertices = tuple(value)  # type: ignore[arg-type]
                self._validate_indices()
            elif name == "triangles":
                self.triangles = tuple(tuple(triangle) for triangle in value)  # type: ignore[assignment, union-attr]
                self._validate_indices()
            elif name == "source_ids":
                source_ids = tuple(value)  # type: ignore[arg-type]
                if source_ids and len(source_ids) != len(self.triangles):
                    raise ValueError("source_ids must contain one id per triangle")
                self.source_ids = source_ids
            elif name in {"material", "edges", "cull_back_faces", "visible"}:
                setattr(self, name, value)
            else:
                raise AttributeError(f"TriangleMesh3D has no field {name!r}")

    def _collect_triangle(self, triangle: MeshTriangle) -> Iterable[WorldRenderPacket]:
        if len(set(triangle.indices)) != 3:
            return
        points = tuple(self.vertices[index] for index in triangle.indices)
        normal = polygon_normal(points)
        if normal == (0.0, 0.0, 0.0):
            return
        material = self._triangle_material(triangle)
        if material is None:
            return
        yield WorldRenderPacket(
            kind="polygon",
            points=points,
            material=material,
            normal=normal,
            cull_back_face=self.cull_back_faces and not _material_is_translucent(material),
            source_id=triangle.source_id,
        )
        if _material_is_translucent(material):
            yield WorldRenderPacket(
                kind="polygon",
                points=tuple(reversed(points)),
                material=material,
                normal=(-normal[0], -normal[1], -normal[2]),
                cull_back_face=False,
                source_id=triangle.source_id,
            )
    def _collect_new_edges(
        self,
        triangle: tuple[int, int, int],
        source_id: int,
        emitted_edges: set[tuple[int, int]],
    ) -> Iterable[WorldRenderPacket]:
        assert self.edges is not None
        material = SolidMaterial(
            fill=None,
            outline=self.edges.color,
            thickness=self.edges.thickness,
            shaded=False,
            line_occluder=False,
        )
        for start_index, end_index in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge_key = tuple(sorted((start_index, end_index)))
            if edge_key in emitted_edges:
                continue
            emitted_edges.add(edge_key)
            yield WorldRenderPacket(
                kind="line",
                points=(self.vertices[start_index], self.vertices[end_index]),
                material=material,
                line_render_layer=self.edges.render_layer,
                line_occluder=False,
                source_id=source_id,
            )

    def _triangle_material(self, triangle: MeshTriangle) -> Material3D | None:
        material = self.material
        if not isinstance(material, ScalarFieldMaterial):
            return material
        value = self._field_value(material, triangle)
        if value is None:
            return None
        fill = material.color_for_value(value)
        if fill is None:
            return None
        return SolidMaterial(
            fill=fill,
            outline=material.outline,
            thickness=material.thickness,
            shaded=material.shaded,
            blend_mode=material.blend_mode,
            line_occluder=material.line_occluder,
        )

    def _field_value(self, material: ScalarFieldMaterial, triangle: MeshTriangle) -> float | None:
        if material.association is FieldAssociation.CELL:
            if triangle.source_id < 0 or triangle.source_id >= len(material.values):
                return None
            return material.values[triangle.source_id]
        values = []
        for vertex_index in triangle.indices:
            if vertex_index < 0 or vertex_index >= len(material.values):
                return None
            values.append(material.values[vertex_index])
        return sum(values) / len(values)

    def _validate_indices(self) -> None:
        for triangle in self.triangles:
            if len(triangle) != 3:
                raise ValueError("triangles must contain exactly three vertex indices")
            for vertex_index in triangle:
                if vertex_index < 0 or vertex_index >= len(self.vertices):
                    raise IndexError("triangle vertex index out of range")


@dataclass
class TetrahedralMesh3D:
    vertices: tuple[Vec3, ...]
    cells: tuple[tuple[int, int, int, int], ...]
    material: Material3D | ScalarFieldMaterial
    edges: MeshEdgeStyle | None = None
    cull_back_faces: bool = True
    visible: bool = True
    _exterior_faces: tuple[MeshTriangle, ...] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.vertices = tuple(self.vertices)
        self.cells = tuple(tuple(cell) for cell in self.cells)  # type: ignore[assignment]
        self._validate_indices()

    def collect(self, frame: FrameContext) -> Iterable[WorldRenderPacket]:
        surface = TriangleMesh3D(
            vertices=self.vertices,
            triangles=tuple(face.indices for face in self.exterior_faces()),
            material=self.material,
            source_ids=tuple(face.source_id for face in self.exterior_faces()),
            edges=self.edges,
            cull_back_faces=self.cull_back_faces,
        )
        yield from surface.collect(frame)

    def exterior_faces(self) -> tuple[MeshTriangle, ...]:
        if self._exterior_faces is None:
            self._exterior_faces = self._extract_exterior_faces()
        return self._exterior_faces

    def update_object(self, **changes: object) -> None:
        for name, value in changes.items():
            if name == "vertices":
                self.vertices = tuple(value)  # type: ignore[arg-type]
                self._validate_indices()
            elif name == "cells":
                self.cells = tuple(tuple(cell) for cell in value)  # type: ignore[assignment, union-attr]
                self._validate_indices()
                self._exterior_faces = None
            elif name in {"material", "edges", "cull_back_faces", "visible"}:
                setattr(self, name, value)
            else:
                raise AttributeError(f"TetrahedralMesh3D has no field {name!r}")

    def _extract_exterior_faces(self) -> tuple[MeshTriangle, ...]:
        occurrences: dict[tuple[int, int, int], list[tuple[int, tuple[int, int, int], int]]] = {}
        for cell_index, cell in enumerate(self.cells):
            if len(set(cell)) != 4:
                continue
            face_specs = (
                ((cell[1], cell[2], cell[3]), cell[0]),
                ((cell[0], cell[3], cell[2]), cell[1]),
                ((cell[0], cell[1], cell[3]), cell[2]),
                ((cell[0], cell[2], cell[1]), cell[3]),
            )
            for face, opposite_index in face_specs:
                key = tuple(sorted(face))
                occurrences.setdefault(key, []).append((cell_index, face, opposite_index))

        exterior: list[MeshTriangle] = []
        for matches in occurrences.values():
            if len(matches) != 1:
                continue
            cell_index, face, opposite_index = matches[0]
            oriented = _oriented_away_from_opposite(self.vertices, face, opposite_index)
            if polygon_normal(tuple(self.vertices[index] for index in oriented)) == (0.0, 0.0, 0.0):
                continue
            exterior.append(MeshTriangle(indices=oriented, source_id=cell_index))
        return tuple(exterior)

    def _validate_indices(self) -> None:
        for cell in self.cells:
            if len(cell) != 4:
                raise ValueError("cells must contain exactly four vertex indices")
            for vertex_index in cell:
                if vertex_index < 0 or vertex_index >= len(self.vertices):
                    raise IndexError("cell vertex index out of range")


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