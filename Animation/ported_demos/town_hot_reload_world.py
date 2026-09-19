"""Reloadable world definition for the town hot-reload experiment."""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    AnimatedImageMaterial,
    AnimationProjection,
    Billboard3D,
    BillboardFacing,
    Box3D,
    CollisionWorld,
    GroundPlane3D,
    ImageMaterial,
    Line3D,
    LineRenderLayer,
    MeshEdgeStyle,
    MeshTerrainSurface,
    OutOfBoundsPolicy,
    Polyline3D,
    Scene3D,
    SolidMaterial,
    TerrainMode,
    Text3D,
    TriangleMesh3D,
    TraversalRole,
    TraversalSettings,
)


WORLD_W = 150.0
WORLD_H = 150.0
GRID_STEP = 5
MAJOR_GRID_STEP = 25
AVATAR_SIZE = 5.0
AVATAR_HEIGHT = 6.0
GROUND_PAD = 200.0
ROAD_WIDTH = 30.0
ROAD_SEGMENT_LENGTH = 15.0
ROAD_TEXTURE_SIZE = (64, 512)
ROAD_TEXTURE_ENABLED = False
POSITION_LABELS_ENABLED = False
HILL_ENABLED = True
TERRAIN_FOLLOWING_ENABLED = True
BOULDER_ENABLED = True
TOWER_ENABLED = True
ARCH_ENABLED = False
FLOATING_ISLAND_ENABLED = False
COLLISION_GAP = 2.0
HILL_CORNER = (150.0, 150.0)
HILL_EXTENT = (30.0, 50.0)
HILL_HEIGHT = 16.0
HILL_MAX_SLOPE_DEGREES = 38.0

SKY_COLOR = (23, 29, 34)
GROUND_COLOR = (78, 116, 76)
ROAD_COLOR = (112, 79, 52)
GRID_MAJOR_COLOR = (126, 142, 150)
GRID_MINOR_COLOR = (108, 140, 96)
LABEL_COLOR = (210, 218, 211)
BORDER_COLOR = (178, 146, 88)
HILL_GRID_MAJOR_COLOR = (176, 182, 178)
HILL_GRID_MINOR_COLOR = (138, 148, 141)
HILL_MATERIAL = SolidMaterial(fill=(92, 132, 82), outline=None, thickness=-1.0, shaded=True)
BOULDER_MATERIAL = SolidMaterial(fill=(116, 119, 116), outline=(58, 62, 60), thickness=-1.0, shaded=True)
BOULDER_EDGES = MeshEdgeStyle(color=(72, 76, 74), thickness=-1.0)
HOUSE_WALL_MATERIAL = SolidMaterial(fill=(146, 154, 150), outline=(54, 62, 66), thickness=-1.0)
GABLE_ROOF_MATERIAL = SolidMaterial(fill=(178, 76, 54), outline=(74, 43, 36), thickness=-1.0)
HIP_ROOF_MATERIAL = SolidMaterial(fill=(67, 112, 139), outline=(27, 50, 65), thickness=-1.0)
ROOF_EDGES = MeshEdgeStyle(color=(34, 38, 40, 155), thickness=-1.0)
ARCH_MATERIAL = SolidMaterial(fill=(184, 164, 126), outline=(92, 76, 56), thickness=-1.0, shaded=True)
HOUSE_SPECS = (
    ((35.0, 30.0), (20.0, 18.0), 12.0, "gable"),
    ((115.0, 48.0), (18.0, 22.0), 14.0, "hip"),
    ((35.0, 95.0), (22.0, 16.0), 13.0, "hip"),
)
BOULDER_CENTER = (96.0, 75.0)
BOULDER_SIZE = (2.0, 3.5)
BOULDER_HEIGHT = 4.5
BOULDER_COLLISION_SCALE = 0.7
ARCH_Y = 75.0
ARCH_PILLAR_WIDTH = 5.0
ARCH_PILLAR_DEPTH = 4.0
ARCH_PILLAR_HEIGHT = 20.0
TOWER_CENTER = (100.0, 125.0)
TOWER_SIZE = (18.0, 18.0)
TOWER_HEIGHT = 34.0
TOWER_ROOF_HEIGHT = 9.0
TOWER_SIDES = 10
WINDMILL_FRAME_COUNT = 12
WINDMILL_LOOP_SECONDS = 2.4
WINDMILL_BITMAP_SIZE = 96
WINDMILL_WORLD_SIZE = (18.0, 18.0)
TOWER_WALL_MATERIAL = SolidMaterial(fill=(112, 126, 137), outline=(43, 52, 58), thickness=-1.0, shaded=True)
TOWER_ROOF_MATERIAL = SolidMaterial(fill=(92, 58, 48), outline=(52, 35, 30), thickness=-1.0, shaded=True)
_WINDMILL_TEXTURES: tuple[dcg.Texture, ...] = ()

