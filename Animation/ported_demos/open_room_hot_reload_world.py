"""Reloadable four-wall, open-ceiling wizard's room with a textured flush rug box.

The host's ``create_road_texture`` hook supplies the rug texture in this world
(and, as a side effect, the craft-table mat and crystal-ball sprite textures);
Reload world regenerates all of them along with the scene. Set the wall
booleans below, save this file, and reload to show or hide walls and their
collisions.
"""

from __future__ import annotations

import math

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Billboard3D,
    BillboardFacing,
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
CRAFT_MAT_TEXTURE_SIZE = (72, 56)
CRYSTAL_BALL_TEXTURE_SIZE = 64

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
CRAFT_MAT_MATERIAL = SolidMaterial(fill=(58, 32, 74), outline=(33, 22, 42), thickness=-1.0, shaded=False)

WALL_SPECS = (
    ("back wall", "BACK_WALL_ENABLED", (45.0, 78.0), (90.0, 4.0)),
    ("left wall", "LEFT_WALL_ENABLED", (2.0, 37.9), (4.0, 75.8)),
    ("front wall", "FRONT_WALL_ENABLED", (47.1, 2.0), (85.8, 4.0)),
    ("right wall", "RIGHT_WALL_ENABLED", (88.0, 40.0), (4.0, 71.6)),
)

# Bookcase footprint shared by every case, plus per-case center and a book
# color offset so neighboring cases read with slightly different palettes.
BOOKCASE_WIDTH = 20.0
BOOKCASE_DEPTH = 8.0
BOOKCASE_HEIGHT = 24.0
BOOKCASE_SPECS = (
    ("bookcase 1", (17.0, 70.0), 0),
    ("bookcase 2", (45.0, 70.0), 3),
    ("bookcase 3", (72.0, 70.0), 6),
)
BOOK_COLORS = (
    (157, 58, 42), (65, 103, 135), (154, 126, 49), (112, 63, 126),
    (84, 140, 96), (176, 92, 150), (74, 150, 168), (138, 110, 60),
)
BOOK_ROW_X_OFFSETS = (-7.5, -5.0, -2.5, 0.0, 2.5, 5.0)
BOOK_ROW_HEIGHTS = (
    (3.0, 3.8, 3.3, 4.2, 3.6, 4.0),
    (4.4, 3.6, 5.0, 3.8, 4.6, 3.4),
    (3.2, 4.0, 3.5, 3.0, 3.8, 3.3),
)
BOOK_ROW_Z = (1.4, 9.4, 17.4)

# Small four-legged tables share these proportions; ``add_small_table`` returns
# the z height of the finished top surface for a caller to stack items on.
TABLE_LEG_HEIGHT = 6.0
TABLE_TOP_THICKNESS = 1.0
CRAFT_TABLE_CENTER = (15.0, 14.0)
CRAFT_TABLE_SIZE = (14.0, 10.0)
CRAFT_MAT_SIZE = (10.0, 6.0)
CRYSTAL_TABLE_CENTER = (78.0, 14.0)
CRYSTAL_TABLE_SIZE = (12.0, 10.0)
CRYSTAL_BALL_WORLD_SIZE = (4.5, 4.5)

