"""Violet crystal caverns with cyan floor veins and floating luminous gems.

Brightness is authored with solid colors, not bloom or dynamic lights. The
floor stays flat and walkable; crystal clusters block movement, floating gems
do not. This is a separate world from the natural cave and its side lake.
"""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Box3D, MeshEdgeStyle, Scene3D, SolidMaterial,
    TerrainMode, TriangleMesh3D, TraversalSettings, Vec3,
)
from Animation.ported_demos.cave_geometry import (
    CaveCollisionWorld, CaveSection, add_flat_patch, generate_rings, generate_sections,
)


WORLD_W = 1800.0
WORLD_H = 1200.0
GRID_STEP = 12.0
AVATAR_SIZE = 8.0
AVATAR_HEIGHT = 12.0
AVATAR_START_XY = (900.0, 600.0)
COLLISION_GAP = 1.0
SECTION_STEP = 24.0
ARCH_SEGMENTS = 14
FLOOR_BANDS = 10
ROCK_ROUGHNESS = 0.11
OUTLINE_ROUGHNESS = 22.0

WALLS_ENABLED = True
CEILING_ENABLED = True
CRYSTALS_ENABLED = True
FLOATING_GEMS_ENABLED = True
FLOOR_VEINS_ENABLED = True
MESH_EDGES_ENABLED = False

OUTLINE_CONTROLS = (
    CaveSection(0, 280, 500, 260, 0),
    CaveSection(180, 160, 700, 300, 0),
    CaveSection(360, 300, 980, 350, 0),
    CaveSection(540, 540, 1020, 310, 0),
    CaveSection(720, 200, 940, 360, 0),
    CaveSection(900, 160, 980, 380, 0),
    CaveSection(1080, 420, 1080, 340, 0),
    CaveSection(1260, 200, 900, 350, 0),
    CaveSection(1440, 140, 560, 300, 0),
    CaveSection(1620, 340, 850, 320, 0),
    CaveSection(1800, 740, 1060, 280, 0),
)

BACKGROUND_COLOR = (12, 6, 38)
FLOOR_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((76, 42, 163), (87, 46, 179), (69, 39, 150), (96, 48, 189))
)
VEIN_MATERIAL = SolidMaterial(fill=(42, 159, 207), outline=None, shaded=False)
WALL_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=True)
    for color in ((141, 74, 226), (118, 58, 208), (161, 85, 237))
)
CEILING_MATERIAL = SolidMaterial(fill=(100, 53, 183), outline=None, shaded=True)
CRYSTAL_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=True)
    for color in ((102, 234, 255), (139, 111, 255), (210, 113, 255), (68, 202, 249), (177, 152, 255))
)
GEM_TOP_MATERIAL = SolidMaterial(fill=(166, 255, 255), outline=None, shaded=False)
GEM_BOTTOM_MATERIAL = SolidMaterial(fill=(42, 177, 229), outline=None, shaded=False)
AVATAR_MATERIAL = SolidMaterial(fill=(255, 204, 82), outline=(58, 23, 79), shaded=True)
CRYSTAL_EDGES = MeshEdgeStyle(color=(80, 39, 155), thickness=-1.0)

# x, y, tallest crystal height; each cluster has one central and four side shards.
CRYSTAL_SPECS = (
    (180.0, 240.0, 85.0), (360.0, 850.0, 105.0),
    (540.0, 640.0, 95.0), (720.0, 350.0, 110.0),
    (900.0, 880.0, 115.0), (1080.0, 800.0, 100.0),
    (1260.0, 340.0, 105.0), (1440.0, 450.0, 90.0),
    (1620.0, 660.0, 100.0), (1740.0, 790.0, 85.0),
)
FLOATING_GEM_POSITIONS = (
    (250.0, 500.0, 55.0), (650.0, 650.0, 60.0), (930.0, 550.0, 55.0),
    (1220.0, 630.0, 65.0), (1550.0, 500.0, 55.0),
)