# Off-center overhead landmark: floats above the town, not centered over it.
FLOATING_ISLAND_CENTER = (95.0, 55.0)
FLOATING_ISLAND_TOP_Z = 95.0
FLOATING_ISLAND_TOP_RADIUS = 22.0
FLOATING_ISLAND_TAPER_DEPTH = 45.0
FLOATING_ISLAND_RING_COUNT = 5
FLOATING_ISLAND_SEGMENTS = 16
FLOATING_ISLAND_TOP_MATERIAL = SolidMaterial(fill=(88, 142, 74), outline=None, thickness=-1.0, shaded=True)
FLOATING_ISLAND_ROCK_MATERIAL = SolidMaterial(fill=(122, 118, 110), outline=(56, 53, 48), thickness=-1.0, shaded=True)
FLOATING_ISLAND_ROCK_EDGES = MeshEdgeStyle(color=(54, 51, 46, 150), thickness=-1.0)
FLOATING_ISLAND_TRUNK_MATERIAL = SolidMaterial(fill=(96, 66, 42), outline=(46, 34, 24), thickness=-1.0, shaded=True)
FLOATING_ISLAND_CANOPY_MATERIAL = SolidMaterial(fill=(52, 108, 58), outline=(28, 58, 34), thickness=-1.0, shaded=True)
FLOATING_ISLAND_TREE_SIDES = 8
# (offset_x, offset_y, trunk_height, canopy_height, canopy_radius) relative to the island center.
FLOATING_ISLAND_TREE_SPECS = (
    (-9.0, 4.0, 5.0, 9.0, 3.4),
    (-4.0, 9.0, 6.0, 10.0, 3.8),
    (2.0, 7.0, 5.5, 9.5, 3.6),
    (7.0, 2.0, 6.5, 11.0, 4.0),
    (9.0, -6.0, 5.0, 9.0, 3.2),
    (-2.0, -8.0, 6.0, 10.0, 3.7),
    (4.0, -3.0, 5.0, 9.0, 3.3),
)
AVATAR_START_XY = (126.0, 112.5)


def add_gable_house(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], height: float) -> None:
    width, depth = size
    x0, x1 = center[0] - width * 0.5, center[0] + width * 0.5
    y0, y1 = center[1] - depth * 0.5, center[1] + depth * 0.5
    ridge_z = height + 7.0
    scene.add(Box3D(center=(center[0], center[1], 0.0), size=(width, depth, height), material=HOUSE_WALL_MATERIAL))
    scene.add(
        TriangleMesh3D(
            vertices=((x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height), (x0, center[1], ridge_z), (x1, center[1], ridge_z)),
            triangles=((0, 1, 5), (0, 5, 4), (3, 5, 2), (3, 4, 5), (0, 4, 3), (1, 2, 5)),
            material=GABLE_ROOF_MATERIAL,
            edges=ROOF_EDGES,
        )
    )


def add_hip_house(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], height: float) -> None:
    width, depth = size
    x0, x1 = center[0] - width * 0.5, center[0] + width * 0.5
    y0, y1 = center[1] - depth * 0.5, center[1] + depth * 0.5
    ridge_z = height + 6.0
    scene.add(Box3D(center=(center[0], center[1], 0.0), size=(width, depth, height), material=HOUSE_WALL_MATERIAL))
    scene.add(
        TriangleMesh3D(
            vertices=((x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height), (center[0] - width * 0.22, center[1], ridge_z), (center[0] + width * 0.22, center[1], ridge_z)),
            triangles=((0, 1, 5), (0, 5, 4), (1, 2, 5), (2, 3, 4), (2, 4, 5), (3, 0, 4)),
            material=HIP_ROOF_MATERIAL,
            edges=ROOF_EDGES,
        )
    )


