from __future__ import annotations

from dataclasses import dataclass

from .math3d import Camera3D, Vec3
from .terrain import TerrainSurface


@dataclass
class EdgeBandFollowController:
    """Keep a world focus point inside a screen-space dead zone by retargeting the camera."""

    viewport: "DrawInWindow3D"
    band_x: float
    band_y: float
    world_bounds: tuple[float, float, float, float] | None = None
    ground_z: float = 0.0
    terrain: TerrainSurface | None = None

    def update(self, focus_point: Vec3) -> Camera3D:
        focus_surface = focus_point if self.terrain is not None else (focus_point[0], focus_point[1], self.ground_z)
        screen = self.viewport.world_to_screen(focus_surface)
        if screen is None:
            return self.viewport.camera
        current_viewport = self.viewport.viewport
        target_screen = (
            max(self.band_x, min(current_viewport.width - self.band_x, screen[0])),
            max(self.band_y, min(current_viewport.height - self.band_y, screen[1])),
        )
        if target_screen == screen:
            return self.viewport.camera
        target_surface = self.viewport.screen_to_surface(
            target_screen,
            terrain=self.terrain,
            ground_z=self.ground_z if self.terrain is None else None,
        )
        if target_surface is None:
            return self.viewport.camera
        camera = self.viewport.camera
        offset_x = target_surface[0] - camera.target[0]
        offset_y = target_surface[1] - camera.target[1]
        next_target = (
            focus_surface[0] - offset_x,
            focus_surface[1] - offset_y,
            focus_surface[2] if self.terrain is not None else camera.target[2],
        )
        if self.world_bounds is not None:
            x0, y0, x1, y1 = self.world_bounds
            next_target = (
                max(x0, min(x1, next_target[0])),
                max(y0, min(y1, next_target[1])),
                next_target[2],
            )
        return self.viewport.set_camera(
            Camera3D(
                target=next_target,
                yaw_deg=camera.yaw_deg,
                pitch_deg=camera.pitch_deg,
                zoom=camera.zoom,
                fov_y_deg=camera.fov_y_deg,
                near_plane=camera.near_plane,
            )
        )