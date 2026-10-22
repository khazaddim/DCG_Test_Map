from __future__ import annotations

from itertools import combinations, product

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import Box3D, Camera3D, CpuRenderer3D, GroundPlane3D, ImageMaterial, OverlapDepthSorter
from Animation.draw_in_window_3d_framework.math3d import Viewport
from Animation.draw_in_window_3d_framework.scene import FrameContext
from Animation.ported_demos import open_room_hot_reload_world as room
from Animation.ported_demos import town_hot_reload as host


def box_bounds(box: Box3D) -> tuple[tuple[float, float], ...]:
    x, y, z = box.center
    width, depth, height = box.size
    return (
        (x - width * 0.5, x + width * 0.5),
        (y - depth * 0.5, y + depth * 0.5),
        (z, z + height),
    )


def test_room_parts_have_clearance_instead_of_intersections_or_shared_faces() -> None:
    scene, avatar = room.build_scene()
    boxes = [obj for obj in scene.iter_visible() if isinstance(obj, Box3D)]
    for first, second in combinations(boxes, 2):
        assert any(
            max(b_min - a_max, a_min - b_max) >= room.PART_GAP - 1e-7
            for (a_min, a_max), (b_min, b_max) in zip(box_bounds(first), box_bounds(second))
        ), f"Parts have no clearance: {first.center}/{first.size}, {second.center}/{second.size}"
    assert all(
        box.center[2] >= room.PART_GAP or box.center[2] + box.size[2] <= 0
        for box in boxes if box is not avatar
    )


def test_floor_and_rug_tile_the_room_without_overlapping_surfaces() -> None:
    scene, _ = room.build_scene()
    planes = [obj for obj in scene.iter_visible() if isinstance(obj, GroundPlane3D)]
    assert len(planes) == 4
    assert all(plane.z == 0 for plane in planes)
    bounds = [plane.bounds for plane in planes] + [room.RUG_BOUNDS]
    assert sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in bounds) == pytest.approx(
        room.WORLD_W * room.WORLD_H
    )
    for first, second in combinations(bounds, 2):
        ax0, ay0, ax1, ay1 = first
        bx0, by0, bx1, by1 = second
        assert min(ax1, bx1) <= max(ax0, bx0) or min(ay1, by1) <= max(ay0, by0)


def test_rug_texture_is_retained_reloaded_and_emitted_on_the_flush_box_top() -> None:
    context = dcg.Context()
    prepared = host.build_world(context, room)
    rug = next(
        obj for obj in prepared.scene.iter_visible()
        if isinstance(obj, Box3D) and obj.face_materials is not None
    )
    assert rug.center[2] + rug.size[2] == 0
    top = rug.face_materials[1]
    assert isinstance(top, ImageMaterial)
    assert top.texture is prepared.road_texture is not None
    assert all(material is None for index, material in enumerate(rug.face_materials) if index != 1)
    frame = FrameContext(
        camera=Camera3D(target=prepared.avatar.center, yaw_deg=45, pitch_deg=52, zoom=3.5),
        viewport=Viewport(900, 600),
    )
    drawing = dcg.DrawingList(context)
    try:
        stats = CpuRenderer3D().render(context, drawing, prepared.scene, frame.camera, frame.viewport)
        assert not stats.cycle_detected
        assert sum(type(child).__name__ == "DrawImage" for child in drawing.children) == top.tessellation ** 2
        candidate = host.build_world(context, host.load_world_candidate(room))
        assert candidate.road_texture is not prepared.road_texture
    finally:
        drawing.delete_item()


@pytest.mark.parametrize("pitch", [0.0, 30.0, 47.1, 52.0, 65.0, 78.0])
@pytest.mark.parametrize("width", [900, 1540])
@pytest.mark.parametrize("zoom", [3.5, 12.0])
def test_room_rotation_preserves_depth_constraints_without_cycle_fallback(pitch, width, zoom) -> None:
    context = dcg.Context()
    scene, avatar = room.build_scene(room.create_road_texture(context))
    renderer = CpuRenderer3D()
    sorter = OverlapDepthSorter()
    floor_indices = set()
    above_floor_indices = set()
    packet_index = 0
    initial_frame = FrameContext(
        camera=Camera3D(target=avatar.center, yaw_deg=0, pitch_deg=pitch, zoom=zoom),
        viewport=Viewport(width, 600),
    )
    for obj in scene.iter_visible():
        for _packet in obj.collect(initial_frame):
            if isinstance(obj, GroundPlane3D):
                floor_indices.add(packet_index)
            if any(point[2] > 0 for point in _packet.points):
                above_floor_indices.add(packet_index)
            packet_index += 1
    for yaw in (*range(-180, 181, 5), 86.5):
        frame = FrameContext(
            camera=Camera3D(target=avatar.center, yaw_deg=yaw, pitch_deg=pitch, zoom=zoom),
            viewport=Viewport(width, 600),
        )
        entries, _ = renderer.project_packets(renderer.collect_packets(scene, frame), frame)
        result = sorter.sort(entries, frame)
        assert not result.cycle_detected, f"Cycle at pitch={pitch}, yaw={yaw}, width={width}, zoom={zoom}"
        candidates, _, _ = sorter.generate_candidates(entries)
        edges = sorter.test_overlaps(entries, candidates, frame)
        ranks = {entry.stable_index: index for index, entry in enumerate(result.entries)}
        assert all(ranks[entries[far].stable_index] < ranks[entries[near].stable_index] for far, near in edges)
        assert all(
            entries[far].stable_index not in above_floor_indices or entries[near].stable_index not in floor_indices
            for far, near in edges
        ), (
            f"Floor occludes a room part at pitch={pitch}, yaw={yaw}, width={width}"
        )


