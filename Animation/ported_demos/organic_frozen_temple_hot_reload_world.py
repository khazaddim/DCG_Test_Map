"""Icebound temple chambers based on the complex cave's asymmetric outline.

The former side lake is solid, traversable ice. A rectangular entrance is cut
out of the cave's end wall; its jambs block movement, not the open passage.
"""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Box3D, MeshEdgeStyle, MeshTerrainSurface, Polygon3D, Scene3D,
    SolidMaterial, TerrainMode, TriangleMesh3D, TraversalSettings, Vec3,
)
from Animation.ported_demos.cave_geometry import (
    CaveCollisionWorld, CaveSection, add_flat_patch, faceted_prop_mesh,
    generate_rings, generate_sections,
)


WORLD_W = 1800.0
WORLD_H = 1200.0
GRID_STEP = 12.0
AVATAR_SIZE = 8.0
AVATAR_HEIGHT = 12.0
AVATAR_START_XY = (840.0, 600.0)
COLLISION_GAP = 1.0
SECTION_STEP = 30.0
ARCH_SEGMENTS = 12
FLOOR_BANDS = 10
ROCK_ROUGHNESS = 0.07
OUTLINE_ROUGHNESS = 14.0

WALLS_ENABLED = True
CEILING_ENABLED = True
FROZEN_LAKE_ENABLED = True
PILLARS_ENABLED = True
SHRINE_ENABLED = True
BRAZIERS_ENABLED = True
ICICLES_ENABLED = True
RUBBLE_ENABLED = True
DOORWAY_ENABLED = True
SANCTUM_ENABLED = True
SANCTUM_GLOW_ENABLED = True
ICE_RIDGE_ENABLED = True
MESH_EDGES_ENABLED = False

# Same chamber chain and lake outline as the natural complex cave.
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
PILLAR_SPECS = ((625.0, 480.0, 170.0), (780.0, 850.0, 165.0),
                (1120.0, 790.0, 190.0), (1320.0, 770.0, 150.0),
                (950.0, 350.0, 160.0))
BRAZIER_POSITIONS = ((540.0, 440.0), (690.0, 660.0), (930.0, 480.0),
                     (1120.0, 920.0), (1380.0, 700.0), (1620.0, 890.0))
RUBBLE_SPECS = ((600.0, 720.0, 18.0, 20.0), (1240.0, 540.0, 22.0, 18.0),
                (1500.0, 850.0, 16.0, 20.0))
SHRINE_XY = (960.0, 650.0)
ICICLE_POSITIONS = ((540.0, 500.0), (660.0, 550.0), (780.0, 650.0),
                    (900.0, 550.0), (1020.0, 820.0), (1140.0, 740.0),
                    (1260.0, 820.0), (1440.0, 750.0), (1620.0, 860.0))
DOOR_X = 120.0
DOOR_WIDTH = 84.0
DOOR_HEIGHT = 140.0
SANCTUM_X = 1000.0
SANCTUM_WIDTH = 220.0
SANCTUM_HEIGHT = 210.0
SANCTUM_FRONT_Y = 880.0
SANCTUM_BACK_Y = 1000.0
SANCTUM_WALL_WIDTH = 280.0
RIDGE_WIDTH = 22.0
RIDGE_X_RANGE = (560.0, 1420.0)

BACKGROUND_COLOR = (8, 20, 36)
FLOOR_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((111, 159, 185), (126, 176, 199), (143, 190, 211), (101, 146, 175))
)
LAKE_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((91, 171, 208), (106, 193, 223), (140, 213, 233))
)
WARM_FLOOR_MATERIAL = SolidMaterial(fill=(195, 188, 153), outline=None, shaded=False)
WALL_MATERIAL = SolidMaterial(fill=(83, 125, 157), outline=None)
CEILING_MATERIAL = SolidMaterial(fill=(99, 153, 185), outline=None)
STONE_MATERIAL = SolidMaterial(fill=(107, 143, 165), outline=None)
FROST_MATERIAL = SolidMaterial(fill=(186, 223, 236), outline=None)
ICE_MATERIAL = SolidMaterial(fill=(116, 207, 237), outline=None)
BRONZE_MATERIAL = SolidMaterial(fill=(159, 112, 58), outline=None)
FLAME_MATERIAL = SolidMaterial(fill=(255, 191, 73), outline=None, shaded=False)
ENTRY_WALL_MATERIAL = SolidMaterial(fill=(71, 106, 137), outline=None)
GOLD_MATERIAL = SolidMaterial(fill=(223, 177, 88), outline=None)
AVATAR_MATERIAL = SolidMaterial(fill=(229, 103, 83), outline=(55, 37, 48))
ICE_EDGES = MeshEdgeStyle(color=(55, 115, 150), thickness=-1.0)
RIDGE_MATERIAL = SolidMaterial(fill=(160, 214, 234), outline=None)
SANCTUM_MATERIAL = SolidMaterial(fill=(115, 91, 65), outline=None)
GLOW_MATERIAL = SolidMaterial(
    fill=(255, 207, 112), outline=None, shaded=False,
)
GLOW_FLOOR_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((133, 177, 190), (157, 186, 182), (181, 195, 173),
                  (205, 204, 161), (228, 213, 149), (246, 222, 142))
)


