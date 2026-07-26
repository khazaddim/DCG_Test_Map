"""Full-screen perspective map with inclination, zoom, and rotation.

This extends demo 09 with a rotation transform in source space. World points
are first mapped through the camera and inclination-dependent depth extent,
then rotated around the viewport center, clipped, and projected.
"""

import math

import dearcygui as dcg


VIEW_W = 800
VIEW_H = 560
WORLD_W = 2200
WORLD_H = 1500
EDGE_BAND = 150
AVATAR_RADIUS = 14
MOVE_STEP = 12.0
START_X = WORLD_W * 0.5
START_Y = WORLD_H * 0.5
MAX_A = 0.49
CIRCLE_SEGMENTS = 24
ZOOM_MIN = 0.3
ZOOM_MAX = 4.0
GROUND_PAD = 50_000.0


def project_xy(x: float, y: float, a: float) -> tuple[float, float]:
    if a <= 0.0:
        return x, y
    u = x / VIEW_W
    v = y / VIEW_H
    denom = max(1e-4, 1.0 - 2.0 * a * v)
    sx = VIEW_W * ((1.0 - 2.0 * a) * u - a * v + a) / denom
    sy = VIEW_H * ((1.0 - 2.0 * a) * v) / denom
    return sx, sy


def depth_scale_at(y: float, a: float) -> float:
    if a <= 0.0:
        return 1.0
    v = y / VIEW_H
    return (1.0 - 2.0 * a) / (1.0 - 2.0 * a * v)


def depth_extent_at(a: float) -> float:
    return 1.0 / (1.0 - a)


def world_to_unrotated_source(wx: float, wy: float, cam_x: float,
                              cam_y: float, zoom: float,
                              a: float) -> tuple[float, float]:
    x = (wx - cam_x) * zoom
    base_y = (wy - cam_y) * zoom
    extent = depth_extent_at(a)
    y = VIEW_H - (VIEW_H - base_y) / extent
    return x, y


def rotate_source(x: float, y: float,
                  rotation_deg: float) -> tuple[float, float]:
    angle = math.radians(rotation_deg)
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    dx = x - VIEW_W * 0.5
    dy = y - VIEW_H * 0.5
    return (
        VIEW_W * 0.5 + cos_angle * dx - sin_angle * dy,
        VIEW_H * 0.5 + sin_angle * dx + cos_angle * dy,
    )


def world_to_source(wx: float, wy: float, cam_x: float, cam_y: float,
                    zoom: float, a: float,
                    rotation_deg: float) -> tuple[float, float]:
    x, y = world_to_unrotated_source(wx, wy, cam_x, cam_y, zoom, a)
    return rotate_source(x, y, rotation_deg)


def source_trapezoid_halfplanes(a: float):
    if a <= 0.0:
        top_left_x = 0.0
        top_right_x = VIEW_W
    else:
        top_left_x = -a * VIEW_W / (1.0 - 2.0 * a)
        top_right_x = (1.0 - a) * VIEW_W / (1.0 - 2.0 * a)
    height = float(VIEW_H)
    width = float(VIEW_W)
    return (
        (0.0, 1.0, 0.0),
        (0.0, -1.0, height),
        (height, top_left_x, -top_left_x * height),
        (-height, width - top_right_x, height * top_right_x),
    )


def clip_polygon_halfplanes(points, halfplanes):
    poly = list(points)
    for (coef_x, coef_y, constant) in halfplanes:
        if not poly:
            return []
        output = []
        previous = poly[-1]
        previous_distance = (coef_x * previous[0]
                             + coef_y * previous[1] + constant)
        for current in poly:
            current_distance = (coef_x * current[0]
                                + coef_y * current[1] + constant)
            if current_distance >= 0:
                if previous_distance < 0:
                    t = previous_distance / (previous_distance - current_distance)
                    output.append((
                        previous[0] + t * (current[0] - previous[0]),
                        previous[1] + t * (current[1] - previous[1]),
                    ))
                output.append(current)
            elif previous_distance >= 0:
                t = previous_distance / (previous_distance - current_distance)
                output.append((
                    previous[0] + t * (current[0] - previous[0]),
                    previous[1] + t * (current[1] - previous[1]),
                ))
            previous = current
            previous_distance = current_distance
        poly = output
    return poly