FURNITURE_SPECS = (
    ("table", (50.0, 36.0), (18.0, 12.0)),
    ("chair", (66.0, 36.0), (6.0, 6.0)),
    ("bed", (35.0, 57.0), (25.4, 13.0)),
    *((name, center, (BOOKCASE_WIDTH, BOOKCASE_DEPTH)) for name, center, _offset in BOOKCASE_SPECS),
    ("craft table", CRAFT_TABLE_CENTER, CRAFT_TABLE_SIZE),
    ("crystal ball table", CRYSTAL_TABLE_CENTER, CRYSTAL_TABLE_SIZE),
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


_CRAFT_MAT_TEXTURE: dcg.Texture | None = None
_CRYSTAL_BALL_TEXTURE: dcg.Texture | None = None


def create_craft_mat_texture(context: dcg.Context) -> dcg.Texture | None:
    """Build the arcane-circle mat texture; cached in a module global like the
    windmill sprite pattern so it stays alive through the active module bundle."""
    global _CRAFT_MAT_TEXTURE
    if not (ROOM_ENABLED and FURNITURE_ENABLED):
        _CRAFT_MAT_TEXTURE = None
        return None
    width, height = CRAFT_MAT_TEXTURE_SIZE
    pixels = bytearray(width * height * 4)
    cx, cy = (width - 1) * 0.5, (height - 1) * 0.5
    max_radius = min(cx, cy) - 2.0
    for y in range(height):
        for x in range(width):
            dx, dy = x - cx, y - cy
            radius = math.hypot(dx, dy)
            angle = math.atan2(dy, dx)
            spoke = abs(math.sin(angle * 4.0)) < 0.05 and radius < max_radius - 3.0
            ring = abs(radius - max_radius) < 1.6 or abs(radius - max_radius * 0.55) < 1.3
            if spoke or ring:
                color = (205, 173, 82)
            elif radius > max_radius:
                color = (33, 22, 42)
            else:
                color = (58, 32, 74) if (int(radius) // 3) % 2 else (49, 26, 64)
            offset = (y * width + x) * 4
            pixels[offset:offset + 4] = bytes((*color, 255))
    texture = dcg.Texture(context)
    texture.set_value(memoryview(pixels).cast("B", shape=(height, width, 4)))
    _CRAFT_MAT_TEXTURE = texture
    return texture


def create_crystal_ball_texture(context: dcg.Context) -> dcg.Texture | None:
    """Build a round, transparent-background glowing-orb sprite for the billboard."""
    global _CRYSTAL_BALL_TEXTURE
    if not (ROOM_ENABLED and FURNITURE_ENABLED):
        _CRYSTAL_BALL_TEXTURE = None
        return None
    size = CRYSTAL_BALL_TEXTURE_SIZE
    pixels = bytearray(size * size * 4)
    center = (size - 1) * 0.5
    radius = center - 1.0
    for y in range(size):
        for x in range(size):
            dx, dy = x - center, y - center
            distance = math.hypot(dx, dy)
            if distance > radius:
                continue  # leave fully transparent (alpha 0) outside the sphere
            glow = 1.0 - distance / radius
            swirl = 0.5 + 0.5 * math.sin(math.atan2(dy, dx) * 3.0 + distance * 0.35)
            if distance < radius * 0.28 and dx < 0 and dy < 0:
                color = (235, 225, 250)
            else:
                color = (
                    min(255, int(70 + 90 * glow + 40 * swirl)),
                    min(255, int(60 + 70 * glow + 60 * swirl)),
                    min(255, int(140 + 100 * glow)),
                )
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes((*color, 255))
    texture = dcg.Texture(context)
    texture.set_value(memoryview(pixels).cast("B", shape=(size, size, 4)))
    _CRYSTAL_BALL_TEXTURE = texture
    return texture


def create_road_texture(context: dcg.Context) -> dcg.Texture | None:
    """Supply the rug texture through the host's existing resource hook.

    As a side effect this also (re)builds the craft-table mat and crystal-ball
    sprite textures, following the same single-hook-plus-module-global pattern
    the town world uses for its windmill sprite frames.
    """
    create_craft_mat_texture(context)
    create_crystal_ball_texture(context)
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


def add_bookcase(scene: Scene3D, center: tuple[float, float], color_offset: int = 0) -> None:
    """Build one bookcase at ``center`` with separate sides, shelves, and
    three filled rows of books (books on every shelf, not just one row)."""
    cx, cy = center
    back_y = cy + BOOKCASE_DEPTH * 0.5 - 0.5
    shelf_y = cy - 0.6
    book_y = shelf_y - 0.9
    scene.add(Box3D(center=(cx, back_y, PART_GAP), size=(BOOKCASE_WIDTH, 1.0, BOOKCASE_HEIGHT), material=WOOD_MATERIAL))
    for dx in (-(BOOKCASE_WIDTH * 0.5 - 0.5), BOOKCASE_WIDTH * 0.5 - 0.5):
        scene.add(Box3D(center=(cx + dx, shelf_y, PART_GAP), size=(1.0, BOOKCASE_DEPTH - 1.2, BOOKCASE_HEIGHT), material=WOOD_MATERIAL))
    for shelf_z in (0.2, 8.2, 16.2, 23.2):
        scene.add(Box3D(center=(cx, shelf_y, shelf_z), size=(BOOKCASE_WIDTH - 2.4, BOOKCASE_DEPTH - 1.2, 1.0), material=TRIM_MATERIAL))
    for row_index, row_z in enumerate(BOOK_ROW_Z):
        heights = BOOK_ROW_HEIGHTS[row_index]
        for slot_index, dx in enumerate(BOOK_ROW_X_OFFSETS):
            color = BOOK_COLORS[(color_offset + row_index * 3 + slot_index) % len(BOOK_COLORS)]
            scene.add(
                Box3D(
                    center=(cx + dx, book_y, row_z),
                    size=(2.0, 3.0, heights[slot_index]),
                    material=SolidMaterial(fill=color, outline=None, thickness=-1.0, shaded=True),
                )
            )


def add_small_table(scene: Scene3D, center: tuple[float, float], size: tuple[float, float]) -> float:
    """Build a small four-legged table at ``center`` and return the z height
    of its finished top surface, so a caller can stack an item above it."""
    cx, cy = center
    width, depth = size
    leg_dx, leg_dy = width * 0.5 - 2.0, depth * 0.5 - 2.0
    for x in (cx - leg_dx, cx + leg_dx):
        for y in (cy - leg_dy, cy + leg_dy):
            scene.add(Box3D(center=(x, y, PART_GAP), size=(1.2, 1.2, TABLE_LEG_HEIGHT), material=WOOD_MATERIAL))
    top_z = PART_GAP + TABLE_LEG_HEIGHT + PART_GAP
    scene.add(Box3D(center=(cx, cy, top_z), size=(width, depth, TABLE_TOP_THICKNESS), material=WOOD_MATERIAL))
    return top_z + TABLE_TOP_THICKNESS


def add_craft_table(scene: Scene3D, craft_mat_texture: dcg.Texture | None) -> None:
    """Build the wizard's craft table with a decorative mat on top, textured
    when a mat texture is available and falling back to a solid mat color."""
    surface_z = add_small_table(scene, CRAFT_TABLE_CENTER, CRAFT_TABLE_SIZE)
    mat_material = (
        ImageMaterial(
            texture=craft_mat_texture, tessellation=4,
            fill=CRAFT_MAT_MATERIAL.fill, outline=CRAFT_MAT_MATERIAL.outline,
            thickness=-1.0, shaded=False,
        )
        if craft_mat_texture is not None else CRAFT_MAT_MATERIAL
    )
    mat_width, mat_depth = CRAFT_MAT_SIZE
    scene.add(Box3D(
        center=(CRAFT_TABLE_CENTER[0], CRAFT_TABLE_CENTER[1], surface_z + PART_GAP),
        size=(mat_width, mat_depth, 0.3),
        material=CRAFT_MAT_MATERIAL,
        face_materials=(None, mat_material, None, None, None, None),
    ))


def add_crystal_ball_table(scene: Scene3D, crystal_ball_texture: dcg.Texture | None) -> None:
    """Build the second table and, when a sprite texture is available, a
    camera-facing crystal ball floating just above its surface."""
    surface_z = add_small_table(scene, CRYSTAL_TABLE_CENTER, CRYSTAL_TABLE_SIZE)
    if crystal_ball_texture is None:
        return
    scene.add(
        Billboard3D(
            anchor=(CRYSTAL_TABLE_CENTER[0], CRYSTAL_TABLE_CENTER[1], surface_z + PART_GAP),
            world_size=CRYSTAL_BALL_WORLD_SIZE,
            facing=BillboardFacing.CAMERA_YAW,
            material=ImageMaterial(texture=crystal_ball_texture, tessellation=1),
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
        for _name, center, color_offset in BOOKCASE_SPECS:
            add_bookcase(scene, center, color_offset)
        add_craft_table(scene, _CRAFT_MAT_TEXTURE)
        add_crystal_ball_table(scene, _CRYSTAL_BALL_TEXTURE)

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
