from __future__ import annotations

from collections import Counter
import math

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import AabbFootprint, Camera3D, CpuRenderer3D, Line3D, OverlapDepthSorter, TraversalRole
from Animation.draw_in_window_3d_framework.math3d import Viewport, cross, dot, length, subtract
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.ported_demos import volcano_cave_hot_reload_profiling as launcher
from Animation.ported_demos import volcano_cave_hot_reload_world as cave
from Animation.ported_demos import town_hot_reload as host


def test_dome_is_inward_facing_hemisphere_with_no_ceiling_holes() -> None:
    candidate = host.load_world_candidate(cave)
    candidate.DOME_ROUGHNESS = 0.0
    meshes = candidate.build_dome()
    frame = FrameContext(Camera3D((*candidate.CENTER, 0), 0, 52, 3.5), Viewport(900, 600))
    edges = Counter()
    for mesh in meshes:
        for x, y, z in mesh.vertices:
            dx, dy = x - candidate.CENTER[0], y - candidate.CENTER[1]
            angle = math.atan2(dy, dx)
            radius = candidate.radial_profile(angle)[2]
            assert (math.hypot(dx, dy) / radius) ** 2 + (z / candidate.DOME_HEIGHT) ** 2 == pytest.approx(1)
        for packet in mesh.collect(frame):
            center = tuple(sum(p[axis] for p in packet.points) / 3 for axis in range(3))
            assert packet.normal is not None
            assert dot(packet.normal, subtract((*candidate.CENTER, 0), center)) > 0
        for indices in mesh.triangles:
            a, b, c = (mesh.vertices[index] for index in indices)
            edges.update((frozenset((a, b)), frozenset((b, c)), frozenset((c, a))))
    boundary = [edge for edge, count in edges.items() if count == 1]
    assert len(boundary) == candidate.SECTORS
    assert all(all(point[2] == 0 for point in edge) for edge in boundary)
    assert all(count in (1, 2) for count in edges.values())


def test_stone_lava_and_bridges_partition_the_chamber_floor() -> None:
    cells = cave.build_floor()
    area = 0.0
    for cell in cells:
        assert cell.walkable is (cell.mesh.material not in cave.LAVA_MATERIALS)
        if not cell.walkable:
            assert all(p[2] == cave.LAVA_LEVEL for p in cell.mesh.vertices)
        if cell.mesh.material is cave.BRIDGE_MATERIAL:
            assert min(p[2] for p in cell.mesh.vertices) > cave.LAVA_LEVEL + cave.BRIDGE_MIN_THICKNESS
            continue
        for indices in cell.mesh.triangles:
            a, b, c = (cell.mesh.vertices[index] for index in indices)
            area += abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * 0.5
    boundary = [
        cave.polar_point(math.tau * sector / cave.SECTORS, cave.radial_profile(math.tau * sector / cave.SECTORS)[2])
        for sector in range(cave.SECTORS)
    ]
    expected_area = abs(sum(
        a[0] * b[1] - b[0] * a[1] for a, b in zip(boundary, boundary[1:] + boundary[:1])
    )) * 0.5
    assert area == pytest.approx(expected_area)
    collisions = cave.build_collision_world()
    scene, _avatar = cave.build_scene()
    lines = [obj for obj in scene.iter_visible() if isinstance(obj, Line3D)]
    assert lines
    for line in lines:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            x, y, _z = (a * (1 - t) + b * t for a, b in zip(line.start, line.end))
            assert collisions.first_blocker(AabbFootprint.from_center(x, y, 0.1, 0.1)) is None
            assert _z == pytest.approx(collisions.terrain.sample(x, y).height + 0.2, abs=1e-7)


