from __future__ import annotations

from itertools import combinations

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import (
    AabbFootprint, Camera3D, CpuRenderer3D, OverlapDepthSorter, Polygon3D, TriangleMesh3D,
)
from Animation.draw_in_window_3d_framework.math3d import Viewport, cross, length, subtract
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.draw_in_window_3d_framework.renderer import _point_in_polygon
from Animation.ported_demos import complex_cave_hot_reload_world as natural
from Animation.ported_demos import organic_frozen_temple_hot_reload_profiling as launcher
from Animation.ported_demos import organic_frozen_temple_hot_reload_world as temple
from Animation.ported_demos import town_hot_reload as host


def triangle_area(mesh: TriangleMesh3D | Polygon3D) -> float:
    points = mesh.points if isinstance(mesh, Polygon3D) else mesh.vertices
    triangles = tuple((0, i, i + 1) for i in range(1, len(points) - 1)) if isinstance(mesh, Polygon3D) else mesh.triangles
    return sum(
        length(cross(subtract(points[b], points[a]), subtract(points[c], points[a]))) * 0.5
        for a, b, c in triangles
    )


def entrance_ring(world):
    sections = world.cave_sections()
    return world.cave_rings(sections)[next(i for i, section in enumerate(sections) if section.x == world.DOOR_X)]


def test_organic_floor_matches_complex_cave_and_frozen_lake_is_traversable() -> None:
    sections = temple.cave_sections()
    assert sections == natural.cave_sections()
    assert max(s.upper - s.lower for s in sections) > 3 * min(s.upper - s.lower for s in sections)
    candidate = host.load_world_candidate(temple)
    candidate.SANCTUM_ENABLED = False
    for enabled in (True, False):
        candidate.FROZEN_LAKE_ENABLED = enabled
        scene, _ = candidate.build_scene()
        floor = [
            obj for obj in scene.iter_visible() if isinstance(obj, TriangleMesh3D)
            and obj.material in (*candidate.FLOOR_MATERIALS, *candidate.LAKE_MATERIALS, candidate.WARM_FLOOR_MATERIAL)
        ]
        assert all(p[2] == 0 for mesh in floor for p in mesh.vertices)
        expected = sum((b.x - a.x) * (a.upper - a.lower + b.upper - b.lower) * 0.5 for a, b in zip(sections, sections[1:]))
        assert sum(triangle_area(mesh) for mesh in floor) == pytest.approx(expected)
        assert any(mesh.material in candidate.LAKE_MATERIALS for mesh in floor) is enabled
        collisions = candidate.build_collision_world()
        assert collisions.first_blocker(AabbFootprint.from_center(900, 400, 8, 8)) is None
        assert collisions.first_blocker(AabbFootprint.from_center(900, 200, 8, 8)) is collisions.boundary


def test_props_and_icicles_fit_inside_the_organic_shell() -> None:
    surface = temple.roof_surface(temple.cave_rings(temple.cave_sections()))
    props = temple.floor_props()
    for (_, first), (_, second) in combinations(props, 2):
        assert not temple.prop_footprint(first).conflicts(temple.prop_footprint(second), gap=0.2)
    for _, meshes in props:
        for first, second in combinations(meshes, 2):
            assert max(p[2] for p in first.vertices) + 0.19 < min(p[2] for p in second.vertices)
        for mesh in meshes:
            for x, y, z in mesh.vertices:
                assert 0.2 <= z < surface.sample(x, y).height - 0.2
    for mesh in temple.hanging_icicles(surface):
        assert min(p[2] for p in mesh.vertices) > temple.AVATAR_HEIGHT
        for x, y, z in mesh.vertices:
            assert z <= surface.sample(x, y).height - 0.19


