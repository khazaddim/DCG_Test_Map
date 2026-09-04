from __future__ import annotations

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    AverageDepthSorter,
    Box3D,
    Camera3D,
    DrawInWindow3D,
    EdgeBandFollowController,
    FrameContext,
    GroundPlane3D,
    Line3D,
    ProjectedRenderEntry,
    Scene3D,
    SolidMaterial,
    Text3D,
    Viewport,
)


class ProbeRenderable:
    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.collect_calls = 0

    def collect(self, frame: FrameContext):
        self.collect_calls += 1
        return []


def build_widget(scene: Scene3D | None = None, camera: Camera3D | None = None):
    context = dcg.Context()
    with dcg.Window(context, label="milestone-2", width=400, height=320):
        with DrawInWindow3D(
            context,
            width=240,
            height=160,
            scene=scene,
            camera=camera,
        ) as viewport:
            yielded = viewport
    return context, yielded


def test_scene_handles_remain_stable_and_hidden_objects_are_skipped() -> None:
    scene = Scene3D()
    visible = ProbeRenderable(visible=True)
    hidden = ProbeRenderable(visible=False)
    other = ProbeRenderable(visible=True)

    visible_handle = scene.add(visible)
    hidden_handle = scene.add(hidden)
    other_handle = scene.add(other)
    scene.remove(hidden_handle)

    assert scene.get(visible_handle) is visible
    assert scene.get(other_handle) is other

    frame = FrameContext(
        camera=Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=52.0, zoom=1.0),
        viewport=Viewport(240.0, 160.0),
    )
    for item in scene.iter_visible():
        list(item.collect(frame))

    assert visible.collect_calls == 1
    assert hidden.collect_calls == 0
    assert other.collect_calls == 1


def test_average_depth_sorter_breaks_ties_with_stable_index() -> None:
    sorter = AverageDepthSorter()
    ordered = sorter.sort(
        [
            ProjectedRenderEntry(kind="line", stable_index=3, average_depth=10.0, points=((0.0, 0.0), (1.0, 1.0))),
            ProjectedRenderEntry(kind="line", stable_index=1, average_depth=10.0, points=((0.0, 0.0), (1.0, 1.0))),
            ProjectedRenderEntry(kind="line", stable_index=2, average_depth=8.0, points=((0.0, 0.0), (1.0, 1.0))),
        ]
    )

    assert [entry.stable_index for entry in ordered.entries] == [1, 3, 2]


def test_widget_render_now_publishes_layer_and_coalesces_dirty_flag() -> None:
    scene = Scene3D(background=(10, 20, 30))
    scene.add(GroundPlane3D(bounds=(0.0, 0.0, 100.0, 100.0), z=0.0, material=SolidMaterial(fill=(20, 30, 40), outline=None, shaded=False)))
    scene.add(Line3D(start=(0.0, 0.0, 5.0), end=(100.0, 100.0, 5.0), color=(255, 200, 0)))
    scene.add(Text3D(position=(50.0, 50.0, 5.0), text="label", size=12.0, color=(255, 255, 255)))
    scene.add(Box3D(center=(50.0, 50.0, 0.0), size=(30.0, 30.0, 40.0), material=SolidMaterial(fill=(160, 120, 80))))
    camera = Camera3D(target=(50.0, 50.0, 0.0), yaw_deg=25.0, pitch_deg=52.0, zoom=0.8)
    _context, viewport = build_widget(scene, camera)

    stats = viewport.render_now()

    assert stats.packet_count == 9
    assert stats.projected_count > 0
    assert viewport.last_render_revision == 1
    assert viewport.displayed_layer.show is True
    assert viewport.back_layer.show is False
    assert len(viewport.displayed_layer.children) == stats.emitted_count
    assert type(viewport.displayed_layer.children[0]).__name__ == "DrawRect"
    assert viewport.render_if_needed() is None


def test_world_to_screen_and_resize_use_live_viewport_dimensions() -> None:
    camera = Camera3D(target=(50.0, 50.0, 0.0), yaw_deg=20.0, pitch_deg=52.0, zoom=0.8)
    _context, viewport = build_widget(Scene3D(), camera)

    original = viewport.world_to_screen((150.0, 50.0, 0.0))
    assert original is not None

    viewport.width = 360.0
    viewport.height = 220.0

    resized = viewport.world_to_screen((150.0, 50.0, 0.0))
    assert resized is not None
    assert resized != original


def test_edge_band_follow_controller_pans_camera_toward_focus_point() -> None:
    camera = Camera3D(target=(50.0, 50.0, 0.0), yaw_deg=0.0, pitch_deg=52.0, zoom=0.8)
    _context, viewport = build_widget(Scene3D(), camera)
    controller = EdgeBandFollowController(
        viewport=viewport,
        band_x=70.0,
        band_y=50.0,
        world_bounds=(0.0, 0.0, 300.0, 300.0),
    )

    updated_camera = controller.update((150.0, 50.0, 0.0))
    updated_screen = viewport.world_to_screen((150.0, 50.0, 0.0))

    assert updated_camera.target != (50.0, 50.0, 0.0)
    assert updated_screen is not None
    assert 70.0 <= updated_screen[0] <= viewport.viewport.width - 70.0
    assert 50.0 <= updated_screen[1] <= viewport.viewport.height - 50.0