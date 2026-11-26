"""Stateless mesh and floor-boundary helpers shared by authored cave worlds."""

from __future__ import annotations

import math
from typing import NamedTuple

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Collider, CollisionShape2D, CollisionWorld, MeshEdgeStyle, Scene3D,
    SolidMaterial, TriangleMesh3D, TraversalRole, Vec3,
)


class CaveSection(NamedTuple):
    x: float
    lower: float
    upper: float
    height: float
    water_width: float

    @property
    def shore(self) -> float:
        return self.lower + self.water_width


def generate_sections(
    controls: tuple[CaveSection, ...], *, world_width: float, world_height: float,
    step: float, outline_roughness: float, avatar_height: float, water_enabled: bool,
) -> tuple[CaveSection, ...]:
    if step <= 0 or outline_roughness < 0:
        raise ValueError("Invalid cave section step or outline roughness")
    if len(controls) < 2 or controls[0].x != 0 or controls[-1].x != world_width:
        raise ValueError("Outline controls must span the world width")
    sections = []
    for first, second in zip(controls, controls[1:]):
        if second.x <= first.x:
            raise ValueError("Outline control x coordinates must increase")
        steps = math.ceil((second.x - first.x) / step)
        for index in range(steps):
            t = index / steps
            x = first.x + (second.x - first.x) * t
            jitter = outline_roughness * math.sin(math.pi * t)
            lower = first.lower + (second.lower - first.lower) * t + jitter * math.sin(x * 0.071)
            upper = first.upper + (second.upper - first.upper) * t + jitter * math.cos(x * 0.053)
            height = first.height + (second.height - first.height) * t
            water = (first.water_width + (second.water_width - first.water_width) * t) if water_enabled else 0.0
            sections.append(CaveSection(x, lower, upper, height, water))
    last = controls[-1]
    sections.append(last if water_enabled else last._replace(water_width=0.0))
    for section in sections:
        if not (0 < section.lower <= section.shore < section.upper < world_height):
            raise ValueError("Outline must contain dry floor and stay inside world bounds")
        if section.water_width < 0 or section.height <= avatar_height:
            raise ValueError("Invalid water width or cave headroom")
    return tuple(sections)


def generate_rings(
    sections: tuple[CaveSection, ...], *, arch_segments: int, roughness: float,
) -> tuple[tuple[Vec3, ...], ...]:
    if arch_segments < 4 or not 0 <= roughness <= 0.2:
        raise ValueError("Invalid arch tessellation or rock roughness")
    rings = []
    for station, section in enumerate(sections):
        center = (section.lower + section.upper) * 0.5
        radius = (section.upper - section.lower) * 0.5
        ring = []
        for arc in range(arch_segments + 1):
            if arc in (0, arch_segments):
                ring.append((section.x, section.lower if arc == 0 else section.upper, 0.0))
                continue
            angle = math.pi * arc / arch_segments
            jitter = roughness * (
                0.65 * math.sin(station * 1.73 + arc * 2.31)
                + 0.35 * math.cos(station * 0.63 - arc * 1.19)
            )
            ring.append((
                section.x,
                center - radius * math.cos(angle) * (1 + jitter),
                section.height * math.sin(angle) * (1 + jitter),
            ))
        rings.append(tuple(ring))
    return tuple(rings)


def add_flat_patch(scene: Scene3D, points: tuple[Vec3, Vec3, Vec3, Vec3], material: SolidMaterial) -> None:
    triangles = tuple(
        triangle for triangle in ((0, 1, 2), (0, 2, 3))
        if len({points[index] for index in triangle}) == 3
    )
    if triangles:
        scene.add(TriangleMesh3D(vertices=points, triangles=triangles, material=material, cull_back_faces=False))


def faceted_prop_mesh(
    x: float, y: float, levels: tuple[tuple[float, float], ...], material: SolidMaterial,
    *, edges: MeshEdgeStyle | None = None,
) -> TriangleMesh3D:
    """Closed octagonal frustum or pointed shard, with outward winding."""
    if len(levels) < 2 or any(b[0] <= a[0] for a, b in zip(levels, levels[1:])):
        raise ValueError("Prop levels must have increasing heights")
    if any(not math.isfinite(v) for level in levels for v in level) or any(r < 0 for _, r in levels):
        raise ValueError("Prop levels must be finite with nonnegative radii")
    if any(r == 0 for _, r in levels[1:-1]) or all(r == 0 for _, r in levels):
        raise ValueError("Only prop endpoints may be tips")
    vertices, rings, triangles = [], [], []
    for z, radius in levels:
        start = len(vertices)
        if radius == 0:
            vertices.append((x, y, z))
            rings.append((start,))
        else:
            vertices.extend(
                (x + radius * math.cos(math.tau * i / 8),
                 y + radius * math.sin(math.tau * i / 8), z) for i in range(8)
            )
            rings.append(tuple(range(start, start + 8)))
    for first, second in zip(rings, rings[1:]):
        for i in range(8):
            j = (i + 1) % 8
            if len(first) == 1:
                triangles.append((first[0], second[j], second[i]))
            elif len(second) == 1:
                triangles.append((first[i], first[j], second[0]))
            else:
                triangles.extend(((first[i], first[j], second[j]), (first[i], second[j], second[i])))
    for ring, reverse in ((rings[0], True), (rings[-1], False)):
        if len(ring) > 1:
            for i in range(1, 7):
                triangles.append((ring[0], ring[i + 1], ring[i]) if reverse else (ring[0], ring[i], ring[i + 1]))
    return TriangleMesh3D(
        vertices=tuple(vertices), triangles=tuple(triangles), material=material, edges=edges,
    )


class CaveCollisionWorld(CollisionWorld):
    """Exact AABB containment against piecewise-linear, x-monotone floor edges."""

    def __init__(
        self, sections: tuple[CaveSection, ...], *, gap: float = 1.0,
        world_bounds: AabbFootprint | None = None,
    ) -> None:
        super().__init__(gap=gap)
        if len(sections) < 2 or any(b.x <= a.x for a, b in zip(sections, sections[1:])):
            raise ValueError("Collision sections must have increasing x coordinates")
        self.sections = sections
        bounds = world_bounds if world_bounds is not None else AabbFootprint(
            sections[0].x, min(s.lower for s in sections), sections[-1].x, max(s.upper for s in sections),
        )
        self.boundary = Collider("cave floor / shoreline", bounds, TraversalRole.BOUNDARY)

    def first_blocker(self, candidate: CollisionShape2D, *, ignore: object | None = None) -> Collider | None:
        if not isinstance(candidate, AabbFootprint):
            raise TypeError("Cave movement requires an AABB player footprint")
        left, right = candidate.min_x - self.gap, candidate.max_x + self.gap
        if left < self.sections[0].x or right > self.sections[-1].x:
            return self.boundary
        # Check every section inside the footprint: a concave notch can enter
        # between the corners even when all four corners are inside.
        for first, second in zip(self.sections, self.sections[1:]):
            x0, x1 = max(left, first.x), min(right, second.x)
            if x0 > x1:
                continue
            for x in (x0, x1):
                t = (x - first.x) / (second.x - first.x)
                shore = first.shore + (second.shore - first.shore) * t
                upper = first.upper + (second.upper - first.upper) * t
                if candidate.min_y - self.gap < shore or candidate.max_y + self.gap > upper:
                    return self.boundary
        return super().first_blocker(candidate, ignore=ignore)