def add_tower(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], height: float, roof_height: float) -> None:
    width, depth = size
    radius_x, radius_y = width * 0.5, depth * 0.5
    angles = tuple(2.0 * math.pi * index / TOWER_SIDES for index in range(TOWER_SIDES))
    bottom_ring = tuple(
        (center[0] + radius_x * math.cos(angle), center[1] + radius_y * math.sin(angle), 0.0)
        for angle in angles
    )
    top_ring = tuple((x, y, height) for x, y, _z in bottom_ring)
    side_triangles = []
    for index in range(TOWER_SIDES):
        next_index = (index + 1) % TOWER_SIDES
        side_triangles.extend(
            (
                (index, next_index, TOWER_SIDES + next_index),
                (index, TOWER_SIDES + next_index, TOWER_SIDES + index),
            )
        )
    scene.add(
        TriangleMesh3D(
            vertices=bottom_ring + top_ring,
            triangles=tuple(side_triangles),
            material=TOWER_WALL_MATERIAL,
            edges=ROOF_EDGES,
            cull_back_faces=False,
        )
    )
    roof_apex_index = TOWER_SIDES
    scene.add(
        TriangleMesh3D(
            vertices=top_ring + ((center[0], center[1], height + roof_height),),
            triangles=tuple(
                (index, (index + 1) % TOWER_SIDES, roof_apex_index)
                for index in range(TOWER_SIDES)
            ),
            material=TOWER_ROOF_MATERIAL,
            edges=ROOF_EDGES,
            cull_back_faces=False,
        )
    )


def add_arch(scene: Scene3D) -> None:
    """Add a shallow extruded arch over the road."""
    front_y = ARCH_Y - 4.0
    back_y = ARCH_Y + 4.0
    outer = ((58.0, 20.0), (58.0, 32.0), (92.0, 32.0), (92.0, 20.0))
    inner = ((63.0, 20.0), (69.0, 27.0), (81.0, 27.0), (87.0, 20.0))
    vertices = []
    triangles = []

    def add_face(corners: tuple[tuple[float, float], ...], y: float, reverse: bool = False) -> None:
        start = len(vertices)
        face = tuple(reversed(corners)) if reverse else corners
        vertices.extend((x, y, z) for x, z in face)
        triangles.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))

    def add_depth_face(start_point: tuple[float, float], end_point: tuple[float, float]) -> None:
        start = len(vertices)
        vertices.extend(
            (
                (start_point[0], front_y, start_point[1]),
                (end_point[0], front_y, end_point[1]),
                (end_point[0], back_y, end_point[1]),
                (start_point[0], back_y, start_point[1]),
            )
        )
        triangles.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))

    sections = [
        ((58.0, 0.0), (63.0, 0.0), (63.0, 20.0), (58.0, 20.0)),
        ((87.0, 0.0), (92.0, 0.0), (92.0, 20.0), (87.0, 20.0)),
    ]
    for index in range(4):
        if index < 3:
            sections.append((outer[index], outer[index + 1], inner[index + 1], inner[index]))
    for section in sections:
        add_face(section, front_y)
        add_face(section, back_y, reverse=True)
    for start_point, end_point in (
        ((58.0, 0.0), (58.0, 20.0)),
        ((58.0, 20.0), (58.0, 32.0)),
        ((58.0, 32.0), (92.0, 32.0)),
        ((92.0, 32.0), (92.0, 20.0)),
        ((92.0, 20.0), (92.0, 0.0)),
        ((63.0, 0.0), (63.0, 20.0)),
        ((63.0, 20.0), (69.0, 27.0)),
        ((69.0, 27.0), (81.0, 27.0)),
        ((81.0, 27.0), (87.0, 20.0)),
        ((87.0, 20.0), (87.0, 0.0)),
        ((58.0, 0.0), (63.0, 0.0)),
        ((87.0, 0.0), (92.0, 0.0)),
    ):
        add_depth_face(start_point, end_point)
    top_start = len(vertices)
    vertices.extend(
        (
            (58.0, front_y, 32.0),
            (92.0, front_y, 32.0),
            (92.0, back_y, 32.0),
            (58.0, back_y, 32.0),
        )
    )
    triangles.extend(((top_start, top_start + 1, top_start + 2), (top_start, top_start + 2, top_start + 3)))
    scene.add(
        TriangleMesh3D(
            vertices=tuple(vertices),
            triangles=tuple(triangles),
            material=ARCH_MATERIAL,
            cull_back_faces=False,
        )
    )


