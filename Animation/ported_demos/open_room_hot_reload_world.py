"""Reloadable four-wall, open-ceiling room with a textured flush rug box.

The host's ``create_road_texture`` hook supplies the rug texture in this world;
Reload world regenerates it along with the scene. Set the wall booleans below,
save this file, and reload to show or hide walls and their collisions.
"""

from __future__ import annotations

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Box3D,
    CollisionWorld,
    GroundPlane3D,
    ImageMaterial,
    OutOfBoundsPolicy,
    Scene3D,
    SolidMaterial,
    TerrainMode,
    TraversalSettings,
)


WORLD_W = 90.0
WORLD_H = 80.0
GRID_STEP = 4.0
AVATAR_SIZE = 4.0
AVATAR_HEIGHT = 5.5
COLLISION_GAP = 1.0
AVATAR_START_XY = (66.0, 18.0)
PART_GAP = 0.2
RUG_BOUNDS = (35.2, 26.0, 62.8, 46.0)
RUG_TEXTURE_SIZE = (96, 64)

ROOM_ENABLED = True
FURNITURE_ENABLED = True
BACK_WALL_ENABLED = True
LEFT_WALL_ENABLED = True
FRONT_WALL_ENABLED = False
RIGHT_WALL_ENABLED = False

SKY_COLOR = (20, 18, 22)
FLOOR_MATERIAL = SolidMaterial(fill=(93, 65, 43), outline=None, thickness=-1.0, shaded=False)
WALL_MATERIAL = SolidMaterial(fill=(105, 78, 57), outline=(56, 42, 32), thickness=-1.0, shaded=True)
TRIM_MATERIAL = SolidMaterial(fill=(54, 36, 25), outline=None, thickness=-1.0, shaded=True)
RUG_MATERIAL = SolidMaterial(fill=(104, 48, 42), outline=(55, 25, 24), thickness=-1.0, shaded=False)
WOOD_MATERIAL = SolidMaterial(fill=(124, 78, 42), outline=(62, 37, 21), thickness=-1.0, shaded=True)
BED_MATERIAL = SolidMaterial(fill=(91, 72, 96), outline=(45, 35, 49), thickness=-1.0, shaded=True)
BOOK_MATERIAL = SolidMaterial(fill=(140, 98, 48), outline=(70, 47, 25), thickness=-1.0, shaded=True)
AVATAR_MATERIAL = SolidMaterial(fill=(240, 193, 72), outline=(45, 34, 25), thickness=-2.0, shaded=True)

WALL_SPECS = (
    ("back wall", "BACK_WALL_ENABLED", (45.0, 78.0), (90.0, 4.0)),
    ("left wall", "LEFT_WALL_ENABLED", (2.0, 37.9), (4.0, 75.8)),
    ("front wall", "FRONT_WALL_ENABLED", (47.1, 2.0), (85.8, 4.0)),
    ("right wall", "RIGHT_WALL_ENABLED", (88.0, 40.0), (4.0, 71.6)),
)
FURNITURE_SPECS = (
    ("table", (50.0, 36.0), (18.0, 12.0)),
    ("chair", (66.0, 36.0), (6.0, 6.0)),
    ("bed", (35.0, 57.0), (25.4, 13.0)),
    ("bookcase", (17.0, 70.0), (20.0, 8.0)),
)


def effective_world_flags() -> dict[str, bool]:
    return {
        "ROOM_ENABLED": ROOM_ENABLED,
        "FURNITURE_ENABLED": ROOM_ENABLED and FURNITURE_ENABLED,
        "BACK_WALL_ENABLED": ROOM_ENABLED and BACK_WALL_ENABLED,
        "LEFT_WALL_ENABLED": ROOM_ENABLED and LEFT_WALL_ENABLED,
        "FRONT_WALL_ENABLED": ROOM_ENABLED and FRONT_WALL_ENABLED,
        "RIGHT_WALL_ENABLED": ROOM_ENABLED and RIGHT_WALL_ENABLED,
    }


def enabled_wall_specs() -> tuple[tuple[str, tuple[float, float], tuple[float, float]], ...]:
    flags = effective_world_flags()
    return tuple(
        (name, center, size)
        for name, flag, center, size in WALL_SPECS if flags[flag]
    )


