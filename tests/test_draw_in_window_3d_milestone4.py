from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AnimatedImageMaterial,
    AnimationProjection,
    Billboard3D,
    Box3D,
    Camera3D,
    DrawInWindow3D,
    DrawStream3D,
    FrameContext,
    ImageMaterial,
    Line3D,
    LineRenderLayer,
    ProjectionPipeline,
    Polygon3D,
    Scene3D,
    SolidMaterial,
    Viewport,
)
from Animation.draw_in_window_3d_framework.renderer import CpuRenderer3D
from Animation.draw_in_window_3d_framework.objects import billboard_quad


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_demo_14():
    source = REPO_ROOT / "Animation" / "ported_demos" / "14_dearcygui_cpu_3d_trees.py"
    spec = importlib.util.spec_from_file_location("framework_demo_14_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_widget(scene: Scene3D, camera: Camera3D):
    context = dcg.Context()
    with dcg.Window(context, label="milestone-4", width=440, height=320):
        with DrawInWindow3D(
            context,
            width=280,
            height=180,
            scene=scene,
            camera=camera,
        ) as viewport:
            yielded = viewport
    return context, yielded


def noop_frame_builder(context, parent, frame, frame_index: int) -> None:
    dcg.DrawLine(
        context,
        parent=parent,
        p1=(float(frame_index), 0.0),
        p2=(float(frame_index) + 1.0, 1.0),
        color=(255, 255, 255),
        thickness=-1,
    )


def make_tree_frames(context: dcg.Context) -> tuple[dcg.Texture, ...]:
    textures: list[dcg.Texture] = []
    for rgba in ((80, 140, 90, 255), (70, 120, 80, 255)):
        texture = dcg.Texture(context)
        pixels = bytearray(bytes(rgba) * 4)
        texture.set_value(memoryview(pixels).cast("B", shape=(2, 2, 4)))
        textures.append(texture)
    return tuple(textures)


def first_child_named(parent, type_name: str):
    return next(child for child in parent.children if type(child).__name__ == type_name)


def test_billboard_quad_matches_image_corner_order() -> None:
    points = billboard_quad(anchor=(10.0, 20.0, 5.0), world_size=(8.0, 12.0), yaw_deg=0.0)

    assert points == (
        (6.0, 20.0, 17.0),
        (14.0, 20.0, 17.0),
        (14.0, 20.0, 5.0),
        (6.0, 20.0, 5.0),
    )


def test_persistent_overlay_stream_survives_camera_change_without_rebuild() -> None:
    scene = Scene3D()
    scene.add(
        DrawStream3D(
            projection_policy=AnimationProjection.PERSISTENT_OVERLAY,
            frame_count=2,
            loop_seconds=1.0,
            frame_builder=noop_frame_builder,
            anchor=(60.0, 0.0, 60.0),
            world_size=(40.0, 40.0),
        )
    )
    camera = Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=35.0, zoom=1.0, near_plane=1.0)
    _context, viewport = build_widget(scene, camera)

    viewport.render_now()
    transform = first_child_named(viewport.overlay_layer, "DrawingScale")
    stream = first_child_named(transform, "DrawStream")
    first_origin = transform.origin
    first_scale = transform.scales

    viewport.orbit(yaw_delta=18.0)
    viewport.render_now()
    second_transform = first_child_named(viewport.overlay_layer, "DrawingScale")
    second_stream = first_child_named(second_transform, "DrawStream")

    assert second_transform is transform
    assert second_stream is stream
    assert second_transform.origin != first_origin or second_transform.scales != first_scale


def test_preprojected_background_stream_rebuilds_after_camera_change() -> None:
    scene = Scene3D()
    scene.add(
        DrawStream3D(
            projection_policy=AnimationProjection.PREPROJECTED_BACKGROUND,
            frame_count=2,
            loop_seconds=1.0,
            frame_builder=noop_frame_builder,
        )
    )
    camera = Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=35.0, zoom=1.0, near_plane=1.0)
    _context, viewport = build_widget(scene, camera)

    viewport.render_now()
    first_stream = first_child_named(viewport.displayed_layer, "DrawStream")

    viewport.orbit(yaw_delta=18.0)
    viewport.render_now()
    second_stream = first_child_named(viewport.displayed_layer, "DrawStream")

    assert second_stream is not first_stream


