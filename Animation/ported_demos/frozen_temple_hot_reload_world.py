"""An original icebound sanctuary with a vaulted hall and a walkable frozen floor.

Warm floor tiles and flames use static colors, not dynamic lighting. All props,
collision proxies, and comparison switches belong to this reloadable world.
"""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Box3D, MeshEdgeStyle, MeshTerrainSurface, Scene3D,
    SolidMaterial, TerrainMode, TriangleMesh3D, TraversalSettings, Vec3,
)
from Animation.ported_demos.cave_geometry import (
    CaveCollisionWorld, CaveSection, add_flat_patch, faceted_prop_mesh, generate_sections,
)


WORLD_W = 1800.0
WORLD_H = 1200.0
GRID_STEP = 12.0
AVATAR_SIZE = 8.0
AVATAR_HEIGHT = 12.0
AVATAR_START_XY = (840.0, 600.0)
COLLISION_GAP = 1.0
SECTION_STEP = 48.0
FLOOR_BANDS = 18
ARCH_SEGMENTS = 16
WALL_HEIGHT = 300.0
ROOF_RISE = 240.0
ROOF_ROUGHNESS = 0.04

WALLS_ENABLED = True
CEILING_ENABLED = True
PILLARS_ENABLED = True
SHRINE_ENABLED = True
BRAZIERS_ENABLED = True
ICICLES_ENABLED = True
RUBBLE_ENABLED = True
FLOOR_CRACKS_ENABLED = True
MESH_EDGES_ENABLED = False

OUTLINE_CONTROLS = (
    CaveSection(0, 160, 1040, 540, 0),
    CaveSection(1800, 160, 1040, 540, 0),
)
PILLAR_POSITIONS = tuple(
    (float(x), float(y)) for x in (240, 480, 720, 1080, 1320, 1560) for y in (300, 900)
)
BRAZIER_POSITIONS = tuple(
    (float(x), float(y)) for x in (360, 900, 1440) for y in (420, 780)
)
RUBBLE_SPECS = ((420.0, 660.0, 20.0, 16.0), (1260.0, 510.0, 24.0, 20.0),
                (600.0, 960.0, 18.0, 24.0), (1500.0, 240.0, 22.0, 18.0))
SHRINE_XY = (960.0, 600.0)
ICICLE_POSITIONS = tuple(
    (float(x), float(y)) for x in (300, 600, 900, 1200, 1500) for y in (380, 600, 820)
)

BACKGROUND_COLOR = (8, 20, 36)
FLOOR_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((111, 159, 185), (126, 176, 199), (143, 190, 211), (101, 146, 175))
)
WARM_FLOOR_MATERIAL = SolidMaterial(fill=(195, 188, 153), outline=None, shaded=False)
CRACK_MATERIAL = SolidMaterial(fill=(44, 94, 125), outline=None, shaded=False)
WALL_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None)
    for color in ((73, 110, 143), (90, 133, 163), (107, 150, 178))
)
CEILING_MATERIAL = SolidMaterial(fill=(99, 153, 185), outline=None)
STONE_MATERIAL = SolidMaterial(fill=(107, 143, 165), outline=None)
FROST_MATERIAL = SolidMaterial(fill=(186, 223, 236), outline=None)
ICE_MATERIAL = SolidMaterial(fill=(116, 207, 237), outline=None)
BRONZE_MATERIAL = SolidMaterial(fill=(159, 112, 58), outline=None)
FLAME_MATERIAL = SolidMaterial(fill=(255, 191, 73), outline=None, shaded=False)
AVATAR_MATERIAL = SolidMaterial(fill=(229, 103, 83), outline=(55, 37, 48))
ICE_EDGES = MeshEdgeStyle(color=(55, 115, 150), thickness=-1.0)


def effective_world_flags() -> dict[str, bool]:
    return {
        "WALLS_ENABLED": WALLS_ENABLED,
        "CEILING_ENABLED": CEILING_ENABLED,
        "PILLARS_ENABLED": PILLARS_ENABLED,
        "SHRINE_ENABLED": SHRINE_ENABLED,
        "BRAZIERS_ENABLED": BRAZIERS_ENABLED,
        "ICICLES_ENABLED": ICICLES_ENABLED and CEILING_ENABLED,
        "RUBBLE_ENABLED": RUBBLE_ENABLED,
        "FLOOR_CRACKS_ENABLED": FLOOR_CRACKS_ENABLED,
        "MESH_EDGES_ENABLED": MESH_EDGES_ENABLED and (
            WALLS_ENABLED or CEILING_ENABLED or PILLARS_ENABLED or SHRINE_ENABLED
            or BRAZIERS_ENABLED or RUBBLE_ENABLED
        ),
    }


def create_road_texture(context: dcg.Context) -> None:
    del context