def test_raised_islands_and_arch_structure_have_real_relief_and_clear_openings() -> None:
    cells = cave.build_floor()
    terrain = cave.terrain_from_cells(cells)
    island_points = [
        p for cell in cells if cell.walkable for p in cell.mesh.vertices
        if math.hypot(p[0] - cave.CENTER[0], p[1] - cave.CENTER[1])
        <= cave.radial_profile(math.atan2(p[1] - cave.CENTER[1], p[0] - cave.CENTER[0]))[0] + 1e-7
    ]
    assert min(p[2] for p in island_points) >= cave.LAVA_LEVEL + 60 - 1e-7
    assert max(p[2] for p in island_points) - min(p[2] for p in island_points) >= 100
    assert terrain.sample(*cave.CENTER).height == pytest.approx(cave.ISLAND_PEAK_HEIGHT)
    angle = math.radians(cave.SECONDARY_ISLAND_ANGLE_DEG)
    island, lava, _outer = cave.radial_profile(angle)
    radius = island + (lava - island) * (cave.SECONDARY_ISLAND_START + cave.SECONDARY_ISLAND_END) * 0.5
    x, y, _z = cave.polar_point(angle, radius)
    assert terrain.sample(x, y).height >= cave.LAVA_LEVEL + 75
    structures = cave.build_bridge_structure(cells)
    assert structures and cave.build_shore_cliffs(cells)
    frame = FrameContext(Camera3D((*cave.CENTER, cave.ISLAND_PEAK_HEIGHT), 0, 52, 3.5), Viewport(900, 600))
    for mesh in structures:
        for packet in mesh.collect(frame):
            assert packet.normal is not None and packet.normal[2] <= 1e-8
        for x, y, z in mesh.vertices:
            assert z <= terrain.sample(x, y).height + 1e-6
    for axis in (*cave.BRIDGE_ANGLES_DEG, cave.SECONDARY_ISLAND_ANGLE_DEG):
        midpoint = []
        for mesh in structures:
            for x, y, z in mesh.vertices:
                angle = math.atan2(y - cave.CENTER[1], x - cave.CENTER[0])
                if abs(cave.angular_offset(math.degrees(angle), axis)) > cave.BRIDGE_HALF_WIDTH_DEG + 1e-7:
                    continue
                u = cave.bridge_fraction(angle, math.hypot(x - cave.CENTER[0], y - cave.CENTER[1]))
                if axis == cave.SECONDARY_ISLAND_ANGLE_DEG:
                    u /= cave.SECONDARY_ISLAND_START
                if abs(u - 0.5) < 1e-7:
                    midpoint.append(z)
        assert midpoint
        assert min(midpoint) > cave.LAVA_LEVEL + 20
        assert max(midpoint) - min(midpoint) >= cave.BRIDGE_MIN_THICKNESS


def test_boulder_contact_edges_follow_terrain_without_interpenetration() -> None:
    terrain = cave.build_terrain_surface()
    for spec in cave.ROCK_SPECS:
        mesh = cave.rock_mesh(*spec, terrain=terrain)
        count = (len(mesh.vertices) - 1) // 2
        for index in range(count):
            a, b = mesh.vertices[index], mesh.vertices[(index + 1) % count]
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                x, y, z = (a[axis] * (1 - t) + b[axis] * t for axis in range(3))
                assert z - terrain.sample(x, y).height == pytest.approx(0.2, abs=1e-7)
        for triangle in mesh.triangles:
            points = [mesh.vertices[index] for index in triangle]
            x, y, z = (sum(p[axis] for p in points) / 3 for axis in range(3))
            assert z >= terrain.sample(x, y).height + 0.2 - 1e-7


