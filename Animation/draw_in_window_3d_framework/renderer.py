from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Iterable

import dearcygui as dcg

from .math3d import ProjectionPipeline, shade_directional
from .scene import (
    AnimatedImageMaterial,
    AnimationProjection,
    FrameContext,
    ImageMaterial,
    OverlapDepthSorter,
    ProjectedRenderEntry,
    ray_plane_depth,
    RenderSorter,
    RenderStats,
    Scene3D,
    SolidMaterial,
    WorldRenderPacket,
)


@dataclass
class PersistentOverlayState:
    transform: dcg.DrawingScale


def clear_drawing_list(layer: dcg.DrawingList) -> None:
    for child in list(layer.children):
        child.delete_item()


def _screen_lerp(p0: tuple[float, float], p1: tuple[float, float], amount: float) -> tuple[float, float]:
    return (
        p0[0] + (p1[0] - p0[0]) * amount,
        p0[1] + (p1[1] - p0[1]) * amount,
    )


def _bilinear_quad(
    points: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, ...]],
    u: float,
    v: float,
) -> tuple[float, ...]:
    weights = ((1.0 - u) * (1.0 - v), u * (1.0 - v), u * v, (1.0 - u) * v)
    return tuple(
        sum(point[coordinate] * weight for point, weight in zip(points, weights))
        for coordinate in range(len(points[0]))
    )


def _point_on_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float], epsilon: float) -> bool:
    cross = (point[0] - start[0]) * (end[1] - start[1]) - (point[1] - start[1]) * (end[0] - start[0])
    if abs(cross) > epsilon:
        return False
    dot = ((point[0] - start[0]) * (end[0] - start[0])) + ((point[1] - start[1]) * (end[1] - start[1]))
    if dot < -epsilon:
        return False
    squared_length = ((end[0] - start[0]) ** 2) + ((end[1] - start[1]) ** 2)
    return dot <= squared_length + epsilon


def _point_in_polygon(point: tuple[float, float], polygon: tuple[tuple[float, float], ...], epsilon: float = 1e-6) -> bool:
    inside = False
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        if _point_on_segment(point, start, end, epsilon):
            return True
        intersects = ((start[1] > point[1]) != (end[1] > point[1]))
        if not intersects:
            continue
        denominator = end[1] - start[1]
        if abs(denominator) <= epsilon:
            continue
        boundary_x = start[0] + (point[1] - start[1]) * (end[0] - start[0]) / denominator
        if boundary_x >= point[0] - epsilon:
            inside = not inside
    return inside


def _segment_intersection_parameter(
    line_start: tuple[float, float],
    line_end: tuple[float, float],
    edge_start: tuple[float, float],
    edge_end: tuple[float, float],
    epsilon: float = 1e-7,
) -> float | None:
    line_dx = line_end[0] - line_start[0]
    line_dy = line_end[1] - line_start[1]
    edge_dx = edge_end[0] - edge_start[0]
    edge_dy = edge_end[1] - edge_start[1]
    denominator = line_dx * edge_dy - line_dy * edge_dx
    if abs(denominator) <= epsilon:
        return None
    offset_x = edge_start[0] - line_start[0]
    offset_y = edge_start[1] - line_start[1]
    line_amount = (offset_x * edge_dy - offset_y * edge_dx) / denominator
    edge_amount = (offset_x * line_dy - offset_y * line_dx) / denominator
    if -epsilon <= line_amount <= 1.0 + epsilon and -epsilon <= edge_amount <= 1.0 + epsilon:
        return min(1.0, max(0.0, line_amount))
    return None