def create_windmill_textures(context: dcg.Context) -> tuple[dcg.Texture, ...]:
    global _WINDMILL_TEXTURES
    textures = []
    center = (WINDMILL_BITMAP_SIZE - 1) * 0.5
    for frame_index in range(WINDMILL_FRAME_COUNT):
        phase = frame_index * 2.0 * math.pi / WINDMILL_FRAME_COUNT
        pixels = bytearray(WINDMILL_BITMAP_SIZE * WINDMILL_BITMAP_SIZE * 4)
        for y in range(WINDMILL_BITMAP_SIZE):
            for x in range(WINDMILL_BITMAP_SIZE):
                dx, dy = x - center, y - center
                color = None
                for blade_index in range(4):
                    angle = phase + blade_index * math.pi * 0.5
                    along = dx * math.cos(angle) + dy * math.sin(angle)
                    across = abs(-dx * math.sin(angle) + dy * math.cos(angle))
                    blade_width = 3.8 - max(0.0, along - 9.0) * 0.035
                    if 7.0 <= along <= 39.0 and across <= blade_width:
                        color = (224, 190, 92, 255)
                        break
                if dx * dx + dy * dy <= 7.0 * 7.0:
                    color = (74, 57, 43, 255)
                if color is not None:
                    offset = (y * WINDMILL_BITMAP_SIZE + x) * 4
                    pixels[offset:offset + 4] = bytes(color)
        texture = dcg.Texture(context)
        texture.nearest_neighbor_upsampling = True
        texture.set_value(memoryview(pixels).cast("B", shape=(WINDMILL_BITMAP_SIZE, WINDMILL_BITMAP_SIZE, 4)))
        textures.append(texture)
    _WINDMILL_TEXTURES = tuple(textures)
    return _WINDMILL_TEXTURES


def add_boulder(scene: Scene3D, center: tuple[float, float], size: tuple[float, float], height: float) -> None:
    size_x, size_y = size
    bottom_ring = tuple(
        (
            center[0] + size_x * radius_x * math.cos(angle),
            center[1] + size_y * radius_y * math.sin(angle),
            0.1,
        )
        for angle, radius_x, radius_y in (
            (0.0, 1.00, 0.86),
            (0.78, 0.92, 1.00),
            (1.57, 0.78, 0.95),
            (2.35, 1.00, 0.82),
            (3.14, 0.88, 1.00),
            (3.92, 1.00, 0.90),
            (4.71, 0.82, 1.00),
            (5.49, 0.94, 0.84),
        )
    )
    shoulder_ring = tuple(
        (
            center[0] + size_x * radius_x * math.cos(angle),
            center[1] + size_y * radius_y * math.sin(angle),
            shoulder_height,
        )
        for (angle, radius_x, radius_y), shoulder_height in zip(
            (
                (0.0, 0.88, 0.72),
                (0.78, 0.78, 0.86),
                (1.57, 0.68, 0.80),
                (2.35, 0.84, 0.70),
                (3.14, 0.74, 0.84),
                (3.92, 0.86, 0.76),
                (4.71, 0.70, 0.84),
                (5.49, 0.80, 0.72),
            ),
            (height * 0.52, height * 0.64, height * 0.58, height * 0.70, height * 0.55, height * 0.62, height * 0.68, height * 0.57),
        )
    )
    vertices = bottom_ring + shoulder_ring + ((center[0] + size_x * 0.12, center[1] - size_y * 0.08, height),)
    triangles = []
    for index in range(8):
        next_index = (index + 1) % 8
        triangles.extend(
            (
                (index, next_index, 8 + next_index),
                (index, 8 + next_index, 8 + index),
                (8 + index, 8 + next_index, 16),
            )
        )
    scene.add(
        TriangleMesh3D(
            vertices=vertices,
            triangles=tuple(triangles),
            material=BOULDER_MATERIAL,
            edges=BOULDER_EDGES,
            cull_back_faces=False,
        )
    )