def clip_line_halfplanes(p0, p1, halfplanes):
    t_enter, t_leave = 0.0, 1.0
    for (coef_x, coef_y, constant) in halfplanes:
        distance_0 = coef_x * p0[0] + coef_y * p0[1] + constant
        distance_1 = coef_x * p1[0] + coef_y * p1[1] + constant
        delta = distance_1 - distance_0
        if abs(delta) < 1e-9:
            if distance_0 < 0:
                return None
            continue
        t = -distance_0 / delta
        if delta > 0:
            t_enter = max(t_enter, t)
        else:
            t_leave = min(t_leave, t)
        if t_enter > t_leave:
            return None
    if t_enter >= t_leave:
        return None
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    return (
        p0[0] + t_enter * dx,
        p0[1] + t_enter * dy,
        p0[0] + t_leave * dx,
        p0[1] + t_leave * dy,
    )


def inside_halfplanes(point, halfplanes) -> bool:
    return all(coef_x * point[0] + coef_y * point[1] + constant >= 0
               for (coef_x, coef_y, constant) in halfplanes)


class WorldModel:
    def __init__(self) -> None:
        self.rects: list = []
        self.lines: list = []
        self.circles: list = []
        self.texts: list = []


def build_world_model() -> WorldModel:
    model = WorldModel()
    model.rects.append((
        (-GROUND_PAD, -GROUND_PAD),
        (WORLD_W + GROUND_PAD, WORLD_H + GROUND_PAD),
        (36, 64, 44), 0, -1,
    ))
    for grid_x in range(0, WORLD_W + 1, 100):
        model.lines.append(((grid_x, 0), (grid_x, WORLD_H),
                            (55, 85, 62), -1))
    for grid_y in range(0, WORLD_H + 1, 100):
        model.lines.append(((0, grid_y), (WORLD_W, grid_y),
                            (55, 85, 62), -1))
    for grid_x in range(0, WORLD_W + 1, 200):
        for grid_y in range(0, WORLD_H + 1, 200):
            model.texts.append(((grid_x + 4, grid_y + 2),
                                f"{grid_x},{grid_y}", -12,
                                (120, 160, 130)))
    model.rects.append(((0, 620), (WORLD_W, 700),
                        (72, 112, 167), 0, -1))
    model.rects.append(((900, 0), (980, WORLD_H),
                        (120, 110, 90), 0, -1))
    landmarks = [
        (250, 300, (84, 130, 70), "forest"),
        (1700, 250, (84, 130, 70), "forest"),
        (1400, 1100, (140, 100, 70), "hills"),
        (400, 1200, (180, 160, 90), "fields"),
        (1900, 900, (180, 160, 90), "fields"),
    ]
    for center_x, center_y, color, name in landmarks:
        model.circles.append(((center_x, center_y), 140, color,
                              (20, 25, 20), -2))
        model.texts.append(((center_x - 25, center_y - 6), name, -14,
                            (20, 25, 20)))
    border = (240, 220, 120)
    model.lines.extend([
        ((0, 0), (WORLD_W, 0), border, -3),
        ((WORLD_W, 0), (WORLD_W, WORLD_H), border, -3),
        ((WORLD_W, WORLD_H), (0, WORLD_H), border, -3),
        ((0, WORLD_H), (0, 0), border, -3),
    ])
    return model


def circle_polygon(center_x: float, center_y: float, radius: float):
    return [
        (center_x + radius * math.cos(2 * math.pi * index / CIRCLE_SEGMENTS),
         center_y + radius * math.sin(2 * math.pi * index / CIRCLE_SEGMENTS))
        for index in range(CIRCLE_SEGMENTS)
    ]


def project_world_polygon(points, cam_x, cam_y, zoom, a, rotation_deg,
                          halfplanes):
    source_points = [
        world_to_source(world_x, world_y, cam_x, cam_y, zoom, a, rotation_deg)
        for world_x, world_y in points
    ]
    clipped = clip_polygon_halfplanes(source_points, halfplanes)
    if len(clipped) < 3:
        return None
    projected = [project_xy(x, y, a) for x, y in clipped]
    deduped = []
    for point in projected:
        if (not deduped
                or abs(point[0] - deduped[-1][0]) > 1e-3
                or abs(point[1] - deduped[-1][1]) > 1e-3):
            deduped.append(point)
    if (len(deduped) >= 2
            and abs(deduped[0][0] - deduped[-1][0]) < 1e-3
            and abs(deduped[0][1] - deduped[-1][1]) < 1e-3):
        deduped.pop()
    return deduped if len(deduped) >= 3 else None


def clear_layer(parent) -> None:
    for child in list(parent.children):
        child.delete_item()


