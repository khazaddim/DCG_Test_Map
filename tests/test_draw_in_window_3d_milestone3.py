from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import random
import sys
from typing import Callable

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import (
    AabbFootprint,
    AnimatedImageMaterial,
    Box3D,
    Camera3D,
    CollisionWorld,
    CpuRenderer3D,
    FrameContext,
    ImageMaterial,
    Line3D,
    OverlapDepthSorter,
    Polygon3D,
    ProjectedRenderEntry,
    ProjectionPipeline,
    RenderStats,
    Scene3D,
    SolidMaterial,
    Viewport,
)
from Animation.draw_in_window_3d_framework import scene as scene_module


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_demo_12():
    source = REPO_ROOT / "Animation" / "ported_demos" / "12_dearcygui_cpu_3d_map.py"
    spec = importlib.util.spec_from_file_location("framework_demo_12_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_demo_11():
    source = REPO_ROOT / "Animation" / "ported_demos" / "11_dearcygui_cpu_3d_map.py"
    spec = importlib.util.spec_from_file_location("framework_demo_11_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_collision_sort_example():
    source = REPO_ROOT / "Animation" / "ported_demos" / "collision_sort_diagnostics.py"
    spec = importlib.util.spec_from_file_location("framework_collision_sort_example_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_collision_two_boxes_demo():
    source = REPO_ROOT / "Animation" / "ported_demos" / "collision_two_boxes.py"
    spec = importlib.util.spec_from_file_location("framework_collision_two_boxes_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_aabb_footprints_allow_exact_gap_and_reject_smaller_separation() -> None:
    obstacle = AabbFootprint.from_center(0.0, 0.0, 10.0, 10.0)
    exactly_at_gap = AabbFootprint.from_center(7.0, 0.0, 2.0, 2.0)
    inside_gap = AabbFootprint.from_center(6.9, 0.0, 2.0, 2.0)

    assert obstacle.conflicts(exactly_at_gap, gap=1.0) is False
    assert obstacle.conflicts(inside_gap, gap=1.0) is True


def test_collision_world_returns_first_registered_blocker_and_honors_ignore() -> None:
    world = CollisionWorld(gap=0.0)
    first_owner = object()
    second_owner = object()
    first = world.add(first_owner, AabbFootprint(-5.0, -5.0, 5.0, 5.0))
    second = world.add(second_owner, AabbFootprint(-4.0, -4.0, 4.0, 4.0))
    candidate = AabbFootprint(-1.0, -1.0, 1.0, 1.0)

    assert world.first_blocker(candidate) is first
    assert world.first_blocker(candidate, ignore=first_owner) is second


def test_collision_world_gap_changes_touching_boundary_result() -> None:
    candidate = AabbFootprint(-5.0, -5.0, 5.0, 5.0)

    assert CollisionWorld(gap=0.0).first_blocker(candidate) is None

    world = CollisionWorld(gap=2.0)
    blocker = world.add("touching obstacle", AabbFootprint(5.0, -5.0, 15.0, 5.0))

    assert world.first_blocker(candidate) is blocker


def test_collision_controller_leaves_player_and_camera_follow_unchanged_when_blocked() -> None:
    demo = load_demo_12()
    player = demo.Box3D(
        center=(100.0, 100.0, 0.0),
        size=(70.0, 70.0, 115.0),
        material=SolidMaterial(fill=(245, 194, 67)),
    )
    collisions = CollisionWorld(gap=2.0)
    collisions.add("building", AabbFootprint.from_center(200.0, 100.0, 100.0, 100.0))
    controller = object.__new__(demo.CollisionDemoController)
    controller.player = player
    controller.collisions = collisions
    controller.blocked_by = None
    follow_calls = []
    controller.follow = type("FollowProbe", (), {"update": lambda self, point: follow_calls.append(point)})()
    repaint_calls = []
    controller.repaint = lambda: repaint_calls.append(True)

    controller._move(100.0, 0.0)

    assert player.center == (100.0, 100.0, 0.0)
    assert follow_calls == []
    assert controller.blocked_by == "building"
    assert repaint_calls == [True]


def make_sort_frame() -> FrameContext:
    return FrameContext(
        camera=Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=0.0, zoom=1.0, near_plane=1.0),
        viewport=Viewport(200.0, 200.0),
    )


def make_flat_polygon(stable_index: int, depth: float, average_depth: float | None = None) -> ProjectedRenderEntry:
    return ProjectedRenderEntry(
        kind="polygon",
        stable_index=stable_index,
        average_depth=depth if average_depth is None else average_depth,
        points=((80.0, 80.0), (120.0, 80.0), (120.0, 120.0), (80.0, 120.0)),
        camera_points=((-10.0, -10.0, depth), (10.0, -10.0, depth), (10.0, 10.0, depth), (-10.0, 10.0, depth)),
    )


def make_projected_entry(
    *,
    stable_index: int,
    kind: str = "polygon",
    points: tuple[tuple[float, float], ...],
    average_depth: float = 100.0,
) -> ProjectedRenderEntry:
    return ProjectedRenderEntry(
        kind=kind,
        stable_index=stable_index,
        average_depth=average_depth,
        points=points,
        camera_points=tuple((point[0], point[1], average_depth) for point in points),
    )


def make_bounds_entry(stable_index: int, bounds: tuple[float, float, float, float]) -> ProjectedRenderEntry:
    min_x, min_y, max_x, max_y = bounds
    return make_projected_entry(
        stable_index=stable_index,
        points=((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)),
    )


def independent_closed_bounds_pairs(entries: tuple[ProjectedRenderEntry, ...]) -> tuple[tuple[int, int], ...]:
    eligible = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.kind == "polygon" and len(entry.points) >= 3
    ]
    pairs: list[tuple[int, int]] = []
    for first_offset, (first_index, first) in enumerate(eligible):
        first_min_x = min(point[0] for point in first.points)
        first_max_x = max(point[0] for point in first.points)
        first_min_y = min(point[1] for point in first.points)
        first_max_y = max(point[1] for point in first.points)
        for second_index, second in eligible[first_offset + 1 :]:
            second_min_x = min(point[0] for point in second.points)
            second_max_x = max(point[0] for point in second.points)
            second_min_y = min(point[1] for point in second.points)
            second_max_y = max(point[1] for point in second.points)
            if (
                first_max_x >= second_min_x
                and second_max_x >= first_min_x
                and first_max_y >= second_min_y
                and second_max_y >= first_min_y
            ):
                pairs.append((first_index, second_index))
    return tuple(pairs)


def make_camera_space_polygon_entry(
    frame: FrameContext,
    stable_index: int,
    camera_points: tuple[tuple[float, float, float], ...],
) -> ProjectedRenderEntry:
    return ProjectedRenderEntry(
        kind="polygon",
        stable_index=stable_index,
        average_depth=sum(point[2] for point in camera_points) / len(camera_points),
        points=tuple(frame.camera.camera_to_screen(point, frame.viewport) for point in camera_points),
        camera_points=camera_points,
        material=SolidMaterial(fill=(160, 120, 80)),
    )


def make_screen_plane_entry(
    frame: FrameContext,
    stable_index: int,
    points: tuple[tuple[float, float], ...],
    inverse_depth: float | Callable[[float, float], float],
) -> ProjectedRenderEntry:
    focal_length = frame.camera.focal_length(frame.viewport)
    center_x, center_y = frame.viewport.center
    camera_points = tuple(
        (
            (screen_x - center_x) * (1.0 / depth_at_point) / focal_length,
            (screen_y - center_y) * (1.0 / depth_at_point) / focal_length,
            1.0 / depth_at_point,
        )
        for screen_x, screen_y in points
        for depth_at_point in (inverse_depth(screen_x, screen_y) if callable(inverse_depth) else inverse_depth,)
    )
    return make_camera_space_polygon_entry(frame, stable_index, camera_points)


def assert_sorter_strategies_agree(entries: tuple[ProjectedRenderEntry, ...], frame: FrameContext) -> None:
    all_pairs = OverlapDepthSorter(use_sweep_and_prune=False).sort(entries, frame)
    sweep = OverlapDepthSorter(use_sweep_and_prune=True).sort(entries, frame)
    assert all_pairs.sort_stats is not None
    assert sweep.sort_stats is not None
    assert [entry.stable_index for entry in sweep.entries] == [entry.stable_index for entry in all_pairs.entries]
    assert sweep.cycle_detected is all_pairs.cycle_detected
    assert sweep.sort_stats.accepted_edge_count == all_pairs.sort_stats.accepted_edge_count

    all_edge_pairs = set()
    for first_index, second_index in scene_module._all_pairs_candidate_pairs(entries)[0]:
        depths = scene_module.overlapping_polygon_depths(entries[first_index], entries[second_index], frame)
        if depths is not None and abs(depths[0] - depths[1]) > 1e-5:
            all_edge_pairs.add((first_index, second_index))
    assert all_edge_pairs <= set(scene_module._sweep_candidate_pairs(entries)[0])


def make_camera_space_line_entry(
    frame: FrameContext,
    stable_index: int,
    camera_points: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> ProjectedRenderEntry:
    return ProjectedRenderEntry(
        kind="line",
        stable_index=stable_index,
        average_depth=0.5 * (camera_points[0][2] + camera_points[1][2]),
        points=tuple(frame.camera.camera_to_screen(point, frame.viewport) for point in camera_points),
        camera_points=camera_points,
        material=SolidMaterial(fill=None, outline=(235, 214, 116), thickness=-3.0, shaded=False),
    )


def project_scene_entries(
    scene: Scene3D,
    camera: Camera3D,
    viewport: Viewport | None = None,
) -> tuple[CpuRenderer3D, FrameContext, tuple[ProjectedRenderEntry, ...]]:
    viewport = viewport or Viewport(400.0, 300.0)
    renderer = CpuRenderer3D()
    frame = FrameContext(camera=camera, viewport=viewport)
    pipeline = ProjectionPipeline(camera, viewport)
    entries: list[ProjectedRenderEntry] = []
    for stable_index, packet in enumerate(renderer._collect_packets(scene, frame)):
        entry = renderer._project_packet(packet, stable_index, frame, pipeline)
        if entry is not None:
            entries.append(entry)
    sorted_entries = renderer.sorter.sort(entries, frame).entries
    return renderer, frame, sorted_entries


def test_image_material_uses_complete_quad_and_preserves_tessellation_metadata() -> None:
    frame = make_sort_frame()
    texture = object()
    material = ImageMaterial(texture=texture, tessellation=3, uv_coordinates=((0.1, 0.2), (0.8, 0.2), (0.8, 0.9), (0.1, 0.9)))
    packet = scene_module.WorldRenderPacket(
        kind="polygon",
        points=((-10.0, -10.0, 50.0), (10.0, -10.0, 50.0), (10.0, 10.0, 50.0), (-10.0, 10.0, 50.0)),
        material=material,
    )

    entry = CpuRenderer3D()._project_packet(packet, 0, frame, ProjectionPipeline(frame.camera, frame.viewport))

    assert entry is not None
    assert entry.material is material
    assert len(entry.points) == 4


def test_image_material_emits_one_draw_image_per_tessellation_cell() -> None:
    context = dcg.Context()
    texture = dcg.Texture(context)
    scene = Scene3D()
    scene.add(
        Polygon3D(
            points=((-10.0, -10.0, 50.0), (10.0, -10.0, 50.0), (10.0, 10.0, 50.0), (-10.0, 10.0, 50.0)),
            material=ImageMaterial(texture=texture, tessellation=2),
            cull_back_face=False,
        )
    )
    layer = dcg.DrawingList(context)

    stats = CpuRenderer3D().render(context, layer, scene, make_sort_frame().camera, make_sort_frame().viewport)

    assert stats.emitted_count == 5
    assert [type(child).__name__ for child in layer.children].count("DrawImage") == 4


def test_image_material_preserves_uv_coordinates_on_emitted_draw_image() -> None:
    context = dcg.Context()
    texture = dcg.Texture(context)
    material = ImageMaterial(
        texture=texture,
        tessellation=1,
        uv_coordinates=((0.1, 0.2), (0.8, 0.2), (0.7, 0.9), (0.2, 0.85)),
    )
    scene = Scene3D()
    scene.add(
        Polygon3D(
            points=((-10.0, -10.0, 50.0), (10.0, -10.0, 50.0), (10.0, 10.0, 50.0), (-10.0, 10.0, 50.0)),
            material=material,
            cull_back_face=False,
        )
    )
    layer = dcg.DrawingList(context)

    CpuRenderer3D().render(context, layer, scene, make_sort_frame().camera, make_sort_frame().viewport)

    draw_image = next(child for child in layer.children if type(child).__name__ == "DrawImage")
    for emitted_uv, expected_uv in zip(
        (draw_image.uv1, draw_image.uv2, draw_image.uv3, draw_image.uv4),
        material.uv_coordinates,
    ):
        assert math.isclose(emitted_uv[0], expected_uv[0], rel_tol=0.0, abs_tol=1e-6)
        assert math.isclose(emitted_uv[1], expected_uv[1], rel_tol=0.0, abs_tol=1e-6)


def test_clipped_image_quad_falls_back_to_shaded_solid_polygon() -> None:
    frame = make_sort_frame()
    material = ImageMaterial(texture=object(), fill=(100, 120, 140), shaded=True)
    packet = scene_module.WorldRenderPacket(
        kind="polygon",
        points=((-1000.0, -10.0, 50.0), (10.0, -10.0, 50.0), (10.0, 10.0, 50.0), (-10.0, 10.0, 50.0)),
        material=material,
        normal=(0.0, 0.0, 1.0),
    )

    entry = CpuRenderer3D()._project_packet(packet, 0, frame, ProjectionPipeline(frame.camera, frame.viewport))

    assert entry is not None
    assert isinstance(entry.material, SolidMaterial)
    assert entry.material.fill != material.fill


def test_animated_image_material_cycles_frames_with_offset_and_loop_timing() -> None:
    frames = (object(), object(), object())
    material = AnimatedImageMaterial(frames=frames, loop_seconds=1.5, frame_offset=1)

    assert material.texture is frames[0]
    assert material.frame_texture(0) is frames[1]
    assert material.frame_texture(2) is frames[0]
    assert material.frame_end_time(1) == 1.0


def test_animated_image_material_emits_draw_stream_frames_with_expected_timing() -> None:
    context = dcg.Context()
    textures = (dcg.Texture(context), dcg.Texture(context), dcg.Texture(context))
    scene = Scene3D()
    scene.add(
        Polygon3D(
            points=((-10.0, -10.0, 50.0), (10.0, -10.0, 50.0), (10.0, 10.0, 50.0), (-10.0, 10.0, 50.0)),
            material=AnimatedImageMaterial(frames=textures, tessellation=2, loop_seconds=1.5, frame_offset=1),
            cull_back_face=False,
        )
    )
    layer = dcg.DrawingList(context)

    stats = CpuRenderer3D().render(context, layer, scene, make_sort_frame().camera, make_sort_frame().viewport)

    assert stats.emitted_count == 2
    stream = next(child for child in layer.children if type(child).__name__ == "DrawStream")
    assert stream.time_modulus == 1.5
    assert len(stream.children) == 3
    assert [type(child).__name__ for child in stream.children] == ["DrawingList", "DrawingList", "DrawingList"]
    for drawing, texture in zip(stream.children, textures[1:] + textures[:1]):
        assert [type(child).__name__ for child in drawing.children].count("DrawImage") == 4
        assert drawing.children[0].texture is texture


def test_box_can_override_material_on_selected_faces() -> None:
    base_material = SolidMaterial(fill=(100, 100, 100))
    image_material = ImageMaterial(texture=object(), tessellation=1)
    box = Box3D(
        center=(0.0, 0.0, 0.0),
        size=(10.0, 10.0, 10.0),
        material=base_material,
        face_materials=(None, image_material, None, image_material, None, None),
    )

    packets = tuple(box.collect(make_sort_frame()))

    assert [packet.material for packet in packets] == [
        base_material,
        image_material,
        base_material,
        image_material,
        base_material,
        base_material,
    ]


def test_collision_two_boxes_demo_uses_tessellated_image_material_faces() -> None:
    demo = load_collision_two_boxes_demo()
    context = dcg.Context()
    context.viewport.initialize(width=demo.VIEW_WIDTH + 70, height=demo.VIEW_HEIGHT + 140)

    controller = demo.build_ui(context)

    assert controller.player.face_materials
    assert all(
        isinstance(material, ImageMaterial)
        for material in controller.player.face_materials
        if material is not None
    )
    assert {
        material.tessellation
        for material in controller.player.face_materials
        if isinstance(material, ImageMaterial)
    } == {demo.TEXTURE_TESSELLATION}
    context.viewport.render_frame()
    controller.repaint()
    assert any(
        type(child).__name__ == "DrawImage"
        for child in controller.viewport.displayed_layer.children
    )


def test_convex_screen_polygon_overlap_uses_positive_area_separation() -> None:
    first = ((0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0))
    overlapping = ((10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0))
    touching = ((20.0, 0.0), (40.0, 0.0), (40.0, 20.0), (20.0, 20.0))

    assert scene_module.convex_screen_polygons_overlap(first, overlapping) is True
    assert scene_module.convex_screen_polygons_overlap(first, touching) is False


def test_ray_plane_depth_samples_camera_space_face() -> None:
    frame = make_sort_frame()
    entry = make_flat_polygon(stable_index=0, depth=75.0)

    assert scene_module.ray_plane_depth((100.0, 100.0), entry.camera_points, frame) == 75.0


def test_overlap_depth_sorter_orders_by_ray_plane_depth_at_overlap() -> None:
    sorter = OverlapDepthSorter()
    frame = make_sort_frame()
    nearer_but_average_farther = make_flat_polygon(stable_index=0, depth=50.0, average_depth=300.0)
    farther_but_average_nearer = make_flat_polygon(stable_index=1, depth=150.0, average_depth=100.0)

    ordered = sorter.sort([nearer_but_average_farther, farther_but_average_nearer], frame)

    assert [entry.stable_index for entry in ordered.entries] == [1, 0]
    assert ordered.cycle_detected is False


@pytest.mark.parametrize(
    ("second_points", "material", "expected_skipped"),
    [
        (((0, -30, 0), (30, -30, 0), (30, 30, 0), (0, 30, 0)), SolidMaterial(fill=(100, 100, 100)), 1),
        (((0, -30, 0), (30, -30, 0), (30, 30, 0), (0, 30, 0)), SolidMaterial(fill=(100, 100, 100, 100)), 1),
        (((-30, -30, 0), (0, -30, 0), (0, 30, 0), (-30, 30, 0)), SolidMaterial(fill=(100, 100, 100)), 0),
        (((-10, -20, 0), (10, -20, 0), (10, 20, 0), (-10, 20, 0)), SolidMaterial(fill=(100, 100, 100)), 0),
        (((-10, -20, 0.000001), (10, -20, 0.000001), (10, 20, 0.000001), (-10, 20, 0.000001)), SolidMaterial(fill=(100, 100, 100)), 0),
        (((0, -30, 0), (20, -30, 10), (20, 30, 10), (0, 30, 0)), SolidMaterial(fill=(100, 100, 100)), 0),
    ],
)
@pytest.mark.parametrize("sweep", [True, False])
def test_coplanar_edge_filter_matches_baseline(second_points, material, expected_skipped, sweep) -> None:
    frame = make_sort_frame()
    scene = Scene3D()
    scene.add(Polygon3D(
        ((-30, -30, 0), (0, -30, 0), (0, 30, 0), (-30, 30, 0)),
        SolidMaterial(fill=(200, 200, 200)), cull_back_face=False,
    ))
    scene.add(Polygon3D(second_points, material, cull_back_face=False))
    experimental = OverlapDepthSorter(use_sweep_and_prune=sweep, use_coplanar_edge_filter=True)
    renderer = CpuRenderer3D(experimental)
    entries, _ = renderer.project_packets(renderer.collect_packets(scene, frame), frame)

    baseline = OverlapDepthSorter(use_sweep_and_prune=sweep).sort(entries, frame)
    actual = experimental.sort(entries, frame)

    assert baseline.sort_stats is not None and actual.sort_stats is not None
    assert baseline.sort_stats.bounds_candidate_pair_count == actual.sort_stats.bounds_candidate_pair_count == 1
    assert actual.sort_stats.skipped_pair_count == expected_skipped
    assert actual.sort_stats.exact_test_count + expected_skipped == 1
    assert [entry.stable_index for entry in actual.entries] == [entry.stable_index for entry in baseline.entries]
    assert actual.cycle_detected == baseline.cycle_detected
    assert actual.sort_stats.accepted_edge_count == baseline.sort_stats.accepted_edge_count


def test_coplanar_edge_filter_reports_actual_exact_calls(monkeypatch) -> None:
    frame = make_sort_frame()
    scene = Scene3D()
    material = SolidMaterial(fill=(200, 200, 200))
    for points in (
        ((-30, -30, 0), (0, -30, 0), (0, 30, 0), (-30, 30, 0)),
        ((0, -30, 0), (30, -30, 0), (30, 30, 0), (0, 30, 0)),
        ((-10, -20, 1), (10, -20, 1), (10, 20, 1), (-10, 20, 1)),
    ):
        scene.add(Polygon3D(points, material, cull_back_face=False))
    experimental = OverlapDepthSorter(use_coplanar_edge_filter=True)
    renderer = CpuRenderer3D(experimental)
    entries, _ = renderer.project_packets(renderer.collect_packets(scene, frame), frame)
    original = scene_module.overlapping_polygon_depths
    calls = []

    def record(*args, **kwargs):
        calls.append((args[0].stable_index, args[1].stable_index))
        return original(*args, **kwargs)

    monkeypatch.setattr(scene_module, "overlapping_polygon_depths", record)
    result = experimental.sort(entries, frame)

    assert result.sort_stats is not None
    assert result.sort_stats.skipped_pair_count == 1
    assert result.sort_stats.exact_test_count == len(calls) == 2
    assert result.sort_stats.bounds_candidate_pair_count == len(calls) + 1


def test_coplanar_edge_filter_with_viewport_clipping_matches_baseline() -> None:
    frame = FrameContext(Camera3D((0, 0, 0), 0, 0, 1, near_plane=1), Viewport(100, 100))
    scene = Scene3D()
    material = SolidMaterial(fill=(200, 200, 200))
    for points in (
        ((-100, -20, 0), (0, -20, 0), (0, 20, 0), (-100, 20, 0)),
        ((0, -20, 0), (100, -20, 0), (100, 20, 0), (0, 20, 0)),
    ):
        scene.add(Polygon3D(points, material, cull_back_face=False))
    experimental = OverlapDepthSorter(use_coplanar_edge_filter=True)
    renderer = CpuRenderer3D(experimental)
    entries, _ = renderer.project_packets(renderer.collect_packets(scene, frame), frame)

    baseline = OverlapDepthSorter().sort(entries, frame)
    actual = experimental.sort(entries, frame)
    assert len(entries) == 2
    assert actual.sort_stats is not None and baseline.sort_stats is not None
    assert actual.sort_stats.skipped_pair_count == 1
    assert actual.sort_stats.accepted_edge_count == baseline.sort_stats.accepted_edge_count
    assert [e.stable_index for e in actual.entries] == [e.stable_index for e in baseline.entries]
    assert actual.cycle_detected == baseline.cycle_detected


def test_coplanar_edge_filter_with_near_plane_clipping_matches_baseline() -> None:
    frame = FrameContext(Camera3D((0, 0, 0), 0, 78, 1, near_plane=55), Viewport(100, 100))
    scene = Scene3D()
    material = SolidMaterial(fill=(200, 200, 200))
    for points in (
        ((-10, 10, 0), (0, 10, 0), (0, 60, 0), (-10, 60, 0)),
        ((0, 10, 0), (10, 10, 0), (10, 60, 0), (0, 60, 0)),
    ):
        scene.add(Polygon3D(points, material, cull_back_face=False))
    experimental = OverlapDepthSorter(use_coplanar_edge_filter=True)
    renderer = CpuRenderer3D(experimental)
    packets = renderer.collect_packets(scene, frame)
    assert any(frame.camera.world_to_camera(point, frame.viewport)[2] < frame.camera.near_plane
               for packet in packets for point in packet.points)
    entries, _ = renderer.project_packets(packets, frame)

    baseline = OverlapDepthSorter().sort(entries, frame)
    actual = experimental.sort(entries, frame)
    assert len(entries) == 2
    assert actual.sort_stats is not None and baseline.sort_stats is not None
    assert actual.sort_stats.accepted_edge_count == baseline.sort_stats.accepted_edge_count
    assert [e.stable_index for e in actual.entries] == [e.stable_index for e in baseline.entries]
    assert actual.cycle_detected == baseline.cycle_detected


def test_default_sorter_and_renderer_use_sweep_with_all_pairs_opt_out() -> None:
    frame = make_sort_frame()
    entries = (
        make_screen_plane_entry(frame, 7, ((20.0, 20.0), (40.0, 20.0), (40.0, 40.0), (20.0, 40.0)), 0.01),
        make_screen_plane_entry(frame, 3, ((100.0, 20.0), (120.0, 20.0), (120.0, 40.0), (100.0, 40.0)), 0.01),
    )
    for sorter in (OverlapDepthSorter(), CpuRenderer3D().sorter):
        assert isinstance(sorter, OverlapDepthSorter)
        assert sorter.use_sweep_and_prune is True
        result = sorter.sort(entries, frame)
        assert result.sort_stats is not None
        assert result.sort_stats.candidate_strategy == "sweep_and_prune"
        assert result.sort_stats.exact_test_count == 0
        assert [entry.stable_index for entry in result.entries] == [3, 7]

    baseline = OverlapDepthSorter(use_sweep_and_prune=False).sort(entries, frame)
    assert baseline.sort_stats is not None
    assert baseline.sort_stats.candidate_strategy == "all_pairs"
    assert baseline.sort_stats.exact_test_count == 1
    assert [entry.stable_index for entry in baseline.entries] == [3, 7]
    assert not baseline.cycle_detected


def test_overlap_depth_sorter_reports_cycles_and_uses_average_depth_fallback(monkeypatch) -> None:
    frame = make_sort_frame()
    entries = [
        make_flat_polygon(stable_index=0, depth=10.0, average_depth=30.0),
        make_flat_polygon(stable_index=1, depth=10.0, average_depth=20.0),
        make_flat_polygon(stable_index=2, depth=10.0, average_depth=10.0),
    ]

    def cyclic_depths(first, second, frame, overlap_area_epsilon=0.25):
        pair = {first.stable_index, second.stable_index}
        if pair == {0, 1}:
            return (2.0, 1.0) if first.stable_index == 0 else (1.0, 2.0)
        if pair == {1, 2}:
            return (2.0, 1.0) if first.stable_index == 1 else (1.0, 2.0)
        if pair == {0, 2}:
            return (1.0, 2.0) if first.stable_index == 0 else (2.0, 1.0)
        return None

    monkeypatch.setattr(scene_module, "overlapping_polygon_depths", cyclic_depths)

    ordered = OverlapDepthSorter().sort(entries, frame)

    assert ordered.cycle_detected is True
    assert [entry.stable_index for entry in ordered.entries] == [0, 1, 2]


def test_screen_bounds_calculates_immutable_aabb_from_polygon_points() -> None:
    bounds = scene_module._screen_bounds(((5.0, 7.0), (-1.0, 2.0), (9.0, -3.0), (4.0, 6.0)))

    assert scene_module._ProjectedBounds.__dataclass_params__.frozen is True
    assert bounds.min_x == -1.0
    assert bounds.min_y == -3.0
    assert bounds.max_x == 9.0
    assert bounds.max_y == 7.0


def test_entry_screen_bounds_excludes_non_polygons_and_degenerate_entries() -> None:
    entries = (
        make_projected_entry(stable_index=0, points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
        make_projected_entry(stable_index=1, points=((20.0, 0.0), (30.0, 0.0)), average_depth=90.0),
        make_projected_entry(stable_index=2, kind="line", points=((0.0, 0.0), (10.0, 10.0)), average_depth=80.0),
        make_projected_entry(stable_index=3, points=((40.0, 10.0), (60.0, 10.0), (60.0, 30.0), (40.0, 30.0)), average_depth=70.0),
    )

    bounds = scene_module._entry_screen_bounds(entries)

    assert set(bounds) == {0, 3}
    assert bounds[0] == scene_module._ProjectedBounds(0.0, 0.0, 10.0, 10.0)
    assert bounds[3] == scene_module._ProjectedBounds(40.0, 10.0, 60.0, 30.0)


def test_sweep_candidate_generation_is_deterministic_and_keeps_touching_aabbs() -> None:
    entries = (
        make_projected_entry(stable_index=0, points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
        make_projected_entry(stable_index=1, points=((10.0, 4.0), (18.0, 4.0), (18.0, 12.0), (10.0, 12.0))),
        make_projected_entry(stable_index=2, points=((0.0, 30.0), (10.0, 30.0), (10.0, 40.0), (0.0, 40.0))),
        make_projected_entry(stable_index=3, points=((4.0, 3.0), (8.0, 3.0), (8.0, 8.0), (4.0, 8.0))),
    )

    pairs, metrics, _bounds = scene_module._sweep_candidate_pairs(entries)

    assert pairs == ((0, 3), (0, 1))
    assert metrics.x_active_pair_count == 5
    assert metrics.bounds_candidate_pair_count == 2


@pytest.mark.parametrize(
    ("bounds", "expected_pairs", "expected_x_active"),
    [
        ((), (), 0),
        (((0.0, 0.0, 10.0, 10.0),), (), 0),
        (((0.0, 0.0, 10.0, 10.0), (11.0, 0.0, 21.0, 10.0)), (), 0),
        (((0.0, 0.0, 10.0, 10.0), (0.0, 11.0, 10.0, 21.0)), (), 1),
        (((0.0, 0.0, 10.0, 10.0), (5.0, 5.0, 15.0, 15.0)), ((0, 1),), 1),
        (((0.0, 0.0, 10.0, 10.0), (10.0, 10.0, 20.0, 20.0)), ((0, 1),), 1),
        (((0.0, 0.0, 10.0, 10.0), (0.0, 0.0, 10.0, 10.0), (0.0, 0.0, 10.0, 10.0)), ((0, 1), (0, 2), (1, 2)), 3),
        (((4.0, 0.0, 14.0, 10.0), (0.0, 0.0, 10.0, 10.0), (2.0, 0.0, 12.0, 10.0)), ((1, 2), (0, 1), (0, 2)), 3),
    ],
)
def test_sweep_candidate_matrix_matches_independent_closed_bounds_oracle(
    bounds: tuple[tuple[float, float, float, float], ...],
    expected_pairs: tuple[tuple[int, int], ...],
    expected_x_active: int,
) -> None:
    entries = tuple(make_bounds_entry(41 - index * 7, rectangle) for index, rectangle in enumerate(bounds))

    pairs, metrics, _bounds = scene_module._sweep_candidate_pairs(entries)

    assert pairs == expected_pairs
    assert set(pairs) == set(independent_closed_bounds_pairs(entries))
    assert all(first < second for first, second in pairs)
    assert len(pairs) == len(set(pairs))
    assert metrics.x_active_pair_count == expected_x_active
    assert metrics.bounds_candidate_pair_count == len(expected_pairs)


def test_sweep_candidate_generation_retains_nextafter_touching_boundaries() -> None:
    base = (0.0, 0.0, 10.0, 10.0)
    for separated_coordinate, expected_pairs in (
        (math.nextafter(10.0, math.inf), ()),
        (math.nextafter(10.0, -math.inf), ((0, 1),)),
    ):
        x_entries = (make_bounds_entry(0, base), make_bounds_entry(1, (separated_coordinate, 0.0, 20.0, 10.0)))
        y_entries = (make_bounds_entry(0, base), make_bounds_entry(1, (0.0, separated_coordinate, 10.0, 20.0)))
        assert scene_module._sweep_candidate_pairs(x_entries)[0] == expected_pairs
        assert scene_module._sweep_candidate_pairs(y_entries)[0] == expected_pairs


def test_sweep_sorter_recomputes_bounds_per_frame_and_tracks_exact_tests(monkeypatch) -> None:
    sorter = OverlapDepthSorter(use_sweep_and_prune=True)
    frame = make_sort_frame()
    exact_pairs: list[tuple[int, int]] = []

    def record_depths(first, second, frame, overlap_area_epsilon=0.25):
        exact_pairs.append((first.stable_index, second.stable_index))
        return None

    monkeypatch.setattr(scene_module, "overlapping_polygon_depths", record_depths)

    separated_entries = (
        make_projected_entry(stable_index=0, points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
        make_projected_entry(stable_index=1, points=((30.0, 0.0), (40.0, 0.0), (40.0, 10.0), (30.0, 10.0))),
    )
    overlapping_entries = (
        make_projected_entry(stable_index=0, points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
        make_projected_entry(stable_index=1, points=((8.0, 0.0), (18.0, 0.0), (18.0, 10.0), (8.0, 10.0))),
    )

    first_result = sorter.sort(separated_entries, frame)
    second_result = sorter.sort(overlapping_entries, frame)

    assert first_result.sort_stats is not None
    assert first_result.sort_stats.bounds_candidate_pair_count == 0
    assert first_result.sort_stats.exact_test_count == 0
    assert second_result.sort_stats is not None
    assert second_result.sort_stats.bounds_candidate_pair_count == 1
    assert second_result.sort_stats.exact_test_count == 1
    assert second_result.sort_stats.candidate_strategy == "sweep_and_prune"
    assert exact_pairs == [(0, 1)]


def test_overlap_sorter_selector_chooses_candidate_strategy_and_preserves_frame_none_fallback(monkeypatch) -> None:
    entries = [
        make_flat_polygon(stable_index=0, depth=50.0, average_depth=10.0),
        make_flat_polygon(stable_index=1, depth=60.0, average_depth=20.0),
    ]
    frame = make_sort_frame()
    calls: list[str] = []
    bounds = {0: scene_module._screen_bounds(entries[0].points), 1: scene_module._screen_bounds(entries[1].points)}
    metrics = scene_module._CandidatePairMetrics(x_active_pair_count=1, bounds_candidate_pair_count=1)

    def fake_all_pairs(_entries):
        calls.append("all_pairs")
        return ((0, 1),), metrics, bounds

    def fake_sweep(_entries):
        calls.append("sweep")
        return ((0, 1),), metrics, bounds

    monkeypatch.setattr(scene_module, "_all_pairs_candidate_pairs", fake_all_pairs)
    monkeypatch.setattr(scene_module, "_sweep_candidate_pairs", fake_sweep)
    monkeypatch.setattr(scene_module, "overlapping_polygon_depths", lambda *args, **kwargs: None)

    all_pairs_result = OverlapDepthSorter(use_sweep_and_prune=False).sort(entries, frame)
    sweep_result = OverlapDepthSorter(use_sweep_and_prune=True).sort(entries, frame)

    assert calls == ["all_pairs", "sweep"]
    assert all_pairs_result.sort_stats is not None
    assert all_pairs_result.sort_stats.candidate_strategy == "all_pairs"
    assert sweep_result.sort_stats is not None
    assert sweep_result.sort_stats.candidate_strategy == "sweep_and_prune"

    monkeypatch.setattr(scene_module, "_all_pairs_candidate_pairs", lambda *_args: (_ for _ in ()).throw(AssertionError("all-pairs helper should not run without a frame")))
    monkeypatch.setattr(scene_module, "_sweep_candidate_pairs", lambda *_args: (_ for _ in ()).throw(AssertionError("sweep helper should not run without a frame")))

    fallback_false = OverlapDepthSorter(use_sweep_and_prune=False).sort(entries, None)
    fallback_true = OverlapDepthSorter(use_sweep_and_prune=True).sort(entries, None)

    assert [entry.stable_index for entry in fallback_false.entries] == [1, 0]
    assert [entry.stable_index for entry in fallback_true.entries] == [1, 0]
    assert fallback_false.cycle_detected is False
    assert fallback_true.cycle_detected is False


@pytest.mark.parametrize("use_sweep_and_prune", (False, True))
def test_overlap_sorter_fallback_clears_statistics_after_frame_backed_sort(use_sweep_and_prune: bool) -> None:
    sorter = OverlapDepthSorter(use_sweep_and_prune=use_sweep_and_prune)
    frame = make_sort_frame()
    entries = (
        make_flat_polygon(stable_index=7, depth=50.0, average_depth=10.0),
        make_flat_polygon(stable_index=3, depth=60.0, average_depth=10.0),
    )

    frame_result = sorter.sort(entries, frame)
    assert frame_result.sort_stats is sorter.last_sort_stats
    fallback_result = sorter.sort(iter(entries), None)

    assert fallback_result.sort_stats is None
    assert sorter.last_sort_stats is None
    assert fallback_result.cycle_detected is False
    assert [entry.stable_index for entry in fallback_result.entries] == [3, 7]


def test_overlap_sorter_strategies_match_distributed_projected_faces_and_mixed_entries() -> None:
    frame = make_sort_frame()
    entries: list[ProjectedRenderEntry] = [
        make_projected_entry(stable_index=99, kind="line", points=((0.0, 0.0), (1.0, 1.0))),
        make_projected_entry(stable_index=98, points=((1.0, 1.0), (2.0, 2.0))),
    ]
    for cell_x in (20.0, 100.0):
        for offset, depth in enumerate((80.0, 100.0, 120.0, 140.0)):
            dx, dy = ((0.0, 0.0), (6.0, 0.0), (0.0, 6.0), (6.0, 6.0))[offset]
            entries.append(
                make_screen_plane_entry(
                    frame,
                    41 - offset - int(cell_x),
                    ((cell_x + dx, 20.0 + dy), (cell_x + dx + 24.0, 20.0 + dy), (cell_x + dx + 24.0, 44.0 + dy), (cell_x + dx, 44.0 + dy)),
                    1.0 / depth,
                )
            )

    assert_sorter_strategies_agree(tuple(entries), frame)


def geometric_cycle_entries(frame):
    return (
        make_screen_plane_entry(frame, 41, ((40.0, 40.0), (160.0, 40.0), (160.0, 60.0), (40.0, 60.0)), 0.01),
        make_screen_plane_entry(frame, 7, ((140.0, 40.0), (160.0, 40.0), (160.0, 160.0), (140.0, 160.0)), lambda _x, y: 0.01 + 0.00001 * (100.0 - y)),
        make_screen_plane_entry(frame, 23, ((40.0, 50.0), (50.0, 40.0), (160.0, 150.0), (150.0, 160.0)), lambda x, _y: 0.01 + 0.00001 * (x - 100.0)),
        make_screen_plane_entry(frame, 3, ((70.0, 70.0), (90.0, 70.0), (90.0, 90.0), (70.0, 90.0)), 0.004),
    )


def test_overlap_sorter_strategies_match_real_geometric_cycle_fallback() -> None:
    frame = make_sort_frame()
    entries = geometric_cycle_entries(frame)

    all_pairs = OverlapDepthSorter(use_sweep_and_prune=False).sort(entries, frame)
    sweep = OverlapDepthSorter(use_sweep_and_prune=True).sort(entries, frame)
    expected = [entry.stable_index for entry in scene_module.AverageDepthSorter().sort(entries).entries]

    assert all_pairs.cycle_detected is True
    assert sweep.cycle_detected is True
    assert [entry.stable_index for entry in all_pairs.entries] == expected
    assert [entry.stable_index for entry in sweep.entries] == expected


@pytest.fixture(scope="module")
def taichi_exact_eval():
    ti = pytest.importorskip("taichi")
    from Animation.ported_demos import taichi_exact_eval as backend

    ti.init(arch=ti.cpu, cpu_max_num_threads=2, default_fp=ti.f64,
            fast_math=False, offline_cache=False, enable_fallback=False)
    yield backend
    ti.reset()


def test_taichi_exact_pair_boundaries_and_partial_fallback(taichi_exact_eval, monkeypatch) -> None:
    from Animation.ported_demos.benchmark_taichi_exact import verify_depths

    frame = make_sort_frame()
    flat = make_flat_polygon(0, 100)
    box = ((80.0, 80.0), (120.0, 80.0), (120.0, 120.0), (80.0, 120.0))
    cases = (
        ("opposite winding", make_screen_plane_entry(frame, 1, box[::-1], 0.005), True),
        ("same plane", make_flat_polygon(2, 100), True),
        ("inside depth epsilon", make_flat_polygon(3, 100 + 0.999 * 1e-5), True),
        ("outside depth epsilon", make_flat_polygon(4, 100 + 1.001 * 1e-5), True),
        ("near plane equality", make_flat_polygon(5, 1.0), True),
        ("behind near plane", make_flat_polygon(6, 0.99), False),
        ("collinear camera points", make_camera_space_polygon_entry(
            frame, 7, ((-10.0, -10.0, 100.0), (0.0, 0.0, 100.0), (10.0, 10.0, 100.0))), False),
        ("edge touch", make_bounds_entry(8, (120.0, 90.0, 130.0, 110.0)), False),
        ("point touch", make_bounds_entry(9, (120.0, 120.0, 130.0, 130.0)), False),
        ("AABB overlaps but polygons separate", make_projected_entry(
            stable_index=10, points=((118.0, 126.0), (126.0, 118.0), (130.0, 130.0))), False),
        ("area equal to epsilon", make_bounds_entry(11, (90.0, 90.0, 90.5, 90.5)), False),
        ("area just below epsilon", make_bounds_entry(12, (90.0, 90.0, 90.499, 90.5)), False),
        ("area just above epsilon", make_bounds_entry(13, (90.0, 90.0, 90.501, 90.5)), True),
        ("missing plane", ProjectedRenderEntry("polygon", 14, 100, box), False),
        ("non-polygon", make_projected_entry(stable_index=15, kind="line", points=box), False),
        ("duplicate edge", make_projected_entry(stable_index=16, points=(box[0], *box)), False),
        ("parallel ray", ProjectedRenderEntry("polygon", 17, 100, box,
                                             ((0, 0, 100), (0, 10, 100), (0, 0, 110))), False),
        ("oversized polygon", make_screen_plane_entry(frame, 18, tuple(
            (100 + 10 * math.cos(angle), 100 + 10 * math.sin(angle))
            for angle in (i * math.tau / 17 for i in range(17))
        ), 0.005), True),
    )
    entries = (flat, *(entry for _, entry, _ in cases))
    pairs = tuple((0, i) for i in range(1, len(entries)))
    sorter = OverlapDepthSorter()
    monkeypatch.setattr(taichi_exact_eval, "BATCH_SIZE", 4)
    result = taichi_exact_eval.evaluate(entries, pairs, frame, sorter.overlap_area_epsilon)
    assert result.fallback_pairs == 1
    for row, (name, _, valid) in enumerate(cases):
        assert bool(result.statuses[row]) == valid, name
    verify_depths(entries, pairs, frame, sorter.overlap_area_epsilon, result)
    assert result.edges(pairs, sorter.depth_epsilon) == sorter.test_overlaps(entries, pairs, frame)
    empty = taichi_exact_eval.evaluate(entries, (), frame, sorter.overlap_area_epsilon)
    assert empty.edges((), sorter.depth_epsilon) == () and empty.kernel_sync_ns == 0


def test_taichi_exact_preserves_real_geometric_cycle(taichi_exact_eval) -> None:
    from Animation.ported_demos.benchmark_taichi_exact import verify_depths

    frame = make_sort_frame()
    entries = geometric_cycle_entries(frame)
    sorter = OverlapDepthSorter()
    pairs, _, _ = sorter.generate_candidates(entries)
    result = taichi_exact_eval.evaluate(entries, pairs, frame, sorter.overlap_area_epsilon)
    verify_depths(entries, pairs, frame, sorter.overlap_area_epsilon, result)
    edges = result.edges(pairs, sorter.depth_epsilon)
    baseline = sorter.test_overlaps(entries, pairs, frame)
    assert result.fallback_pairs == 0
    assert edges == baseline
    ordered = sorter.order_entries(entries, edges)
    assert ordered == sorter.order_entries(entries, baseline)
    assert ordered[0].cycle_detected


def test_taichi_exact_handles_maximum_convex_intersection(taichi_exact_eval) -> None:
    from Animation.ported_demos.benchmark_taichi_exact import verify_depths

    frame = make_sort_frame()
    sides = taichi_exact_eval.MAX_VERTICES
    step = math.tau / sides
    entries = tuple(
        make_screen_plane_entry(frame, i, tuple(
            (100 + 20 * math.cos(j * step + phase), 100 + 20 * math.sin(j * step + phase))
            for j in range(sides)
        ), 1.0 / (100 + i))
        for i, phase in enumerate((0.0, step * 0.5))
    )
    assert len(scene_module._convex_polygon_intersection(entries[0].points, entries[1].points)) == 2 * sides
    pairs = ((0, 1), (1, 0))
    sorter = OverlapDepthSorter()
    result = taichi_exact_eval.evaluate(entries, pairs, frame, sorter.overlap_area_epsilon)
    verify_depths(entries, pairs, frame, sorter.overlap_area_epsilon, result)
    assert result.fallback_pairs == 0
    assert result.edges(pairs, sorter.depth_epsilon) == ((1, 0), (1, 0))


def test_taichi_exact_matches_near_and_viewport_clipped_translucent_faces(taichi_exact_eval) -> None:
    from Animation.ported_demos.benchmark_taichi_exact import verify_depths

    frame = FrameContext(Camera3D((0, 0, 0), 0, 78, 1, near_plane=55), Viewport(100, 100))
    scene = Scene3D()
    for offset, height in ((0, 0), (5, 1), (-5, 0)):
        scene.add(Polygon3D(
            ((-150 + offset, 10, height), (150 + offset, 10, height),
             (150 + offset, 80, height), (-150 + offset, 80, height)),
            SolidMaterial(fill=(200, 200, 200, 100)), cull_back_face=False,
        ))
    sorter = OverlapDepthSorter()
    renderer = CpuRenderer3D(sorter)
    packets = renderer.collect_packets(scene, frame)
    assert any(frame.camera.world_to_camera(point, frame.viewport)[2] < frame.camera.near_plane
               for packet in packets for point in packet.points)
    entries, _ = renderer.project_packets(packets, frame)
    pairs, _, _ = sorter.generate_candidates(entries)
    assert len(entries) == 3 and len(pairs) == 3
    assert any(x in (0, 100) for entry in entries for x, _ in entry.points)
    result = taichi_exact_eval.evaluate(entries, pairs, frame, sorter.overlap_area_epsilon)
    verify_depths(entries, pairs, frame, sorter.overlap_area_epsilon, result)
    assert result.fallback_pairs == 0
    assert result.edges(pairs, sorter.depth_epsilon) == sorter.test_overlaps(entries, pairs, frame)


@pytest.mark.parametrize("seed,count", ((54010, 8), (54012, 32), (54013, 64)))
def test_overlap_sorter_strategies_match_deterministic_convex_face_permutations(seed: int, count: int) -> None:
    frame = make_sort_frame()
    generator = random.Random(seed)
    entries: list[ProjectedRenderEntry] = []
    for index in range(count):
        center_x = 50.0 + (index % 8) * 18.0 + generator.uniform(-2.0, 2.0)
        center_y = 50.0 + (index // 8) * 18.0 + generator.uniform(-2.0, 2.0)
        radius = generator.uniform(4.0, 9.0)
        sides = 3 + index % 4
        points = tuple(
            (
                center_x + radius * math.cos(2.0 * math.pi * point_index / sides),
                center_y + radius * math.sin(2.0 * math.pi * point_index / sides),
            )
            for point_index in range(sides)
        )
        entries.append(make_screen_plane_entry(frame, 1000 - index * 11, points, 1.0 / (80.0 + index)))

    for permutation in (entries, list(reversed(entries)), generator.sample(entries, len(entries))):
        assert_sorter_strategies_agree(tuple(permutation), frame)


def test_line_occlusion_splits_partially_hidden_grid_line() -> None:
    frame = make_sort_frame()
    face = make_camera_space_polygon_entry(
        frame,
        stable_index=0,
        camera_points=((-25.0, -25.0, 100.0), (25.0, -25.0, 100.0), (25.0, 25.0, 100.0), (-25.0, 25.0, 100.0)),
    )
    grid_line = make_camera_space_line_entry(
        frame,
        stable_index=1,
        camera_points=((-55.0, 0.0, 140.0), (55.0, 0.0, 140.0)),
    )

    segments = CpuRenderer3D()._visible_line_segments(grid_line, (face,), frame)

    assert len(segments) == 2
    face_min_x = min(point[0] for point in face.points)
    face_max_x = max(point[0] for point in face.points)
    assert segments[0][1][0] <= face_min_x + 1e-5
    assert segments[1][0][0] >= face_max_x - 1e-5


def test_rotated_building_faces_clip_line_segments_by_default() -> None:
    scene = Scene3D()
    scene.add(Box3D(center=(0.0, 0.0, 0.0), size=(80.0, 80.0, 120.0), material=SolidMaterial(fill=(150, 100, 80))))
    scene.add(Line3D(start=(-150.0, 0.0, 30.0), end=(150.0, 0.0, 30.0), color=(255, 255, 0)))
    camera = Camera3D(target=(0.0, 0.0, 40.0), yaw_deg=35.0, pitch_deg=45.0, zoom=1.0)

    renderer, frame, entries = project_scene_entries(scene, camera)
    line_entry = next(entry for entry in entries if entry.kind == "line")
    polygon_entries = tuple(entry for entry in entries if entry.kind == "polygon")
    segments = renderer._visible_line_segments(line_entry, polygon_entries, frame)

    assert len(segments) == 2


def test_non_occluding_surface_skips_rotated_line_depth_tests() -> None:
    camera = Camera3D(target=(0.0, 0.0, 40.0), yaw_deg=35.0, pitch_deg=45.0, zoom=1.0)

    occluding_scene = Scene3D()
    occluding_scene.add(
        Polygon3D(
            points=((-40.0, -20.0, 0.0), (40.0, -20.0, 0.0), (40.0, 20.0, 120.0), (-40.0, 20.0, 120.0)),
            material=SolidMaterial(fill=(80, 120, 170), shaded=False),
            cull_back_face=False,
        )
    )
    occluding_scene.add(Line3D(start=(-150.0, 0.0, 30.0), end=(150.0, 0.0, 30.0), color=(255, 255, 0)))
    occluding_renderer, occluding_frame, occluding_entries = project_scene_entries(occluding_scene, camera)
    occluding_line = next(entry for entry in occluding_entries if entry.kind == "line")
    occluding_polygons = tuple(entry for entry in occluding_entries if entry.kind == "polygon")

    decorative_scene = Scene3D()
    decorative_scene.add(
        Polygon3D(
            points=((-40.0, -20.0, 0.0), (40.0, -20.0, 0.0), (40.0, 20.0, 120.0), (-40.0, 20.0, 120.0)),
            material=SolidMaterial(fill=(80, 120, 170), shaded=False, line_occluder=False),
            cull_back_face=False,
        )
    )
    decorative_scene.add(Line3D(start=(-150.0, 0.0, 30.0), end=(150.0, 0.0, 30.0), color=(255, 255, 0)))
    decorative_renderer, decorative_frame, decorative_entries = project_scene_entries(decorative_scene, camera)
    decorative_line = next(entry for entry in decorative_entries if entry.kind == "line")
    decorative_polygons = tuple(entry for entry in decorative_entries if entry.kind == "polygon")

    occluding_segments = occluding_renderer._visible_line_segments(occluding_line, occluding_polygons, occluding_frame)
    decorative_segments = decorative_renderer._visible_line_segments(decorative_line, decorative_polygons, decorative_frame)

    assert len(occluding_segments) > 1
    assert len(decorative_segments) == 1


@pytest.mark.parametrize("alpha", [80, 255])
def test_non_occluding_translucent_surface_is_emitted_in_depth_order(monkeypatch, alpha) -> None:
    scene = Scene3D()
    floor = SolidMaterial(fill=(80, 100, 120), outline=None, shaded=False)
    tint = SolidMaterial(fill=(255, 180, 80, alpha), outline=None, shaded=False, line_occluder=False)
    for z, material in ((0, floor), (10, tint)):
        scene.add(Polygon3D(
            points=((-40, -40, z), (40, -40, z), (40, 40, z), (-40, 40, z)),
            material=material, cull_back_face=False,
        ))
    renderer = CpuRenderer3D()
    emitted = []

    def capture(context, target, scene, frame, prepared, *args):
        emitted.extend(draw.entry for draw in prepared)
        return len(emitted)

    monkeypatch.setattr(renderer, "emit_entries", capture)
    context = dcg.Context()
    layer = dcg.DrawingList(context)
    try:
        renderer.render(context, layer, scene, Camera3D((0, 0, 0), 0, 0, 1), Viewport(800, 600))
        assert emitted[-1].material == (tint if alpha < 255 else floor)
        assert next(entry for entry in emitted if entry.material == tint).line_occluder is False
    finally:
        layer.delete_item()


def test_demo_11_marks_road_and_water_surfaces_as_non_occluding_decoration() -> None:
    demo = load_demo_11()
    scene, _player = demo.build_scene()
    materials = [item.material for item in scene.iter_visible() if hasattr(item, "material")]
    decorative_by_fill = {
        material.fill: material.line_occluder
        for material in materials
        if material.fill in {(68, 116, 168), (130, 116, 91)}
    }

    assert decorative_by_fill == {
        (68, 116, 168): False,
        (130, 116, 91): False,
    }
    assert any(
        isinstance(item, Box3D) and item.material.line_occluder
        for item in scene.iter_visible()
    )


def test_collision_sort_example_allows_disabling_collision_checks() -> None:
    example = load_collision_sort_example()
    demo = load_demo_12()
    player = demo.Box3D(
        center=(100.0, 100.0, 0.0),
        size=(70.0, 70.0, 115.0),
        material=SolidMaterial(fill=(245, 194, 67)),
    )
    collisions = CollisionWorld(gap=2.0)
    collisions.add("building", AabbFootprint.from_center(200.0, 100.0, 100.0, 100.0))
    controller = object.__new__(example.ConfigurableCollisionSortController)
    controller.player = player
    controller.collisions = collisions
    controller.collision_enabled = False
    controller.blocked_by = None
    follow_calls = []
    controller.follow = type("FollowProbe", (), {"update": lambda self, point: follow_calls.append(point)})()
    repaint_calls = []
    controller.repaint = lambda: repaint_calls.append(True)

    controller._move(100.0, 0.0)

    assert player.center == (200.0, 100.0, 0.0)
    assert controller.blocked_by is None
    assert follow_calls == [(200.0, 100.0, 0.0)]
    assert repaint_calls == [True]


def test_collision_sort_example_status_surfaces_cycle_fallback() -> None:
    example = load_collision_sort_example()
    player = load_demo_12().Box3D(
        center=(120.0, 240.0, 0.0),
        size=(70.0, 70.0, 115.0),
        material=SolidMaterial(fill=(245, 194, 67)),
    )
    camera = Camera3D(target=(1100.0, 750.0, 0.0), yaw_deg=15.0, pitch_deg=52.0, zoom=0.72)

    status = example.build_status_text(
        player,
        camera,
        (900.0, 600.0),
        RenderStats(packet_count=20, clipped_count=3, projected_count=17, emitted_count=22, cycle_detected=True),
        collision_enabled=True,
        sorter_mode="overlap",
        blocked_by="building 2",
    )

    assert "collision=on" in status
    assert "sort=overlap" in status
    assert "blocked by=building 2" in status
    assert "occlusion cycle fallback" in status


@pytest.mark.parametrize("use_sweep_and_prune", (True, False))
def test_collision_sort_example_uses_startup_sweep_toggle(monkeypatch, use_sweep_and_prune: bool) -> None:
    example = load_collision_sort_example()

    assert example.USE_SWEEP_AND_PRUNE is True
    monkeypatch.setattr(example, "USE_SWEEP_AND_PRUNE", use_sweep_and_prune)
    sorter = example.build_sorter("overlap")

    assert isinstance(sorter, OverlapDepthSorter)
    assert sorter.use_sweep_and_prune is use_sweep_and_prune