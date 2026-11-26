from __future__ import annotations

from itertools import combinations

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Camera3D, CpuRenderer3D, OverlapDepthSorter, TriangleMesh3D,
)
from Animation.draw_in_window_3d_framework.math3d import Viewport, cross, length, subtract
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.ported_demos import frozen_temple_hot_reload_profiling as launcher
from Animation.ported_demos import frozen_temple_hot_reload_world as temple
from Animation.ported_demos import town_hot_reload as host


def test_props_have_clearance_and_icicles_leave_walkable_headroom() -> None:
    surface = temple.roof_surface(temple.temple_rings(temple.temple_sections()))
    props = temple.floor_props()
    for (_, first), (_, second) in combinations(props, 2):
        assert not temple.prop_footprint(first).conflicts(temple.prop_footprint(second), gap=0.2)
    for _, meshes in props:
        for first, second in combinations(meshes, 2):
            assert max(p[2] for p in first.vertices) + 0.19 < min(p[2] for p in second.vertices)
        for mesh in meshes:
            for x, y, z in mesh.vertices:
                assert z >= 0.2
                assert z < surface.sample(x, y).height - 0.2
            for indices in mesh.triangles:
                a, b, c = (mesh.vertices[i] for i in indices)
                assert length(cross(subtract(b, a), subtract(c, a))) > 1e-7
    for mesh in temple.hanging_icicles(surface):
        assert min(p[2] for p in mesh.vertices) > temple.AVATAR_HEIGHT
        for x, y, z in mesh.vertices:
            assert z <= surface.sample(x, y).height - 0.19
        x, y, _ = mesh.vertices[0]
        assert temple.build_collision_world().first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is None


def test_floor_tiles_cover_the_hall_and_switches_remove_matching_blockers() -> None:
    candidate = host.load_world_candidate(temple)
    for enabled in (True, False):
        candidate.BRAZIERS_ENABLED = candidate.FLOOR_CRACKS_ENABLED = enabled
        scene, _ = candidate.build_scene()
        area = 0.0
        materials = []
        for mesh in scene.iter_visible():
            if not isinstance(mesh, TriangleMesh3D) or mesh.material not in (
                *candidate.FLOOR_MATERIALS, candidate.WARM_FLOOR_MATERIAL, candidate.CRACK_MATERIAL,
            ):
                continue
            materials.append(mesh.material)
            assert all(p[2] == 0 for p in mesh.vertices)
            for indices in mesh.triangles:
                a, b, c = (mesh.vertices[i] for i in indices)
                area += length(cross(subtract(b, a), subtract(c, a))) * 0.5
        assert area == pytest.approx(1800 * 880)
        assert (candidate.WARM_FLOOR_MATERIAL in materials) is enabled
        assert (candidate.CRACK_MATERIAL in materials) is enabled
    collisions = temple.build_collision_world()
    for _, meshes in temple.floor_props():
        footprint = temple.prop_footprint(meshes)
        assert collisions.first_blocker(footprint) is not None
    candidate.PILLARS_ENABLED = candidate.SHRINE_ENABLED = candidate.RUBBLE_ENABLED = False
    candidate.CEILING_ENABLED = candidate.WALLS_ENABLED = False
    candidate.MESH_EDGES_ENABLED = True
    assert not candidate.build_collision_world().colliders
    assert not candidate.effective_world_flags()["ICICLES_ENABLED"]
    assert not candidate.effective_world_flags()["MESH_EDGES_ENABLED"]
    boundary = candidate.build_collision_world()
    assert boundary.first_blocker(AabbFootprint.from_center(900, 160, 8, 8)) is boundary.boundary


@pytest.mark.parametrize("zoom", [0.25, 1.0, 3.5])
@pytest.mark.parametrize("pitch,yaw", [(0, 0), (52, 0), (52, 45), (52, 90), (52, 180), (78, 90)])
def test_frozen_temple_clips_and_preserves_painter_order(zoom, pitch, yaw) -> None:
    scene, avatar = temple.build_scene()
    frame = FrameContext(Camera3D(avatar.center, yaw, pitch, zoom), Viewport(900, 600))
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(scene, frame)
    entries, _ = renderer.project_packets(packets, frame)
    assert entries
    assert all(
        -1e-7 <= x <= 900 + 1e-7 and -1e-7 <= y <= 600 + 1e-7
        for entry in entries for x, y in entry.points
    )
    materials = [packets[entry.stable_index].material for entry in entries]
    assert temple.AVATAR_MATERIAL in materials
    assert any(material in temple.FLOOR_MATERIALS for material in materials)
    if zoom <= 1:
        assert temple.FLAME_MATERIAL in materials
        assert temple.ICE_MATERIAL in materials
    assert not OverlapDepthSorter().sort(entries).cycle_detected


def test_launcher_movement_reload_and_failure_preservation(monkeypatch) -> None:
    context = dcg.Context()
    controller, panel = launcher.build_ui(context)
    try:
        assert controller.world_module is temple
        controller.viewport.width = 900
        controller.viewport.height = 600
        controller._configure_follow()
        panel.telemetry.enabled = True
        controller.render_if_needed()
        assert len(panel.telemetry.samples) == 1
        for _ in range(5):
            controller.move_right()
        assert controller.avatar.center == (900, 600, 0)
        controller.move_right()
        assert controller.avatar.center == (900, 600, 0)
        for _ in range(5):
            controller.move_left()
        # Detour around the central shrine, then walk to both ends of the hall.
        for callback, count in ((controller.move_left, 60), (controller.move_up, 5),
                                (controller.move_right, 130), (controller.move_down, 5)):
            for _ in range(count):
                before = controller.avatar.center
                callback()
                assert controller.avatar.center != before
                assert controller.avatar.center[2] == 0
        assert controller.avatar.center == (1680, 600, 0)
        load_candidate = host.load_world_candidate
        candidate = load_candidate(temple)
        candidate.PILLARS_ENABLED = candidate.SHRINE_ENABLED = candidate.BRAZIERS_ENABLED = candidate.RUBBLE_ENABLED = False
        monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
        old_scene, old_collisions = controller.viewport.scene, controller.collisions
        controller.reload_world()
        assert controller.viewport.scene is not old_scene
        assert controller.collisions is not old_collisions
        assert not controller.collisions.colliders
        assert controller.scene_generation == 2 and not panel.telemetry.samples
        controller.render_if_needed()
        before = (controller.world_module, controller.viewport.scene, controller.collisions,
                  controller.avatar, controller.effective_flags, controller.scene_generation,
                  panel.telemetry.snapshot())
        candidate = load_candidate(temple)
        candidate.PILLAR_POSITIONS = ((960, 600),)
        controller.reload_world()
        assert "overlaps" in controller.reload_status.value
        assert before == (controller.world_module, controller.viewport.scene, controller.collisions,
                          controller.avatar, controller.effective_flags, controller.scene_generation,
                          panel.telemetry.snapshot())
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()