def test_entrance_wall_has_a_real_rectangular_hole_and_matching_blockers() -> None:
    ring = entrance_ring(temple)
    lower, upper = temple.doorway_bounds(ring)
    full_area = sum(
        (a[2] + b[2]) * abs(b[1] - a[1]) * 0.5 for a, b in zip(ring, ring[1:])
    )
    wall = temple.entrance_wall(ring)
    assert sum(triangle_area(mesh) for mesh in wall) == pytest.approx(full_area - temple.DOOR_WIDTH * temple.DOOR_HEIGHT)
    for mesh in wall:
        clipped = temple.clip_polygon(mesh.vertices, 1, lower, above=True)
        clipped = temple.clip_polygon(clipped, 1, upper, above=False)
        clipped = temple.clip_polygon(clipped, 2, temple.DOOR_HEIGHT, above=False)
        if len(clipped) >= 3:
            assert triangle_area(TriangleMesh3D(
                vertices=clipped, triangles=tuple((0, i, i + 1) for i in range(1, len(clipped) - 1)),
                material=temple.ENTRY_WALL_MATERIAL,
            )) < 1e-7
    boxes = temple.doorway_frame(ring)
    for first, second in combinations(boxes, 2):
        assert any(
            abs(first.center[axis] - second.center[axis]) >= (first.size[axis] + second.size[axis]) * 0.5 + 0.19
            for axis in (0, 1)
        ) or first.center[2] + first.size[2] + 0.19 < second.center[2] or second.center[2] + second.size[2] + 0.19 < first.center[2]
    collisions = temple.build_collision_world()
    for x in range(84, 169, 12):
        assert collisions.first_blocker(AabbFootprint.from_center(x, (lower + upper) * 0.5, 8, 8)) is None
    for y in (lower - 6, lower + 2, upper - 2, upper + 6):
        assert collisions.first_blocker(AabbFootprint.from_center(temple.DOOR_X, y, 8, 8)) is not None
    candidate = host.load_world_candidate(temple)
    candidate.DOORWAY_ENABLED = False
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(temple.DOOR_X, lower - 6, 8, 8)) is None
    scene, _ = candidate.build_scene()
    assert not any(
        isinstance(obj, TriangleMesh3D) and obj.material == candidate.ENTRY_WALL_MATERIAL
        and all(p[0] == candidate.DOOR_X for p in obj.vertices)
        for obj in scene.iter_visible()
    )


@pytest.mark.parametrize("target", [(840, 600, 0), (120, 240, 0)])
@pytest.mark.parametrize("zoom", [0.25, 1.0, 3.5])
@pytest.mark.parametrize("pitch,yaw", [(0, 0), (52, 0), (52, 45), (52, 90), (52, 180), (78, 90)])
def test_organic_temple_and_doorway_clipping_keep_painter_order(target, zoom, pitch, yaw) -> None:
    scene, avatar = temple.build_scene()
    avatar.center = target
    frame = FrameContext(Camera3D(target, yaw, pitch, zoom), Viewport(900, 600))
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(scene, frame)
    entries, _ = renderer.project_packets(packets, frame)
    assert entries
    assert all(-1e-7 <= x <= 900 + 1e-7 and -1e-7 <= y <= 600 + 1e-7 for entry in entries for x, y in entry.points)
    materials = [packets[entry.stable_index].material for entry in entries]
    assert temple.AVATAR_MATERIAL in materials
    assert any(material in temple.FLOOR_MATERIALS for material in materials)
    if target[0] == 120 and pitch != 0 and zoom <= 1:
        assert temple.GOLD_MATERIAL in materials
        if yaw not in (0, 180):
            assert temple.ENTRY_WALL_MATERIAL in materials
    assert not OverlapDepthSorter().sort(entries).cycle_detected


