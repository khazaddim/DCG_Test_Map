"""Irregular chambers, winding entrances, rock pillars, and a side lake.

Cross-sections define both the mesh outline and the dry-floor boundary. Water
tiles replace, rather than overlap, dry floor. Inward-facing wall/ceiling
triangles retain the first cave's clipping/cutaway behavior.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Box3D,
    Collider,
    CollisionShape2D,
    CollisionWorld,
    Line3D,
    MeshEdgeStyle,
    Scene3D,
    SolidMaterial,
    TerrainMode,
    TriangleMesh3D,
    TraversalRole,
    TraversalSettings,
    Vec3,
)


WORLD_W = 1800.0
WORLD_H = 1200.0
GRID_STEP = 12.0
AVATAR_SIZE = 8.0
AVATAR_HEIGHT = 12.0
AVATAR_START_XY = (900.0, 650.0)
COLLISION_GAP = 1.0
SECTION_STEP = 30.0
ARCH_SEGMENTS = 12
FLOOR_BANDS = 6
ROCK_ROUGHNESS = 0.07
OUTLINE_ROUGHNESS = 14.0

WALLS_ENABLED = True
CEILING_ENABLED = True
WATER_ENABLED = True
WATER_RIPPLES_ENABLED = True
PILLARS_ENABLED = True
MESH_EDGES_ENABLED = False


class CaveSection(NamedTuple):
    x: float
    lower: float
    upper: float
    height: float
    water_width: float

    @property
    def shore(self) -> float:
        return self.lower + self.water_width


# x, lower wall, upper wall, arch height, water width on the lower side.
OUTLINE_CONTROLS = (
    CaveSection(0, 120, 280, 210, 0),
    CaveSection(240, 160, 350, 230, 0),
    CaveSection(400, 210, 430, 240, 0),
    CaveSection(560, 240, 800, 310, 0),
    CaveSection(720, 300, 1000, 350, 160),
    CaveSection(900, 200, 1040, 350, 300),
    CaveSection(1100, 280, 1060, 340, 360),
    CaveSection(1280, 360, 960, 310, 360),
    CaveSection(1420, 480, 920, 290, 260),
    CaveSection(1600, 680, 990, 250, 160),
    CaveSection(1800, 820, 1060, 230, 120),
)

FLOOR_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((92, 85, 73), (97, 89, 76), (88, 82, 72), (94, 87, 77))
)
WATER_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((38, 66, 68), (28, 53, 59), (22, 43, 51))
)
WALL_MATERIAL = SolidMaterial(fill=(138, 126, 109), outline=None, shaded=True)
CEILING_MATERIAL = SolidMaterial(fill=(112, 106, 99), outline=None, shaded=True)
PILLAR_MATERIAL = SolidMaterial(fill=(124, 113, 95), outline=None, shaded=True)
AVATAR_MATERIAL = SolidMaterial(fill=(244, 190, 65), outline=(49, 35, 24), shaded=True)
ROCK_EDGES = MeshEdgeStyle(color=(47, 43, 39), thickness=-1.0)
RIPPLE_COLOR = (62, 88, 89)
PILLAR_SPECS = (
    (625.0, 480.0, 36.0, 140.0),
    (825.0, 650.0, 48.0, 185.0),
    (1130.0, 760.0, 42.0, 155.0),
    (1380.0, 810.0, 28.0, 110.0),
)


def effective_world_flags() -> dict[str, bool]:
    return {
        "WALLS_ENABLED": WALLS_ENABLED,
        "CEILING_ENABLED": CEILING_ENABLED,
        "WATER_ENABLED": WATER_ENABLED,
        "WATER_RIPPLES_ENABLED": WATER_ENABLED and WATER_RIPPLES_ENABLED,
        "PILLARS_ENABLED": PILLARS_ENABLED,
        "MESH_EDGES_ENABLED": MESH_EDGES_ENABLED and (WALLS_ENABLED or CEILING_ENABLED or PILLARS_ENABLED),
    }


def create_road_texture(context: dcg.Context) -> None:
    del context


def cave_sections() -> tuple[CaveSection, ...]:
    if SECTION_STEP <= 0 or ARCH_SEGMENTS < 4 or FLOOR_BANDS < 1:
        raise ValueError("Cave needs a positive section step, four arch segments, and one floor band")
    if not 0 <= ROCK_ROUGHNESS <= 0.2 or OUTLINE_ROUGHNESS < 0:
        raise ValueError("Invalid cave roughness")
    if len(OUTLINE_CONTROLS) < 2 or OUTLINE_CONTROLS[0].x != 0 or OUTLINE_CONTROLS[-1].x != WORLD_W:
        raise ValueError("Outline controls must span the world width")
    sections = []
    for first, second in zip(OUTLINE_CONTROLS, OUTLINE_CONTROLS[1:]):
        if second.x <= first.x:
            raise ValueError("Outline control x coordinates must increase")
        steps = math.ceil((second.x - first.x) / SECTION_STEP)
        for index in range(steps):
            t = index / steps
            x = first.x + (second.x - first.x) * t
            jitter = OUTLINE_ROUGHNESS * math.sin(math.pi * t)
            lower = first.lower + (second.lower - first.lower) * t + jitter * math.sin(x * 0.071)
            upper = first.upper + (second.upper - first.upper) * t + jitter * math.cos(x * 0.053)
            height = first.height + (second.height - first.height) * t
            water = (first.water_width + (second.water_width - first.water_width) * t) if WATER_ENABLED else 0.0
            sections.append(CaveSection(x, lower, upper, height, water))
    last = OUTLINE_CONTROLS[-1]
    sections.append(last if WATER_ENABLED else last._replace(water_width=0.0))
    for section in sections:
        if not (0 < section.lower <= section.shore < section.upper < WORLD_H):
            raise ValueError("Outline must contain dry floor and stay inside world bounds")
        if section.water_width < 0 or section.height <= AVATAR_HEIGHT:
            raise ValueError("Invalid water width or cave headroom")
    return tuple(sections)


def cave_rings(sections: tuple[CaveSection, ...]) -> tuple[tuple[Vec3, ...], ...]:
    rings = []
    for station, section in enumerate(sections):
        center = (section.lower + section.upper) * 0.5
        radius = (section.upper - section.lower) * 0.5
        ring = []
        for arc in range(ARCH_SEGMENTS + 1):
            if arc in (0, ARCH_SEGMENTS):
                ring.append((section.x, section.lower if arc == 0 else section.upper, 0.0))
                continue
            angle = math.pi * arc / ARCH_SEGMENTS
            roughness = ROCK_ROUGHNESS * (
                0.65 * math.sin(station * 1.73 + arc * 2.31)
                + 0.35 * math.cos(station * 0.63 - arc * 1.19)
            )
            ring.append((
                section.x,
                center - radius * math.cos(angle) * (1 + roughness),
                section.height * math.sin(angle) * (1 + roughness),
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


def add_pillar(scene: Scene3D, x: float, y: float, radius: float, height: float) -> None:
    segments = 9
    vertices = []
    for level in (0, 1):
        for index in range(segments):
            angle = math.tau * index / segments
            width = radius * (1 + 0.12 * math.sin(index * 2.17)) * (1 - level * 0.22)
            z = 0.2 + level * height * (1 + 0.04 * math.sin(index * 1.83))
            vertices.append((x + width * math.cos(angle), y + width * math.sin(angle), z))
    crown = len(vertices)
    vertices.append((x, y, height + 8.2))
    triangles = []
    for index in range(segments):
        next_index = (index + 1) % segments
        triangles.extend(((index, next_index, segments + next_index),
                          (index, segments + next_index, segments + index),
                          (segments + index, segments + next_index, crown)))
    scene.add(TriangleMesh3D(
        vertices=tuple(vertices), triangles=tuple(triangles), material=PILLAR_MATERIAL,
        edges=ROCK_EDGES if MESH_EDGES_ENABLED else None,
    ))


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    del road_texture
    sections = cave_sections()
    rings = cave_rings(sections)
    scene = Scene3D()
    for station, (first, second) in enumerate(zip(sections, sections[1:])):
        for band in range(FLOOR_BANDS):
            start, end = band / FLOOR_BANDS, (band + 1) / FLOOR_BANDS
            add_flat_patch(scene, (
                (first.x, first.shore + (first.upper - first.shore) * start, 0),
                (second.x, second.shore + (second.upper - second.shore) * start, 0),
                (second.x, second.shore + (second.upper - second.shore) * end, 0),
                (first.x, first.shore + (first.upper - first.shore) * end, 0),
            ), FLOOR_MATERIALS[(station * 7 + band * 3) % len(FLOOR_MATERIALS)])
        if WATER_ENABLED and (first.water_width > 0 or second.water_width > 0):
            for band in range(len(WATER_MATERIALS)):
                start, end = band / len(WATER_MATERIALS), (band + 1) / len(WATER_MATERIALS)
                add_flat_patch(scene, (
                    (first.x, first.lower + first.water_width * start, 0),
                    (second.x, second.lower + second.water_width * start, 0),
                    (second.x, second.lower + second.water_width * end, 0),
                    (first.x, first.lower + first.water_width * end, 0),
                ), WATER_MATERIALS[-1 - band])
            if WATER_RIPPLES_ENABLED and min(first.water_width, second.water_width) > 30:
                for fraction in (0.25, 0.55, 0.8):
                    scene.add(Line3D(
                        start=(
                            first.x + (second.x - first.x) * 0.25,
                            first.lower * 0.75 + second.lower * 0.25
                            + (first.water_width * 0.75 + second.water_width * 0.25) * fraction,
                            0.15,
                        ),
                        end=(
                            first.x + (second.x - first.x) * 0.65,
                            first.lower * 0.35 + second.lower * 0.65
                            + (first.water_width * 0.35 + second.water_width * 0.65) * fraction,
                            0.15,
                        ),
                        color=RIPPLE_COLOR, thickness=-1.0,
                    ))
        for arc in range(ARCH_SEGMENTS):
            ceiling = ARCH_SEGMENTS / 3 <= arc < ARCH_SEGMENTS * 2 / 3
            if not (CEILING_ENABLED if ceiling else WALLS_ENABLED):
                continue
            scene.add(TriangleMesh3D(
                vertices=(rings[station][arc], rings[station + 1][arc],
                          rings[station + 1][arc + 1], rings[station][arc + 1]),
                triangles=((0, 2, 1), (0, 3, 2)),
                material=CEILING_MATERIAL if ceiling else WALL_MATERIAL,
                edges=ROCK_EDGES if MESH_EDGES_ENABLED else None,
            ))
    if PILLARS_ENABLED:
        for spec in PILLAR_SPECS:
            add_pillar(scene, *spec)
    avatar = Box3D(center=(*AVATAR_START_XY, 0), size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT), material=AVATAR_MATERIAL)
    scene.add(avatar)
    return scene, avatar


class CaveCollisionWorld(CollisionWorld):
    """Exact AABB containment against piecewise-linear, x-monotone floor edges."""

    def __init__(self, sections: tuple[CaveSection, ...]) -> None:
        super().__init__(gap=COLLISION_GAP)
        self.sections = sections
        self.boundary = Collider("cave floor / shoreline", AabbFootprint(0, 0, WORLD_W, WORLD_H), TraversalRole.BOUNDARY)

    def first_blocker(self, candidate: CollisionShape2D, *, ignore: object | None = None) -> Collider | None:
        if not isinstance(candidate, AabbFootprint):
            raise TypeError("Cave movement requires an AABB player footprint")
        left, right = candidate.min_x - self.gap, candidate.max_x + self.gap
        if left < self.sections[0].x or right > self.sections[-1].x:
            return self.boundary
        # Check every section inside the footprint, not only its four corners:
        # a narrow concave notch can enter the footprint between those corners.
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


def build_collision_world() -> CaveCollisionWorld:
    collisions = CaveCollisionWorld(cave_sections())
    if PILLARS_ENABLED:
        for index, (x, y, radius, _height) in enumerate(PILLAR_SPECS):
            width = radius * 2 * 1.12
            collisions.add(f"rock pillar {index + 1}", AabbFootprint.from_center(x, y, width, width))
    return collisions


def build_terrain_surface() -> None:
    return None


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(mode=TerrainMode.FLAT, fallback_ground_z=0.0)