def test_occludable_billboard_emits_viewport_clipped_draw_stream() -> None:
    context = dcg.Context()
    scene = Scene3D()
    scene.add(
        Billboard3D(
            anchor=(-40.0, 0.0, 0.0),
            world_size=(120.0, 180.0),
            material=AnimatedImageMaterial(
                frames=make_tree_frames(context),
                loop_seconds=1.25,
                tessellation=1,
                projection_policy=AnimationProjection.OCCLUDABLE_WORLD,
            ),
        )
    )
    camera = Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=35.0, zoom=1.0, near_plane=1.0)
    with dcg.Window(context, label="billboard-clip", width=440, height=320):
        with DrawInWindow3D(
            context,
            width=280,
            height=180,
            scene=scene,
            camera=camera,
        ) as viewport:
            pass

    viewport.render_now()

    clip = first_child_named(viewport.displayed_layer, "DrawingClip")
    stream = first_child_named(clip, "DrawStream")

    assert stream.time_modulus == 1.25
    assert len(stream.children) == 2


def test_billboard_still_sorts_as_polygon_but_does_not_occlude_lines() -> None:
    context = dcg.Context()
    scene = Scene3D()
    scene.add(
        Billboard3D(
            anchor=(0.0, 0.0, 0.0),
            world_size=(120.0, 180.0),
            material=AnimatedImageMaterial(
                frames=make_tree_frames(context),
                loop_seconds=1.0,
                tessellation=1,
                projection_policy=AnimationProjection.OCCLUDABLE_WORLD,
            ),
        )
    )
    scene.add(Box3D(center=(0.0, 40.0, 0.0), size=(50.0, 50.0, 60.0), material=SolidMaterial(fill=(120, 100, 80))))

    renderer = CpuRenderer3D()
    frame = FrameContext(
        camera=Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=35.0, zoom=1.0, near_plane=1.0),
        viewport=Viewport(280.0, 180.0),
    )
    pipeline = ProjectionPipeline(frame.camera, frame.viewport)
    entries = [
        renderer._project_packet(packet, stable_index, frame, pipeline)
        for stable_index, packet in enumerate(renderer._collect_packets(scene, frame))
    ]
    entries = [entry for entry in entries if entry is not None]

    billboard_entry = next(entry for entry in entries if entry.kind == "polygon" and isinstance(entry.material, AnimatedImageMaterial))
    assert billboard_entry.line_occluder is False
    assert any(entry.kind == "polygon" and isinstance(entry.material, SolidMaterial) for entry in entries)

    line_packet = next(iter(Line3D(start=(-100.0, 0.0, 30.0), end=(100.0, 0.0, 30.0), color=(255, 255, 0)).collect(frame)))
    projected_line = renderer._project_packet(line_packet, 999, frame, pipeline)
    assert projected_line is not None

    polygon_entries = (billboard_entry,)
    visible_segments = renderer._visible_line_segments(projected_line, polygon_entries, frame)

    assert len(visible_segments) == 1


