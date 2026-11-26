from __future__ import annotations

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import AabbFootprint, Camera3D, CpuRenderer3D, Line3D, OverlapDepthSorter, TriangleMesh3D
from Animation.draw_in_window_3d_framework.math3d import Viewport, cross, length, subtract
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.ported_demos import complex_cave_hot_reload_profiling as launcher
from Animation.ported_demos import complex_cave_hot_reload_world as cave
from Animation.ported_demos import town_hot_reload as host


def edges_at(sections, x):
    first, second = next((a, b) for a, b in zip(sections, sections[1:]) if a.x <= x <= b.x)
    t = (x - first.x) / (second.x - first.x)
    return tuple(a + (b - a) * t for a, b in zip(first[1:], second[1:]))


def resolve(world, x, y):
    return world.build_collision_world().resolve_movement(
        AabbFootprint.from_center(x, y, world.AVATAR_SIZE, world.AVATAR_SIZE),
        x=x, y=y, settings=world.build_traversal_settings(),
    )


def test_floor_and_water_tile_the_irregular_outline_without_overlap_or_holes() -> None:
    scene, avatar = cave.build_scene()
    sections = cave.cave_sections()
    area = {"dry": 0.0, "water": 0.0}
    for mesh in scene.iter_visible():
        if not isinstance(mesh, TriangleMesh3D):
            continue
        if mesh.material in cave.FLOOR_MATERIALS:
            kind = "dry"
        elif mesh.material in cave.WATER_MATERIALS:
            kind = "water"
        else:
            continue
        for x, y, z in mesh.vertices:
            lower, upper, _height, width = edges_at(sections, x)
            assert z == 0
            if kind == "dry":
                assert lower + width - 1e-7 <= y <= upper + 1e-7
            else:
                assert lower - 1e-7 <= y <= lower + width + 1e-7
        for triangle in mesh.triangles:
            a, b, c = (mesh.vertices[index] for index in triangle)
            area[kind] += length(cross(subtract(b, a), subtract(c, a))) * 0.5
    expected_water = sum((b.x - a.x) * (a.water_width + b.water_width) * 0.5 for a, b in zip(sections, sections[1:]))
    expected_total = sum((b.x - a.x) * (a.upper - a.lower + b.upper - b.lower) * 0.5 for a, b in zip(sections, sections[1:]))
    assert area["water"] == pytest.approx(expected_water)
    assert area["water"] + area["dry"] == pytest.approx(expected_total)
    assert resolve(cave, *avatar.center[:2]).accepted
    assert max(s.upper - s.lower for s in sections) > 3 * min(s.upper - s.lower for s in sections)
    for line in (obj for obj in scene.iter_visible() if isinstance(obj, Line3D)):
        for x, y, _z in (line.start, line.end):
            lower, _upper, _height, width = edges_at(sections, x)
            assert lower < y < lower + width


def test_dry_route_is_connected_and_shoreline_blocks_the_whole_player() -> None:
    sections = cave.cave_sections()
    collisions = cave.build_collision_world()
    for x in range(6, int(cave.WORLD_W) - 5, 12):
        _lower, upper, _height, _width = edges_at(sections, x)
        y = upper - 60
        assert collisions.resolve_movement(
            AabbFootprint.from_center(x, y, cave.AVATAR_SIZE, cave.AVATAR_SIZE),
            x=x, y=y, settings=cave.build_traversal_settings(),
        ).accepted
    assert not resolve(cave, 900, 400).accepted
    # Center is dry, but the player's footprint overlaps the shore.
    assert not resolve(cave, 900, 502).accepted
    assert resolve(cave, 900, 520).accepted
    for x, y, _radius, _height in cave.PILLAR_SPECS:
        assert not resolve(cave, x, y).accepted


