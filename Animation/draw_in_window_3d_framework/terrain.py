from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence, runtime_checkable

from .math3d import Vec3, cross, dot, normalized, subtract


@dataclass(frozen=True)
class TerrainSample:
    position: Vec3
    normal: Vec3 | None = None
    source_id: int | None = None

    @property
    def height(self) -> float:
        return self.position[2]


@runtime_checkable
class TerrainSurface(Protocol):
    def sample(self, x: float, y: float) -> TerrainSample | None:
        ...

    def intersect_ray(self, origin: Vec3, direction: Vec3) -> TerrainSample | None:
        ...


@dataclass(frozen=True)
class _CompiledTerrainTriangle:
    vertices: tuple[Vec3, Vec3, Vec3]
    normal: Vec3
    source_id: int | None
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    projected_denominator: float


@dataclass
class MeshTerrainSurface:
    vertices: tuple[Vec3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    source_ids: tuple[int, ...] = ()
    _compiled_triangles: tuple[_CompiledTerrainTriangle, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.vertices = tuple(self.vertices)
        self.triangles = tuple(tuple(triangle) for triangle in self.triangles)  # type: ignore[assignment]
        if self.source_ids and len(self.source_ids) != len(self.triangles):
            raise ValueError("source_ids must contain one id per triangle")
        self._compiled_triangles = self._compile_triangles()

    @classmethod
    def from_triangle_mesh(cls, mesh: object) -> MeshTerrainSurface:
        vertices = getattr(mesh, "vertices")
        triangles = getattr(mesh, "triangles")
        source_ids = getattr(mesh, "source_ids", ())
        return cls(vertices=vertices, triangles=triangles, source_ids=source_ids)

    def sample(self, x: float, y: float) -> TerrainSample | None:
        best_sample: TerrainSample | None = None
        for triangle in self._compiled_triangles:
            if x < triangle.min_x or x > triangle.max_x or y < triangle.min_y or y > triangle.max_y:
                continue
            weights = _barycentric_xy((x, y), triangle.vertices, triangle.projected_denominator)
            if weights is None:
                continue
            z = sum(weight * vertex[2] for weight, vertex in zip(weights, triangle.vertices))
            sample = TerrainSample(position=(x, y, z), normal=triangle.normal, source_id=triangle.source_id)
            if best_sample is None or sample.height > best_sample.height:
                best_sample = sample
        return best_sample

    def intersect_ray(self, origin: Vec3, direction: Vec3) -> TerrainSample | None:
        best_distance: float | None = None
        best_sample: TerrainSample | None = None
        for triangle in self._compiled_triangles:
            hit_distance = _ray_triangle_distance(origin, direction, triangle.vertices)
            if hit_distance is None:
                continue
            if best_distance is None or hit_distance < best_distance:
                best_distance = hit_distance
                best_sample = TerrainSample(
                    position=(
                        origin[0] + direction[0] * hit_distance,
                        origin[1] + direction[1] * hit_distance,
                        origin[2] + direction[2] * hit_distance,
                    ),
                    normal=triangle.normal,
                    source_id=triangle.source_id,
                )
        return best_sample

    def _compile_triangles(self) -> tuple[_CompiledTerrainTriangle, ...]:
        compiled: list[_CompiledTerrainTriangle] = []
        for triangle_index, triangle in enumerate(self.triangles):
            if len(triangle) != 3 or len(set(triangle)) != 3:
                continue
            vertices = tuple(self.vertices[index] for index in triangle)
            denominator = _projected_denominator(vertices)
            if abs(denominator) <= 1e-8:
                continue
            normal = normalized(cross(subtract(vertices[1], vertices[0]), subtract(vertices[2], vertices[0])))
            if normal == (0.0, 0.0, 0.0) or abs(normal[2]) <= 1e-8:
                continue
            if normal[2] < 0.0:
                normal = (-normal[0], -normal[1], -normal[2])
            source_id = self.source_ids[triangle_index] if self.source_ids else triangle_index
            xs = tuple(vertex[0] for vertex in vertices)
            ys = tuple(vertex[1] for vertex in vertices)
            compiled.append(
                _CompiledTerrainTriangle(
                    vertices=vertices,
                    normal=normal,
                    source_id=source_id,
                    min_x=min(xs),
                    max_x=max(xs),
                    min_y=min(ys),
                    max_y=max(ys),
                    projected_denominator=denominator,
                )
            )
        return tuple(compiled)


def _projected_denominator(vertices: Sequence[Vec3]) -> float:
    v0, v1, v2 = vertices
    return (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])


def _barycentric_xy(
    point: tuple[float, float],
    vertices: Sequence[Vec3],
    denominator: float,
) -> tuple[float, float, float] | None:
    if abs(denominator) <= 1e-8:
        return None
    v0, v1, v2 = vertices
    weight0 = ((v1[1] - v2[1]) * (point[0] - v2[0]) + (v2[0] - v1[0]) * (point[1] - v2[1])) / denominator
    weight1 = ((v2[1] - v0[1]) * (point[0] - v2[0]) + (v0[0] - v2[0]) * (point[1] - v2[1])) / denominator
    weight2 = 1.0 - weight0 - weight1
    epsilon = 1e-7
    if weight0 < -epsilon or weight1 < -epsilon or weight2 < -epsilon:
        return None
    return weight0, weight1, weight2


def _ray_triangle_distance(origin: Vec3, direction: Vec3, vertices: Sequence[Vec3]) -> float | None:
    edge0 = subtract(vertices[1], vertices[0])
    edge1 = subtract(vertices[2], vertices[0])
    cross_direction = cross(direction, edge1)
    determinant = dot(edge0, cross_direction)
    if abs(determinant) <= 1e-8:
        return None
    inverse_determinant = 1.0 / determinant
    offset = subtract(origin, vertices[0])
    u = dot(offset, cross_direction) * inverse_determinant
    if u < -1e-7 or u > 1.0 + 1e-7:
        return None
    cross_offset = cross(offset, edge0)
    v = dot(direction, cross_offset) * inverse_determinant
    if v < -1e-7 or u + v > 1.0 + 1e-7:
        return None
    distance = dot(edge1, cross_offset) * inverse_determinant
    if distance < 1e-7:
        return None
    return distance