def test_all_three_raised_bridges_are_crossable_with_cardinal_player_steps() -> None:
    context = dcg.Context()
    controller, panel = launcher.build_ui(context)
    try:
        controller.viewport.width = 900
        controller.viewport.height = 600
        controller._configure_follow()
        for angle in (*cave.BRIDGE_ANGLES_DEG, cave.SECONDARY_ISLAND_ANGLE_DEG):
            controller.reset_view()
            assert controller.avatar.center[:2] == cave.CENTER
            assert controller.avatar.center[2] == pytest.approx(cave.ISLAND_PEAK_HEIGHT)
            assert controller.viewport.camera.target[2] == pytest.approx(cave.ISLAND_PEAK_HEIGHT)
            secondary = angle == cave.SECONDARY_ISLAND_ANGLE_DEG
            angle = math.radians(angle)
            heights = []
            for radius in range(12, 321 if secondary else 521, 12):
                desired = (
                    cave.CENTER[0] + round(radius * math.cos(angle) / cave.GRID_STEP) * cave.GRID_STEP,
                    cave.CENTER[1] + round(radius * math.sin(angle) / cave.GRID_STEP) * cave.GRID_STEP,
                )
                while controller.avatar.center[:2] != desired:
                    x, y, _z = controller.avatar.center
                    choices = []
                    if x != desired[0]:
                        dx = math.copysign(cave.GRID_STEP, desired[0] - x)
                        choices.append((x + dx, y, controller.move_right if dx > 0 else controller.move_left))
                    if y != desired[1]:
                        dy = math.copysign(cave.GRID_STEP, desired[1] - y)
                        choices.append((x, y + dy, controller.move_down if dy > 0 else controller.move_up))
                    nx, ny, callback = min(
                        choices,
                        key=lambda choice: abs((choice[0] - cave.CENTER[0]) * math.sin(angle) - (choice[1] - cave.CENTER[1]) * math.cos(angle)),
                    )
                    callback()
                    assert controller.avatar.center[:2] == (nx, ny)
                    assert controller.avatar.center[2] == pytest.approx(controller.terrain.sample(nx, ny).height)
                    assert controller.viewport.camera.target[2] == pytest.approx(controller.avatar.center[2])
                    assert controller.viewport.world_to_screen(controller.avatar.center) is not None
                    heights.append(controller.avatar.center[2])
                if radius in (240, 312 if secondary else 516):
                    controller.render_if_needed()
                    assert not controller.viewport.last_render_stats.cycle_detected
            assert max(heights) - min(heights) > 70
            distance = math.hypot(controller.avatar.center[0] - cave.CENTER[0], controller.avatar.center[1] - cave.CENTER[1])
            assert distance > (300 if secondary else 500)
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()


def test_lava_rejects_partial_footprints_and_gaps_between_dry_corners() -> None:
    collisions = cave.build_collision_world()
    cx, cy = cave.CENTER
    assert collisions.first_blocker(AabbFootprint.from_center(cx, cy + 300, 8, 8)) is collisions.boundary
    assert collisions.first_blocker(AabbFootprint.from_center(cx, cy + 164, 8, 8)) is collisions.boundary
    # Center and all four corners are dry, but most of the rectangle covers lava.
    for x, y in ((cx, cy), (cx - 350, cy - 350), (cx - 350, cy + 350), (cx + 350, cy - 350), (cx + 350, cy + 350)):
        assert collisions.first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is None
    assert collisions.first_blocker(AabbFootprint(cx - 350, cy - 350, cx + 350, cy + 350)) is collisions.boundary


def test_feature_switches_rebuild_bridge_and_lava_traversal() -> None:
    candidate = host.load_world_candidate(cave)
    x, y, _z = candidate.polar_point(0, 300)
    candidate.BRIDGES_ENABLED = False
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is not None
    assert not any(cell.mesh.material == candidate.BRIDGE_MATERIAL for cell in candidate.build_floor())
    assert not candidate.effective_world_flags()["BRIDGE_LINES_ENABLED"]
    candidate.LAVA_ENABLED = False
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is None
    assert all(cell.walkable for cell in candidate.build_floor())
    candidate.ROCKS_ENABLED = False
    candidate.DOME_ENABLED = False
    assert all(collider.role is TraversalRole.TRAVERSABLE for collider in candidate.build_collision_world().colliders)
    assert not candidate.effective_world_flags()["MESH_EDGES_ENABLED"]
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(10, 10, 8, 8)) is not None