def test_utility_grid_line_renders_between_underlay_and_billboard() -> None:
    context = dcg.Context()
    scene = Scene3D()
    scene.add(
        Polygon3D(
            points=((-120.0, -120.0, 0.0), (120.0, -120.0, 0.0), (120.0, 120.0, 0.0), (-120.0, 120.0, 0.0)),
            material=SolidMaterial(fill=(42, 66, 47), outline=None, thickness=-1.0, shaded=False, line_occluder=False),
            cull_back_face=False,
        )
    )
    scene.add(
        Line3D(
            start=(-120.0, 0.0, 1.0),
            end=(120.0, 0.0, 1.0),
            color=(255, 255, 0),
            render_layer=LineRenderLayer.UTILITY,
        )
    )
    scene.add(
        Billboard3D(
            anchor=(0.0, 0.0, 0.0),
            world_size=(120.0, 180.0),
            material=AnimatedImageMaterial(
                frames=make_tree_frames(context),
                loop_seconds=1.0,
                tessellation=1,
                projection_policy=AnimationProjection.OCCLUDABLE_WORLD,
            ),
        )
    )
    camera = Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=35.0, zoom=1.0, near_plane=1.0)
    with dcg.Window(context, label="utility-line-order", width=440, height=320):
        with DrawInWindow3D(
            context,
            width=280,
            height=180,
            scene=scene,
            camera=camera,
        ) as viewport:
            pass

    viewport.render_now()

    child_types = [type(child).__name__ for child in viewport.displayed_layer.children]

    assert child_types.index("DrawPolygon") < child_types.index("DrawLine")
    assert child_types.index("DrawLine") < child_types.index("DrawingClip")


def test_demo_14_scene_contains_textured_player_water_overlay_and_billboards() -> None:
    demo = load_demo_14()
    context = dcg.Context()
    scene, player, marker = demo.build_scene(context)
    camera = Camera3D(
        target=(demo.demo11.WORLD_W * 0.5, demo.demo11.WORLD_H * 0.5, 0.0),
        yaw_deg=0.0,
        pitch_deg=52.0,
        zoom=0.72,
    )
    _context, viewport = build_widget(scene, camera)

    stats = viewport.render_now()
    visible_items = list(scene.iter_visible())

    assert isinstance(player.face_materials[4], ImageMaterial)
    assert marker.projection_policy is AnimationProjection.PERSISTENT_OVERLAY
    assert any(
        isinstance(item, DrawStream3D)
        and item.projection_policy is AnimationProjection.PREPROJECTED_BACKGROUND
        for item in visible_items
    )
    assert any(isinstance(item, Billboard3D) for item in visible_items)
    assert stats.projected_count > 0
    assert any(type(child).__name__ == "DrawStream" for child in viewport.displayed_layer.children)
    assert any(type(child).__name__ == "DrawingScale" for child in viewport.overlay_layer.children)


def test_demo_14_controller_blocks_movement_into_building() -> None:
    demo = load_demo_14()
    context = dcg.Context()
    scene, player, marker = demo.build_scene(context)
    collisions = demo.build_collision_world(scene, player)
    _context, viewport = build_widget(
        scene,
        Camera3D(
            target=(demo.demo11.WORLD_W * 0.5, demo.demo11.WORLD_H * 0.5, 0.0),
            yaw_deg=0.0,
            pitch_deg=52.0,
            zoom=0.72,
        ),
    )
    status = dcg.Text(context, value="")
    controller = demo.FrameworkDemo14Controller(viewport, player, marker, status, collisions)
    controller.player.center = (299.0, 400.0, 0.0)
    controller.marker.anchor = (299.0, 400.0, demo.MARKER_HEIGHT)

    controller._apply_move(demo.demo11.MOVE_STEP, 0.0)
    controller.render_if_needed()

    assert controller.player.center == (299.0, 400.0, 0.0)
    assert controller.marker.anchor == (299.0, 400.0, demo.MARKER_HEIGHT)
    assert controller.blocked_by == "building 1"
    assert "blocked by=building 1" in controller.status.value


def test_demo_14_controller_coalesces_key_repeat_into_frame_ticks() -> None:
    demo = load_demo_14()
    context = dcg.Context()
    scene, player, marker = demo.build_scene(context)
    collisions = demo.build_collision_world(scene, player)
    _context, viewport = build_widget(
        scene,
        Camera3D(
            target=(demo.demo11.WORLD_W * 0.5, demo.demo11.WORLD_H * 0.5, 0.0),
            yaw_deg=0.0,
            pitch_deg=52.0,
            zoom=0.72,
        ),
    )
    status = dcg.Text(context, value="")
    controller = demo.FrameworkDemo14Controller(viewport, player, marker, status, collisions)
    start_center = controller.player.center

    controller._queue_move("right", now=1.0)
    controller._queue_move("right", now=1.01)

    moved_first_tick = controller.tick(now=1.02)
    moved_second_tick = controller.tick(now=1.03)
    moved_after_expiry = controller.tick(now=1.20)

    assert moved_first_tick is True
    assert moved_second_tick is False
    assert moved_after_expiry is False
    assert controller.player.center == (start_center[0] + demo.demo11.MOVE_STEP, start_center[1], start_center[2])