def test_boundary_notch_between_footprint_corners_is_rejected() -> None:
    sections = (
        cave.CaveSection(0, 10, 100, 200, 0),
        cave.CaveSection(5, 80, 100, 200, 0),
        cave.CaveSection(10, 10, 100, 200, 0),
    )
    collisions = cave.CaveCollisionWorld(sections)
    collisions.gap = 0
    # All four corners are inside, but the lower edge crosses the notch at x=5.
    assert collisions.first_blocker(AabbFootprint(1, 40, 9, 90)) is collisions.boundary
    assert collisions.first_blocker(AabbFootprint(1, 85, 9, 90)) is None


def test_disabled_water_reclaims_floor_and_disabled_pillars_remove_blockers() -> None:
    candidate = host.load_world_candidate(cave)
    candidate.WATER_ENABLED = candidate.PILLARS_ENABLED = False
    scene, _avatar = candidate.build_scene()
    assert not any(isinstance(obj, Line3D) for obj in scene.iter_visible())
    assert not any(isinstance(obj, TriangleMesh3D) and obj.material in candidate.WATER_MATERIALS for obj in scene.iter_visible())
    assert not candidate.effective_world_flags()["WATER_RIPPLES_ENABLED"]
    assert resolve(candidate, 900, 400).accepted
    for x, y, _radius, _height in candidate.PILLAR_SPECS:
        assert resolve(candidate, x, y).accepted
    candidate.WALLS_ENABLED = candidate.CEILING_ENABLED = False
    assert not resolve(candidate, 900, 100).accepted


@pytest.mark.parametrize("zoom", [0.25, 1.0, 3.5])
@pytest.mark.parametrize("pitch,yaw", [(0, 0), (52, 0), (52, 45), (52, 90), (52, 180), (78, 90)])
def test_complex_cave_clipping_keeps_depth_order_acyclic(zoom, pitch, yaw) -> None:
    scene, avatar = cave.build_scene()
    frame = FrameContext(Camera3D(avatar.center, yaw, pitch, zoom), Viewport(900, 600))
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(scene, frame)
    entries, rejected = renderer.project_packets(packets, frame)
    assert rejected > 0
    assert all(
        -1e-7 <= x <= 900 + 1e-7 and -1e-7 <= y <= 600 + 1e-7
        for entry in entries for x, y in entry.points
    )
    materials = [packets[entry.stable_index].material for entry in entries]
    assert cave.AVATAR_MATERIAL in materials
    assert any(material in cave.FLOOR_MATERIALS for material in materials)
    if zoom == 1.0 or (zoom == 3.5 and pitch == 52 and yaw == 0):
        assert any(material in cave.WATER_MATERIALS for material in materials)
    assert not OverlapDepthSorter().sort(entries).cycle_detected


def test_complex_launcher_reload_replaces_shoreline_and_preserves_failed_world(monkeypatch) -> None:
    context = dcg.Context()
    controller, panel = launcher.build_ui(context)
    try:
        assert controller.world_module is cave
        controller.viewport.width = 900
        controller.viewport.height = 600
        panel.telemetry.enabled = True
        controller.render_if_needed()
        assert len(panel.telemetry.samples) == 1
        controller.move_right()
        assert controller.avatar.center[0] == cave.AVATAR_START_XY[0] + cave.GRID_STEP
        old_scene, old_collisions = controller.viewport.scene, controller.collisions
        candidate = host.load_world_candidate(cave)
        candidate.WATER_ENABLED = False
        monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
        controller.reload_world()
        assert controller.scene_generation == 2
        assert controller.viewport.scene is not old_scene and controller.collisions is not old_collisions
        assert not controller.effective_flags["WATER_ENABLED"]
        assert not panel.telemetry.samples
        assert controller.collisions.resolve_movement(AabbFootprint.from_center(900, 400, 8, 8), x=900, y=400).accepted
        controller.render_if_needed()
        before = (controller.world_module, controller.viewport.scene, controller.collisions, controller.avatar,
                  controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
        candidate = host.load_world_candidate(cave)
        candidate.OUTLINE_CONTROLS = candidate.OUTLINE_CONTROLS[:-1]
        controller.reload_world()
        assert "Outline controls must span" in controller.reload_status.value
        assert before == (controller.world_module, controller.viewport.scene, controller.collisions, controller.avatar,
                          controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()
