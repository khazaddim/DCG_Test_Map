from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Sequence, TypeAlias

import dearcygui as dcg

try:
    from .math3d import Camera3D, Viewport
    from .renderer import CpuRenderer3D
    from .scene import RenderStats, Scene3D
except ImportError:
    from Animation.draw_in_window_3d_framework.math3d import Camera3D, Viewport
    from Animation.draw_in_window_3d_framework.renderer import CpuRenderer3D
    from Animation.draw_in_window_3d_framework.scene import RenderStats, Scene3D


Point2: TypeAlias = tuple[float, float]
Color: TypeAlias = tuple[int, int, int] | tuple[int, int, int, int]
ColorValue: TypeAlias = Color | int
FrameBuilder: TypeAlias = Callable[[dcg.DrawingList], None]


@dataclass(frozen=True)
class PolygonStyle:
    fill: ColorValue = (214, 164, 74)
    outline: ColorValue = (24, 27, 25)
    thickness: float = -2.0


def clear_drawing_list(layer: dcg.DrawingList) -> None:
    for child in list(layer.children):
        child.delete_item()


class FramePublisher:
    """Own a visible/hidden DrawingList pair and swap them atomically."""

    def __init__(self, context: dcg.Context, parent: dcg.baseItem) -> None:
        self._parent = parent
        self.displayed_layer = dcg.DrawingList(context, parent=parent)
        self.back_layer = dcg.DrawingList(context, parent=parent, show=False)
        self.published_revision = 0

    def replace_contents(self, builder: FrameBuilder) -> int:
        clear_drawing_list(self.back_layer)
        builder(self.back_layer)
        with self._parent.mutex:
            self.displayed_layer.show = False
            self.back_layer.show = True
            self.displayed_layer, self.back_layer = (
                self.back_layer,
                self.displayed_layer,
            )
        self.published_revision += 1
        return self.published_revision


class DrawInWindow3D(dcg.DrawInWindow):
    """Retained 3D viewport with atomic publication and event-driven redraw."""

    def __init__(
        self,
        context: dcg.Context,
        *,
        scene: Scene3D | None = None,
        camera: Camera3D | None = None,
        renderer: CpuRenderer3D | None = None,
        **kwargs,
    ) -> None:
        super().__init__(context, **kwargs)
        self.scene_layer = dcg.DrawingList(context, parent=self)
        self.publisher = FramePublisher(context, parent=self.scene_layer)
        self.scene = scene or Scene3D()
        self.camera = camera or Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=52.0, zoom=1.0)
        self.renderer = renderer or CpuRenderer3D()
        self._dirty = True
        self.last_render_revision = 0
        self.last_render_stats = RenderStats(0, 0, 0, 0, False)

    @property
    def displayed_layer(self) -> dcg.DrawingList:
        return self.publisher.displayed_layer

    @property
    def back_layer(self) -> dcg.DrawingList:
        return self.publisher.back_layer

    @property
    def viewport(self) -> Viewport:
        return Viewport(float(self.width.value), float(self.height.value))

    def replace_contents(self, builder: FrameBuilder) -> int:
        self._dirty = False
        return self.publisher.replace_contents(builder)

    def replace_polygon(
        self,
        points: Sequence[Point2],
        style: PolygonStyle = PolygonStyle(),
    ) -> int:
        frozen_points = tuple((float(x), float(y)) for x, y in points)

        def builder(layer: dcg.DrawingList) -> None:
            dcg.DrawPolygon(
                self.context,
                parent=layer,
                points=frozen_points,
                fill=style.fill,
                color=style.outline,
                thickness=style.thickness,
            )

        return self.replace_contents(builder)

    def invalidate(self) -> None:
        self._dirty = True

    def render_if_needed(self) -> RenderStats | None:
        if not self._dirty:
            return None
        return self.render_now()

    def render_now(self) -> RenderStats:
        rendered: dict[str, RenderStats] = {}

        def builder(layer: dcg.DrawingList) -> None:
            rendered["stats"] = self.renderer.render(
                self.context,
                layer,
                self.scene,
                self.camera,
                self.viewport,
            )

        self.last_render_revision = self.publisher.replace_contents(builder)
        self._dirty = False
        self.last_render_stats = rendered["stats"]
        return self.last_render_stats

    def set_camera(self, camera: Camera3D) -> Camera3D:
        self.camera = camera
        self.invalidate()
        return self.camera

    def orbit(self, yaw_delta: float = 0.0, pitch_delta: float = 0.0) -> Camera3D:
        return self.set_camera(
            replace(
                self.camera,
                yaw_deg=self.camera.yaw_deg + yaw_delta,
                pitch_deg=self.camera.pitch_deg + pitch_delta,
            )
        )

    def pan_world(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Camera3D:
        target = self.camera.target
        return self.set_camera(
            replace(
                self.camera,
                target=(target[0] + dx, target[1] + dy, target[2] + dz),
            )
        )

    def zoom_by(self, factor: float) -> Camera3D:
        return self.set_camera(replace(self.camera, zoom=self.camera.zoom * factor))

    def focus_on(self, target: tuple[float, float, float]) -> Camera3D:
        return self.set_camera(replace(self.camera, target=target))

    def world_to_screen(self, point: tuple[float, float, float]) -> tuple[float, float] | None:
        camera_point = self.camera.world_to_camera(point, self.viewport)
        if camera_point[2] < self.camera.near_plane:
            return None
        screen = self.camera.camera_to_screen(camera_point, self.viewport)
        if not self.viewport.contains(screen):
            return None
        return screen

    def screen_to_ground(
        self,
        screen: tuple[float, float],
        *,
        ground_z: float = 0.0,
    ) -> tuple[float, float, float] | None:
        return self.camera.ground_from_screen(screen, self.viewport, ground_z=ground_z)