def _line_depth_at_screen_point(
    screen_point: tuple[float, float],
    camera_points: tuple[tuple[float, float, float], tuple[float, float, float]],
    frame: FrameContext,
) -> float | None:
    start, end = camera_points
    center_x, center_y = frame.viewport.center
    focal_length = frame.camera.focal_length(frame.viewport)
    normalized_x = (screen_point[0] - center_x) / focal_length
    normalized_y = (screen_point[1] - center_y) / focal_length
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    delta_z = end[2] - start[2]
    candidates = []
    x_denominator = normalized_x * delta_z - delta_x
    if abs(x_denominator) > 1e-9:
        candidates.append((abs(x_denominator), (start[0] - normalized_x * start[2]) / x_denominator))
    y_denominator = normalized_y * delta_z - delta_y
    if abs(y_denominator) > 1e-9:
        candidates.append((abs(y_denominator), (start[1] - normalized_y * start[2]) / y_denominator))
    if not candidates:
        depth = 0.5 * (start[2] + end[2])
        return depth if depth >= frame.camera.near_plane else None
    amount = max(candidates, key=lambda item: item[0])[1]
    amount = min(1.0, max(0.0, amount))
    depth = start[2] + delta_z * amount
    return depth if depth >= frame.camera.near_plane else None


class CpuRenderer3D:
    def __init__(self, sorter: RenderSorter | None = None) -> None:
        self.sorter = sorter or OverlapDepthSorter()
        self.depth_epsilon = 1e-5
        self._persistent_overlays: dict[object, PersistentOverlayState] = {}

    def render(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        scene: Scene3D,
        camera,
        viewport,
        persistent_overlay_target: dcg.DrawingList | None = None,
    ) -> RenderStats:
        clear_drawing_list(target)
        dcg.DrawRect(
            context,
            parent=target,
            pmin=(0.0, 0.0),
            pmax=(viewport.width, viewport.height),
            fill=scene.background,
            color=0,
            thickness=-1,
        )

        frame = FrameContext(camera=camera, viewport=viewport)
        pipeline = ProjectionPipeline(camera, viewport)
        packets = list(self._collect_packets(scene, frame))
        clipped_count = 0
        overlay_entries: list[ProjectedRenderEntry] = []
        background_entries: list[ProjectedRenderEntry] = []
        projected_entries: list[ProjectedRenderEntry] = []
        for stable_index, packet in enumerate(packets):
            entry = self._project_packet(packet, stable_index, frame, pipeline)
            if entry is None:
                clipped_count += 1
                continue
            if entry.kind == "stream":
                if entry.animation_projection is AnimationProjection.PERSISTENT_OVERLAY:
                    overlay_entries.append(entry)
                    continue
                if entry.animation_projection is AnimationProjection.PREPROJECTED_BACKGROUND:
                    background_entries.append(entry)
                    continue
            projected_entries.append(entry)

        sorted_result = self.sorter.sort(projected_entries, frame)
        emitted_count = 1
        for entry in background_entries:
            emitted_count += self._emit_entry(context, target, entry, frame, ())
        polygon_entries = tuple(entry for entry in sorted_result.entries if entry.kind == "polygon")
        for entry in sorted_result.entries:
            emitted_count += self._emit_entry(context, target, entry, frame, polygon_entries)
        if persistent_overlay_target is not None:
            self._sync_persistent_overlays(context, persistent_overlay_target, overlay_entries, frame)

        return RenderStats(
            packet_count=len(packets),
            clipped_count=clipped_count,
            projected_count=len(projected_entries),
            emitted_count=emitted_count,
            cycle_detected=sorted_result.cycle_detected,
        )

    def _collect_packets(
        self,
        scene: Scene3D,
        frame: FrameContext,
    ) -> Iterable[WorldRenderPacket]:
        for item in scene.iter_visible():
            yield from item.collect(frame)

    def _project_packet(
        self,
        packet: WorldRenderPacket,
        stable_index: int,
        frame: FrameContext,
        pipeline: ProjectionPipeline,
    ) -> ProjectedRenderEntry | None:
        if packet.kind == "stream":
            if packet.animation_projection is AnimationProjection.PERSISTENT_OVERLAY:
                if len(packet.points) != 1 or packet.world_size is None:
                    return None
                camera_point = frame.camera.world_to_camera(packet.points[0], frame.viewport)
                if camera_point[2] < frame.camera.near_plane:
                    return ProjectedRenderEntry(
                        kind="stream",
                        stable_index=stable_index,
                        average_depth=float("inf"),
                        points=(),
                        animation_projection=packet.animation_projection,
                        line_occluder=False,
                        stream_frame_count=packet.stream_frame_count,
                        stream_loop_seconds=packet.stream_loop_seconds,
                        stream_frame_builder=packet.stream_frame_builder,
                        cache_key=packet.cache_key,
                        visible=False,
                    )
                center = frame.camera.camera_to_screen(camera_point, frame.viewport)
                focal_length = frame.camera.focal_length(frame.viewport)
                scale_x = packet.world_size[0] * focal_length / camera_point[2]
                scale_y = packet.world_size[1] * focal_length / camera_point[2]
                visible = not (
                    center[0] + scale_x * 0.5 < 0.0
                    or center[0] - scale_x * 0.5 > frame.viewport.width
                    or center[1] + scale_y * 0.5 < 0.0
                    or center[1] - scale_y * 0.5 > frame.viewport.height
                )
                return ProjectedRenderEntry(
                    kind="stream",
                    stable_index=stable_index,
                    average_depth=camera_point[2],
                    points=(),
                    animation_projection=packet.animation_projection,
                    line_occluder=False,
                    stream_frame_count=packet.stream_frame_count,
                    stream_loop_seconds=packet.stream_loop_seconds,
                    stream_frame_builder=packet.stream_frame_builder,
                    cache_key=packet.cache_key,
                    overlay_origin=center,
                    overlay_scale=(scale_x, scale_y),
                    visible=visible,
                )
            if packet.animation_projection is AnimationProjection.PREPROJECTED_BACKGROUND:
                return ProjectedRenderEntry(
                    kind="stream",
                    stable_index=stable_index,
                    average_depth=0.0,
                    points=(),
                    animation_projection=packet.animation_projection,
                    line_occluder=False,
                    stream_frame_count=packet.stream_frame_count,
                    stream_loop_seconds=packet.stream_loop_seconds,
                    stream_frame_builder=packet.stream_frame_builder,
                    cache_key=packet.cache_key,
                )
            return None

        if packet.kind == "polygon":
            if (
                packet.cull_back_face
                and packet.normal is not None
                and not self._is_face_visible(packet, frame)
            ):
                return None
            image_material = packet.material if isinstance(packet.material, ImageMaterial) else None
            raw_camera_points = tuple(
                frame.camera.world_to_camera(point, frame.viewport)
                for point in packet.points
            )
            if any(point[2] < frame.camera.near_plane for point in raw_camera_points):
                raw_camera_points = ()
            complete_quad = (
                pipeline.project_complete_quad(packet.points)
                if image_material is not None and not packet.image_clip_to_viewport
                else None
            )
            projected = pipeline.project_polygon(packet.points)
            if projected is None:
                return None
            image_points: tuple[tuple[float, float], ...] = ()
            if image_material is not None and complete_quad is not None:
                points = complete_quad.points
                average_depth = complete_quad.average_depth
                material = image_material
            elif image_material is not None and packet.image_clip_to_viewport and len(raw_camera_points) == 4:
                points = projected.points
                average_depth = projected.average_depth
                material = image_material
                image_points = tuple(
                    frame.camera.camera_to_screen(point, frame.viewport)
                    for point in raw_camera_points
                )
            else:
                points = projected.points
                average_depth = projected.average_depth
                material = self._resolve_polygon_material(
                    replace(packet, material=image_material.fallback_material())
                    if image_material is not None
                    else packet,
                    frame,
                )
            return ProjectedRenderEntry(
                kind="polygon",
                stable_index=stable_index,
                average_depth=average_depth,
                points=points,
                camera_points=raw_camera_points or tuple(
                    frame.camera.world_to_camera(point, frame.viewport)
                    for point in packet.points
                ),
                material=material,
                animation_projection=packet.animation_projection,
                line_occluder=self._resolve_line_occluder(packet, material),
                image_points=image_points,
                image_clip_to_viewport=packet.image_clip_to_viewport,
                cache_key=packet.cache_key,
            )

        if packet.kind == "line":
            if len(packet.points) != 2:
                return None
            projected = pipeline.project_line(packet.points[0], packet.points[1])
            if projected is None:
                return None
            return ProjectedRenderEntry(
                kind="line",
                stable_index=stable_index,
                average_depth=projected.average_depth,
                points=(projected.p0, projected.p1),
                camera_points=projected.camera_points,
                material=packet.material,
                line_occluder=False,
            )

        if packet.kind == "text":
            if len(packet.points) != 1:
                return None
            camera_point = frame.camera.world_to_camera(packet.points[0], frame.viewport)
            if camera_point[2] < frame.camera.near_plane:
                return None
            screen = frame.camera.camera_to_screen(camera_point, frame.viewport)
            if not frame.viewport.contains(screen):
                return None
            apparent_scale = frame.camera.focal_length(frame.viewport) / camera_point[2]
            text_size = max(
                packet.text_min_size,
                min(packet.text_max_size, packet.text_size * apparent_scale),
            )
            return ProjectedRenderEntry(
                kind="text",
                stable_index=stable_index,
                average_depth=camera_point[2],
                points=(screen,),
                line_occluder=False,
                text=packet.text,
                text_size=text_size,
                text_color=packet.text_color,
            )

        return None

    def _is_face_visible(self, packet: WorldRenderPacket, frame: FrameContext) -> bool:
        if packet.normal is None or not packet.points:
            return True
        count = float(len(packet.points))
        center = (
            sum(point[0] for point in packet.points) / count,
            sum(point[1] for point in packet.points) / count,
            sum(point[2] for point in packet.points) / count,
        )
        eye_vector = (
            frame.eye[0] - center[0],
            frame.eye[1] - center[1],
            frame.eye[2] - center[2],
        )
        return (
            packet.normal[0] * eye_vector[0]
            + packet.normal[1] * eye_vector[1]
            + packet.normal[2] * eye_vector[2]
        ) > 1e-6

    def _resolve_polygon_material(
        self,
        packet: WorldRenderPacket,
        frame: FrameContext,
    ) -> SolidMaterial | None:
        if packet.material is None:
            return None
        material = packet.material
        if (
            isinstance(material, SolidMaterial)
            and material.fill is not None
            and material.shaded
            and packet.normal is not None
            and isinstance(material.fill, tuple)
        ):
            return replace(
                material,
                fill=shade_directional(material.fill, packet.normal, frame.light_direction),
            )
        if isinstance(material, SolidMaterial):
            return material
        return SolidMaterial(
            fill=material.fill,
            outline=material.outline,
            thickness=material.thickness,
            shaded=material.shaded,
            blend_mode=material.blend_mode,
            line_occluder=material.line_occluder,
        )

    def _resolve_line_occluder(
        self,
        packet: WorldRenderPacket,
        material: SolidMaterial | None,
    ) -> bool:
        if packet.line_occluder is not None:
            return packet.line_occluder
        if material is not None:
            return material.line_occluder
        return packet.kind == "polygon"

    def _emit_entry(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        frame: FrameContext,
        polygon_entries: tuple[ProjectedRenderEntry, ...],
    ) -> int:
        if entry.kind == "polygon":
            if isinstance(entry.material, AnimatedImageMaterial):
                return self._emit_animated_image(context, target, entry, frame)
            if isinstance(entry.material, ImageMaterial):
                return self._emit_image(context, target, entry, frame, entry.material.texture)
            fill = entry.material.fill if entry.material is not None else None
            outline = entry.material.outline if entry.material is not None else 0
            thickness = entry.material.thickness if entry.material is not None else -1
            dcg.DrawPolygon(
                context,
                parent=target,
                points=entry.points,
                fill=fill,
                color=outline if outline is not None else 0,
                thickness=thickness,
            )
            return 1

        if entry.kind == "stream":
            return self._emit_stream(context, target, entry, frame)

        if entry.kind == "line":
            color = 0
            thickness = -1
            if entry.material is not None:
                if entry.material.outline is not None:
                    color = entry.material.outline
                elif entry.material.fill is not None:
                    color = entry.material.fill
                thickness = entry.material.thickness
            visible_segments = self._visible_line_segments(entry, polygon_entries, frame)
            for start, end in visible_segments:
                dcg.DrawLine(
                    context,
                    parent=target,
                    p1=start,
                    p2=end,
                    color=color,
                    thickness=thickness,
                )
            return len(visible_segments)

        if entry.kind == "text":
            dcg.DrawText(
                context,
                parent=target,
                pos=entry.points[0],
                text=entry.text,
                size=-entry.text_size,
                color=entry.text_color,
            )
            return 1

        return 0

    def _emit_animated_image(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        frame: FrameContext,
    ) -> int:
        material = entry.material
        assert isinstance(material, AnimatedImageMaterial)
        stream_parent = self._stream_parent(context, target, entry, frame)
        stream = dcg.utils.DrawStream(context, parent=stream_parent)
        stream.time_modulus = material.loop_seconds
        for frame_index in range(len(material.frames)):
            with dcg.DrawingList(context) as drawing:
                self._emit_image(
                    context,
                    drawing,
                    entry,
                    frame,
                    material.frame_texture(frame_index),
                )
            stream.push(drawing, material.frame_end_time(frame_index))
        return 1

    def _emit_stream(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        frame: FrameContext,
    ) -> int:
        builder = entry.stream_frame_builder
        if builder is None or entry.stream_frame_count < 1 or entry.stream_loop_seconds <= 0.0:
            return 0
        stream = dcg.utils.DrawStream(context, parent=target)
        stream.time_modulus = entry.stream_loop_seconds
        frame_duration = entry.stream_loop_seconds / entry.stream_frame_count
        for frame_index in range(entry.stream_frame_count):
            with dcg.DrawingList(context) as drawing:
                builder(context, drawing, frame, frame_index)
            stream.push(drawing, (frame_index + 1) * frame_duration)
        return 1

    def _emit_image(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        frame: FrameContext,
        texture: object,
    ) -> int:
        if entry.image_clip_to_viewport and len(entry.image_points) == 4:
            parent = self._stream_parent(context, target, entry, frame)
            return self._emit_quad_image(context, parent, entry, texture)
        return self._emit_tessellated_image(context, target, entry, frame, texture)

    def _emit_tessellated_image(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        frame: FrameContext,
        texture: object,
    ) -> int:
        material = entry.material
        assert isinstance(material, ImageMaterial)
        if len(entry.camera_points) != 4:
            return 0
        emitted = 0
        for row in range(material.tessellation):
            v0 = row / material.tessellation
            v1 = (row + 1) / material.tessellation
            for column in range(material.tessellation):
                u0 = column / material.tessellation
                u1 = (column + 1) / material.tessellation
                camera_points = tuple(
                    _bilinear_quad(entry.camera_points, u, v)
                    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
                )
                screen_points = tuple(
                    frame.camera.camera_to_screen(point, frame.viewport)
                    for point in camera_points
                )
                uv_points = tuple(
                    _bilinear_quad(material.uv_coordinates, u, v)
                    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
                )
                dcg.DrawImage(
                    context,
                    parent=target,
                    texture=texture,
                    p1=screen_points[0],
                    p2=screen_points[1],
                    p3=screen_points[2],
                    p4=screen_points[3],
                    uv1=uv_points[0],
                    uv2=uv_points[1],
                    uv3=uv_points[2],
                    uv4=uv_points[3],
                )
                emitted += 1
        return emitted

    def _emit_quad_image(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        texture: object,
    ) -> int:
        material = entry.material
        assert isinstance(material, ImageMaterial)
        dcg.DrawImage(
            context,
            parent=target,
            texture=texture,
            p1=entry.image_points[0],
            p2=entry.image_points[1],
            p3=entry.image_points[2],
            p4=entry.image_points[3],
            uv1=material.uv_coordinates[0],
            uv2=material.uv_coordinates[1],
            uv3=material.uv_coordinates[2],
            uv4=material.uv_coordinates[3],
        )
        return 1

    def _stream_parent(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entry: ProjectedRenderEntry,
        frame: FrameContext,
    ) -> dcg.DrawingList:
        if not entry.image_clip_to_viewport:
            return target
        return dcg.DrawingClip(
            context,
            parent=target,
            pmin=(0.0, 0.0),
            pmax=(frame.viewport.width, frame.viewport.height),
            clip_rendering=True,
        )

    def _overlay_key(self, entry: ProjectedRenderEntry) -> object:
        cache_key = entry.cache_key
        if cache_key is None:
            return ("stable", entry.stable_index)
        try:
            hash(cache_key)
        except TypeError:
            return (type(cache_key), id(cache_key))
        return cache_key

    def _sync_persistent_overlays(
        self,
        context: dcg.Context,
        target: dcg.DrawingList,
        entries: Iterable[ProjectedRenderEntry],
        frame: FrameContext,
    ) -> None:
        seen_keys: set[object] = set()
        for entry in entries:
            key = self._overlay_key(entry)
            seen_keys.add(key)
            state = self._persistent_overlays.get(key)
            if state is None:
                transform = dcg.DrawingScale(context, parent=target, show=False)
                builder = entry.stream_frame_builder
                if builder is not None and entry.stream_frame_count > 0 and entry.stream_loop_seconds > 0.0:
                    stream = dcg.utils.DrawStream(context, parent=transform)
                    stream.time_modulus = entry.stream_loop_seconds
                    frame_duration = entry.stream_loop_seconds / entry.stream_frame_count
                    for frame_index in range(entry.stream_frame_count):
                        with dcg.DrawingList(context) as drawing:
                            builder(context, drawing, frame, frame_index)
                        stream.push(drawing, (frame_index + 1) * frame_duration)
                state = PersistentOverlayState(transform=transform)
                self._persistent_overlays[key] = state
            state.transform.show = entry.visible
            if entry.visible and entry.overlay_origin is not None:
                state.transform.origin = entry.overlay_origin
                state.transform.scales = entry.overlay_scale
        for key in list(self._persistent_overlays):
            if key in seen_keys:
                continue
            self._persistent_overlays[key].transform.delete_item()
            del self._persistent_overlays[key]

    def _visible_line_segments(
        self,
        entry: ProjectedRenderEntry,
        polygon_entries: tuple[ProjectedRenderEntry, ...],
        frame: FrameContext,
    ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        if len(entry.points) != 2 or len(entry.camera_points) != 2:
            return []

        parameters = [0.0, 1.0]
        line_start, line_end = entry.points
        line_bounds = (
            min(line_start[0], line_end[0]),
            min(line_start[1], line_end[1]),
            max(line_start[0], line_end[0]),
            max(line_start[1], line_end[1]),
        )
        candidate_polygons: list[ProjectedRenderEntry] = []
        for polygon in polygon_entries:
            if polygon is entry or len(polygon.points) < 3 or not polygon.line_occluder:
                continue
            polygon_bounds = (
                min(point[0] for point in polygon.points),
                min(point[1] for point in polygon.points),
                max(point[0] for point in polygon.points),
                max(point[1] for point in polygon.points),
            )
            if (
                line_bounds[2] < polygon_bounds[0]
                or line_bounds[0] > polygon_bounds[2]
                or line_bounds[3] < polygon_bounds[1]
                or line_bounds[1] > polygon_bounds[3]
            ):
                continue
            candidate_polygons.append(polygon)
            for index, edge_start in enumerate(polygon.points):
                edge_end = polygon.points[(index + 1) % len(polygon.points)]
                parameter = _segment_intersection_parameter(line_start, line_end, edge_start, edge_end)
                if parameter is not None:
                    parameters.append(parameter)

        if not candidate_polygons:
            return [(line_start, line_end)]

        parameters = sorted(parameters)
        unique_parameters: list[float] = []
        for parameter in parameters:
            if not unique_parameters or abs(parameter - unique_parameters[-1]) > 1e-6:
                unique_parameters.append(parameter)

        visible_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for start_amount, end_amount in zip(unique_parameters, unique_parameters[1:]):
            if end_amount - start_amount <= 1e-6:
                continue
            midpoint = _screen_lerp(line_start, line_end, 0.5 * (start_amount + end_amount))
            line_depth = _line_depth_at_screen_point(midpoint, entry.camera_points, frame)
            if line_depth is None:
                continue
            occluded = False
            for polygon in candidate_polygons:
                if not _point_in_polygon(midpoint, polygon.points):
                    continue
                polygon_depth = ray_plane_depth(midpoint, polygon.camera_points, frame)
                if polygon_depth is None:
                    continue
                if line_depth > polygon_depth + self.depth_epsilon:
                    occluded = True
                    break
            if occluded:
                continue
            visible_segments.append(
                (
                    _screen_lerp(line_start, line_end, start_amount),
                    _screen_lerp(line_start, line_end, end_amount),
                )
            )
        return visible_segments
