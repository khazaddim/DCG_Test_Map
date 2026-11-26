"""A basalt island, lava moat, and stone bridges beneath an irregular dome.

The island has raised, traversable relief and shoreline cliffs. Stone arches
support cambered bridge decks above the lava. Movement follows the authored
surface mesh. Lava brightness is static color, not a fluid simulation.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Box3D, Collider, CollisionShape2D, CollisionWorld, Line3D,
    MeshEdgeStyle, MeshTerrainSurface, OutOfBoundsPolicy, Scene3D, SolidMaterial, TerrainMode, TriangleMesh3D,
    TraversalRole, TraversalSettings, Vec2, Vec3,
)
from Animation.draw_in_window_3d_framework.math3d import Viewport, clip_polygon_to_viewport


WORLD_W = 1400.0
WORLD_H = 1400.0
CENTER = (WORLD_W * 0.5, WORLD_H * 0.5)
AVATAR_START_XY = CENTER
GRID_STEP = 12.0
AVATAR_SIZE = 8.0
AVATAR_HEIGHT = 12.0
COLLISION_GAP = 1.0
ISLAND_RADIUS = 180.0
ISLAND_RINGS = 8
ISLAND_EDGE_HEIGHT = 60.0
ISLAND_PEAK_HEIGHT = 160.0
ISLAND_RELIEF = 30.0
RIM_HEIGHT = 40.0
LAVA_LEVEL = 0.0
MAX_SLOPE_DEGREES = 65.0
LAVA_OUTER_RADIUS = 430.0
DOME_RADIUS = 560.0
DOME_HEIGHT = 620.0
DOME_ROUGHNESS = 0.05
SECTORS = 72
LAVA_BANDS = 12
DOME_RINGS = 12
BRIDGE_ANGLES_DEG = (0.0, 210.0)
BRIDGE_HALF_WIDTH_DEG = 5.0
BRIDGE_CAMBER = 25.0
BRIDGE_ARCH_RISE = 35.0
BRIDGE_ABUTMENT_FRACTION = 1.0 / 6.0
BRIDGE_BASE_HEIGHT = 0.2
BRIDGE_MIN_THICKNESS = 12.0
SECONDARY_ISLAND_ANGLE_DEG = 135.0
SECONDARY_ISLAND_HALF_WIDTH_DEG = 15.0
SECONDARY_ISLAND_START = 1.0 / 3.0
SECONDARY_ISLAND_END = 5.0 / 6.0
SECONDARY_ISLAND_HEIGHT = 55.0
SECONDARY_ISLAND_RELIEF = 25.0
SECONDARY_BRIDGE_CAMBER = 12.0
SECONDARY_BRIDGE_ARCH_RISE = 22.0

LAVA_ENABLED = True
BRIDGES_ENABLED = True
SECONDARY_ISLAND_ENABLED = True
SECONDARY_BRIDGE_ENABLED = True
BRIDGE_LINES_ENABLED = True
DOME_ENABLED = True
ROCKS_ENABLED = True
MESH_EDGES_ENABLED = False

BACKGROUND_COLOR = (18, 15, 13)
STONE_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=True)
    for color in ((77, 74, 70), (85, 81, 76), (66, 65, 63), (91, 86, 79))
)
LAVA_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=False)
    for color in ((174, 30, 5), (219, 46, 6), (244, 79, 8),
                  (255, 126, 12), (255, 182, 23), (255, 224, 68))
)
BRIDGE_MATERIAL = SolidMaterial(fill=(112, 106, 96), outline=None, shaded=True)
BRIDGE_STRUCTURE_MATERIAL = SolidMaterial(fill=(99, 91, 79), outline=None, shaded=True)
CLIFF_MATERIAL = SolidMaterial(fill=(76, 70, 61), outline=None, shaded=True)
DOME_MATERIALS = tuple(
    SolidMaterial(fill=color, outline=None, shaded=True)
    for color in ((105, 96, 83), (94, 89, 80), (116, 104, 88))
)
ROCK_MATERIAL = SolidMaterial(fill=(91, 87, 80), outline=None, shaded=True)
AVATAR_MATERIAL = SolidMaterial(fill=(246, 202, 91), outline=(42, 30, 22), shaded=True)
ROCK_EDGES = MeshEdgeStyle(color=(43, 39, 34), thickness=-1.0)
BRIDGE_LINE_COLOR = (54, 49, 42)

# Offsets from the dome center, footprint radius, and boulder height.
ROCK_SPECS = (
    (65.0, 70.0, 35.0, 80.0),
    (-110.0, 0.0, 28.0, 45.0),
    (100.0, -30.0, 24.0, 38.0),
    (490 * math.cos(math.radians(60)), 490 * math.sin(math.radians(60)), 26.0, 60.0),
    (500 * math.cos(math.radians(150)), 500 * math.sin(math.radians(150)), 24.0, 55.0),
    (495 * math.cos(math.radians(290)), 495 * math.sin(math.radians(290)), 25.0, 65.0),
)


class FloorCell(NamedTuple):
    mesh: TriangleMesh3D
    walkable: bool


class FloorTriangle(NamedTuple):
    points: tuple[Vec2, Vec2, Vec2]
    bounds: AabbFootprint


def effective_world_flags() -> dict[str, bool]:
    bridges = LAVA_ENABLED and BRIDGES_ENABLED
    secondary = LAVA_ENABLED and SECONDARY_ISLAND_ENABLED
    return {
        "LAVA_ENABLED": LAVA_ENABLED,
        "BRIDGES_ENABLED": bridges,
        "SECONDARY_ISLAND_ENABLED": secondary,
        "SECONDARY_BRIDGE_ENABLED": bridges and secondary and SECONDARY_BRIDGE_ENABLED,
        "BRIDGE_LINES_ENABLED": bridges and BRIDGE_LINES_ENABLED,
        "DOME_ENABLED": DOME_ENABLED,
        "ROCKS_ENABLED": ROCKS_ENABLED,
        "MESH_EDGES_ENABLED": MESH_EDGES_ENABLED and (DOME_ENABLED or ROCKS_ENABLED or LAVA_ENABLED),
    }


def create_road_texture(context: dcg.Context) -> None:
    del context


def validate_geometry() -> None:
    if SECTORS < 24 or LAVA_BANDS < 4 or DOME_RINGS < 3 or ISLAND_RINGS < 4:
        raise ValueError("Volcano cave needs 24 sectors, four lava/island bands, and three dome rings")
    if not 0 < ISLAND_RADIUS < LAVA_OUTER_RADIUS < DOME_RADIUS:
        raise ValueError("Island, lava, and dome radii must be positive and increasing")
    if DOME_RADIUS * 1.05 >= min(WORLD_W, WORLD_H) * 0.5 or DOME_HEIGHT <= AVATAR_HEIGHT:
        raise ValueError("Dome must fit within world bounds and above the avatar")
    if not 0 <= DOME_ROUGHNESS <= 0.15 or not 0 < BRIDGE_HALF_WIDTH_DEG < 45:
        raise ValueError("Invalid dome roughness or bridge width")
    if not (
        LAVA_LEVEL < min(ISLAND_EDGE_HEIGHT, RIM_HEIGHT)
        and max(ISLAND_EDGE_HEIGHT, RIM_HEIGHT) < ISLAND_PEAK_HEIGHT
        and ISLAND_PEAK_HEIGHT + ISLAND_RELIEF < DOME_HEIGHT - AVATAR_HEIGHT
    ):
        raise ValueError("Island and rim must rise above lava and stay below the dome")
    if ISLAND_RELIEF < 0 or BRIDGE_CAMBER < 0 or BRIDGE_ARCH_RISE <= 0:
        raise ValueError("Relief, bridge camber, and arch rise must be nonnegative")
    if not 0 < BRIDGE_ABUTMENT_FRACTION < 0.5 or BRIDGE_BASE_HEIGHT <= LAVA_LEVEL:
        raise ValueError("Bridge abutments and foundations must leave an opening above lava")
    if not 0 < SECONDARY_ISLAND_START < SECONDARY_ISLAND_END < 1:
        raise ValueError("Secondary island must lie within the lava moat")
    if not LAVA_LEVEL < SECONDARY_ISLAND_HEIGHT < ISLAND_PEAK_HEIGHT or SECONDARY_ISLAND_RELIEF < 0:
        raise ValueError("Secondary island must rise above lava and below the main island")
    if not BRIDGE_HALF_WIDTH_DEG < SECONDARY_ISLAND_HALF_WIDTH_DEG < 45:
        raise ValueError("Secondary island must be wider than its bridge")
    if LAVA_ENABLED and SECONDARY_ISLAND_ENABLED and any(
        not math.isclose(value * LAVA_BANDS, round(value * LAVA_BANDS), abs_tol=1e-8)
        for value in (SECONDARY_ISLAND_START, SECONDARY_ISLAND_END)
    ):
        raise ValueError("Secondary island boundaries must align with lava bands")


def radial_profile(angle: float) -> tuple[float, float, float]:
    island = ISLAND_RADIUS * (1 + 0.08 * math.sin(angle * 3) + 0.05 * math.cos(angle * 5))
    lava = LAVA_OUTER_RADIUS * (1 + 0.025 * math.sin(angle * 4) + 0.015 * math.cos(angle * 7))
    outer = DOME_RADIUS * (1 + 0.025 * math.cos(angle * 3) + 0.015 * math.sin(angle * 5))
    if not 0 < island < lava < outer:
        raise ValueError("Irregular radial profile leaves no island, lava moat, or outer rim")
    return island, lava, outer


def polar_point(angle: float, radius: float, z: float = 0.0) -> Vec3:
    return CENTER[0] + radius * math.cos(angle), CENTER[1] + radius * math.sin(angle), z


def radial_rings(angle: float) -> tuple[float, ...]:
    island, lava, outer = radial_profile(angle)
    return (
        *(island * ring / ISLAND_RINGS for ring in range(ISLAND_RINGS + 1)),
        *(island + (lava - island) * band / LAVA_BANDS for band in range(1, LAVA_BANDS + 1)),
        lava + (outer - lava) * 0.45, outer,
    )


def island_height(angle: float, radius: float) -> float:
    u = radius / radial_profile(angle)[0]
    ridge = 4 * ISLAND_RELIEF * u * (1 - u) * (0.65 * math.sin(angle * 2) + 0.35 * math.cos(angle * 3))
    return ISLAND_EDGE_HEIGHT + (ISLAND_PEAK_HEIGHT - ISLAND_EDGE_HEIGHT) * (1 - u ** 1.5) + ridge


def bridge_fraction(angle: float, radius: float) -> float:
    island, lava, _outer = radial_profile(angle)
    return max(0.0, min(1.0, (radius - island) / (lava - island)))


def bridge_deck_height(u: float, *, cambered: bool = True, secondary: bool = False) -> float:
    end = SECONDARY_ISLAND_HEIGHT if secondary else RIM_HEIGHT
    camber = SECONDARY_BRIDGE_CAMBER if secondary else BRIDGE_CAMBER
    return ISLAND_EDGE_HEIGHT * (1 - u) + end * u + (camber * math.sin(math.pi * u) if cambered else 0.0)


def bridge_underside_height(u: float, *, secondary: bool = False) -> float:
    opening = max(0.0, min(1.0, (u - BRIDGE_ABUTMENT_FRACTION) / (1 - 2 * BRIDGE_ABUTMENT_FRACTION)))
    rise = SECONDARY_BRIDGE_ARCH_RISE if secondary else BRIDGE_ARCH_RISE
    return BRIDGE_BASE_HEIGHT + rise * math.sin(math.pi * opening)


def angular_offset(angle_deg: float, axis: float) -> float:
    return (angle_deg - axis + 180) % 360 - 180


def is_secondary_bridge_sector(sector: int) -> bool:
    return (
        effective_world_flags()["SECONDARY_BRIDGE_ENABLED"]
        and abs(angular_offset((sector + 0.5) * 360 / SECTORS, SECONDARY_ISLAND_ANGLE_DEG)) <= BRIDGE_HALF_WIDTH_DEG + 1e-9
    )


def is_secondary_island_cell(sector: int, band: int) -> bool:
    if not effective_world_flags()["SECONDARY_ISLAND_ENABLED"]:
        return False
    offset = abs(angular_offset((sector + 0.5) * 360 / SECTORS, SECONDARY_ISLAND_ANGLE_DEG))
    if offset >= SECONDARY_ISLAND_HALF_WIDTH_DEG:
        return False
    inset = 1.0 / 6.0 if offset > SECONDARY_ISLAND_HALF_WIDTH_DEG * 2 / 3 else 0.0
    u = (band - ISLAND_RINGS + 0.5) / LAVA_BANDS
    return SECONDARY_ISLAND_START + inset <= u <= SECONDARY_ISLAND_END - inset


def secondary_island_height(angle: float, radius: float) -> float:
    u = bridge_fraction(angle, radius)
    t = max(0.0, min(1.0, (u - SECONDARY_ISLAND_START) / (SECONDARY_ISLAND_END - SECONDARY_ISLAND_START)))
    offset = abs(angular_offset(math.degrees(angle), SECONDARY_ISLAND_ANGLE_DEG))
    across = max(0.0, math.cos(math.pi * 0.5 * offset / SECONDARY_ISLAND_HALF_WIDTH_DEG))
    return SECONDARY_ISLAND_HEIGHT + SECONDARY_ISLAND_RELIEF * math.sin(math.pi * t) * across


def floor_height(angle: float, radius: float, band: int, bridge: bool, secondary: bool, secondary_bridge: bool) -> float:
    if band < ISLAND_RINGS:
        return island_height(angle, radius)
    if band < ISLAND_RINGS + LAVA_BANDS:
        if secondary:
            return secondary_island_height(angle, radius)
        u = bridge_fraction(angle, radius)
        return bridge_deck_height(
            u / SECONDARY_ISLAND_START if secondary_bridge else u,
            cambered=bridge, secondary=secondary_bridge,
        )
    _island, lava, outer = radial_profile(angle)
    return RIM_HEIGHT * (outer - radius) / (outer - lava)


def is_bridge_sector(sector: int) -> bool:
    if not (LAVA_ENABLED and BRIDGES_ENABLED):
        return False
    angle = (sector + 0.5) * 360 / SECTORS
    return any(
        abs((angle - axis + 180) % 360 - 180) <= BRIDGE_HALF_WIDTH_DEG + 1e-9
        for axis in BRIDGE_ANGLES_DEG
    )


def build_floor() -> tuple[FloorCell, ...]:
    validate_geometry()
    if LAVA_ENABLED and BRIDGES_ENABLED and not any(is_bridge_sector(sector) for sector in range(SECTORS)):
        raise ValueError("Bridge width is too small for the floor tessellation")
    cells = []
    for sector in range(SECTORS):
        first = math.tau * sector / SECTORS
        second = math.tau * ((sector + 1) % SECTORS) / SECTORS
        radii_a, radii_b = radial_rings(first), radial_rings(second)
        for band in range(len(radii_a) - 1):
            moat = ISLAND_RINGS <= band < ISLAND_RINGS + LAVA_BANDS
            secondary = moat and is_secondary_island_cell(sector, band)
            secondary_bridge = moat and is_secondary_bridge_sector(sector) and (band - ISLAND_RINGS + 1) / LAVA_BANDS <= SECONDARY_ISLAND_START + 1e-9
            bridge = moat and (is_bridge_sector(sector) or secondary_bridge)
            walkable = not LAVA_ENABLED or not moat or bridge or secondary
            if bridge:
                material = BRIDGE_MATERIAL
            elif walkable:
                material = STONE_MATERIALS[(sector * 3 + band) % len(STONE_MATERIALS)]
            elif band in (ISLAND_RINGS, ISLAND_RINGS + LAVA_BANDS - 1):
                material = LAVA_MATERIALS[4 + sector % 2]
            else:
                material = LAVA_MATERIALS[(sector * 3 + band * 7) % 4]
            points = (
                polar_point(first, radii_a[band], floor_height(first, radii_a[band], band, bridge, secondary, secondary_bridge) if walkable else LAVA_LEVEL),
                polar_point(first, radii_a[band + 1], floor_height(first, radii_a[band + 1], band, bridge, secondary, secondary_bridge) if walkable else LAVA_LEVEL),
                polar_point(second, radii_b[band + 1], floor_height(second, radii_b[band + 1], band, bridge, secondary, secondary_bridge) if walkable else LAVA_LEVEL),
                polar_point(second, radii_b[band], floor_height(second, radii_b[band], band, bridge, secondary, secondary_bridge) if walkable else LAVA_LEVEL),
            )
            triangles = tuple(
                triangle for triangle in ((0, 1, 2), (0, 2, 3))
                if len({points[index] for index in triangle}) == 3
            )
            cells.append(FloorCell(TriangleMesh3D(
                vertices=points, triangles=triangles, material=material, cull_back_faces=False,
            ), walkable))
            if bridge:
                cells.append(FloorCell(TriangleMesh3D(
                    vertices=tuple((x, y, LAVA_LEVEL) for x, y, _z in points),
                    triangles=triangles, material=LAVA_MATERIALS[(sector + band) % len(LAVA_MATERIALS)],
                    cull_back_faces=False,
                ), False))
    return tuple(cells)


def terrain_from_cells(cells: tuple[FloorCell, ...]) -> MeshTerrainSurface:
    vertices, triangles = [], []
    for cell in cells:
        if not cell.walkable:
            continue
        base = len(vertices)
        vertices.extend(cell.mesh.vertices)
        triangles.extend(tuple(index + base for index in triangle) for triangle in cell.mesh.triangles)
    return MeshTerrainSurface(vertices=tuple(vertices), triangles=tuple(triangles))


def quad_mesh(points: tuple[Vec3, Vec3, Vec3, Vec3], material: SolidMaterial) -> TriangleMesh3D:
    return TriangleMesh3D(
        vertices=points, triangles=((0, 1, 2), (0, 2, 3)), material=material,
        edges=ROCK_EDGES if MESH_EDGES_ENABLED else None,
    )


def build_bridge_structure(cells: tuple[FloorCell, ...]) -> tuple[TriangleMesh3D, ...]:
    meshes = []
    for cell in cells:
        if not cell.walkable or cell.mesh.material is not BRIDGE_MATERIAL:
            continue
        top = cell.mesh.vertices
        sector = round(math.atan2(top[0][1] - CENTER[1], top[0][0] - CENTER[0]) * SECTORS / math.tau) % SECTORS
        secondary = is_secondary_bridge_sector(sector)
        fractions, bottom = [], []
        for x, y, z in top:
            angle = math.atan2(y - CENTER[1], x - CENTER[0])
            u = bridge_fraction(angle, math.hypot(x - CENTER[0], y - CENTER[1]))
            if secondary:
                u /= SECONDARY_ISLAND_START
            underside = bridge_underside_height(u, secondary=secondary)
            if z - underside < BRIDGE_MIN_THICKNESS:
                raise ValueError("Bridge arch leaves insufficient stone beneath the deck")
            fractions.append(u)
            bottom.append((x, y, underside))
        meshes.append(quad_mesh((bottom[0], bottom[3], bottom[2], bottom[1]), BRIDGE_STRUCTURE_MATERIAL))
        if not (is_bridge_sector((sector - 1) % SECTORS) or is_secondary_bridge_sector((sector - 1) % SECTORS)):
            meshes.append(quad_mesh((top[0], bottom[0], bottom[1], top[1]), BRIDGE_STRUCTURE_MATERIAL))
        if not (is_bridge_sector((sector + 1) % SECTORS) or is_secondary_bridge_sector((sector + 1) % SECTORS)):
            meshes.append(quad_mesh((top[3], top[2], bottom[2], bottom[3]), BRIDGE_STRUCTURE_MATERIAL))
        if fractions[0] < 1e-8:
            meshes.append(quad_mesh((top[0], top[3], bottom[3], bottom[0]), BRIDGE_STRUCTURE_MATERIAL))
        if fractions[1] > 1 - 1e-8:
            meshes.append(quad_mesh((top[1], bottom[1], bottom[2], top[2]), BRIDGE_STRUCTURE_MATERIAL))
    return tuple(meshes)


def build_shore_cliffs(cells: tuple[FloorCell, ...]) -> tuple[TriangleMesh3D, ...]:
    if not LAVA_ENABLED:
        return ()
    edges: dict[frozenset[Vec2], list[tuple[Vec3, Vec3, bool]]] = {}
    for cell in cells:
        if not cell.walkable:
            continue
        for triangle in cell.mesh.triangles:
            points = [cell.mesh.vertices[index] for index in triangle]
            for a, b in zip(points, points[1:] + points[:1]):
                key = frozenset(((a[0], a[1]), (b[0], b[1])))
                edges.setdefault(key, []).append((a, b, cell.mesh.material is BRIDGE_MATERIAL))
    meshes = []
    for shared in edges.values():
        if len(shared) != 1:
            continue
        a, b, bridge = shared[0]
        if bridge or max(a[2], b[2]) <= LAVA_LEVEL + 0.2:
            continue
        meshes.append(quad_mesh((
            (a[0], a[1], LAVA_LEVEL + 0.2), (b[0], b[1], LAVA_LEVEL + 0.2), b, a,
        ), CLIFF_MATERIAL))
    return tuple(meshes)


def build_dome() -> tuple[TriangleMesh3D, ...]:
    validate_geometry()
    meshes = []
    for level in range(DOME_RINGS):
        for sector in range(SECTORS):
            angles = (math.tau * sector / SECTORS, math.tau * ((sector + 1) % SECTORS) / SECTORS)

            def point(ring: int, angle: float) -> Vec3:
                tilt = math.pi * 0.5 * (1 - ring / DOME_RINGS)
                radius = radial_profile(angle)[2] * math.sin(tilt)
                z = 0.0 if ring == 0 else DOME_HEIGHT * math.cos(tilt) * (
                    1 + DOME_ROUGHNESS * math.sin(tilt) * math.sin(angle * 3 + ring * 1.31)
                )
                return polar_point(angle, radius, z)

            if level == DOME_RINGS - 1:
                points = (point(level, angles[0]), point(level, angles[1]), (*CENTER, DOME_HEIGHT))
                triangles = ((0, 2, 1),)
            else:
                points = (point(level, angles[0]), point(level, angles[1]),
                          point(level + 1, angles[1]), point(level + 1, angles[0]))
                triangles = ((0, 2, 1), (0, 3, 2))
            meshes.append(TriangleMesh3D(
                vertices=points, triangles=triangles,
                material=DOME_MATERIALS[(sector + level) % len(DOME_MATERIALS)],
                edges=ROCK_EDGES if MESH_EDGES_ENABLED else None,
            ))
    return tuple(meshes)


def terrain_edge_parameters(a: Vec3, b: Vec3, terrain: MeshTerrainSurface) -> tuple[float, ...]:
    direction = (b[0] - a[0], b[1] - a[1])
    parameters = {0.0, 1.0}
    for triangle in terrain.triangles:
        points = [terrain.vertices[index] for index in triangle]
        if (
            max(p[0] for p in points) < min(a[0], b[0]) or min(p[0] for p in points) > max(a[0], b[0])
            or max(p[1] for p in points) < min(a[1], b[1]) or min(p[1] for p in points) > max(a[1], b[1])
        ):
            continue
        for c, d in zip(points, points[1:] + points[:1]):
            edge = (d[0] - c[0], d[1] - c[1])
            offset = (c[0] - a[0], c[1] - a[1])
            denominator = direction[0] * edge[1] - direction[1] * edge[0]
            if abs(denominator) < 1e-10:
                if abs(offset[0] * direction[1] - offset[1] * direction[0]) < 1e-8:
                    squared = direction[0] ** 2 + direction[1] ** 2
                    for p in (c, d):
                        t = ((p[0] - a[0]) * direction[0] + (p[1] - a[1]) * direction[1]) / squared
                        if 0 < t < 1:
                            parameters.add(round(t, 12))
                continue
            t = (offset[0] * edge[1] - offset[1] * edge[0]) / denominator
            u = (offset[0] * direction[1] - offset[1] * direction[0]) / denominator
            if 0 < t < 1 and -1e-9 <= u <= 1 + 1e-9:
                parameters.add(round(t, 12))
    return tuple(sorted(parameters))


def rock_mesh(dx: float, dy: float, radius: float, height: float, terrain: MeshTerrainSurface | None = None) -> TriangleMesh3D:
    if radius <= 0 or height <= 0:
        raise ValueError("Basalt boulders need positive radius and height")
    surface = build_terrain_surface() if terrain is None else terrain
    rings: list[list[Vec3]] = [[], []]
    for level in (0, 1):
        for index in range(8):
            angle = math.tau * index / 8
            width = radius * (1 + 0.08 * math.sin(index * 2.17)) * (1 - level * 0.4)
            x, y = CENTER[0] + dx + width * math.cos(angle), CENTER[1] + dy + width * math.sin(angle)
            support = surface.sample(x, y)
            if support is None:
                raise ValueError("Basalt boulder must lie entirely on dry terrain")
            rings[level].append((x, y, support.height + 0.2 + level * height * (0.68 + 0.04 * math.sin(index * 1.83))))
    bottom: list[Vec3] = []
    top: list[Vec3] = []
    for index in range(8):
        a, b = rings[0][index], rings[0][(index + 1) % 8]
        c, d = rings[1][index], rings[1][(index + 1) % 8]
        # Split at every terrain triangle crossing so the contact edge follows
        # the piecewise-planar terrain exactly, rather than cutting through ridges.
        for t in terrain_edge_parameters(a, b, surface)[:-1]:
            x, y = a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t
            support = surface.sample(x, y)
            if support is None:
                raise ValueError("Basalt boulder contact edge leaves dry terrain")
            bottom.append((x, y, support.height + 0.2))
            top.append((c[0] * (1 - t) + d[0] * t, c[1] * (1 - t) + d[1] * t, c[2] * (1 - t) + d[2] * t))
    segments = len(bottom)
    vertices = bottom + top
    tip = len(vertices)
    x, y = CENTER[0] + dx + radius * 0.15, CENTER[1] + dy - radius * 0.15
    support = surface.sample(x, y)
    if support is None:
        raise ValueError("Basalt boulder tip must lie above dry terrain")
    vertices.append((x, y, support.height + height + 0.2))
    triangles = []
    for index in range(segments):
        next_index = (index + 1) % segments
        triangles.extend(((index, next_index, segments + next_index),
                          (index, segments + next_index, segments + index),
                          (segments + index, segments + next_index, tip)))
    return TriangleMesh3D(
        vertices=tuple(vertices), triangles=tuple(triangles), material=ROCK_MATERIAL,
        edges=ROCK_EDGES if MESH_EDGES_ENABLED else None,
    )


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    del road_texture
    scene = Scene3D(background=BACKGROUND_COLOR)
    cells = build_floor()
    terrain = terrain_from_cells(cells)
    for cell in cells:
        scene.add(cell.mesh)
    for mesh in (*build_shore_cliffs(cells), *build_bridge_structure(cells)):
        scene.add(mesh)
    if DOME_ENABLED:
        for mesh in build_dome():
            scene.add(mesh)
    if ROCKS_ENABLED:
        for spec in ROCK_SPECS:
            scene.add(rock_mesh(*spec, terrain=terrain))
    if effective_world_flags()["BRIDGE_LINES_ENABLED"]:
        axes = (*BRIDGE_ANGLES_DEG, SECONDARY_ISLAND_ANGLE_DEG) if effective_world_flags()["SECONDARY_BRIDGE_ENABLED"] else BRIDGE_ANGLES_DEG
        for axis in axes:
            for index in range(LAVA_BANDS * 2):
                fraction = (index + 0.5) / (LAVA_BANDS * 2)
                points = []
                for side in (-1, 1):
                    angle = math.radians(axis + side * BRIDGE_HALF_WIDTH_DEG * 0.8)
                    island, lava, _outer = radial_profile(angle)
                    length = SECONDARY_ISLAND_START if axis == SECONDARY_ISLAND_ANGLE_DEG else 1.0
                    x, y, _z = polar_point(angle, island + (lava - island) * fraction * length)
                    support = terrain.sample(x, y)
                    if support is None:
                        raise ValueError("Bridge lines must lie over a traversable deck")
                    points.append((x, y, support.height + 0.2))
                a, b = points
                stripe = []
                for t in terrain_edge_parameters(a, b, terrain):
                    x, y = a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t
                    support = terrain.sample(x, y)
                    if support is None:
                        raise ValueError("Bridge stripe leaves the traversable deck")
                    stripe.append((x, y, support.height + 0.2))
                for start, end in zip(stripe, stripe[1:]):
                    scene.add(Line3D(start=start, end=end, color=BRIDGE_LINE_COLOR, thickness=-1.0))
    support = terrain.sample(*AVATAR_START_XY)
    if support is None:
        raise ValueError("Player start must be on dry terrain")
    avatar = Box3D(center=(*AVATAR_START_XY, support.height), size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT), material=AVATAR_MATERIAL)
    scene.add(avatar)
    return scene, avatar


class VolcanoCollisionWorld(CollisionWorld):
    """Require the entire player footprint to be covered by disjoint dry tiles."""

    def __init__(self, cells: tuple[FloorCell, ...]) -> None:
        super().__init__(gap=COLLISION_GAP)
        self.boundary = Collider("lava / cave perimeter", AabbFootprint(0, 0, WORLD_W, WORLD_H), TraversalRole.BOUNDARY)
        triangles = []
        for cell in cells:
            if not cell.walkable:
                continue
            for indices in cell.mesh.triangles:
                a, b, c = (cell.mesh.vertices[index] for index in indices)
                points = ((a[0], a[1]), (b[0], b[1]), (c[0], c[1]))
                triangles.append(FloorTriangle(points, AabbFootprint(
                    min(p[0] for p in points), min(p[1] for p in points),
                    max(p[0] for p in points), max(p[1] for p in points),
                )))
        self.floor_triangles = tuple(triangles)
        self.terrain = terrain_from_cells(cells)
        self.add("volcano walking surface", self.boundary.shape, role=TraversalRole.TRAVERSABLE, terrain=self.terrain)

    def first_blocker(self, candidate: CollisionShape2D, *, ignore: object | None = None) -> Collider | None:
        if not isinstance(candidate, AabbFootprint):
            raise TypeError("Volcano cave movement requires an AABB player footprint")
        rectangle = AabbFootprint(
            candidate.min_x - self.gap, candidate.min_y - self.gap,
            candidate.max_x + self.gap, candidate.max_y + self.gap,
        )
        viewport = Viewport(rectangle.max_x - rectangle.min_x, rectangle.max_y - rectangle.min_y)
        area = 0.0
        for triangle in self.floor_triangles:
            if not rectangle.conflicts(triangle.bounds):
                continue
            polygon = clip_polygon_to_viewport(
                [(x - rectangle.min_x, y - rectangle.min_y) for x, y in triangle.points], viewport,
            )
            if polygon:
                area += abs(sum(
                    a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1])
                )) * 0.5
        # Tiles do not overlap, so equal clipped area proves full containment,
        # including a lava gap between corners or several joined bridge tiles.
        if abs(area - viewport.width * viewport.height) > 1e-6:
            return self.boundary
        return super().first_blocker(candidate, ignore=ignore)


def build_collision_world() -> VolcanoCollisionWorld:
    collisions = VolcanoCollisionWorld(build_floor())
    if ROCKS_ENABLED:
        for index, spec in enumerate(ROCK_SPECS):
            points = rock_mesh(*spec, terrain=collisions.terrain).vertices
            footprint = AabbFootprint(
                min(p[0] for p in points), min(p[1] for p in points),
                max(p[0] for p in points), max(p[1] for p in points),
            )
            if collisions.first_blocker(footprint) is not None:
                raise ValueError(f"Basalt boulder {index + 1} overlaps lava, the perimeter, or another boulder")
            collisions.add(f"basalt boulder {index + 1}", footprint)
    if collisions.first_blocker(AabbFootprint.from_center(*AVATAR_START_XY, AVATAR_SIZE, AVATAR_SIZE)) is not None:
        raise ValueError("Player start must be on unobstructed dry floor")
    return collisions


def build_terrain_surface() -> MeshTerrainSurface:
    return terrain_from_cells(build_floor())


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(
        mode=TerrainMode.FOLLOW_SURFACE, fallback_ground_z=LAVA_LEVEL,
        max_slope_degrees=MAX_SLOPE_DEGREES, out_of_bounds_policy=OutOfBoundsPolicy.REJECT,
    )
