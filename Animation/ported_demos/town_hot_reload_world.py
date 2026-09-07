"""Reloadable world definition for the town hot-reload experiment."""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Box3D,
    CollisionWorld,
    GroundPlane3D,
    ImageMaterial,
    Line3D,
    LineRenderLayer,
    MeshEdgeStyle,
    Polyline3D,
    Scene3D,
    SolidMaterial,
    Text3D,
    TriangleMesh3D,
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
HILL_ENABLED = False
BOULDER_ENABLED = True
COLLISION_GAP = 2.0

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
HOUSE_SPECS = (
    ((35.0, 30.0), (20.0, 18.0), 12.0, "gable"),
    ((115.0, 48.0), (18.0, 22.0), 14.0, "hip"),
    ((35.0, 95.0), (22.0, 16.0), 13.0, "hip"),
)
BOULDER_CENTER = (96.0, 75.0)
BOULDER_SIZE = (2.0, 3.5)
BOULDER_HEIGHT = 4.5
BOULDER_COLLISION_SCALE = 0.7


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
    return collisions


def add_rolling_hill(
    scene: Scene3D,
    corner: tuple[float, float],
    extent: tuple[float, float],
    height: float,
) -> None:
    # The extents control how far the hill falls off from the peak at the corner.
    # Grid resolution follows the map's 5-unit cells automatically.
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
            # Lower 3.5 for a broader, gentler hill; raise it for a tighter peak.
            vertices.append((x, y, height * math.exp(-3.5 * distance)))

    triangles = []
    row_width = x_divisions + 1
    for row in range(y_divisions):
        for column in range(x_divisions):
            current = row * row_width + column
            next_row = current + row_width
            triangles.extend(((current, current + 1, next_row + 1), (current, next_row + 1, next_row)))

    scene.add(TriangleMesh3D(vertices=tuple(vertices), triangles=tuple(triangles), material=HILL_MATERIAL, cull_back_faces=False))
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
    if BOULDER_ENABLED:
        add_boulder(scene, center=BOULDER_CENTER, size=BOULDER_SIZE, height=BOULDER_HEIGHT)
    if HILL_ENABLED:
        # Experiment here: corner moves the peak, extent changes the footprint,
        # and height controls the peak elevation.
        add_rolling_hill(
            scene,
            corner=(150.0, 150.0),
            extent=(30.0, 50.0),
            height=16.0,
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
        center=(WORLD_W * 0.5, WORLD_H * 0.5, 0.0),
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