def test_demo_14_controller_combines_simultaneous_directions_for_diagonal_motion() -> None:
    demo = load_demo_14()
    context = dcg.Context()
    scene, player, marker = demo.build_scene(context)
    collisions = demo.build_collision_world(scene, player)
    _context, viewport = build_widget(
        scene,
        Camera3D(
            target=(demo.demo11.WORLD_W * 0.5, demo.demo11.WORLD_H * 0.5, 0.0),
            yaw_deg=0.0,
            pitch_deg=52.0,
            zoom=0.72,
        ),
    )
    status = dcg.Text(context, value="")
    controller = demo.FrameworkDemo14Controller(viewport, player, marker, status, collisions)
    controller.player.center = (1100.0, 750.0, 0.0)
    controller.marker.anchor = (1100.0, 750.0, demo.MARKER_HEIGHT)

    controller._queue_move("up", now=1.0)
    controller._queue_move("right", now=1.01)

    moved = controller.tick(now=1.02)

    assert moved is True
    assert controller.player.center == (
        1100.0 + demo.demo11.MOVE_STEP,
        750.0 - demo.demo11.MOVE_STEP,
        0.0,
    )
    assert controller.marker.anchor == (
        1100.0 + demo.demo11.MOVE_STEP,
        750.0 - demo.demo11.MOVE_STEP,
        demo.MARKER_HEIGHT,
    )


def test_mixed_4c_objects_collect_and_project_through_common_packet_api() -> None:
    context = dcg.Context()
    scene = Scene3D()
    scene.add(Box3D(center=(0.0, 0.0, 0.0), size=(30.0, 30.0, 40.0), material=SolidMaterial(fill=(160, 120, 80))))
    scene.add(
        Billboard3D(
            anchor=(20.0, 0.0, 0.0),
            world_size=(40.0, 80.0),
            material=AnimatedImageMaterial(
                frames=make_tree_frames(context),
                loop_seconds=1.0,
                tessellation=1,
                projection_policy=AnimationProjection.OCCLUDABLE_WORLD,
            ),
        )
    )
    scene.add(
        DrawStream3D(
            projection_policy=AnimationProjection.PREPROJECTED_BACKGROUND,
            frame_count=2,
            loop_seconds=1.0,
            frame_builder=noop_frame_builder,
        )
    )
    scene.add(
        DrawStream3D(
            projection_policy=AnimationProjection.PERSISTENT_OVERLAY,
            frame_count=2,
            loop_seconds=1.0,
            frame_builder=noop_frame_builder,
            anchor=(0.0, 0.0, 60.0),
            world_size=(30.0, 30.0),
        )
    )

    renderer = CpuRenderer3D()
    frame = FrameContext(
        camera=Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=35.0, zoom=1.0),
        viewport=Viewport(280.0, 180.0),
    )
    pipeline = ProjectionPipeline(frame.camera, frame.viewport)

    packets = list(renderer._collect_packets(scene, frame))
    entries = [
        renderer._project_packet(packet, stable_index, frame, pipeline)
        for stable_index, packet in enumerate(packets)
    ]
    entries = [entry for entry in entries if entry is not None]

    assert {packet.kind for packet in packets} >= {"polygon", "stream"}
    assert any(entry.kind == "polygon" and isinstance(entry.material, AnimatedImageMaterial) for entry in entries)
    assert any(
        entry.kind == "stream"
        and entry.animation_projection is AnimationProjection.PREPROJECTED_BACKGROUND
        for entry in entries
    )
    assert any(
        entry.kind == "stream"
        and entry.animation_projection is AnimationProjection.PERSISTENT_OVERLAY
        for entry in entries
    )