def add_floating_island_tree(
    scene: Scene3D,
    position: tuple[float, float, float],
    trunk_height: float,
    canopy_height: float,
    canopy_radius: float,
) -> None:
    """Box trunk plus a fanned cone canopy, following add_tower's roof-fan pattern."""
    x, y, base_z = position
    trunk_top = base_z + trunk_height
    scene.add(
        Box3D(
            center=(x, y, base_z),
            size=(1.6, 1.6, trunk_height),
            material=FLOATING_ISLAND_TRUNK_MATERIAL,
        )
    )
    sides = FLOATING_ISLAND_TREE_SIDES
    angles = tuple(2.0 * math.pi * index / sides for index in range(sides))
    base_ring = tuple((x + canopy_radius * math.cos(angle), y + canopy_radius * math.sin(angle), trunk_top) for angle in angles)
    apex_index = sides
    scene.add(
        TriangleMesh3D(
            vertices=base_ring + ((x, y, trunk_top + canopy_height),),
            triangles=tuple((index, (index + 1) % sides, apex_index) for index in range(sides)),
            material=FLOATING_ISLAND_CANOPY_MATERIAL,
            cull_back_faces=False,
        )
    )


def add_floating_island(
    scene: Scene3D,
    center: tuple[float, float],
    top_z: float,
    top_radius: float,
    taper_depth: float,
    ring_count: int,
    segments: int,
) -> None:
    """A rocky spire that tapers to a point below a grassy plateau, hovering above the town."""
    cx, cy = center
    angles = tuple(2.0 * math.pi * index / segments for index in range(segments))

    def jitter(angle: float, t: float) -> float:
        # Jitter fades to zero near the bottom so the spire closes to a clean point.
        return 1.0 + (1.0 - t) * (0.14 * math.sin(3.0 * angle + 0.6) + 0.08 * math.sin(7.0 * angle + 2.3))

    def radius_at(t: float) -> float:
        return top_radius * (1.0 - t) ** 1.5

    rings = []
    for ring_index in range(ring_count):
        t = ring_index / ring_count
        z = top_z - t * taper_depth
        radius = radius_at(t)
        rings.append(tuple((cx + radius * jitter(angle, t) * math.cos(angle), cy + radius * jitter(angle, t) * math.sin(angle), z) for angle in angles))

    side_vertices: list[tuple[float, float, float]] = []
    for ring in rings:
        side_vertices.extend(ring)
    apex_index = len(side_vertices)
    side_vertices.append((cx, cy, top_z - taper_depth))

    side_triangles = []
    for ring_index in range(ring_count - 1):
        base = ring_index * segments
        next_base = (ring_index + 1) * segments
        for segment in range(segments):
            segment_next = (segment + 1) % segments
            side_triangles.extend(
                (
                    (base + segment, base + segment_next, next_base + segment_next),
                    (base + segment, next_base + segment_next, next_base + segment),
                )
            )
    last_base = (ring_count - 1) * segments
    for segment in range(segments):
        segment_next = (segment + 1) % segments
        side_triangles.append((last_base + segment, last_base + segment_next, apex_index))

    scene.add(
        TriangleMesh3D(
            vertices=tuple(side_vertices),
            triangles=tuple(side_triangles),
            material=FLOATING_ISLAND_ROCK_MATERIAL,
            edges=FLOATING_ISLAND_ROCK_EDGES,
            cull_back_faces=False,
        )
    )

    top_ring = rings[0]
    top_center_index = len(top_ring)
    scene.add(
        TriangleMesh3D(
            vertices=top_ring + ((cx, cy, top_z + 1.2),),
            triangles=tuple((segment, (segment + 1) % segments, top_center_index) for segment in range(segments)),
            material=FLOATING_ISLAND_TOP_MATERIAL,
            cull_back_faces=False,
        )
    )

    for offset_x, offset_y, trunk_height, canopy_height, canopy_radius in FLOATING_ISLAND_TREE_SPECS:
        add_floating_island_tree(
            scene,
            position=(cx + offset_x, cy + offset_y, top_z),
            trunk_height=trunk_height,
            canopy_height=canopy_height,
            canopy_radius=canopy_radius,
        )


