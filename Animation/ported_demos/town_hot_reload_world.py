"""Reloadable world definition for the town hot-reload experiment."""

from __future__ import annotations

from Animation.draw_in_window_3d_framework import (
    Box3D,
    GroundPlane3D,
    Line3D,
    LineRenderLayer,
    Polyline3D,
    Scene3D,
    SolidMaterial,
    Text3D,
)


WORLD_W = 150.0
WORLD_H = 150.0
GRID_STEP = 5
MAJOR_GRID_STEP = 25
AVATAR_SIZE = 5.0
AVATAR_HEIGHT = 6.0
GROUND_PAD = 200.0


def build_scene() -> tuple[Scene3D, Box3D]:
    """Build the replaceable town world and return its controllable avatar."""
    scene = Scene3D(background=(135, 195, 230))
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
                fill=(74, 128, 68),
                outline=None,
                thickness=-1.0,
                shaded=False,
                line_occluder=False,
            ),
        )
    )

    for coordinate in range(0, int(WORLD_W) + 1, GRID_STEP):
        major = coordinate % MAJOR_GRID_STEP == 0
        scene.add(
            Line3D(
                start=(float(coordinate), 0.0, 0.5),
                end=(float(coordinate), WORLD_H, 0.5),
                color=(156, 177, 116) if major else (105, 145, 91),
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
                color=(156, 177, 116) if major else (105, 145, 91),
                thickness=-2.0 if major else -1.0,
                render_layer=LineRenderLayer.UTILITY,
            )
        )

    for x_coordinate in range(0, int(WORLD_W) + 1, MAJOR_GRID_STEP):
        for y_coordinate in range(0, int(WORLD_H) + 1, MAJOR_GRID_STEP):
            scene.add(
                Text3D(
                    position=(float(x_coordinate + 1), float(y_coordinate + 1), 1.0),
                    text=f"({x_coordinate}, {y_coordinate})",
                    size=10.0,
                    color=(35, 67, 38),
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
            color=(224, 205, 133),
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
