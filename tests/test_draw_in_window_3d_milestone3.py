from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg

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
    material = AnimatedImageMaterial(texture=frames[0], frames=frames, loop_seconds=1.5, frame_offset=1)

    assert material.frame_texture(0) is frames[1]
    assert material.frame_texture(2) is frames[0]
    assert material.frame_end_time(1) == 1.0


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