def render_perspective(context: dcg.Context, parent: dcg.DrawingList,
                       model: WorldModel, cam_x: float, cam_y: float,
                       zoom: float, a: float, rotation_deg: float,
                       avatar_x: float, avatar_y: float) -> None:
    clear_layer(parent)
    halfplanes = source_trapezoid_halfplanes(a)

    for pmin, pmax, fill, edge, thickness in model.rects:
        corners = [pmin, (pmax[0], pmin[1]), pmax, (pmin[0], pmax[1])]
        projected = project_world_polygon(
            corners, cam_x, cam_y, zoom, a, rotation_deg, halfplanes)
        if projected is not None:
            dcg.DrawPolygon(context, parent=parent, points=projected,
                            fill=fill, color=edge, thickness=thickness)

    for p1, p2, color, thickness in model.lines:
        source_0 = world_to_source(*p1, cam_x, cam_y, zoom, a, rotation_deg)
        source_1 = world_to_source(*p2, cam_x, cam_y, zoom, a, rotation_deg)
        clipped = clip_line_halfplanes(source_0, source_1, halfplanes)
        if clipped is not None:
            screen_0 = project_xy(clipped[0], clipped[1], a)
            screen_1 = project_xy(clipped[2], clipped[3], a)
            dcg.DrawLine(context, parent=parent, p1=screen_0, p2=screen_1,
                         color=color, thickness=thickness)

    for center, radius, fill, edge, thickness in model.circles:
        projected = project_world_polygon(
            circle_polygon(*center, radius), cam_x, cam_y, zoom, a,
            rotation_deg, halfplanes)
        if projected is not None:
            dcg.DrawPolygon(context, parent=parent, points=projected,
                            fill=fill, color=edge, thickness=thickness)

    for position, text, size, color in model.texts:
        source = world_to_source(
            *position, cam_x, cam_y, zoom, a, rotation_deg)
        if not inside_halfplanes(source, halfplanes):
            continue
        unrotated_y = world_to_unrotated_source(
            *position, cam_x, cam_y, zoom, a)[1]
        screen = project_xy(*source, a)
        scale = depth_scale_at(unrotated_y, a) * zoom / depth_extent_at(a)
        dcg.DrawText(context, parent=parent, pos=screen, text=text,
                     size=-max(8.0, abs(size) * scale), color=color)

    body = project_world_polygon(
        circle_polygon(avatar_x, avatar_y, AVATAR_RADIUS),
        cam_x, cam_y, zoom, a, rotation_deg, halfplanes)
    if body is not None:
        dcg.DrawPolygon(context, parent=parent, points=body,
                        fill=(245, 205, 83), color=(30, 30, 35), thickness=-2)
        eye = project_world_polygon(
            circle_polygon(avatar_x, avatar_y - 3, AVATAR_RADIUS * 0.45),
            cam_x, cam_y, zoom, a, rotation_deg, halfplanes)
        if eye is not None:
            dcg.DrawPolygon(context, parent=parent, points=eye,
                            fill=(30, 30, 35), color=0, thickness=-1)


