from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    Camera3D,
    CollisionWorld,
    DrawInWindow3D,
    EdgeBandFollowController,
    MeshTerrainSurface,
    OutOfBoundsPolicy,
    Scene3D,
    TerrainMode,
    TraversalRole,
    TraversalSettings,
    TriangleMesh3D,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_town_hot_reload_world():
    source = REPO_ROOT / "Animation" / "ported_demos" / "town_hot_reload_world.py"
    spec = importlib.util.spec_from_file_location("terrain_hot_reload_world_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_town_hot_reload():
    source = REPO_ROOT / "Animation" / "ported_demos" / "town_hot_reload.py"
    spec = importlib.util.spec_from_file_location("terrain_hot_reload_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_widget(scene: Scene3D, camera: Camera3D, *, terrain=None):
    context = dcg.Context()
    with dcg.Window(context, label="terrain-test", width=440, height=320):
        with DrawInWindow3D(
            context,
            width=280,
            height=180,
            scene=scene,
            camera=camera,
            terrain=terrain,
        ) as viewport:
            yielded = viewport
    return context, yielded


def make_ramp_surface() -> MeshTerrainSurface:
    world = load_town_hot_reload_world()
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 10.0), (10.0, 10.0, 10.0)),
        triangles=((0, 1, 2), (1, 3, 2)),
        material=world.HILL_MATERIAL,
    )
    return MeshTerrainSurface.from_triangle_mesh(mesh)


def test_mesh_terrain_surface_samples_height_and_normal() -> None:
    surface = make_ramp_surface()

    sample = surface.sample(2.5, 7.5)

    assert sample is not None
    assert sample.position == pytest.approx((2.5, 7.5, 7.5))
    assert sample.normal is not None
    assert sample.normal[2] > 0.0


def test_mesh_terrain_surface_prefers_highest_overlapping_triangle() -> None:
    world = load_town_hot_reload_world()
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 5.0), (10.0, 0.0, 5.0), (0.0, 10.0, 5.0)),
        triangles=((0, 1, 2), (3, 4, 5)),
        material=world.HILL_MATERIAL,
    )
    surface = MeshTerrainSurface.from_triangle_mesh(mesh)

    sample = surface.sample(2.0, 2.0)

    assert sample is not None
    assert sample.height == pytest.approx(5.0)
    assert sample.source_id == 1


def test_collision_world_roles_preserve_boundary_blockers_and_ignore_traversable_support() -> None:
    surface = make_ramp_surface()
    world = CollisionWorld(gap=0.0)
    candidate = AabbFootprint.from_center(5.0, 5.0, 2.0, 2.0)

    world.add("hill", AabbFootprint(0.0, 0.0, 10.0, 10.0), role=TraversalRole.TRAVERSABLE, terrain=surface)
    assert world.first_blocker(candidate) is None

    blocker = world.add("wall", AabbFootprint(4.0, 4.0, 6.0, 6.0), role=TraversalRole.BOUNDARY)

    assert world.first_blocker(candidate) is blocker
    support = world.support_sample(5.0, 5.0)
    assert support is not None
    assert support.height == pytest.approx(5.0)


def test_collision_world_resolve_movement_rejects_steep_support_and_out_of_bounds() -> None:
    world_module = load_town_hot_reload_world()
    steep_mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 20.0)),
        triangles=((0, 1, 2),),
        material=world_module.HILL_MATERIAL,
    )
    world = CollisionWorld(gap=0.0)
    world.add(
        "steep hill",
        AabbFootprint(0.0, 0.0, 10.0, 10.0),
        role=TraversalRole.TRAVERSABLE,
        terrain=MeshTerrainSurface.from_triangle_mesh(steep_mesh),
    )
    candidate = AabbFootprint.from_center(2.0, 2.0, 1.0, 1.0)

    too_steep = world.resolve_movement(
        candidate,
        x=2.0,
        y=2.0,
        settings=TraversalSettings(mode=TerrainMode.FOLLOW_SURFACE, fallback_ground_z=0.0, max_slope_degrees=40.0),
    )
    out_of_bounds = world.resolve_movement(
        candidate,
        x=20.0,
        y=20.0,
        settings=TraversalSettings(
            mode=TerrainMode.FOLLOW_SURFACE,
            fallback_ground_z=0.0,
            out_of_bounds_policy=OutOfBoundsPolicy.REJECT,
        ),
    )

    assert too_steep.accepted is False
    assert too_steep.rejection_reason is not None
    assert out_of_bounds.accepted is False
    assert out_of_bounds.rejection_reason is not None