def effective_world_flags() -> dict[str, bool]:
    return {
        "WALLS_ENABLED": WALLS_ENABLED,
        "CEILING_ENABLED": CEILING_ENABLED,
        "CRYSTALS_ENABLED": CRYSTALS_ENABLED,
        "FLOATING_GEMS_ENABLED": FLOATING_GEMS_ENABLED,
        "FLOOR_VEINS_ENABLED": FLOOR_VEINS_ENABLED,
        "MESH_EDGES_ENABLED": MESH_EDGES_ENABLED and (WALLS_ENABLED or CEILING_ENABLED or CRYSTALS_ENABLED),
    }


def create_road_texture(context: dcg.Context) -> None:
    del context


def cave_sections() -> tuple[CaveSection, ...]:
    if FLOOR_BANDS < 1 or ARCH_SEGMENTS < 4 or not 0 <= ROCK_ROUGHNESS <= 0.2:
        raise ValueError("Invalid trippy cave tessellation or roughness")
    return generate_sections(
        OUTLINE_CONTROLS, world_width=WORLD_W, world_height=WORLD_H,
        step=SECTION_STEP, outline_roughness=OUTLINE_ROUGHNESS,
        avatar_height=AVATAR_HEIGHT, water_enabled=False,
    )


def crystal_geometry(
    x: float, y: float, radius: float, height: float, lean: tuple[float, float],
) -> tuple[tuple[Vec3, ...], tuple[tuple[int, int, int], ...]]:
    segments = 6
    vertices = []
    for level in (0, 1):
        for index in range(segments):
            angle = math.tau * index / segments
            width = radius * (1 - level * 0.22)
            vertices.append((
                x + width * math.cos(angle) + lean[0] * level * 0.65,
                y + width * math.sin(angle) + lean[1] * level * 0.65,
                0.2 + level * height * 0.68,
            ))
    tip = len(vertices)
    vertices.append((x + lean[0], y + lean[1], height + 0.2))
    triangles = []
    for index in range(segments):
        next_index = (index + 1) % segments
        triangles.extend(((index, next_index, segments + next_index),
                          (index, segments + next_index, segments + index),
                          (segments + index, segments + next_index, tip)))
    return tuple(vertices), tuple(triangles)


def crystal_cluster(x: float, y: float, height: float) -> tuple[TriangleMesh3D, ...]:
    if height <= AVATAR_HEIGHT:
        raise ValueError("Crystal height must exceed avatar height")
    meshes = []
    for shard in range(5):
        angle = math.tau * (shard - 1) / 4
        offset = 0.0 if shard == 0 else 34.0
        lean = (0.0, 0.0) if shard == 0 else (7 * math.cos(angle), 7 * math.sin(angle))
        vertices, triangles = crystal_geometry(
            x + offset * math.cos(angle), y + offset * math.sin(angle),
            15.0 if shard == 0 else 9.0,
            height if shard == 0 else height * (0.5 + 0.05 * shard), lean,
        )
        meshes.append(TriangleMesh3D(
            vertices=vertices, triangles=triangles, material=CRYSTAL_MATERIALS[shard],
            edges=CRYSTAL_EDGES if MESH_EDGES_ENABLED else None,
        ))
    return tuple(meshes)


def cluster_footprint(meshes: tuple[TriangleMesh3D, ...]) -> AabbFootprint:
    points = [point for mesh in meshes for point in mesh.vertices]
    return AabbFootprint(
        min(p[0] for p in points), min(p[1] for p in points),
        max(p[0] for p in points), max(p[1] for p in points),
    )