class PerspectiveRotationController:
    def __init__(self, context: dcg.Context, layer: dcg.DrawingList,
                 model: WorldModel, status: dcg.Text) -> None:
        self.context = context
        self.layer = layer
        self.model = model
        self.status = status
        self.zoom = 1.0
        self.angle_deg = 35.0
        self.rotation_deg = 0.0
        self.px = START_X
        self.py = START_Y
        self.cam_x = self._clamp_cam_x(self.px - VIEW_W * 0.5 / self.zoom)
        self.cam_y = self._clamp_cam_y(self.py - VIEW_H * 0.5 / self.zoom)
        self.repaint()

    def move_left(self, *_):  self._move(-MOVE_STEP, 0)
    def move_right(self, *_): self._move(+MOVE_STEP, 0)
    def move_up(self, *_):    self._move(0, -MOVE_STEP)
    def move_down(self, *_):  self._move(0, +MOVE_STEP)

    def set_angle(self, sender, target, value) -> None:
        self.angle_deg = float(sender.value)
        self.repaint()

    def set_rotation(self, sender, target, value) -> None:
        self.rotation_deg = float(sender.value)
        self.repaint()

    def set_zoom(self, sender, target, value) -> None:
        self.zoom = float(sender.value)
        self.cam_x = self._clamp_cam_x(self.px - VIEW_W * 0.5 / self.zoom)
        self.cam_y = self._clamp_cam_y(self.py - VIEW_H * 0.5 / self.zoom)
        self.repaint()

    def _move(self, dx: float, dy: float) -> None:
        self.px = max(AVATAR_RADIUS, min(WORLD_W - AVATAR_RADIUS,
                                        self.px + dx))
        self.py = max(AVATAR_RADIUS, min(WORLD_H - AVATAR_RADIUS,
                                        self.py + dy))
        a = self._a_from_angle()
        screen_x, screen_y = world_to_source(
            self.px, self.py, self.cam_x, self.cam_y, self.zoom, a,
            self.rotation_deg)
        correction_x = 0.0
        correction_y = 0.0
        if screen_x < EDGE_BAND:
            correction_x = EDGE_BAND - screen_x
        elif screen_x > VIEW_W - EDGE_BAND:
            correction_x = VIEW_W - EDGE_BAND - screen_x
        if screen_y < EDGE_BAND:
            correction_y = EDGE_BAND - screen_y
        elif screen_y > VIEW_H - EDGE_BAND:
            correction_y = VIEW_H - EDGE_BAND - screen_y

        angle = math.radians(self.rotation_deg)
        base_correction_x = (math.cos(angle) * correction_x
                             + math.sin(angle) * correction_y)
        base_correction_y = (-math.sin(angle) * correction_x
                             + math.cos(angle) * correction_y)
        self.cam_x -= base_correction_x / self.zoom
        self.cam_y -= (base_correction_y * depth_extent_at(a) / self.zoom)
        self.cam_x = self._clamp_cam_x(self.cam_x)
        self.cam_y = self._clamp_cam_y(self.cam_y)
        self.repaint()

    def _clamp_cam_x(self, value: float) -> float:
        maximum = max(0.0, WORLD_W - VIEW_W / self.zoom)
        return max(0.0, min(maximum, value))

    def _clamp_cam_y(self, value: float) -> float:
        maximum = max(0.0, WORLD_H - VIEW_H / self.zoom)
        return max(0.0, min(maximum, value))

    def _a_from_angle(self) -> float:
        return MAX_A * math.sin(math.radians(self.angle_deg))

    def repaint(self) -> None:
        a = self._a_from_angle()
        render_perspective(
            self.context, self.layer, self.model, self.cam_x, self.cam_y,
            self.zoom, a, self.rotation_deg, self.px, self.py)
        self.status.value = (
            f"avatar=({self.px:.0f},{self.py:.0f})  "
            f"camera=({self.cam_x:.0f},{self.cam_y:.0f})  "
            f"zoom={self.zoom:.2f}x  inclination={self.angle_deg:.1f} deg  "
            f"rotation={self.rotation_deg:.1f} deg  "
            f"depth={depth_extent_at(a):.2f}x"
        )


def build_ui(context: dcg.Context) -> None:
    model = build_world_model()
    with dcg.Window(context, label="Perspective map with rotation",
                    width=VIEW_W + 40, height=VIEW_H + 310) as window:
        dcg.Text(context, value="Arrow keys move the avatar.", wrap=VIEW_W)
        status = dcg.Text(context, value="")
        with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0),
                         pmax=(VIEW_W, VIEW_H), fill=(18, 22, 30),
                         color=0, thickness=-1)
            perspective_layer = dcg.DrawingList(context, parent=canvas)
            band_color = (245, 205, 83, 40)
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0),
                         pmax=(VIEW_W, EDGE_BAND), fill=band_color,
                         color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, VIEW_H - EDGE_BAND),
                         pmax=(VIEW_W, VIEW_H), fill=band_color,
                         color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas, pmin=(0, EDGE_BAND),
                         pmax=(EDGE_BAND, VIEW_H - EDGE_BAND),
                         fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(VIEW_W - EDGE_BAND, EDGE_BAND),
                         pmax=(VIEW_W, VIEW_H - EDGE_BAND),
                         fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(EDGE_BAND, EDGE_BAND),
                         pmax=(VIEW_W - EDGE_BAND, VIEW_H - EDGE_BAND),
                         color=(245, 205, 83, 120), thickness=-1)
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0),
                         pmax=(VIEW_W, VIEW_H), color=(110, 130, 160),
                         thickness=-2)

        controller = PerspectiveRotationController(
            context, perspective_layer, model, status)
        dcg.Slider(context, label="Inclination angle (degrees)",
                   min_value=0.0, max_value=80.0,
                   value=controller.angle_deg, width=VIEW_W,
                   callback=controller.set_angle)
        dcg.Slider(context, label="Map rotation (degrees)",
                   min_value=-180.0, max_value=180.0,
                   value=controller.rotation_deg, width=VIEW_W,
                   callback=controller.set_rotation)
        dcg.Slider(context, label="Zoom (x world units per viewport pixel)",
                   min_value=ZOOM_MIN, max_value=ZOOM_MAX,
                   value=controller.zoom, width=VIEW_W,
                   callback=controller.set_zoom)
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW,
                               callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW,
                               callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW,
                               callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW,
                               callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Perspective rotation",
        width=VIEW_W + 80, height=VIEW_H + 350,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()