def effective_world_flags() -> dict[str, bool]:
    return {
        "WALLS_ENABLED": WALLS_ENABLED,
        "CEILING_ENABLED": CEILING_ENABLED,
        "FROZEN_LAKE_ENABLED": FROZEN_LAKE_ENABLED,
        "PILLARS_ENABLED": PILLARS_ENABLED,
        "SHRINE_ENABLED": SHRINE_ENABLED,
        "BRAZIERS_ENABLED": BRAZIERS_ENABLED,
        "ICICLES_ENABLED": ICICLES_ENABLED and CEILING_ENABLED,
        "RUBBLE_ENABLED": RUBBLE_ENABLED,
        "DOORWAY_ENABLED": DOORWAY_ENABLED,
        "SANCTUM_ENABLED": SANCTUM_ENABLED,
        "SANCTUM_GLOW_ENABLED": SANCTUM_ENABLED and SANCTUM_GLOW_ENABLED,
        "ICE_RIDGE_ENABLED": ICE_RIDGE_ENABLED and WALLS_ENABLED,
        "MESH_EDGES_ENABLED": MESH_EDGES_ENABLED and (
            WALLS_ENABLED or CEILING_ENABLED or PILLARS_ENABLED or SHRINE_ENABLED
            or BRAZIERS_ENABLED or RUBBLE_ENABLED or DOORWAY_ENABLED
        ),
    }


def create_road_texture(context: dcg.Context) -> None:
    del context


def cave_sections() -> tuple[CaveSection, ...]:
    if ARCH_SEGMENTS < 4 or FLOOR_BANDS < 1:
        raise ValueError("Invalid organic frozen temple tessellation")
    sections = generate_sections(
        OUTLINE_CONTROLS, world_width=WORLD_W, world_height=WORLD_H,
        step=SECTION_STEP, outline_roughness=OUTLINE_ROUGHNESS,
        avatar_height=AVATAR_HEIGHT, water_enabled=FROZEN_LAKE_ENABLED,
    )
    if not 0 < DOOR_X < sections[-1].x:
        raise ValueError("Doorway must lie inside the cave length")
    # Insert a station without changing the piecewise-linear authored outline.
    if not any(section.x == DOOR_X for section in sections):
        first, second = next((a, b) for a, b in zip(sections, sections[1:]) if a.x < DOOR_X < b.x)
        t = (DOOR_X - first.x) / (second.x - first.x)
        inserted = CaveSection(DOOR_X, *(a + (b - a) * t for a, b in zip(first[1:], second[1:])))
        sections = tuple(sorted((*sections, inserted), key=lambda section: section.x))
    return sections