def temple_sections() -> tuple[CaveSection, ...]:
    if FLOOR_BANDS < 1 or ARCH_SEGMENTS < 4:
        raise ValueError("Invalid frozen temple tessellation")
    if WALL_HEIGHT <= AVATAR_HEIGHT or ROOF_RISE <= 0 or not 0 <= ROOF_ROUGHNESS <= 0.1:
        raise ValueError("Invalid frozen temple headroom or roughness")
    return generate_sections(
        OUTLINE_CONTROLS, world_width=WORLD_W, world_height=WORLD_H,
        step=SECTION_STEP, outline_roughness=0, avatar_height=AVATAR_HEIGHT,
        water_enabled=False,
    )


def temple_rings(sections: tuple[CaveSection, ...]) -> tuple[tuple[Vec3, ...], ...]:
    rings = []
    for station, section in enumerate(sections):
        center = (section.lower + section.upper) * 0.5
        radius = (section.upper - section.lower) * 0.5
        ring = [(section.x, section.lower, 0.0)]
        for arc in range(ARCH_SEGMENTS + 1):
            angle = math.pi * arc / ARCH_SEGMENTS
            rise = ROOF_RISE * math.sin(angle)
            rise *= 1 + ROOF_ROUGHNESS * math.sin(station * 1.7 + arc * 2.3)
            ring.append((section.x, center - radius * math.cos(angle), WALL_HEIGHT + rise))
        ring.append((section.x, section.upper, 0.0))
        rings.append(tuple(ring))
    return tuple(rings)


def roof_surface(rings: tuple[tuple[Vec3, ...], ...]) -> MeshTerrainSurface:
    vertices, triangles = [], []
    for first, second in zip(rings, rings[1:]):
        for arc in range(1, ARCH_SEGMENTS + 1):
            base = len(vertices)
            vertices.extend((first[arc], second[arc], second[arc + 1], first[arc + 1]))
            triangles.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
    return MeshTerrainSurface(vertices=tuple(vertices), triangles=tuple(triangles))


def faceted_mesh(
    x: float, y: float, levels: tuple[tuple[float, float], ...], material: SolidMaterial,
) -> TriangleMesh3D:
    return faceted_prop_mesh(
        x, y, levels, material,
        edges=ICE_EDGES if MESH_EDGES_ENABLED else None,
    )


def floor_props() -> tuple[tuple[str, tuple[TriangleMesh3D, ...]], ...]:
    props = []
    if PILLARS_ENABLED:
        for index, (x, y) in enumerate(PILLAR_POSITIONS):
            props.append((f"frosted pillar {index + 1}", (
                faceted_mesh(x, y, ((0.2, 34), (20, 30)), FROST_MATERIAL),
                faceted_mesh(x, y, ((20.2, 22), (280, 20)), STONE_MATERIAL),
                faceted_mesh(x, y, ((280.2, 27), (304, 36)), FROST_MATERIAL),
            )))
    if SHRINE_ENABLED:
        x, y = SHRINE_XY
        props.append(("frozen shrine", (
            faceted_mesh(x, y, ((0.2, 52), (20, 48)), FROST_MATERIAL),
            faceted_mesh(x, y, ((20.2, 35), (52, 35)), STONE_MATERIAL),
            faceted_mesh(x, y, ((52.2, 40), (64, 40)), FROST_MATERIAL),
            faceted_mesh(x, y, ((64.2, 20), (118, 0)), ICE_MATERIAL),
        )))
        for index, (dx, height) in enumerate(((-60, 125), (0, 175), (60, 140))):
            props.append((f"shrine ice spire {index + 1}", (
                faceted_mesh(x + dx, y + 120, ((0.2, 16), (height * 0.7, 12), (height, 0)), ICE_MATERIAL),
            )))
    if BRAZIERS_ENABLED:
        for index, (x, y) in enumerate(BRAZIER_POSITIONS):
            props.append((f"bronze brazier {index + 1}", (
                faceted_mesh(x, y, ((0.2, 19), (10, 16)), STONE_MATERIAL),
                faceted_mesh(x, y, ((10.2, 8), (32, 8)), BRONZE_MATERIAL),
                faceted_mesh(x, y, ((32.2, 13), (44, 24)), BRONZE_MATERIAL),
                faceted_mesh(x, y, ((44.2, 11), (58, 15), (83, 0)), FLAME_MATERIAL),
            )))
    if RUBBLE_ENABLED:
        for index, (x, y, radius, height) in enumerate(RUBBLE_SPECS):
            props.append((f"fallen masonry {index + 1}", (
                faceted_mesh(x, y, ((0.2, radius), (height, radius * 0.65)), STONE_MATERIAL),
            )))
    return tuple(props)


def prop_footprint(meshes: tuple[TriangleMesh3D, ...]) -> AabbFootprint:
    points = [point for mesh in meshes for point in mesh.vertices]
    return AabbFootprint(min(p[0] for p in points), min(p[1] for p in points),
                         max(p[0] for p in points), max(p[1] for p in points))