def test_secondary_island_and_its_bridge_switch_together_without_ghost_support() -> None:
    candidate = host.load_world_candidate(cave)
    angle = math.radians(candidate.SECONDARY_ISLAND_ANGLE_DEG)
    island, lava, _outer = candidate.radial_profile(angle)
    x, y, _z = candidate.polar_point(angle, island + (lava - island) * 0.58)
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is None
    candidate.SECONDARY_BRIDGE_ENABLED = False
    bx, by, _z = candidate.polar_point(angle, island + (lava - island) * 0.15)
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(bx, by, 8, 8)) is not None
    candidate.SECONDARY_ISLAND_ENABLED = False
    assert candidate.build_terrain_surface().sample(x, y) is None
    assert not candidate.effective_world_flags()["SECONDARY_BRIDGE_ENABLED"]
    assert candidate.build_collision_world().first_blocker(AabbFootprint.from_center(x, y, 8, 8)) is not None
    candidate.DOME_ENABLED = candidate.ROCKS_ENABLED = False
    candidate.MESH_EDGES_ENABLED = True
    assert candidate.effective_world_flags()["MESH_EDGES_ENABLED"]


@pytest.mark.parametrize("zoom", [0.25, 1.0, 3.5])
@pytest.mark.parametrize("pitch,yaw", [(0, 0), (52, 0), (52, 45), (52, 90), (52, 180), (78, 90)])
def test_domelike_volcano_camera_clipping_preserves_order(zoom, pitch, yaw) -> None:
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
    if pitch != 0 or zoom != 3.5:
        assert any(material in cave.LAVA_MATERIALS for material in materials)
    if zoom <= 1:
        assert cave.BRIDGE_MATERIAL in materials
    assert not OverlapDepthSorter().sort(entries).cycle_detected


@pytest.mark.parametrize("bad_setting,message", [
    ("DOME_RADIUS", "radii must be positive and increasing"),
    ("BRIDGE_ARCH_RISE", "insufficient stone beneath the deck"),
])
def test_volcano_reload_updates_hazards_and_preserves_bad_candidate(monkeypatch, bad_setting, message) -> None:
    context = dcg.Context()
    controller, panel = launcher.build_ui(context)
    try:
        controller.viewport.width = 900
        controller.viewport.height = 600
        panel.telemetry.enabled = True
        controller.render_if_needed()
        assert len(panel.telemetry.samples) == 1
        load_candidate = host.load_world_candidate
        candidate = load_candidate(cave)
        candidate.LAVA_ENABLED = False
        candidate.ISLAND_PEAK_HEIGHT = 210
        old_scene, old_collisions = controller.viewport.scene, controller.collisions
        monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
        controller.reload_world()
        assert controller.viewport.scene is not old_scene and controller.collisions is not old_collisions
        assert controller.scene_generation == 2
        assert not controller.effective_flags["LAVA_ENABLED"]
        assert controller.avatar.center[2] == pytest.approx(210)
        assert controller.viewport.camera.target[2] == pytest.approx(210)
        assert controller.viewport.terrain is controller.terrain is controller.follow.terrain
        assert not panel.telemetry.samples
        controller.render_if_needed()
        before = (controller.world_module, controller.viewport.scene, controller.collisions, controller.terrain, controller.avatar,
                  controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
        candidate = load_candidate(cave)
        setattr(candidate, bad_setting, candidate.ISLAND_RADIUS if bad_setting == "DOME_RADIUS" else 200.0)
        controller.reload_world()
        assert message in controller.reload_status.value
        assert before == (controller.world_module, controller.viewport.scene, controller.collisions, controller.terrain, controller.avatar,
                          controller.effective_flags, controller.scene_generation, panel.telemetry.snapshot())
    finally:
        panel.shutdown()
        panel.window.delete_item()
        controller.viewport.delete_item()