@pytest.mark.parametrize("flag", ["ROOM_ENABLED", "FURNITURE_ENABLED"])
def test_disabled_room_groups_remove_geometry_and_collisions(flag) -> None:
    candidate = host.load_world_candidate(room)
    setattr(candidate, flag, False)
    scene, _ = candidate.build_scene()
    assert scene.object_count == (2 if flag == "ROOM_ENABLED" else 6)
    assert len(candidate.build_collision_world().colliders) == (0 if flag == "ROOM_ENABLED" else 2)
    assert not candidate.effective_world_flags()["FURNITURE_ENABLED"]
    assert candidate.create_road_texture(dcg.Context()) is None
    if flag == "ROOM_ENABLED":
        assert not any(candidate.effective_world_flags().values())


@pytest.mark.parametrize(("wall", "xy"), [("front wall", (45.0, 2.0)), ("right wall", (88.0, 40.0))])
def test_added_walls_block_avatar_movement(wall, xy, monkeypatch) -> None:
    monkeypatch.setattr(room, "FRONT_WALL_ENABLED", True)
    monkeypatch.setattr(room, "RIGHT_WALL_ENABLED", True)
    collisions = room.build_collision_world()
    footprint = room.AabbFootprint.from_center(*xy, room.AVATAR_SIZE, room.AVATAR_SIZE)
    blocker = collisions.first_blocker(footprint)
    assert blocker is not None
    assert blocker.owner == wall
    assert not collisions.resolve_movement(
        footprint, x=xy[0], y=xy[1], settings=room.build_traversal_settings(),
    ).accepted


def test_interior_camera_clips_wall_faces_without_hiding_wall_objects(monkeypatch) -> None:
    monkeypatch.setattr(room, "FRONT_WALL_ENABLED", True)
    monkeypatch.setattr(room, "RIGHT_WALL_ENABLED", True)
    scene, _ = room.build_scene()
    frame = FrameContext(
        camera=Camera3D(target=(45.0, 40.0, 0.0), yaw_deg=0, pitch_deg=52, zoom=12),
        viewport=Viewport(900, 600),
    )
    eye = frame.camera.eye(frame.viewport)
    assert 4 < eye[0] < 86 and 4 < eye[1] < 76 and 0 < eye[2] < 38
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(scene, frame)
    entries, _ = renderer.project_packets(packets, frame)
    crossing_wall_indices = {
        index for index, packet in enumerate(packets)
        if packet.material is room.WALL_MATERIAL
        and min(frame.camera.world_to_camera(point, frame.viewport)[2] for point in packet.points)
        < frame.camera.near_plane
        < max(frame.camera.world_to_camera(point, frame.viewport)[2] for point in packet.points)
    }
    clipped_walls = [entry for entry in entries if entry.stable_index in crossing_wall_indices]
    assert clipped_walls
    assert all(frame.viewport.contains(point) for entry in clipped_walls for point in entry.points)
    assert sum(
        isinstance(obj, Box3D) and obj.material is room.WALL_MATERIAL
        for obj in scene.iter_visible()
    ) == 4


@pytest.mark.parametrize("enabled", list(product([False, True], repeat=4)))
def test_wall_switches_keep_geometry_collisions_and_effective_flags_consistent(enabled) -> None:
    candidate = host.load_world_candidate(room)
    for (_name, flag, _center, _size), value in zip(candidate.WALL_SPECS, enabled):
        setattr(candidate, flag, value)
    scene, _ = candidate.build_scene()
    owners = {collider.owner for collider in candidate.build_collision_world().colliders}
    flags = candidate.effective_world_flags()
    for (name, flag, center, size), value in zip(candidate.WALL_SPECS, enabled):
        parts = [
            obj for obj in scene.iter_visible()
            if isinstance(obj, Box3D) and obj.center[:2] == center and obj.size[:2] == size
        ]
        assert len(parts) == (2 if value else 0)
        assert (name in owners) == flags[flag] == value


def test_reloading_wall_switches_replaces_geometry_collisions_and_flag_snapshot(monkeypatch) -> None:
    context = dcg.Context()
    controller = host.build_ui(context)
    original_count = controller.viewport.scene.object_count
    original_module = controller.world_module
    try:
        for enabled in (True, False):
            candidate = host.load_world_candidate(room)
            candidate.FRONT_WALL_ENABLED = candidate.RIGHT_WALL_ENABLED = enabled
            monkeypatch.setattr(host, "load_world_candidate", lambda _module: candidate)
            generation = controller.scene_generation
            controller.reload_world()
            assert controller.scene_generation == generation + 1
            assert controller.viewport.scene.object_count == original_count + (4 if enabled else 0)
            assert controller.effective_flags["FRONT_WALL_ENABLED"] == enabled
            assert controller.effective_flags["RIGHT_WALL_ENABLED"] == enabled
            owners = {collider.owner for collider in controller.collisions.colliders}
            assert ("front wall" in owners) == ("right wall" in owners) == enabled
        assert not original_module.FRONT_WALL_ENABLED
        assert not original_module.RIGHT_WALL_ENABLED
    finally:
        controller.viewport.delete_item()