def hanging_icicles(surface: MeshTerrainSurface) -> tuple[TriangleMesh3D, ...]:
    meshes = []
    for index, (x, y) in enumerate(ICICLE_POSITIONS):
        radius = 14.0 + index % 3 * 3
        samples = [
            surface.sample(x + radius * math.cos(math.tau * i / 8),
                           y + radius * math.sin(math.tau * i / 8))
            for i in range(8)
        ]
        if any(sample is None for sample in samples):
            raise ValueError("Icicle must fit beneath the temple roof")
        top = min(sample.height for sample in samples if sample is not None) - 0.2
        bottom = top - (90 + index % 4 * 22)
        if bottom <= AVATAR_HEIGHT + 0.2:
            raise ValueError("Icicle must leave player headroom")
        meshes.append(faceted_mesh(x, y, ((bottom, 0), (top, radius)), ICE_MATERIAL))
    return tuple(meshes)


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    del road_texture
    sections = temple_sections()
    rings = temple_rings(sections)
    surface = roof_surface(rings)
    props = floor_props()
    for name, meshes in props:
        for mesh in meshes:
            for x, y, z in mesh.vertices:
                roof = surface.sample(x, y)
                if roof is None or z >= roof.height - 0.2:
                    raise ValueError(f"{name} must fit inside the temple")
    scene = Scene3D(background=BACKGROUND_COLOR)
    for station, (first, second) in enumerate(zip(sections, sections[1:])):
        for band in range(FLOOR_BANDS):
            y0 = first.lower + (first.upper - first.lower) * band / FLOOR_BANDS
            y1 = first.lower + (first.upper - first.lower) * (band + 1) / FLOOR_BANDS
            next_y0 = second.lower + (second.upper - second.lower) * band / FLOOR_BANDS
            next_y1 = second.lower + (second.upper - second.lower) * (band + 1) / FLOOR_BANDS
            x, y = (first.x + second.x) * 0.5, (y0 + y1 + next_y0 + next_y1) * 0.25
            warm = BRAZIERS_ENABLED and any(math.hypot(x - bx, y - by) < 65 for bx, by in BRAZIER_POSITIONS)
            material = WARM_FLOOR_MATERIAL if warm else FLOOR_MATERIALS[(station * 7 + band * 3) % 4]
            if FLOOR_CRACKS_ENABLED and (station * 11 + band * 7) % 23 == 0 and not warm:
                slices = []
                for t, fraction in ((0, 0.32), (0.5, 0.63), (1, 0.42)):
                    slice_x = first.x + (second.x - first.x) * t
                    lower = y0 + (next_y0 - y0) * t
                    upper = y1 + (next_y1 - y1) * t
                    slices.append(tuple(
                        (slice_x, lower + (upper - lower) * f, 0)
                        for f in (0, fraction - 0.012, fraction + 0.012, 1)
                    ))
                for left, right in zip(slices, slices[1:]):
                    for strip in range(3):
                        add_flat_patch(scene, (
                            left[strip], right[strip], right[strip + 1], left[strip + 1],
                        ), CRACK_MATERIAL if strip == 1 else material)
                continue
            add_flat_patch(scene, (
                (first.x, y0, 0), (second.x, next_y0, 0),
                (second.x, next_y1, 0), (first.x, y1, 0),
            ), material)
        for arc in range(ARCH_SEGMENTS + 2):
            wall = arc in (0, ARCH_SEGMENTS + 1)
            if not (WALLS_ENABLED if wall else CEILING_ENABLED):
                continue
            scene.add(TriangleMesh3D(
                vertices=(rings[station][arc], rings[station + 1][arc],
                          rings[station + 1][arc + 1], rings[station][arc + 1]),
                triangles=((0, 2, 1), (0, 3, 2)),
                material=WALL_MATERIALS[station % 3] if wall else CEILING_MATERIAL,
                edges=ICE_EDGES if MESH_EDGES_ENABLED else None,
            ))
    for _, meshes in props:
        for mesh in meshes:
            scene.add(mesh)
    if effective_world_flags()["ICICLES_ENABLED"]:
        for mesh in hanging_icicles(surface):
            scene.add(mesh)
    avatar = Box3D(center=(*AVATAR_START_XY, 0), size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT), material=AVATAR_MATERIAL)
    scene.add(avatar)
    return scene, avatar


def build_collision_world() -> CaveCollisionWorld:
    collisions = CaveCollisionWorld(
        temple_sections(), gap=COLLISION_GAP, world_bounds=AabbFootprint(0, 0, WORLD_W, WORLD_H),
    )
    for name, meshes in floor_props():
        footprint = prop_footprint(meshes)
        if collisions.first_blocker(footprint) is not None:
            raise ValueError(f"{name} overlaps the floor boundary or another prop")
        collisions.add(name, footprint)
    if collisions.first_blocker(AabbFootprint.from_center(*AVATAR_START_XY, AVATAR_SIZE, AVATAR_SIZE)) is not None:
        raise ValueError("Player start must be on unobstructed temple floor")
    return collisions


def build_terrain_surface() -> None:
    return None


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(mode=TerrainMode.FLAT, fallback_ground_z=0.0)