def test_launcher_walks_through_doorway_and_reloads_complete_bundle(monkeypatch) -> None:
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
        route = ((controller.move_left, 28), (controller.move_up, 20), (controller.move_left, 7),
                 (controller.move_up, 5), (controller.move_left, 15), (controller.move_up, 5),
                 (controller.move_left, 13))
        for callback, count in route:
            for _ in range(count):
                before = controller.avatar.center
                callback()
                assert controller.avatar.center != before
                assert controller.avatar.center[2] == 0
        assert controller.avatar.center == (84, 240, 0)
        load_candidate = host.load_world_candidate
        candidate = load_candidate(temple)
        candidate.PILLARS_ENABLED = candidate.SHRINE_ENABLED = candidate.BRAZIERS_ENABLED = False
        candidate.RUBBLE_ENABLED = candidate.DOORWAY_ENABLED = candidate.CEILING_ENABLED = False
        candidate.SANCTUM_ENABLED = False
        monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
        old_scene, old_collisions = controller.viewport.scene, controller.collisions
        controller.reload_world()
        assert controller.viewport.scene is not old_scene
        assert controller.collisions is not old_collisions and not controller.collisions.colliders
        assert not controller.effective_flags["ICICLES_ENABLED"]
        assert controller.scene_generation == 2 and not panel.telemetry.samples
        controller.render_if_needed()
        before = (controller.world_module, controller.viewport.scene, controller.collisions, controller.avatar,
                  controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
        for name, value, message in (
            ("DOOR_HEIGHT", 500, "fit inside the cave end wall"),
            ("DOOR_WIDTH", float("nan"), "dimensions must be finite"),
            ("SANCTUM_HEIGHT", 500, "fit below the cave roof"),
            ("RIDGE_WIDTH", -1, "ridge width"),
        ):
            candidate = load_candidate(temple)
            setattr(candidate, name, value)
            controller.reload_world()
            assert message in controller.reload_status.value
            assert before == (controller.world_module, controller.viewport.scene, controller.collisions, controller.avatar,
                              controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()


def test_door_between_stations_preserves_floor_outline_and_clear_passage() -> None:
    candidate = host.load_world_candidate(temple)
    candidate.DOOR_X = 125.0
    sections = candidate.cave_sections()
    original = natural.cave_sections()
    assert tuple(s for s in sections if s.x != 125) == original
    first, second = next((a, b) for a, b in zip(original, original[1:]) if a.x < 125 < b.x)
    inserted = next(s for s in sections if s.x == 125)
    t = (125 - first.x) / (second.x - first.x)
    assert inserted[1:] == pytest.approx(tuple(a + (b - a) * t for a, b in zip(first[1:], second[1:])))
    ring = entrance_ring(candidate)
    lower, upper = candidate.doorway_bounds(ring)
    candidate.build_scene()
    collisions = candidate.build_collision_world()
    assert collisions.first_blocker(AabbFootprint.from_center(125, (lower + upper) * 0.5, 8, 8)) is None


def test_sanctum_recess_has_an_open_front_glow_and_matching_walls() -> None:
    surface = temple.roof_surface(temple.cave_rings(temple.cave_sections()))
    objects = temple.sanctum_geometry(surface)
    lower, upper = temple.SANCTUM_X - temple.SANCTUM_WIDTH / 2, temple.SANCTUM_X + temple.SANCTUM_WIDTH / 2
    for obj in objects:
        if not isinstance(obj, TriangleMesh3D) or obj.material != temple.ENTRY_WALL_MATERIAL:
            continue
        clipped = temple.clip_polygon(obj.vertices, 0, lower, above=True)
        clipped = temple.clip_polygon(clipped, 0, upper, above=False)
        clipped = temple.clip_polygon(clipped, 2, temple.SANCTUM_HEIGHT, above=False)
        if len(clipped) >= 3:
            assert triangle_area(temple.polygon_mesh(clipped, temple.ENTRY_WALL_MATERIAL)) < 1e-7
    scene, _ = temple.build_scene()
    glow = [obj for obj in scene.iter_visible() if isinstance(obj, Polygon3D) and obj.material == temple.GLOW_MATERIAL]
    assert len(glow) == 1
    frame = FrameContext(Camera3D((1000, 940, 0), 0, 0, 3.5), Viewport(900, 600))
    packets = tuple(glow[0].collect(frame))
    assert len(packets) == 1 and len(packets[0].points) == 4
    lit_tiles = [
        obj for obj in scene.iter_visible()
        if isinstance(obj, Polygon3D) and obj.material in temple.GLOW_FLOOR_MATERIALS
    ]
    assert lit_tiles and all(p[2] == 0 for tile in lit_tiles for p in tile.points)
    assert all(len(tuple(tile.collect(frame))) == 1 for tile in lit_tiles)
    assert len({tile.material for tile in lit_tiles}) > 1
    collisions = temple.build_collision_world()
    for y in range(840, 985, 12):
        assert collisions.first_blocker(AabbFootprint.from_center(1000, y, 8, 8)) is None
    for x, y in ((lower + 2, 880), (upper - 2, 880), (1000, 999), (1000, 1020), (860, 950)):
        assert collisions.first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is not None
    candidate = host.load_world_candidate(temple)
    candidate.SANCTUM_GLOW_ENABLED = False
    scene, _ = candidate.build_scene()
    assert not any(
        getattr(obj, "material", None) in (candidate.GLOW_MATERIAL, *candidate.GLOW_FLOOR_MATERIALS)
        for obj in scene.iter_visible()
    )
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(1000, 960, 8, 8)) is None
    candidate.SANCTUM_ENABLED = False
    assert not candidate.effective_world_flags()["SANCTUM_GLOW_ENABLED"]
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(1000, 1020, 8, 8)) is None