def build_collision_world() -> CollisionWorld:
    collisions = CollisionWorld(gap=COLLISION_GAP)
    for index, (center, size, _height, _roof_type) in enumerate(HOUSE_SPECS, start=1):
        collisions.add(f"house {index}", AabbFootprint.from_center(center[0], center[1], size[0], size[1]))
    if BOULDER_ENABLED:
        collisions.add(
            "boulder",
            AabbFootprint.from_center(
                BOULDER_CENTER[0],
                BOULDER_CENTER[1],
                BOULDER_SIZE[0] * 2.0 * BOULDER_COLLISION_SCALE,
                BOULDER_SIZE[1] * 2.0 * BOULDER_COLLISION_SCALE,
            ),
        )
    if TOWER_ENABLED:
        collisions.add("tower", AabbFootprint.from_center(TOWER_CENTER[0], TOWER_CENTER[1], TOWER_SIZE[0], TOWER_SIZE[1]))
    if ARCH_ENABLED:
        collisions.add(
            "arch left pillar",
            AabbFootprint.from_center(60.5, ARCH_Y, ARCH_PILLAR_WIDTH, ARCH_PILLAR_DEPTH),
        )
        collisions.add(
            "arch right pillar",
            AabbFootprint.from_center(89.5, ARCH_Y, ARCH_PILLAR_WIDTH, ARCH_PILLAR_DEPTH),
        )
    terrain = build_terrain_surface()
    if terrain is not None:
        collisions.add(
            "hill terrain",
            AabbFootprint(
                HILL_CORNER[0] - HILL_EXTENT[0],
                HILL_CORNER[1] - HILL_EXTENT[1],
                HILL_CORNER[0],
                HILL_CORNER[1],
            ),
            role=TraversalRole.TRAVERSABLE,
            terrain=terrain,
        )
    return collisions


def build_traversal_settings() -> TraversalSettings:
    if not TERRAIN_FOLLOWING_ENABLED:
        return TraversalSettings(mode=TerrainMode.FLAT, fallback_ground_z=0.0)
    return TraversalSettings(
        mode=TerrainMode.FOLLOW_SURFACE,
        fallback_ground_z=0.0,
        max_slope_degrees=HILL_MAX_SLOPE_DEGREES,
        out_of_bounds_policy=OutOfBoundsPolicy.USE_FALLBACK_GROUND,
    )


def build_terrain_surface() -> MeshTerrainSurface | None:
    if not HILL_ENABLED:
        return None
    return MeshTerrainSurface.from_triangle_mesh(build_rolling_hill_mesh(HILL_CORNER, HILL_EXTENT, HILL_HEIGHT))


def build_rolling_hill_mesh(
    corner: tuple[float, float],
    extent: tuple[float, float],
    height: float,
) -> TriangleMesh3D:
    vertices, triangles = generate_rolling_hill_geometry(corner, extent, height)
    return TriangleMesh3D(vertices=vertices, triangles=triangles, material=HILL_MATERIAL, cull_back_faces=False)


def generate_rolling_hill_geometry(
    corner: tuple[float, float],
    extent: tuple[float, float],
    height: float,
) -> tuple[tuple[tuple[float, float, float], ...], tuple[tuple[int, int, int], ...]]:
    x_divisions = int(extent[0] / GRID_STEP)
    y_divisions = int(extent[1] / GRID_STEP)
    vertices = []
    for row in range(y_divisions + 1):
        y = corner[1] - extent[1] + extent[1] * row / y_divisions
        normalized_y = (corner[1] - y) / extent[1]
        for column in range(x_divisions + 1):
            x = corner[0] - extent[0] + extent[0] * column / x_divisions
            normalized_x = (corner[0] - x) / extent[0]
            distance = normalized_x * normalized_x + normalized_y * normalized_y
            vertices.append((x, y, height * math.exp(-3.5 * distance)))

    triangles = []
    row_width = x_divisions + 1
    for row in range(y_divisions):
        for column in range(x_divisions):
            current = row * row_width + column
            next_row = current + row_width
            triangles.extend(((current, current + 1, next_row + 1), (current, next_row + 1, next_row)))
    return tuple(vertices), tuple(triangles)