def add_floating_gem(scene: Scene3D, position: Vec3) -> None:
    x, y, z = position
    radius = 10.0
    vertices = ((x, y, z - radius), (x + radius, y, z), (x, y + radius, z),
                (x - radius, y, z), (x, y - radius, z), (x, y, z + radius))
    scene.add(TriangleMesh3D(
        vertices=vertices, triangles=((0, 2, 1), (0, 3, 2), (0, 4, 3), (0, 1, 4)),
        material=GEM_BOTTOM_MATERIAL,
    ))
    scene.add(TriangleMesh3D(
        vertices=vertices, triangles=((5, 1, 2), (5, 2, 3), (5, 3, 4), (5, 4, 1)),
        material=GEM_TOP_MATERIAL,
    ))


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    del road_texture
    sections = cave_sections()
    rings = generate_rings(sections, arch_segments=ARCH_SEGMENTS, roughness=ROCK_ROUGHNESS)
    scene = Scene3D(background=BACKGROUND_COLOR)
    for station, (first, second) in enumerate(zip(sections, sections[1:])):
        vein_band = int((0.5 + 0.3 * math.sin(station * 0.37)) * FLOOR_BANDS)
        for band in range(FLOOR_BANDS):
            start, end = band / FLOOR_BANDS, (band + 1) / FLOOR_BANDS
            material = (
                VEIN_MATERIAL if FLOOR_VEINS_ENABLED and band == vein_band
                else FLOOR_MATERIALS[(station * 7 + band * 3) % len(FLOOR_MATERIALS)]
            )
            add_flat_patch(scene, (
                (first.x, first.lower + (first.upper - first.lower) * start, 0),
                (second.x, second.lower + (second.upper - second.lower) * start, 0),
                (second.x, second.lower + (second.upper - second.lower) * end, 0),
                (first.x, first.lower + (first.upper - first.lower) * end, 0),
            ), material)
        for arc in range(ARCH_SEGMENTS):
            ceiling = ARCH_SEGMENTS / 3 <= arc < ARCH_SEGMENTS * 2 / 3
            if not (CEILING_ENABLED if ceiling else WALLS_ENABLED):
                continue
            scene.add(TriangleMesh3D(
                vertices=(rings[station][arc], rings[station + 1][arc],
                          rings[station + 1][arc + 1], rings[station][arc + 1]),
                triangles=((0, 2, 1), (0, 3, 2)),
                material=CEILING_MATERIAL if ceiling else WALL_MATERIALS[(station + arc) % len(WALL_MATERIALS)],
                edges=CRYSTAL_EDGES if MESH_EDGES_ENABLED else None,
            ))
    if CRYSTALS_ENABLED:
        for spec in CRYSTAL_SPECS:
            for mesh in crystal_cluster(*spec):
                scene.add(mesh)
    if FLOATING_GEMS_ENABLED:
        for position in FLOATING_GEM_POSITIONS:
            add_floating_gem(scene, position)
    avatar = Box3D(center=(*AVATAR_START_XY, 0), size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT), material=AVATAR_MATERIAL)
    scene.add(avatar)
    return scene, avatar


def build_collision_world() -> CaveCollisionWorld:
    collisions = CaveCollisionWorld(
        cave_sections(), gap=COLLISION_GAP, world_bounds=AabbFootprint(0, 0, WORLD_W, WORLD_H),
    )
    if CRYSTALS_ENABLED:
        for index, spec in enumerate(CRYSTAL_SPECS):
            footprint = cluster_footprint(crystal_cluster(*spec))
            if collisions.first_blocker(footprint) is not None:
                raise ValueError(f"Crystal cluster {index + 1} overlaps the cave boundary or another cluster")
            collisions.add(f"crystal cluster {index + 1}", footprint)
    spawn = AabbFootprint.from_center(*AVATAR_START_XY, AVATAR_SIZE, AVATAR_SIZE)
    if collisions.first_blocker(spawn) is not None:
        raise ValueError("Player start must be on unobstructed cave floor")
    return collisions


def build_terrain_surface() -> None:
    return None


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(mode=TerrainMode.FLAT, fallback_ground_z=0.0)
