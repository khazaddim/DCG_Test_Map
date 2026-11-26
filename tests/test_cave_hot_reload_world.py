from __future__ import annotations

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import Camera3D, CpuRenderer3D, GroundPlane3D, OverlapDepthSorter, TriangleMesh3D
from Animation.draw_in_window_3d_framework.math3d import Viewport, dot, subtract
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.ported_demos import cave_hot_reload_profiling as launcher
from Animation.ported_demos import cave_hot_reload_world as cave
from Animation.ported_demos import town_hot_reload as host


def test_cave_has_flat_tiled_floor_and_irregular_inward_facing_shell() -> None:
    scene, avatar = cave.build_scene()
    floors = [obj for obj in scene.iter_visible() if isinstance(obj, GroundPlane3D)]
    meshes = [obj for obj in scene.iter_visible() if isinstance(obj, TriangleMesh3D)]
    assert all(floor.z == avatar.center[2] == 0 for floor in floors)
    assert floors[0].bounds[0] == 0
    assert floors[-1].bounds[2] == cave.WORLD_W
    assert all(first.bounds[2] == second.bounds[0] for first, second in zip(floors, floors[1:]))
    assert len({ring[cave.ARCH_SEGMENTS // 2][2] for ring in cave.cave_rings()}) > 10
    frame = FrameContext(Camera3D(avatar.center, 0, 52, 3.5), Viewport(900, 600))
    for mesh in meshes:
        assert mesh.cull_back_faces
        for packet in mesh.collect(frame):
            assert packet.normal is not None
            center = tuple(sum(point[axis] for point in packet.points) / 3 for axis in range(3))
            toward_interior = subtract((center[0], cave.WORLD_H * 0.5, 0.0), center)
            assert dot(packet.normal, toward_interior) > 0


def test_player_can_traverse_the_whole_floor_but_not_cross_its_edges() -> None:
    candidate = host.load_world_candidate(cave)
    for visible in (True, False):
        candidate.WALLS_ENABLED = candidate.CEILING_ENABLED = visible
        collisions = candidate.build_collision_world()
        settings = candidate.build_traversal_settings()
        half = candidate.AVATAR_SIZE * 0.5
        for x in (half, *range(12, int(candidate.WORLD_W) - 12, 12), candidate.WORLD_W - half):
            y = candidate.WORLD_H * 0.5
            result = collisions.resolve_movement(
                candidate.AabbFootprint.from_center(x, y, candidate.AVATAR_SIZE, candidate.AVATAR_SIZE),
                x=x, y=y, settings=settings,
            )
            assert result.accepted and result.position == (x, y, 0.0)
        _, y0, _, y1 = candidate.floor_bounds()
        for y in (y0 + half + candidate.COLLISION_GAP, y1 - half - candidate.COLLISION_GAP):
            assert collisions.resolve_movement(
                candidate.AabbFootprint.from_center(900, y, candidate.AVATAR_SIZE, candidate.AVATAR_SIZE),
                x=900, y=y, settings=settings,
            ).accepted
        for y in (y0 + half, y1 - half, y0 - 12, y1 + 12):
            assert not collisions.resolve_movement(
                candidate.AabbFootprint.from_center(900, y, candidate.AVATAR_SIZE, candidate.AVATAR_SIZE),
                x=900, y=y, settings=settings,
            ).accepted


@pytest.mark.parametrize("pitch", [0, 52, 78])
@pytest.mark.parametrize("yaw", [0, 45, 90, 180])
def test_clipped_cave_preserves_visible_floor_player_and_depth_order(pitch, yaw) -> None:
    scene, avatar = cave.build_scene()
    frame = FrameContext(Camera3D(avatar.center, yaw, pitch, 3.5), Viewport(900, 600))
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(scene, frame)
    entries, rejected = renderer.project_packets(packets, frame)
    assert rejected > len(packets) * 0.5
    assert all(
        -1e-7 <= x <= frame.viewport.width + 1e-7 and -1e-7 <= y <= frame.viewport.height + 1e-7
        for entry in entries for x, y in entry.points
    )
    materials = [packets[entry.stable_index].material for entry in entries]
    assert cave.FLOOR_MATERIAL in materials and cave.AVATAR_MATERIAL in materials
    if pitch == 52:
        assert cave.WALL_MATERIAL in materials
    if pitch == 78 and yaw == 90:
        assert cave.CEILING_MATERIAL in materials
    if pitch == 78 and yaw == 45:
        assert any(
            min(depths) < frame.camera.near_plane < max(depths)
            for entry in entries
            for depths in [[
                frame.camera.world_to_camera(point, frame.viewport)[2]
                for point in packets[entry.stable_index].points
            ]]
        )
    assert not OverlapDepthSorter().sort(entries).cycle_detected


def test_cave_launcher_renders_and_swaps_only_a_complete_candidate(monkeypatch) -> None:
    context = dcg.Context()
    default_world = host.world
    controller, panel = launcher.build_ui(context)
    try:
        assert controller.world_module is cave
        assert host.world is default_world
        assert controller.viewport.telemetry is panel.telemetry
        controller.viewport.width = 900
        controller.viewport.height = 600
        panel.telemetry.enabled = True
        controller.render_if_needed()
        assert controller.viewport.last_render_stats.emitted_count > 1
        assert not controller.viewport.last_render_stats.cycle_detected
        assert len(panel.telemetry.samples) == 1
        controller.move_right()
        assert controller.avatar.center == (cave.AVATAR_START_XY[0] + cave.GRID_STEP, cave.AVATAR_START_XY[1], 0)

        candidate = host.load_world_candidate(cave)
        candidate.CEILING_ENABLED = False
        monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
        old_scene, old_collisions, old_avatar = controller.viewport.scene, controller.collisions, controller.avatar
        camera = controller.viewport.camera
        controller.reload_world()
        assert controller.world_module is candidate
        assert controller.viewport.scene is not old_scene
        assert controller.collisions is not old_collisions
        assert controller.avatar is not old_avatar
        assert controller.scene_generation == 2
        assert not controller.effective_flags["CEILING_ENABLED"]
        assert controller.viewport.camera == camera
        assert not panel.telemetry.samples
        controller.render_if_needed()
        assert len(panel.telemetry.samples) == 1

        before = (
            controller.world_module, controller.viewport.scene, controller.avatar,
            controller.collisions, controller.traversal_settings, controller.follow,
            controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot(),
        )

        def fail(_texture):
            raise ValueError("bad cave geometry")

        candidate = host.load_world_candidate(cave)
        candidate.build_scene = fail
        controller.reload_world()
        assert "bad cave geometry" in controller.reload_status.value
        assert before == (
            controller.world_module, controller.viewport.scene, controller.avatar,
            controller.collisions, controller.traversal_settings, controller.follow,
            controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot(),
        )
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()