def add_rolling_hill(
    scene: Scene3D,
    corner: tuple[float, float],
    extent: tuple[float, float],
    height: float,
) -> None:
    vertices, triangles = generate_rolling_hill_geometry(corner, extent, height)
    scene.add(TriangleMesh3D(vertices=vertices, triangles=triangles, material=HILL_MATERIAL, cull_back_faces=False))
    x_divisions = int(extent[0] / GRID_STEP)
    y_divisions = int(extent[1] / GRID_STEP)
    row_width = x_divisions + 1
    for row in range(y_divisions + 1):
        for column in range(x_divisions):
            start_index = row * row_width + column
            end_index = start_index + 1
            start = vertices[start_index]
            end = vertices[end_index]
            x_coordinate = round(start[0] / GRID_STEP) * GRID_STEP
            major = x_coordinate % MAJOR_GRID_STEP == 0
            scene.add(
                Line3D(
                    start=(start[0], start[1], start[2] + 0.08),
                    end=(end[0], end[1], end[2] + 0.08),
                    color=HILL_GRID_MAJOR_COLOR if major else HILL_GRID_MINOR_COLOR,
                    thickness=-2.0 if major else -1.0,
                    render_layer=LineRenderLayer.WORLD,
                )
            )
    for row in range(y_divisions):
        for column in range(x_divisions + 1):
            start_index = row * row_width + column
            end_index = start_index + row_width
            start = vertices[start_index]
            end = vertices[end_index]
            y_coordinate = round(start[1] / GRID_STEP) * GRID_STEP
            major = y_coordinate % MAJOR_GRID_STEP == 0
            scene.add(
                Line3D(
                    start=(start[0], start[1], start[2] + 0.08),
                    end=(end[0], end[1], end[2] + 0.08),
                    color=HILL_GRID_MAJOR_COLOR if major else HILL_GRID_MINOR_COLOR,
                    thickness=-2.0 if major else -1.0,
                    render_layer=LineRenderLayer.WORLD,
                )
            )