def create_road_texture(context: dcg.Context) -> dcg.Texture | None:
    """Supply the rug texture through the host's existing resource hook."""
    if not (ROOM_ENABLED and FURNITURE_ENABLED):
        return None
    width, height = RUG_TEXTURE_SIZE
    pixels = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            border = min(x, width - 1 - x, y, height - 1 - y)
            diamond = abs(x - (width - 1) * 0.5) / 26 + abs(y - (height - 1) * 0.5) / 18
            if border < 2:
                color = (54, 29, 27)
            elif border < 5 or 0.8 < diamond < 1.0:
                color = (191, 155, 91)
            elif border < 9:
                color = (70, 46, 49) if (x // 4 + y // 4) % 2 else (150, 97, 62)
            elif diamond < 0.35:
                color = (191, 155, 91)
            else:
                color = (112, 43, 40)
            weave = (x % 2) * 6 - (y % 2) * 5
            offset = (y * width + x) * 4
            pixels[offset:offset + 4] = bytes((color[0] + weave, color[1] + weave, color[2] + weave, 255))
    texture = dcg.Texture(context)
    texture.set_value(memoryview(pixels).cast("B", shape=(height, width, 4)))
    return texture


def add_bookcase(scene: Scene3D) -> None:
    scene.add(Box3D(center=(17.0, 73.5, PART_GAP), size=(20.0, 1.0, 24.0), material=WOOD_MATERIAL))
    for x in (7.5, 26.5):
        scene.add(Box3D(center=(x, 69.4, PART_GAP), size=(1.0, 6.8, 24.0), material=WOOD_MATERIAL))
    for shelf_z in (0.2, 8.2, 16.2, 23.2):
        scene.add(Box3D(center=(17.0, 69.4, shelf_z), size=(17.6, 6.8, 1.0), material=TRIM_MATERIAL))
    for x, height, color in ((10.0, 4.0, (157, 58, 42)), (13.0, 5.5, (65, 103, 135)), (16.5, 3.8, (154, 126, 49)), (20.0, 5.0, (112, 63, 126))):
        scene.add(
            Box3D(
                center=(x, 68.5, 9.4),
                size=(2.1, 3.0, height),
                material=SolidMaterial(fill=color, outline=None, thickness=-1.0, shaded=True),
            )
        )


def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    """Build the selected walls, open ceiling, and simple furniture."""
    scene = Scene3D(background=SKY_COLOR)
    if ROOM_ENABLED and FURNITURE_ENABLED:
        # Recess the thin rug box into the floor cutout so its top stays flush.
        for bounds in (
            (0.0, 0.0, 35.2, WORLD_H),
            (62.8, 0.0, WORLD_W, WORLD_H),
            (35.2, 0.0, 62.8, 26.0),
            (35.2, 46.0, 62.8, WORLD_H),
        ):
            scene.add(GroundPlane3D(bounds=bounds, z=0.0, material=FLOOR_MATERIAL))
        x0, y0, x1, y1 = RUG_BOUNDS
        top_material = (
            ImageMaterial(
                texture=road_texture, tessellation=6,
                fill=RUG_MATERIAL.fill, outline=RUG_MATERIAL.outline,
                thickness=-1.0, shaded=False,
            )
            if road_texture is not None else RUG_MATERIAL
        )
        scene.add(Box3D(
            center=((x0 + x1) * 0.5, (y0 + y1) * 0.5, -PART_GAP),
            size=(x1 - x0, y1 - y0, PART_GAP),
            material=RUG_MATERIAL,
            face_materials=(None, top_material, None, None, None, None),
        ))
    else:
        scene.add(GroundPlane3D(bounds=(0.0, 0.0, WORLD_W, WORLD_H), z=0.0, material=FLOOR_MATERIAL))

    if ROOM_ENABLED:
        for _name, (x, y), (width, depth) in enabled_wall_specs():
            scene.add(Box3D(center=(x, y, PART_GAP), size=(width, depth, 3.0), material=TRIM_MATERIAL))
            scene.add(Box3D(center=(x, y, 3.4), size=(width, depth, 34.6), material=WALL_MATERIAL))

    if ROOM_ENABLED and FURNITURE_ENABLED:
        for x in (43.0, 57.0):
            for y in (32.0, 40.0):
                scene.add(Box3D(center=(x, y, PART_GAP), size=(1.5, 1.5, 7.0), material=WOOD_MATERIAL))
        scene.add(Box3D(center=(50.0, 36.0, 7.4), size=(18.0, 12.0, 1.2), material=WOOD_MATERIAL))
        scene.add(Box3D(center=(66.0, 36.0, PART_GAP), size=(6.0, 6.0, 4.0), material=WOOD_MATERIAL))
        scene.add(Box3D(center=(68.5, 36.0, 4.4), size=(1.0, 6.0, 6.0), material=WOOD_MATERIAL))
        scene.add(Box3D(center=(35.7, 57.0, PART_GAP), size=(24.0, 13.0, 3.0), material=WOOD_MATERIAL))
        scene.add(Box3D(center=(35.7, 57.0, 3.4), size=(23.0, 12.0, 2.0), material=BED_MATERIAL))
        scene.add(Box3D(center=(22.9, 57.0, PART_GAP), size=(1.2, 13.0, 10.0), material=WOOD_MATERIAL))
        scene.add(Box3D(center=(27.0, 57.0, 5.6), size=(4.0, 9.0, 1.5), material=BOOK_MATERIAL))
        add_bookcase(scene)

    avatar = Box3D(
        center=(AVATAR_START_XY[0], AVATAR_START_XY[1], 0.0),
        size=(AVATAR_SIZE, AVATAR_SIZE, AVATAR_HEIGHT),
        material=AVATAR_MATERIAL,
    )
    scene.add(avatar)
    return scene, avatar


def build_collision_world() -> CollisionWorld:
    collisions = CollisionWorld(gap=COLLISION_GAP)
    if not ROOM_ENABLED:
        return collisions
    for name, center, size in enabled_wall_specs():
        collisions.add(name, AabbFootprint.from_center(*center, *size))
    if FURNITURE_ENABLED:
        for name, center, size in FURNITURE_SPECS:
            collisions.add(name, AabbFootprint.from_center(*center, *size))
    return collisions


def build_terrain_surface() -> None:
    return None


def build_traversal_settings() -> TraversalSettings:
    return TraversalSettings(
        mode=TerrainMode.FLAT,
        fallback_ground_z=0.0,
        out_of_bounds_policy=OutOfBoundsPolicy.USE_FALLBACK_GROUND,
    )