def test_ice_ridge_is_part_of_the_shell_and_has_more_hanging_ice() -> None:
    sections = temple.cave_sections()
    rings = temple.cave_rings(sections)
    icicles = temple.ridge_icicles(sections, rings)
    underside = temple.roof_surface(rings, arcs=(temple.ARCH_SEGMENTS // 4 + 1,
                                               temple.ARCH_SEGMENTS - temple.ARCH_SEGMENTS // 4 + 6))
    assert len(icicles) > len(temple.ICICLE_POSITIONS)
    for mesh in icicles:
        assert min(p[2] for p in mesh.vertices) > temple.AVATAR_HEIGHT
        base = mesh.vertices[1:]
        for a, b in zip(base, (*base[1:], base[0])):
            for t in (0, 0.25, 0.5, 0.75):
                x, y, z = (v + (w - v) * t for v, w in zip(a, b))
                assert underside.sample(x, y).height - z >= 0.19
    scene, _ = temple.build_scene()
    assert any(isinstance(obj, TriangleMesh3D) and obj.material == temple.RIDGE_MATERIAL for obj in scene.iter_visible())
    candidate = host.load_world_candidate(temple)
    candidate.ICE_RIDGE_ENABLED = False
    scene, _ = candidate.build_scene()
    assert not any(isinstance(obj, TriangleMesh3D) and obj.material == candidate.RIDGE_MATERIAL for obj in scene.iter_visible())
    candidate.WALLS_ENABLED = False
    assert not candidate.effective_world_flags()["ICE_RIDGE_ENABLED"]


@pytest.mark.parametrize("pitch,yaw,zoom", [(62.8, 113.3, 0.98), (52, 90, 1), (52, 135, 1), (78, 90, 0.25)])
def test_glowing_doorway_and_ridge_visible_at_reference_camera(pitch, yaw, zoom) -> None:
    scene, avatar = temple.build_scene()
    frame = FrameContext(Camera3D(avatar.center, yaw, pitch, zoom), Viewport(900, 600))
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(scene, frame)
    entries, _ = renderer.project_packets(packets, frame)
    materials = [packets[e.stable_index].material for e in entries]
    assert temple.GLOW_MATERIAL in materials
    assert temple.RIDGE_MATERIAL in materials
    ordered = OverlapDepthSorter().sort(entries, frame)
    assert not ordered.cycle_detected
    if pitch == 62.8:
        glow_entries = [
            entry for entry in entries if packets[entry.stable_index].material == temple.GLOW_MATERIAL
        ]
        visible = []
        for entry in glow_entries:
            for index in range(1, len(entry.points) - 1):
                a, b, c = entry.points[0], entry.points[index], entry.points[index + 1]
                for weights in ((0.2, 0.2, 0.6), (0.2, 0.6, 0.2), (0.6, 0.2, 0.2), (1 / 3, 1 / 3, 1 / 3)):
                    point = tuple(sum(p[axis] * weight for p, weight in zip((a, b, c), weights)) for axis in (0, 1))
                    last = next(e for e in reversed(ordered.entries) if e.kind == "polygon" and _point_in_polygon(point, e.points))
                    visible.append(last.stable_index == entry.stable_index)
        assert any(visible), "The warm interior must be visible through the doorway, not painted over"


@pytest.mark.parametrize("yaw,zoom", [(0, 1.0), (90, 1.0), (0, 0.25)])
def test_coplanar_edge_filter_matches_temple_baseline(yaw, zoom) -> None:
    scene, avatar = temple.build_scene()
    frame = FrameContext(Camera3D(avatar.center, yaw, 52, zoom), Viewport(900, 600))
    experimental = OverlapDepthSorter(use_coplanar_edge_filter=True)
    renderer = CpuRenderer3D(experimental)
    entries, _ = renderer.project_packets(renderer.collect_packets(scene, frame), frame)

    baseline_sorter = OverlapDepthSorter()
    baseline = baseline_sorter.sort(entries, frame)
    actual = experimental.sort(entries, frame)

    assert baseline.sort_stats is not None and actual.sort_stats is not None
    assert actual.sort_stats.skipped_pair_count > 0
    assert actual.sort_stats.exact_test_count + actual.sort_stats.skipped_pair_count == baseline.sort_stats.exact_test_count
    assert actual.sort_stats.accepted_edge_count == baseline.sort_stats.accepted_edge_count
    baseline_pairs, _, _ = baseline_sorter.generate_candidates(entries)
    experimental_pairs, _, _ = experimental.generate_candidates(entries)
    assert baseline_sorter.test_overlaps(entries, baseline_pairs, frame) == experimental.test_overlaps(
        entries, experimental_pairs, frame,
    )
    assert [entry.stable_index for entry in actual.entries] == [entry.stable_index for entry in baseline.entries]
    assert actual.cycle_detected == baseline.cycle_detected


def test_sanctum_floor_cutout_is_flush_and_has_no_missing_or_double_tiles() -> None:
    sections = temple.cave_sections()
    expected = 0.0
    for a, b in zip(sections, sections[1:]):
        points = ((a.x, a.lower, 0), (b.x, b.lower, 0), (b.x, b.upper, 0), (a.x, a.upper, 0))
        expected += triangle_area(temple.polygon_mesh(points, temple.WALL_MATERIAL))
        removed = temple.clip_polygon(points, 0, temple.SANCTUM_X - temple.SANCTUM_WALL_WIDTH / 2, above=True)
        removed = temple.clip_polygon(removed, 0, temple.SANCTUM_X + temple.SANCTUM_WALL_WIDTH / 2, above=False)
        removed = temple.clip_polygon(removed, 1, temple.SANCTUM_BACK_Y, above=True)
        if len(removed) >= 3:
            expected -= triangle_area(temple.polygon_mesh(removed, temple.WALL_MATERIAL))
    scene, _ = temple.build_scene()
    floor = [
        obj for obj in scene.iter_visible() if isinstance(obj, (TriangleMesh3D, Polygon3D))
        and all(p[2] == 0 for p in (obj.points if isinstance(obj, Polygon3D) else obj.vertices))
        and obj.material in (*temple.FLOOR_MATERIALS, *temple.LAKE_MATERIALS,
                             *temple.GLOW_FLOOR_MATERIALS, temple.WARM_FLOOR_MATERIAL)
    ]
    assert sum(triangle_area(mesh) for mesh in floor) == pytest.approx(expected)


def test_player_can_walk_into_the_glowing_recess_but_not_through_its_back_wall() -> None:
    context = dcg.Context()
    controller, panel = launcher.build_ui(context)
    try:
        for callback, count in ((controller.move_down, 20), (controller.move_right, 13), (controller.move_down, 12)):
            for _ in range(count):
                before = controller.avatar.center
                callback()
                assert controller.avatar.center != before
        assert controller.avatar.center == (996, 984, 0)
        controller.move_down()
        assert controller.avatar.center == (996, 984, 0)
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()
