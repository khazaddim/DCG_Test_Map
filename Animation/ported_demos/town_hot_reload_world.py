"""Reloadable world definition for the town hot-reload experiment."""

from __future__ import annotations

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    Box3D,
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

SKY_COLOR = (23, 29, 34)
GROUND_COLOR = (78, 116, 76)
ROAD_COLOR = (112, 79, 52)
GRID_MAJOR_COLOR = (126, 142, 150)
GRID_MINOR_COLOR = (108, 140, 96)
LABEL_COLOR = (210, 218, 211)
BORDER_COLOR = (178, 146, 88)
HOUSE_WALL_MATERIAL = SolidMaterial(fill=(146, 154, 150), outline=(54, 62, 66), thickness=-1.0)
GABLE_ROOF_MATERIAL = SolidMaterial(fill=(178, 76, 54), outline=(74, 43, 36), thickness=-1.0)
HIP_ROOF_MATERIAL = SolidMaterial(fill=(67, 112, 139), outline=(27, 50, 65), thickness=-1.0)
ROOF_EDGES = MeshEdgeStyle(color=(34, 38, 40, 155), thickness=-1.0)
HOUSE_SPECS = (
    ((35.0, 30.0), (20.0, 18.0), 12.0, "gable"),
    ((115.0, 48.0), (18.0, 22.0), 14.0, "hip"),
    ((35.0, 95.0), (22.0, 16.0), 13.0, "hip"),
    ((115.0, 118.0), (20.0, 18.0), 12.0, "gable"),
)


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