def cave_rings(sections: tuple[CaveSection, ...]) -> tuple[tuple[Vec3, ...], ...]:
    rings = generate_rings(sections, arch_segments=ARCH_SEGMENTS, roughness=ROCK_ROUGHNESS)
    if not effective_world_flags()["ICE_RIDGE_ENABLED"]:
        return rings
    if not math.isfinite(RIDGE_WIDTH) or not 12 < RIDGE_WIDTH < 40:
        raise ValueError("Ice ridge width must be between 12 and 40")
    if not all(math.isfinite(v) for v in RIDGE_X_RANGE) or not 0 <= RIDGE_X_RANGE[0] < RIDGE_X_RANGE[1] <= WORLD_W:
        raise ValueError("Ice ridge range must lie inside the cave length")
    modified = []
    for section, ring in zip(sections, rings):
        points = []
        width = RIDGE_WIDTH if RIDGE_X_RANGE[0] <= section.x <= RIDGE_X_RANGE[1] else 0.0
        for arc, (first, second) in enumerate(zip(ring, ring[1:])):
            points.append(first)
            if arc not in (ARCH_SEGMENTS // 4, ARCH_SEGMENTS - ARCH_SEGMENTS // 4 - 1):
                continue
            a = tuple(v + (w - v) * 0.4 for v, w in zip(first, second))
            b = tuple(v + (w - v) * 0.6 for v, w in zip(first, second))
            direction = 1 if arc < ARCH_SEGMENTS / 2 else -1
            inner_y = (max(a[1], b[1]) if direction == 1 else min(a[1], b[1])) + direction * width
            points.extend((a, (a[0], inner_y, a[2]) if width else a,
                           (b[0], inner_y, b[2]) if width else b, b))
        points.append(ring[-1])
        modified.append(tuple(points))
    return tuple(modified)


def roof_surface(
    rings: tuple[tuple[Vec3, ...], ...], *, arcs: tuple[int, ...] | None = None,
) -> MeshTerrainSurface:
    vertices, triangles = [], []
    for first, second in zip(rings, rings[1:]):
        for arc in arcs if arcs is not None else range(len(first) - 1):
            base = len(vertices)
            vertices.extend((first[arc], second[arc], second[arc + 1], first[arc + 1]))
            triangles.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
    return MeshTerrainSurface(vertices=tuple(vertices), triangles=tuple(triangles))


def prop_mesh(x: float, y: float, levels: tuple[tuple[float, float], ...], material: SolidMaterial) -> TriangleMesh3D:
    return faceted_prop_mesh(x, y, levels, material, edges=ICE_EDGES if MESH_EDGES_ENABLED else None)


def floor_props() -> tuple[tuple[str, tuple[TriangleMesh3D, ...]], ...]:
    props = []
    if PILLARS_ENABLED:
        for index, (x, y, height) in enumerate(PILLAR_SPECS):
            props.append((f"frosted pillar {index + 1}", (
                prop_mesh(x, y, ((0.2, 28), (16, 25)), FROST_MATERIAL),
                prop_mesh(x, y, ((16.2, 18), (height - 18, 16)), STONE_MATERIAL),
                prop_mesh(x, y, ((height - 17.8, 22), (height, 29)), FROST_MATERIAL),
            )))
    if SHRINE_ENABLED:
        x, y = SHRINE_XY
        props.append(("frozen shrine", (
            prop_mesh(x, y, ((0.2, 52), (20, 48)), FROST_MATERIAL),
            prop_mesh(x, y, ((20.2, 35), (52, 35)), STONE_MATERIAL),
            prop_mesh(x, y, ((52.2, 40), (64, 40)), FROST_MATERIAL),
            prop_mesh(x, y, ((64.2, 20), (118, 0)), ICE_MATERIAL),
        )))
        for index, (dx, height) in enumerate(((-60, 125), (0, 175), (60, 140))):
            props.append((f"shrine ice spire {index + 1}", (
                prop_mesh(x + dx, y + 120, ((0.2, 16), (height * 0.7, 12), (height, 0)), ICE_MATERIAL),
            )))
    if BRAZIERS_ENABLED:
        for index, (x, y) in enumerate(BRAZIER_POSITIONS):
            props.append((f"bronze brazier {index + 1}", (
                prop_mesh(x, y, ((0.2, 19), (10, 16)), STONE_MATERIAL),
                prop_mesh(x, y, ((10.2, 8), (32, 8)), BRONZE_MATERIAL),
                prop_mesh(x, y, ((32.2, 13), (44, 24)), BRONZE_MATERIAL),
                prop_mesh(x, y, ((44.2, 11), (58, 15), (83, 0)), FLAME_MATERIAL),
            )))
    if RUBBLE_ENABLED:
        for index, (x, y, radius, height) in enumerate(RUBBLE_SPECS):
            props.append((f"fallen masonry {index + 1}", (
                prop_mesh(x, y, ((0.2, radius), (height, radius * 0.65)), STONE_MATERIAL),
            )))
    return tuple(props)


def prop_footprint(meshes: tuple[TriangleMesh3D, ...]) -> AabbFootprint:
    points = [point for mesh in meshes for point in mesh.vertices]
    return AabbFootprint(min(p[0] for p in points), min(p[1] for p in points),
                         max(p[0] for p in points), max(p[1] for p in points))


def clip_polygon(points: tuple[Vec3, ...], axis: int, boundary: float, *, above: bool) -> tuple[Vec3, ...]:
    if not points:
        return ()
    result = []
    for first, second in zip(points, (*points[1:], points[0])):
        a, b = first[axis] - boundary, second[axis] - boundary
        inside_a, inside_b = (a >= 0, b >= 0) if above else (a <= 0, b <= 0)
        if inside_a:
            result.append(first)
        if inside_a != inside_b:
            t = a / (a - b)
            result.append(tuple(a + (b - a) * t for a, b in zip(first, second)))
    return tuple(result)


def doorway_bounds(ring: tuple[Vec3, ...]) -> tuple[float, float]:
    center = (ring[0][1] + ring[-1][1]) * 0.5
    lower, upper = center - DOOR_WIDTH * 0.5, center + DOOR_WIDTH * 0.5
    if not math.isfinite(DOOR_WIDTH) or not math.isfinite(DOOR_HEIGHT):
        raise ValueError("Doorway dimensions must be finite")
    if DOOR_WIDTH <= AVATAR_SIZE + 2 * COLLISION_GAP or DOOR_HEIGHT <= AVATAR_HEIGHT:
        raise ValueError("Doorway must have player clearance")
    crossings = []
    for first, second in zip(ring, ring[1:]):
        if (first[2] <= DOOR_HEIGHT < second[2]) or (second[2] <= DOOR_HEIGHT < first[2]):
            t = (DOOR_HEIGHT - first[2]) / (second[2] - first[2])
            crossings.append(first[1] + (second[1] - first[1]) * t)
    if len(crossings) != 2 or lower - 16 <= min(crossings) or upper + 16 >= max(crossings):
        raise ValueError("Doorway and its frame must fit inside the cave end wall")
    return lower, upper


def entrance_wall(ring: tuple[Vec3, ...]) -> tuple[TriangleMesh3D, ...]:
    lower, upper = doorway_bounds(ring)
    center = (DOOR_X, (ring[0][1] + ring[-1][1]) * 0.5, 0.0)
    meshes = []
    for first, second in zip(ring, ring[1:]):
        triangle = (center, first, second)
        left = clip_polygon(triangle, 1, lower, above=False)
        middle = clip_polygon(triangle, 1, lower, above=True)
        right = clip_polygon(middle, 1, upper, above=True)
        middle = clip_polygon(middle, 1, upper, above=False)
        top = clip_polygon(middle, 2, DOOR_HEIGHT, above=True)
        for polygon in (left, right, top):
            if len(polygon) >= 3:
                meshes.append(TriangleMesh3D(
                    vertices=polygon, triangles=tuple((0, i, i + 1) for i in range(1, len(polygon) - 1)),
                    material=ENTRY_WALL_MATERIAL, cull_back_faces=False,
                    edges=ICE_EDGES if MESH_EDGES_ENABLED else None,
                ))
    return tuple(meshes)


def outside_sanctum(points: tuple[Vec3, ...], front_y: float) -> tuple[tuple[Vec3, ...], ...]:
    lower, upper = SANCTUM_X - SANCTUM_WALL_WIDTH / 2, SANCTUM_X + SANCTUM_WALL_WIDTH / 2
    left = clip_polygon(points, 0, lower, above=False)
    middle = clip_polygon(points, 0, lower, above=True)
    right = clip_polygon(middle, 0, upper, above=True)
    middle = clip_polygon(middle, 0, upper, above=False)
    front = clip_polygon(middle, 1, front_y, above=False)
    return tuple(p for p in (left, right, front) if len(p) >= 3)


def polygon_mesh(
    points: tuple[Vec3, ...], material: SolidMaterial, *, cull_back_faces: bool = False,
) -> TriangleMesh3D:
    return TriangleMesh3D(
        vertices=points, triangles=tuple((0, i, i + 1) for i in range(1, len(points) - 1)),
        material=material, cull_back_faces=cull_back_faces,
        edges=ICE_EDGES if MESH_EDGES_ENABLED else None,
    )


def sanctum_profile(surface: MeshTerrainSurface) -> tuple[Vec3, ...]:
    lower, upper = SANCTUM_X - SANCTUM_WALL_WIDTH / 2, SANCTUM_X + SANCTUM_WALL_WIDTH / 2
    if not all(math.isfinite(v) for v in (
        SANCTUM_X, SANCTUM_WIDTH, SANCTUM_HEIGHT, SANCTUM_FRONT_Y, SANCTUM_BACK_Y, SANCTUM_WALL_WIDTH,
    )):
        raise ValueError("Sanctum dimensions must be finite")
    if not (AVATAR_SIZE + 2 * COLLISION_GAP < SANCTUM_WIDTH < SANCTUM_WALL_WIDTH - 32
            and AVATAR_HEIGHT < SANCTUM_HEIGHT and SANCTUM_FRONT_Y < SANCTUM_BACK_Y < WORLD_H):
        raise ValueError("Sanctum needs a clear opening and a recessed back wall")
    xs = {lower, upper}
    for indices in surface.triangles:
        vertices = tuple(surface.vertices[i] for i in indices)
        for a, b in zip(vertices, (*vertices[1:], vertices[0])):
            if a[1] == SANCTUM_FRONT_Y:
                if lower < a[0] < upper:
                    xs.add(a[0])
            elif (a[1] < SANCTUM_FRONT_Y <= b[1]) or (b[1] < SANCTUM_FRONT_Y <= a[1]):
                t = (SANCTUM_FRONT_Y - a[1]) / (b[1] - a[1])
                x = a[0] + (b[0] - a[0]) * t
                if lower < x < upper:
                    xs.add(x)
    profile = []
    sections = cave_sections()
    for x in sorted(xs):
        sample = surface.sample(x, SANCTUM_FRONT_Y)
        if sample is None or sample.height <= SANCTUM_HEIGHT + 25:
            raise ValueError("Sanctum doorway must fit below the cave roof")
        # This extension stays inside the original walkable floor outline.
        first, second = next((a, b) for a, b in zip(sections, sections[1:]) if a.x <= x <= b.x)
        t = (x - first.x) / (second.x - first.x)
        floor_edge = first.upper + (second.upper - first.upper) * t
        if SANCTUM_BACK_Y >= floor_edge - COLLISION_GAP:
            raise ValueError("Sanctum back wall must remain inside the cave floor")
        profile.append((x, SANCTUM_FRONT_Y, sample.height))
    return tuple(profile)


def sanctum_geometry(surface: MeshTerrainSurface) -> tuple[TriangleMesh3D | Box3D | Polygon3D, ...]:
    profile = sanctum_profile(surface)
    lower, upper = SANCTUM_X - SANCTUM_WIDTH / 2, SANCTUM_X + SANCTUM_WIDTH / 2
    objects = []
    for a, b in zip(profile, profile[1:]):
        face = ((a[0], a[1], 0), (b[0], b[1], 0), b, a)
        left = clip_polygon(face, 0, lower, above=False)
        middle = clip_polygon(face, 0, lower, above=True)
        right = clip_polygon(middle, 0, upper, above=True)
        middle = clip_polygon(middle, 0, upper, above=False)
        top = clip_polygon(middle, 2, SANCTUM_HEIGHT, above=True)
        objects.extend(polygon_mesh(p, ENTRY_WALL_MATERIAL) for p in (left, right, top) if len(p) >= 3)
        objects.append(polygon_mesh((a, b, (b[0], SANCTUM_BACK_Y, b[2]), (a[0], SANCTUM_BACK_Y, a[2])), FROST_MATERIAL))
        objects.append(polygon_mesh((
            (a[0], SANCTUM_BACK_Y, SANCTUM_HEIGHT + 20),
            (b[0], SANCTUM_BACK_Y, SANCTUM_HEIGHT + 20),
            (b[0], SANCTUM_BACK_Y, b[2]), (a[0], SANCTUM_BACK_Y, a[2]),
        ), SANCTUM_MATERIAL))
    objects.append(Polygon3D(
        points=((profile[0][0], SANCTUM_BACK_Y, 0), (profile[-1][0], SANCTUM_BACK_Y, 0),
                (profile[-1][0], SANCTUM_BACK_Y, SANCTUM_HEIGHT + 20),
                (profile[0][0], SANCTUM_BACK_Y, SANCTUM_HEIGHT + 20)),
        material=GLOW_MATERIAL if SANCTUM_GLOW_ENABLED else SANCTUM_MATERIAL, cull_back_face=False,
    ))
    for point in (profile[0], profile[-1]):
        objects.append(polygon_mesh((
            (point[0], SANCTUM_FRONT_Y, 0), (point[0], SANCTUM_BACK_Y, 0),
            (point[0], SANCTUM_BACK_Y, point[2]), point,
        ), SANCTUM_MATERIAL))
    for x in (lower - 10, upper + 10):
        objects.extend((
            Box3D(center=(x, SANCTUM_FRONT_Y - 8.2, 0.2), size=(20, 16, SANCTUM_HEIGHT - 0.2), material=FROST_MATERIAL),
            Box3D(center=(x, SANCTUM_FRONT_Y - 17.4, 0.4), size=(10, 2, SANCTUM_HEIGHT - 0.6), material=GOLD_MATERIAL),
        ))
        for z in range(25, int(SANCTUM_HEIGHT) - 10, 32):
            objects.append(Box3D(center=(x, SANCTUM_FRONT_Y - 19.6, z), size=(15, 2, 5), material=BRONZE_MATERIAL))
    objects.append(Box3D(
        center=(SANCTUM_X, SANCTUM_FRONT_Y - 8.2, SANCTUM_HEIGHT + 0.2),
        size=(SANCTUM_WIDTH + 40, 16, 20), material=FROST_MATERIAL,
    ))
    for dx in (-80, -40, 0, 40, 80):
        objects.append(Box3D(
            center=(SANCTUM_X + dx, SANCTUM_FRONT_Y - 17.4, SANCTUM_HEIGHT + 4),
            size=(12, 2, 12), material=GOLD_MATERIAL,
        ))
    return tuple(objects)


def ridge_icicles(sections: tuple[CaveSection, ...], rings: tuple[tuple[Vec3, ...], ...]) -> tuple[TriangleMesh3D, ...]:
    meshes = []
    underside = roof_surface(rings, arcs=(ARCH_SEGMENTS // 4 + 1, ARCH_SEGMENTS - ARCH_SEGMENTS // 4 + 6))
    for station, (section, ring) in enumerate(zip(sections, rings)):
        if station % 2 or not RIDGE_X_RANGE[0] <= section.x <= RIDGE_X_RANGE[1]:
            continue
        for side, index in enumerate((ARCH_SEGMENTS // 4 + 2, ARCH_SEGMENTS - ARCH_SEGMENTS // 4 + 6)):
            if side == 1 and SANCTUM_ENABLED and abs(section.x - SANCTUM_X) < SANCTUM_WALL_WIDTH / 2 + 8:
                continue
            point = ring[index]
            outer = ring[index - 1 if side == 0 else index + 1]
            y = (point[1] + outer[1]) * 0.5
            radius = min(5, RIDGE_WIDTH * 0.2)
            base = tuple(
                (section.x + radius * math.cos(math.tau * i / 8),
                 y + radius * math.sin(math.tau * i / 8)) for i in range(8)
            )
            samples = [underside.sample(section.x, y)]
            for a, b in zip(base, (*base[1:], base[0])):
                for t in (0, 0.25, 0.5, 0.75):
                    samples.append(underside.sample(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            if any(sample is None for sample in samples):
                raise ValueError("Ridge icicles must fit beneath the ledge")
            top = min(sample.height for sample in samples if sample is not None) - 0.2
            bottom = top - (60 + (station * 7 + side * 11) % 70)
            if bottom <= AVATAR_HEIGHT:
                raise ValueError("Ridge icicles must leave player headroom")
            meshes.append(prop_mesh(section.x, y, ((bottom, 0), (top, radius)), ICE_MATERIAL))
    return tuple(meshes)

def doorway_frame(ring: tuple[Vec3, ...]) -> tuple[Box3D, ...]:
    lower, upper = doorway_bounds(ring)
    boxes = []
    for y in (lower - 8, upper + 8):
        boxes.extend((
            Box3D(center=(DOOR_X - 6.2, y, 0.2), size=(12, 16, DOOR_HEIGHT - 0.2), material=FROST_MATERIAL),
            Box3D(center=(DOOR_X - 13.4, y, 0.4), size=(2, 8, DOOR_HEIGHT - 0.6), material=GOLD_MATERIAL),
        ))
        for z in (24, 60, 96):
            boxes.append(Box3D(center=(DOOR_X - 15.6, y, z), size=(2, 12, 4), material=BRONZE_MATERIAL))
    boxes.append(Box3D(
        center=(DOOR_X - 6.2, (lower + upper) * 0.5, DOOR_HEIGHT + 0.2),
        size=(12, DOOR_WIDTH + 32, 16), material=FROST_MATERIAL,
    ))
    for fraction in (0.15, 0.35, 0.5, 0.65, 0.85):
        boxes.append(Box3D(
            center=(DOOR_X - 13.4, lower + DOOR_WIDTH * fraction, DOOR_HEIGHT + 4),
            size=(2, 5, 8), material=GOLD_MATERIAL,
        ))
    return tuple(boxes)


def hanging_icicles(surface: MeshTerrainSurface) -> tuple[TriangleMesh3D, ...]:
    meshes = []
    for index, (x, y) in enumerate(ICICLE_POSITIONS):
        radius = 10.0 + index % 3 * 2
        samples = [
            surface.sample(x + radius * math.cos(math.tau * i / 8),
                           y + radius * math.sin(math.tau * i / 8)) for i in range(8)
        ]
        if any(sample is None for sample in samples):
            raise ValueError("Icicle must fit beneath the cave roof")
        top = min(sample.height for sample in samples if sample is not None) - 0.2
        bottom = top - (65 + index % 4 * 16)
        if bottom <= AVATAR_HEIGHT + 0.2:
            raise ValueError("Icicle must leave player headroom")
        meshes.append(prop_mesh(x, y, ((bottom, 0), (top, radius)), ICE_MATERIAL))
    return tuple(meshes)


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    del road_texture
    sections = cave_sections()
    rings = cave_rings(sections)
    surface = roof_surface(rings)
    if SANCTUM_ENABLED:
        sanctum_profile(surface)
    props = floor_props()
    for name, meshes in props:
        for mesh in meshes:
            for x, y, z in mesh.vertices:
                roof = surface.sample(x, y)
                if roof is None or z >= roof.height - 0.2:
                    raise ValueError(f"{name} must fit inside the cave")
    scene = Scene3D(background=BACKGROUND_COLOR)
    for station, (first, second) in enumerate(zip(sections, sections[1:])):
        for band in range(FLOOR_BANDS):
            start, end = band / FLOOR_BANDS, (band + 1) / FLOOR_BANDS
            points = (
                (first.x, first.shore + (first.upper - first.shore) * start, 0),
                (second.x, second.shore + (second.upper - second.shore) * start, 0),
                (second.x, second.shore + (second.upper - second.shore) * end, 0),
                (first.x, first.shore + (first.upper - first.shore) * end, 0),
            )
            x, y = sum(p[0] for p in points) / 4, sum(p[1] for p in points) / 4
            warm = BRAZIERS_ENABLED and any(math.hypot(x - bx, y - by) < 55 for bx, by in BRAZIER_POSITIONS)
            material = WARM_FLOOR_MATERIAL if warm else FLOOR_MATERIALS[(station * 7 + band * 3) % 4]
            if effective_world_flags()["SANCTUM_GLOW_ENABLED"]:
                distance = math.hypot(
                    (x - SANCTUM_X) / (SANCTUM_WIDTH / 2 + 60),
                    max(0, SANCTUM_FRONT_Y + 40 - y) / 190,
                )
                if distance < 1:
                    material = GLOW_FLOOR_MATERIALS[min(5, int((1 - distance) * 6))]
            if SANCTUM_ENABLED:
                for polygon in outside_sanctum(points, SANCTUM_BACK_Y):
                    scene.add(Polygon3D(points=polygon, material=material, cull_back_face=False))
            else:
                add_flat_patch(scene, points, material)
        if first.water_width > 0 or second.water_width > 0:
            for band in range(3):
                start, end = band / 3, (band + 1) / 3
                add_flat_patch(scene, (
                    (first.x, first.lower + first.water_width * start, 0),
                    (second.x, second.lower + second.water_width * start, 0),
                    (second.x, second.lower + second.water_width * end, 0),
                    (first.x, first.lower + first.water_width * end, 0),
                ), LAKE_MATERIALS[band])
        if first.x < DOOR_X:
            continue
        ridged = effective_world_flags()["ICE_RIDGE_ENABLED"]
        left, right = ARCH_SEGMENTS // 4, ARCH_SEGMENTS - ARCH_SEGMENTS // 4 - 1
        for arc in range(len(rings[station]) - 1):
            ridge = ridged and arc in (*range(left + 1, left + 4), *range(right + 5, right + 8))
            source_arc = arc - (4 if ridged and arc > left + 4 else 0) - (4 if ridged and arc > right + 8 else 0)
            ceiling = not ridge and ARCH_SEGMENTS / 3 <= source_arc < ARCH_SEGMENTS * 2 / 3
            if not (CEILING_ENABLED if ceiling else WALLS_ENABLED):
                continue
            points = (rings[station][arc], rings[station + 1][arc],
                      rings[station + 1][arc + 1], rings[station][arc + 1])
            material = RIDGE_MATERIAL if ridge else CEILING_MATERIAL if ceiling else WALL_MATERIAL
            for indices in ((0, 2, 1), (0, 3, 2)):
                triangle = tuple(points[i] for i in indices)
                polygons = outside_sanctum(triangle, SANCTUM_FRONT_Y) if SANCTUM_ENABLED else (triangle,)
                for polygon in polygons:
                    scene.add(polygon_mesh(polygon, material, cull_back_faces=True))
    for _, meshes in props:
        for mesh in meshes:
            scene.add(mesh)
    if effective_world_flags()["ICICLES_ENABLED"]:
        for mesh in hanging_icicles(surface):
            scene.add(mesh)
        if effective_world_flags()["ICE_RIDGE_ENABLED"]:
            for mesh in ridge_icicles(sections, rings):
                scene.add(mesh)
    if SANCTUM_ENABLED:
        for obj in sanctum_geometry(surface):
            scene.add(obj)
    if DOORWAY_ENABLED:
        ring = rings[next(i for i, section in enumerate(sections) if section.x == DOOR_X)]
        for obj in (*entrance_wall(ring), *doorway_frame(ring)):
            scene.add(obj)
    avatar = Box3D(center=(*AVATAR_START_XY, 0), size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT), material=AVATAR_MATERIAL)
    scene.add(avatar)
    return scene, avatar


def build_collision_world() -> CaveCollisionWorld:
    sections = cave_sections()
    collisions = CaveCollisionWorld(
        tuple(section._replace(water_width=0.0) for section in sections),
        gap=COLLISION_GAP, world_bounds=AabbFootprint(0, 0, WORLD_W, WORLD_H),
    )
    for name, meshes in floor_props():
        footprint = prop_footprint(meshes)
        if collisions.first_blocker(footprint) is not None:
            raise ValueError(f"{name} overlaps the floor boundary or another prop")
        collisions.add(name, footprint)
    if SANCTUM_ENABLED:
        surface = roof_surface(cave_rings(sections))
        profile = sanctum_profile(surface)
        lower, upper = SANCTUM_X - SANCTUM_WIDTH / 2, SANCTUM_X + SANCTUM_WIDTH / 2
        outer_lower, outer_upper = profile[0][0], profile[-1][0]
        collisions.add("sanctum wall left", AabbFootprint(outer_lower, SANCTUM_FRONT_Y - 0.2, lower, SANCTUM_FRONT_Y + 0.2))
        collisions.add("sanctum wall right", AabbFootprint(upper, SANCTUM_FRONT_Y - 0.2, outer_upper, SANCTUM_FRONT_Y + 0.2))
        collisions.add("sanctum back wall", AabbFootprint(outer_lower, SANCTUM_BACK_Y - 0.2, outer_upper, WORLD_H))
        for x in (outer_lower, outer_upper):
            collisions.add("sanctum side wall", AabbFootprint(x - 0.2, SANCTUM_FRONT_Y, x + 0.2, SANCTUM_BACK_Y))
        for index, obj in enumerate(sanctum_geometry(surface)):
            if isinstance(obj, Box3D) and obj.center[2] < AVATAR_HEIGHT:
                collisions.add(f"sanctum jamb {index + 1}", AabbFootprint.from_center(
                    obj.center[0], obj.center[1], obj.size[0], obj.size[1],
                ))
    if DOORWAY_ENABLED:
        ring = cave_rings(sections)[next(i for i, section in enumerate(sections) if section.x == DOOR_X)]
        lower, upper = doorway_bounds(ring)
        collisions.add("entrance wall left", AabbFootprint(DOOR_X - 0.2, ring[0][1], DOOR_X + 0.2, lower))
        collisions.add("entrance wall right", AabbFootprint(DOOR_X - 0.2, upper, DOOR_X + 0.2, ring[-1][1]))
        for index, box in enumerate(doorway_frame(ring)):
            if box.center[2] < AVATAR_HEIGHT:
                collisions.add(f"door jamb {index + 1}", AabbFootprint.from_center(
                    box.center[0], box.center[1], box.size[0], box.size[1],
                ))
    if collisions.first_blocker(AabbFootprint.from_center(*AVATAR_START_XY, AVATAR_SIZE, AVATAR_SIZE)) is not None:
        raise ValueError("Player start must be on unobstructed temple floor")
    return collisions


def build_terrain_surface() -> None:
    return None


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(mode=TerrainMode.FLAT, fallback_ground_z=0.0)
