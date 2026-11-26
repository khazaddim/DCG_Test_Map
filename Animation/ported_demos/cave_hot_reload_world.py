"""One oversized, open-ended cave passage for clipping and CPU profiling.

The floor is flat; only the wall/ceiling shell is irregular. Inward-facing
triangles show the interior, not an opaque exterior roof. The default camera
fits inside the passage; near-plane and viewport clipping trim nearby rock.
Edit the dimensions, tessellation, materials, or flags and press Reload world.
"""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Box3D,
    CollisionWorld,
    GroundPlane3D,
    MeshEdgeStyle,
    Scene3D,
    SolidMaterial,
    TerrainMode,
    TriangleMesh3D,
    TraversalRole,
    TraversalSettings,
)


WORLD_W = 1800.0
WORLD_H = 600.0
CAVE_HALF_WIDTH = 220.0
CAVE_HEIGHT = 320.0
LENGTH_SEGMENTS = 60
ARCH_SEGMENTS = 12
ROCK_ROUGHNESS = 0.09
GRID_STEP = 12.0
AVATAR_SIZE = 8.0
AVATAR_HEIGHT = 12.0
AVATAR_START_XY = (WORLD_W * 0.5, WORLD_H * 0.5)
COLLISION_GAP = 1.0

WALLS_ENABLED = True
CEILING_ENABLED = True
MESH_EDGES_ENABLED = False

FLOOR_MATERIAL = SolidMaterial(fill=(94, 85, 73), outline=None, shaded=False)
WALL_MATERIAL = SolidMaterial(fill=(139, 126, 108), outline=None, shaded=True)
CEILING_MATERIAL = SolidMaterial(fill=(115, 109, 103), outline=None, shaded=True)
AVATAR_MATERIAL = SolidMaterial(fill=(244, 190, 65), outline=(49, 35, 24), shaded=True)
ROCK_EDGES = MeshEdgeStyle(color=(47, 43, 39), thickness=-1.0)


def effective_world_flags() -> dict[str, bool]:
    return {
        "WALLS_ENABLED": WALLS_ENABLED,
        "CEILING_ENABLED": CEILING_ENABLED,
        "MESH_EDGES_ENABLED": MESH_EDGES_ENABLED and (WALLS_ENABLED or CEILING_ENABLED),
    }


def floor_bounds() -> tuple[float, float, float, float]:
    return (0.0, WORLD_H * 0.5 - CAVE_HALF_WIDTH, WORLD_W, WORLD_H * 0.5 + CAVE_HALF_WIDTH)


def create_road_texture(context: dcg.Context) -> None:
    """The shared host's resource hook; this solid-color world needs no texture."""
    del context


def cave_rings() -> tuple[tuple[tuple[float, float, float], ...], ...]:
    if LENGTH_SEGMENTS < 1 or ARCH_SEGMENTS < 4:
        raise ValueError("Cave needs at least one length segment and four arch segments")
    if not (WORLD_W > 0 and 0 < CAVE_HALF_WIDTH < WORLD_H * 0.5 and CAVE_HEIGHT > AVATAR_HEIGHT):
        raise ValueError("Cave dimensions must contain a positive-width floor and avatar headroom")
    if not 0 <= ROCK_ROUGHNESS <= 0.2:
        raise ValueError("ROCK_ROUGHNESS must be between 0 and 0.2")
    rings = []
    for station in range(LENGTH_SEGMENTS + 1):
        x = WORLD_W * station / LENGTH_SEGMENTS
        ring = []
        for arc in range(ARCH_SEGMENTS + 1):
            angle = math.pi * arc / ARCH_SEGMENTS
            if arc in (0, ARCH_SEGMENTS):
                y = WORLD_H * 0.5 + (-CAVE_HALF_WIDTH if arc == 0 else CAVE_HALF_WIDTH)
                ring.append((x, y, 0.0))
                continue
            roughness = ROCK_ROUGHNESS * (
                0.55 * math.sin(station * 1.73 + arc * 2.31)
                + 0.30 * math.sin(station * 0.47 - arc * 1.19)
                + 0.15 * math.cos(station * 2.57 + arc * 0.83)
            )
            y = WORLD_H * 0.5 - CAVE_HALF_WIDTH * math.cos(angle) * (1.0 + roughness)
            z = CAVE_HEIGHT * math.sin(angle) * (1.0 + roughness)
            ring.append((x, y, z))
        rings.append(tuple(ring))
    return tuple(rings)


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    del road_texture
    rings = cave_rings()
    scene = Scene3D()
    _x0, y0, _x1, y1 = floor_bounds()
    for station in range(LENGTH_SEGMENTS):
        x0, x1 = rings[station][0][0], rings[station + 1][0][0]
        scene.add(GroundPlane3D(bounds=(x0, y0, x1, y1), z=0.0, material=FLOOR_MATERIAL))
        for arc in range(ARCH_SEGMENTS):
            ceiling = ARCH_SEGMENTS / 3 <= arc < ARCH_SEGMENTS * 2 / 3
            if not (CEILING_ENABLED if ceiling else WALLS_ENABLED):
                continue
            # Each patch shares ring vertices with its neighbors; winding faces inward.
            scene.add(TriangleMesh3D(
                vertices=(rings[station][arc], rings[station + 1][arc],
                          rings[station + 1][arc + 1], rings[station][arc + 1]),
                triangles=((0, 2, 1), (0, 3, 2)),
                material=CEILING_MATERIAL if ceiling else WALL_MATERIAL,
                edges=ROCK_EDGES if MESH_EDGES_ENABLED else None,
                cull_back_faces=True,
            ))
    avatar = Box3D(
        center=(*AVATAR_START_XY, 0.0),
        size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT),
        material=AVATAR_MATERIAL,
    )
    scene.add(avatar)
    return scene, avatar


def build_collision_world() -> CollisionWorld:
    collisions = CollisionWorld(gap=COLLISION_GAP)
    _x0, y0, _x1, y1 = floor_bounds()
    # Floor-edge boundaries remain when rock is hidden for a profiling comparison.
    collisions.add("floor left edge", AabbFootprint(0.0, 0.0, WORLD_W, y0), role=TraversalRole.BOUNDARY)
    collisions.add("floor right edge", AabbFootprint(0.0, y1, WORLD_W, WORLD_H), role=TraversalRole.BOUNDARY)
    return collisions


def build_terrain_surface() -> None:
    return None


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(mode=TerrainMode.FLAT, fallback_ground_z=0.0)