def create_road_texture(context: dcg.Context) -> dcg.Texture | None:
    create_windmill_textures(context)
    if not ROAD_TEXTURE_ENABLED:
        return None
    width, height = ROAD_TEXTURE_SIZE
    pixels = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            variation = ((x * 17 + y * 31 + x * y * 3) % 23) - 11
            patch = ((x // 8) * 3 + (y // 32) * 5) % 9
            if patch in {0, 1}:
                base_color = (151, 106, 66)
            elif patch == 8:
                base_color = (79, 55, 40)
            else:
                base_color = ROAD_COLOR
            streak = 10 if ((x * 5 + y * 2) % 47) < 4 else 0
            color = (
                max(0, min(255, base_color[0] + variation + streak)),
                max(0, min(255, base_color[1] + variation + streak)),
                max(0, min(255, base_color[2] + variation + streak)),
                255,
            )
            offset = (y * width + x) * 4
            pixels[offset:offset + 4] = bytes(color)
    texture = dcg.Texture(context)
    texture.nearest_neighbor_upsampling = True
    texture.set_value(memoryview(pixels).cast("B", shape=(height, width, 4)))
    return texture


def build_scene(road_texture: object | None = None) -> tuple[Scene3D, Box3D]:
    """Build the replaceable town world and return its controllable avatar."""
    scene = Scene3D(background=SKY_COLOR)
    scene.add(
        GroundPlane3D(
            bounds=(
                -GROUND_PAD,
                -GROUND_PAD,
                WORLD_W + GROUND_PAD,
                WORLD_H + GROUND_PAD,
            ),
            z=0.0,
            material=SolidMaterial(
                fill=GROUND_COLOR,
                outline=None,
                thickness=-1.0,
                shaded=False,
                line_occluder=False,
            ),
        )
    )
    road_material = SolidMaterial(
        fill=ROAD_COLOR,
        outline=None,
        thickness=-1.0,
        shaded=False,
        line_occluder=False,
    )
    road_top_material = (
        ImageMaterial(texture=road_texture, tessellation=12, fill=ROAD_COLOR, outline=None, thickness=-1.0, shaded=False)
        if road_texture is not None
        else None
    )
    for road_start in range(0, int(WORLD_H), int(ROAD_SEGMENT_LENGTH)):
        scene.add(
            Box3D(
                center=(
                    WORLD_W * 0.5,
                    road_start + ROAD_SEGMENT_LENGTH * 0.5,
                    0.2,
                ),
                size=(ROAD_WIDTH, ROAD_SEGMENT_LENGTH, 0.4),
                material=road_material,
                face_materials=(None, road_top_material, None, None, None, None),
            )
        )

    for center, size, height, roof_type in HOUSE_SPECS:
        if roof_type == "gable":
            add_gable_house(scene, center, size, height)
        else:
            add_hip_house(scene, center, size, height)
    if ARCH_ENABLED:
        add_arch(scene)
    if TOWER_ENABLED:
        add_tower(scene, center=TOWER_CENTER, size=TOWER_SIZE, height=TOWER_HEIGHT, roof_height=TOWER_ROOF_HEIGHT)
        if _WINDMILL_TEXTURES:
            scene.add(
                Billboard3D(
                    anchor=(TOWER_CENTER[0], TOWER_CENTER[1], TOWER_HEIGHT + TOWER_ROOF_HEIGHT - 2.0),
                    world_size=WINDMILL_WORLD_SIZE,
                    facing=BillboardFacing.CAMERA_YAW,
                    material=AnimatedImageMaterial(
                        frames=_WINDMILL_TEXTURES,
                        loop_seconds=WINDMILL_LOOP_SECONDS,
                        projection_policy=AnimationProjection.OCCLUDABLE_WORLD,
                        tessellation=1,
                    ),
                )
            )
    if BOULDER_ENABLED:
        add_boulder(scene, center=BOULDER_CENTER, size=BOULDER_SIZE, height=BOULDER_HEIGHT)
    if HILL_ENABLED:
        # Experiment here: corner moves the peak, extent changes the footprint,
        # and height controls the peak elevation.
        add_rolling_hill(
            scene,
            corner=HILL_CORNER,
            extent=HILL_EXTENT,
            height=HILL_HEIGHT,
        )
    if FLOATING_ISLAND_ENABLED:
        add_floating_island(
            scene,
            center=FLOATING_ISLAND_CENTER,
            top_z=FLOATING_ISLAND_TOP_Z,
            top_radius=FLOATING_ISLAND_TOP_RADIUS,
            taper_depth=FLOATING_ISLAND_TAPER_DEPTH,
            ring_count=FLOATING_ISLAND_RING_COUNT,
            segments=FLOATING_ISLAND_SEGMENTS,
        )

    for coordinate in range(0, int(WORLD_W) + 1, GRID_STEP):
        major = coordinate % MAJOR_GRID_STEP == 0
        scene.add(
            Line3D(
                start=(float(coordinate), 0.0, 0.5),
                end=(float(coordinate), WORLD_H, 0.5),
                color=GRID_MAJOR_COLOR if major else GRID_MINOR_COLOR,
                thickness=-2.0 if major else -1.0,
                render_layer=LineRenderLayer.UTILITY,
            )
        )

    for coordinate in range(0, int(WORLD_H) + 1, GRID_STEP):
        major = coordinate % MAJOR_GRID_STEP == 0
        scene.add(
            Line3D(
                start=(0.0, float(coordinate), 0.5),
                end=(WORLD_W, float(coordinate), 0.5),
                color=GRID_MAJOR_COLOR if major else GRID_MINOR_COLOR,
                thickness=-2.0 if major else -1.0,
                render_layer=LineRenderLayer.UTILITY,
            )
        )

    if POSITION_LABELS_ENABLED:
        for x_coordinate in range(0, int(WORLD_W) + 1, MAJOR_GRID_STEP):
            for y_coordinate in range(0, int(WORLD_H) + 1, MAJOR_GRID_STEP):
                scene.add(
                    Text3D(
                        position=(float(x_coordinate + 1), float(y_coordinate + 1), 1.0),
                        text=f"({x_coordinate}, {y_coordinate})",
                        size=10.0,
                        color=LABEL_COLOR,
                        min_size=7.0,
                        max_size=12.0,
                    )
                )

    scene.add(
        Polyline3D(
            points=(
                (0.0, 0.0, 0.7),
                (WORLD_W, 0.0, 0.7),
                (WORLD_W, WORLD_H, 0.7),
                (0.0, WORLD_H, 0.7),
            ),
            color=BORDER_COLOR,
            thickness=-3.0,
            closed=True,
            render_layer=LineRenderLayer.UTILITY,
        )
    )

    avatar = Box3D(
        center=(AVATAR_START_XY[0], AVATAR_START_XY[1], 0.0),
        size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT),
        material=SolidMaterial(
            fill=(245, 194, 67),
            outline=(35, 45, 30),
            thickness=-2.0,
            shaded=True,
        ),
    )
    scene.add(avatar)
    return scene, avatar