def test_widget_screen_to_surface_resolves_town_hill_point() -> None:
    world = load_town_hot_reload_world()
    terrain = world.build_terrain_surface()
    assert terrain is not None
    sample = terrain.sample(world.HILL_CORNER[0] - 12.5, world.HILL_CORNER[1] - 17.5)
    assert sample is not None
    _context, viewport = build_widget(
        Scene3D(),
        Camera3D(target=(sample.position[0], sample.position[1], sample.position[2]), yaw_deg=0.0, pitch_deg=52.0, zoom=3.5),
        terrain=terrain,
    )

    screen = viewport.world_to_screen(sample.position)
    assert screen is not None
    resolved = viewport.screen_to_surface(screen, ground_z=None)

    assert resolved is not None
    assert resolved == pytest.approx(sample.position, abs=1e-4)


def test_hot_reload_controller_anchors_avatar_to_hill_height_during_movement() -> None:
    demo = load_town_hot_reload()
    world = load_town_hot_reload_world()
    context = dcg.Context()
    scene, avatar = world.build_scene(None)
    collisions = world.build_collision_world()
    terrain = world.build_terrain_surface()
    assert terrain is not None
    with dcg.Window(context, label="terrain-demo", width=500, height=360):
        with DrawInWindow3D(
            context,
            width=320,
            height=220,
            scene=scene,
            camera=Camera3D(target=avatar.center, yaw_deg=0.0, pitch_deg=52.0, zoom=3.5),
            terrain=terrain,
        ) as viewport:
            yielded = viewport
    status = dcg.Text(context, value="")
    reload_status = dcg.Text(context, value="")
    controller = demo.HotReloadTownController(yielded, avatar, context, None, world, collisions, status, reload_status)
    start_sample = terrain.sample(avatar.center[0], avatar.center[1])
    assert start_sample is not None
    assert avatar.center[2] == pytest.approx(start_sample.height)

    controller._move(world.GRID_STEP, world.GRID_STEP)

    moved_sample = terrain.sample(avatar.center[0], avatar.center[1])
    assert moved_sample is not None
    assert avatar.center[2] == pytest.approx(moved_sample.height)
    assert avatar.center[2] > 0.0


def test_edge_band_follow_controller_tracks_terrain_height() -> None:
    world = load_town_hot_reload_world()
    terrain = world.build_terrain_surface()
    assert terrain is not None
    focus_sample = terrain.sample(world.HILL_CORNER[0] - 6.0, world.HILL_CORNER[1] - 10.0)
    assert focus_sample is not None
    _context, viewport = build_widget(
        Scene3D(),
        Camera3D(
            target=(focus_sample.position[0], focus_sample.position[1], 0.0),
            yaw_deg=0.0,
            pitch_deg=52.0,
            zoom=3.5,
        ),
        terrain=terrain,
    )
    follow = EdgeBandFollowController(
        viewport=viewport,
        band_x=40.0,
        band_y=60.0,
        world_bounds=(0.0, 0.0, world.WORLD_W, world.WORLD_H),
        terrain=terrain,
    )

    follow.update(focus_sample.position)

    assert viewport.camera.target[2] > 0.0
    assert math.isclose(viewport.camera.target[0], focus_sample.position[0], abs_tol=30.0)