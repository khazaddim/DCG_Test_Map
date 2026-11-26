from __future__ import annotations

from itertools import combinations

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import AabbFootprint, Camera3D, CpuRenderer3D, MeshTerrainSurface, OverlapDepthSorter, TriangleMesh3D
from Animation.draw_in_window_3d_framework.math3d import Viewport, cross, length, subtract
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.ported_demos import trippy_cave_hot_reload_profiling as launcher
from Animation.ported_demos import trippy_cave_hot_reload_world as cave
from Animation.ported_demos import town_hot_reload as host


def test_crystal_shards_have_clearance_and_fit_below_the_mesh_ceiling() -> None:
    scene, _avatar = cave.build_scene()
    vertices, triangles = [], []
    for obj in scene.iter_visible():
        if not isinstance(obj, TriangleMesh3D):
            continue
        if obj.material not in cave.WALL_MATERIALS and obj.material != cave.CEILING_MATERIAL:
            continue
        base = len(vertices)
        vertices.extend(obj.vertices)
        triangles.extend(tuple(index + base for index in triangle) for triangle in obj.triangles)
    ceiling = MeshTerrainSurface(vertices=tuple(vertices), triangles=tuple(triangles))
    for spec in cave.CRYSTAL_SPECS:
        cluster = cave.crystal_cluster(*spec)
        for first, second in combinations(cluster, 2):
            a, b = cave.cluster_footprint((first,)), cave.cluster_footprint((second,))
            assert not a.conflicts(b, gap=0.2)
        for mesh in cluster:
            for x, y, z in mesh.vertices:
                support = ceiling.sample(x, y)
                assert z >= 0.2
                assert support is not None and z < support.height - 0.2
    for mesh in (
        obj for obj in scene.iter_visible()
        if isinstance(obj, TriangleMesh3D) and obj.material in (cave.GEM_TOP_MATERIAL, cave.GEM_BOTTOM_MATERIAL)
    ):
        assert min(point[2] for point in mesh.vertices) > cave.AVATAR_HEIGHT


def test_floor_veins_are_flat_replacement_patches_and_disabling_props_removes_blockers() -> None:
    candidate = host.load_world_candidate(cave)
    areas = []
    for veins in (True, False):
        candidate.FLOOR_VEINS_ENABLED = veins
        scene, _avatar = candidate.build_scene()
        area = 0.0
        for mesh in scene.iter_visible():
            if not isinstance(mesh, TriangleMesh3D) or mesh.material not in (*candidate.FLOOR_MATERIALS, candidate.VEIN_MATERIAL):
                continue
            assert all(point[2] == 0 for point in mesh.vertices)
            for indices in mesh.triangles:
                a, b, c = (mesh.vertices[index] for index in indices)
                area += length(cross(subtract(b, a), subtract(c, a))) * 0.5
        areas.append(area)
        assert any(
            isinstance(mesh, TriangleMesh3D) and mesh.material == candidate.VEIN_MATERIAL
            for mesh in scene.iter_visible()
        ) is veins
    sections = candidate.cave_sections()
    expected_area = sum((b.x - a.x) * (a.upper - a.lower + b.upper - b.lower) * 0.5 for a, b in zip(sections, sections[1:]))
    assert areas == pytest.approx([expected_area, expected_area])
    collisions = candidate.build_collision_world()
    for x, y, _height in candidate.CRYSTAL_SPECS:
        assert collisions.first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is not None
    for x, y, _z in candidate.FLOATING_GEM_POSITIONS:
        assert collisions.first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is None
    candidate.CRYSTALS_ENABLED = candidate.FLOATING_GEMS_ENABLED = False
    candidate.WALLS_ENABLED = candidate.CEILING_ENABLED = False
    collisions = candidate.build_collision_world()
    assert not collisions.colliders
    for x, y, _height in candidate.CRYSTAL_SPECS:
        assert collisions.first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is None
    assert collisions.first_blocker(AabbFootprint.from_center(900, 20, 8, 8)) is collisions.boundary
    assert not candidate.effective_world_flags()["MESH_EDGES_ENABLED"]


@pytest.mark.parametrize("zoom", [0.25, 1.0, 3.5])
@pytest.mark.parametrize("pitch,yaw", [(0, 0), (52, 0), (52, 45), (52, 90), (52, 180), (78, 90)])
def test_trippy_cave_clipping_preserves_depth_order_and_neon_visibility(zoom, pitch, yaw) -> None:
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
    assert cave.AVATAR_MATERIAL in materials and cave.VEIN_MATERIAL in materials
    assert any(material in (cave.GEM_TOP_MATERIAL, cave.GEM_BOTTOM_MATERIAL) for material in materials)
    if pitch != 0:
        assert any(material in cave.CRYSTAL_MATERIALS for material in materials)
    assert not OverlapDepthSorter().sort(entries).cycle_detected


def test_trippy_launcher_publishes_reloads_and_keeps_failed_candidate_isolated(monkeypatch) -> None:
    context = dcg.Context()
    controller, panel = launcher.build_ui(context)
    try:
        assert controller.world_module is cave
        controller.viewport.width = 900
        controller.viewport.height = 600
        panel.telemetry.enabled = True
        controller.render_if_needed()
        assert len(panel.telemetry.samples) == 1
        assert controller.viewport.last_render_stats.emitted_count > 1
        controller.move_right()
        assert controller.avatar.center == (cave.AVATAR_START_XY[0] + cave.GRID_STEP, cave.AVATAR_START_XY[1], 0)
        old_scene, old_collisions = controller.viewport.scene, controller.collisions
        load_candidate = host.load_world_candidate
        candidate = load_candidate(cave)
        candidate.CRYSTALS_ENABLED = False
        candidate.FLOOR_VEINS_ENABLED = False
        monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
        controller.reload_world()
        assert controller.viewport.scene is not old_scene and controller.collisions is not old_collisions
        assert not controller.collisions.colliders
        assert controller.scene_generation == 2
        assert not panel.telemetry.samples
        controller.render_if_needed()
        before = (controller.world_module, controller.viewport.scene, controller.collisions, controller.avatar,
                  controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
        candidate = load_candidate(cave)
        candidate.CRYSTAL_SPECS = ((10.0, 10.0, 100.0),)
        controller.reload_world()
        assert "overlaps the cave boundary" in controller.reload_status.value
        assert before == (controller.world_module, controller.viewport.scene, controller.collisions, controller.avatar,
                          controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()
