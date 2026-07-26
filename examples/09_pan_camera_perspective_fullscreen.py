"""Pan-camera map with full-screen perspective (no dark wedges).

Follow-up to `07_pan_camera_perspective_tilt.py`. Same world, same controls,
same edge-band camera, same tilt + zoom sliders. The difference is the
projection geometry:

In `07`, the homography mapped the viewport rectangle (source) to a
trapezoid (output). The area of the viewport OUTSIDE that trapezoid had
nothing mapped to it, so the top corners showed up as dark wedges.

Here we flip the rendering convention: we treat the OUTPUT trapezoid as the
fixed viewport rectangle, and clip world content to the SOURCE trapezoid
(its preimage). Concretely:

    source trapezoid (in viewport-pixel space, BEFORE projection):
        bottom edge: (0, H)              -> (W, H)
        top edge:    (top_x_left, 0)     -> (top_x_right, 0)
    where
        top_x_left  = -a * W / (1 - 2a)   (<= 0)
        top_x_right = (1 - a) * W / (1 - 2a)  (>= W)

When this trapezoid is fed through the existing forward projection it lands
exactly on [0,W] x [0,H], filling the whole viewport. So we just:

  1. Clip every world polygon/line to that trapezoid (not the rect).
  2. Extend the ground rect well past the world bounds so the trapezoid
     always has content to clip — no green-edge cliffs even when the camera
     is near a world border.
    3. Increase the world-space depth represented by the source viewport as
         inclination rises, anchored at the near edge so more distant map appears.

Pattern reference: same as `07`. This is one extra step on top of Pattern 6
of the `dcg-animation-patterns` skill (edge-band pan camera).
"""

import math

import dearcygui as dcg


# --- Viewport ---------------------------------------------------------------
VIEW_W = 800
VIEW_H = 560

# --- World ------------------------------------------------------------------
WORLD_W = 2200
WORLD_H = 1500

# --- Edge-band follow camera ------------------------------------------------
EDGE_BAND = 150

# --- Avatar -----------------------------------------------------------------
AVATAR_RADIUS = 14
MOVE_STEP = 12.0
START_X = WORLD_W * 0.5
START_Y = WORLD_H * 0.5

# --- Perspective ------------------------------------------------------------
MAX_A = 0.49
CIRCLE_SEGMENTS = 24

# --- Zoom -------------------------------------------------------------------
ZOOM_MIN = 0.3
ZOOM_MAX = 4.0

# --- Extended ground --------------------------------------------------------
# Pad the ground rect well past the world so the source trapezoid is always
# covered, even at high tilt + low zoom + camera at a world edge.
GROUND_PAD = 50_000.0


# -----------------------------------------------------------------------------
# Perspective projection
# -----------------------------------------------------------------------------
def project_xy(x: float, y: float, a: float) -> tuple[float, float]:
    if a <= 0.0:
        return x, y
    u = x / VIEW_W
    v = y / VIEW_H
    denom = 1.0 - 2.0 * a * v
    if denom < 1e-4:
        denom = 1e-4
    sx = VIEW_W * ((1.0 - 2.0 * a) * u - a * v + a) / denom
    sy = VIEW_H * ((1.0 - 2.0 * a) * v) / denom
    return sx, sy


def depth_scale_at(y: float, a: float) -> float:
    if a <= 0.0:
        return 1.0
    v = y / VIEW_H
    return (1.0 - 2.0 * a) / (1.0 - 2.0 * a * v)


def depth_extent_at(a: float) -> float:
    """World-depth multiplier revealed by the perspective inclination."""
    return 1.0 / (1.0 - a)


def world_to_source(wx: float, wy: float, cam_x: float, cam_y: float,
                    zoom: float, a: float) -> tuple[float, float]:
    x = (wx - cam_x) * zoom
    base_y = (wy - cam_y) * zoom
    extent = depth_extent_at(a)
    y = VIEW_H - (VIEW_H - base_y) / extent
    return x, y


# -----------------------------------------------------------------------------
# Source-trapezoid half-planes (in viewport-pixel space)
# -----------------------------------------------------------------------------
def source_trapezoid_halfplanes(a: float):
    """Return four (A, B, C) such that A*x + B*y + C >= 0 means 'inside'.

    The trapezoid is exactly the preimage of the viewport rect under
    `project_xy(., ., a)`. At a = 0 it degenerates to the viewport rect.
    """
    if a <= 0.0:
        top_left_x = 0.0
        top_right_x = VIEW_W
    else:
        top_left_x = -a * VIEW_W / (1.0 - 2.0 * a)
        top_right_x = (1.0 - a) * VIEW_W / (1.0 - 2.0 * a)
    H = float(VIEW_H)
    W = float(VIEW_W)
    return (
        (0.0,  1.0, 0.0),                           # top:    y >= 0
        (0.0, -1.0, H),                             # bottom: y <= H
        (H,    top_left_x,   -top_left_x * H),      # left slope
        (-H,   W - top_right_x, H * top_right_x),   # right slope
    )


# -----------------------------------------------------------------------------
# Convex clipping (Sutherland-Hodgman / Cyrus-Beck against the trapezoid)
# -----------------------------------------------------------------------------
def clip_polygon_halfplanes(points, halfplanes):
    """Clip a polygon to the intersection of the given half-planes."""
    poly = list(points)
    for (A, B, C) in halfplanes:
        if not poly:
            return []
        out = []
        prev = poly[-1]
        prev_d = A * prev[0] + B * prev[1] + C
        for cur in poly:
            cur_d = A * cur[0] + B * cur[1] + C
            if cur_d >= 0:
                if prev_d < 0:
                    t = prev_d / (prev_d - cur_d)
                    out.append((prev[0] + t * (cur[0] - prev[0]),
                                prev[1] + t * (cur[1] - prev[1])))
                out.append(cur)
            elif prev_d >= 0:
                t = prev_d / (prev_d - cur_d)
                out.append((prev[0] + t * (cur[0] - prev[0]),
                            prev[1] + t * (cur[1] - prev[1])))
            prev, prev_d = cur, cur_d
        poly = out
    return poly


def clip_line_halfplanes(p0, p1, halfplanes):
    """Clip a segment to the convex region defined by the half-planes."""
    t_enter, t_leave = 0.0, 1.0
    for (A, B, C) in halfplanes:
        d0 = A * p0[0] + B * p0[1] + C
        d1 = A * p1[0] + B * p1[1] + C
        delta = d1 - d0
        if abs(delta) < 1e-9:
            if d0 < 0:
                return None
            continue
        t = -d0 / delta
        if delta > 0:
            if t > t_enter:
                t_enter = t
        else:
            if t < t_leave:
                t_leave = t
        if t_enter > t_leave:
            return None
    if t_enter >= t_leave:
        return None
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    return (p0[0] + t_enter * dx, p0[1] + t_enter * dy,
            p0[0] + t_leave * dx, p0[1] + t_leave * dy)


def inside_halfplanes(p, halfplanes) -> bool:
    for (A, B, C) in halfplanes:
        if A * p[0] + B * p[1] + C < 0:
            return False
    return True


# -----------------------------------------------------------------------------
# World model
# -----------------------------------------------------------------------------
class WorldModel:
    def __init__(self) -> None:
        self.rects: list = []
        self.lines: list = []
        self.circles: list = []
        self.texts: list = []


def build_world_model() -> WorldModel:
    m = WorldModel()
    # Extended ground — large enough that the source trapezoid always has
    # something to clip to, regardless of pan/tilt/zoom.
    m.rects.append((
        (-GROUND_PAD, -GROUND_PAD),
        (WORLD_W + GROUND_PAD, WORLD_H + GROUND_PAD),
        (36, 64, 44), 0, -1,
    ))
    # Grid (only inside the actual world)
    step = 100
    for gx in range(0, WORLD_W + 1, step):
        m.lines.append(((gx, 0), (gx, WORLD_H), (55, 85, 62), -1))
    for gy in range(0, WORLD_H + 1, step):
        m.lines.append(((0, gy), (WORLD_W, gy), (55, 85, 62), -1))
    # Coordinate labels
    for gx in range(0, WORLD_W + 1, 200):
        for gy in range(0, WORLD_H + 1, 200):
            m.texts.append(((gx + 4, gy + 2), f"{gx},{gy}", -12, (120, 160, 130)))
    # River
    m.rects.append(((0, 620), (WORLD_W, 700), (72, 112, 167), 0, -1))
    # Road
    m.rects.append(((900, 0), (980, WORLD_H), (120, 110, 90), 0, -1))
    # Landmarks
    landmarks = [
        (250, 300, (84, 130, 70), "forest"),
        (1700, 250, (84, 130, 70), "forest"),
        (1400, 1100, (140, 100, 70), "hills"),
        (400, 1200, (180, 160, 90), "fields"),
        (1900, 900, (180, 160, 90), "fields"),
    ]
    for cx, cy, color, name in landmarks:
        m.circles.append(((cx, cy), 140, color, (20, 25, 20), -2))
        m.texts.append(((cx - 25, cy - 6), name, -14, (20, 25, 20)))
    # World border (still drawn so the user can see where the mapped area ends)
    border = (240, 220, 120)
    m.lines.append(((0, 0), (WORLD_W, 0), border, -3))
    m.lines.append(((WORLD_W, 0), (WORLD_W, WORLD_H), border, -3))
    m.lines.append(((WORLD_W, WORLD_H), (0, WORLD_H), border, -3))
    m.lines.append(((0, WORLD_H), (0, 0), border, -3))
    return m


# -----------------------------------------------------------------------------
# Renderer
# -----------------------------------------------------------------------------
def _circle_polygon(cx: float, cy: float, r: float, n: int = CIRCLE_SEGMENTS):
    return [
        (cx + r * math.cos(2 * math.pi * i / n),
         cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _project_world_polygon(pts, cam_x, cam_y, zoom, a, halfplanes):
    view_pts = [world_to_source(wx, wy, cam_x, cam_y, zoom, a)
                for (wx, wy) in pts]
    clipped = clip_polygon_halfplanes(view_pts, halfplanes)
    if len(clipped) < 3:
        return None
    proj = [project_xy(x, y, a) for (x, y) in clipped]
    deduped = []
    for p in proj:
        if (not deduped
                or abs(p[0] - deduped[-1][0]) > 1e-3
                or abs(p[1] - deduped[-1][1]) > 1e-3):
            deduped.append(p)
    if (len(deduped) >= 2
            and abs(deduped[0][0] - deduped[-1][0]) < 1e-3
            and abs(deduped[0][1] - deduped[-1][1]) < 1e-3):
        deduped.pop()
    if len(deduped) < 3:
        return None
    return deduped


def _clear(parent) -> None:
    for child in list(parent.children):
        child.delete_item()


def render_perspective(context: dcg.Context, parent: dcg.DrawingList,
                       model: WorldModel,
                       cam_x: float, cam_y: float, zoom: float, a: float,
                       avatar_x: float, avatar_y: float) -> None:
    _clear(parent)
    halfplanes = source_trapezoid_halfplanes(a)

    for (pmin, pmax, fill, edge, thickness) in model.rects:
        corners = [
            (pmin[0], pmin[1]),
            (pmax[0], pmin[1]),
            (pmax[0], pmax[1]),
            (pmin[0], pmax[1]),
        ]
        proj = _project_world_polygon(corners, cam_x, cam_y, zoom, a, halfplanes)
        if proj is None:
            continue
        dcg.DrawPolygon(context, parent=parent, points=proj,
                        fill=fill, color=edge, thickness=thickness)

    for (p1, p2, color, thickness) in model.lines:
        a0 = world_to_source(*p1, cam_x, cam_y, zoom, a)
        a1 = world_to_source(*p2, cam_x, cam_y, zoom, a)
        clipped = clip_line_halfplanes(a0, a1, halfplanes)
        if clipped is None:
            continue
        sx0, sy0 = project_xy(clipped[0], clipped[1], a)
        sx1, sy1 = project_xy(clipped[2], clipped[3], a)
        dcg.DrawLine(context, parent=parent, p1=(sx0, sy0), p2=(sx1, sy1),
                     color=color, thickness=thickness)

    for (center, r, fill, edge, thickness) in model.circles:
        proj = _project_world_polygon(_circle_polygon(*center, r),
                                      cam_x, cam_y, zoom, a, halfplanes)
        if proj is None:
            continue
        dcg.DrawPolygon(context, parent=parent, points=proj,
                        fill=fill, color=edge, thickness=thickness)

    for (pos, text, size, color) in model.texts:
        vx, vy = world_to_source(*pos, cam_x, cam_y, zoom, a)
        if not inside_halfplanes((vx, vy), halfplanes):
            continue
        sx, sy = project_xy(vx, vy, a)
        scale = depth_scale_at(vy, a) * zoom / depth_extent_at(a)
        new_size = -max(8.0, abs(size) * scale)
        dcg.DrawText(context, parent=parent, pos=(sx, sy),
                     text=text, size=new_size, color=color)

    body = _project_world_polygon(
        _circle_polygon(avatar_x, avatar_y, AVATAR_RADIUS),
        cam_x, cam_y, zoom, a, halfplanes)
    if body is not None:
        dcg.DrawPolygon(context, parent=parent, points=body,
                        fill=(245, 205, 83), color=(30, 30, 35), thickness=-2)
        eye = _project_world_polygon(
            _circle_polygon(avatar_x, avatar_y - 3, AVATAR_RADIUS * 0.45),
            cam_x, cam_y, zoom, a, halfplanes)
        if eye is not None:
            dcg.DrawPolygon(context, parent=parent, points=eye,
                            fill=(30, 30, 35), color=0, thickness=-1)


# -----------------------------------------------------------------------------
# Controller (identical to `07` aside from threading the new clip through)
# -----------------------------------------------------------------------------
class PerspectivePanController:
    def __init__(self, context: dcg.Context, layer: dcg.DrawingList,
                 model: WorldModel, status: dcg.Text) -> None:
        self.context = context
        self.layer = layer
        self.model = model
        self.status = status

        self.zoom = 1.0
        self.px = START_X
        self.py = START_Y
        self.cam_x = self._clamp_cam_x(self.px - VIEW_W * 0.5 / self.zoom)
        self.cam_y = self._clamp_cam_y(self.py - VIEW_H * 0.5 / self.zoom)
        self.angle_deg = 35.0
        self.repaint()

    def move_left(self, *_):  self._move(-MOVE_STEP, 0)
    def move_right(self, *_): self._move(+MOVE_STEP, 0)
    def move_up(self, *_):    self._move(0, -MOVE_STEP)
    def move_down(self, *_):  self._move(0, +MOVE_STEP)

    def set_angle(self, sender, target, value) -> None:
        self.angle_deg = float(sender.value)
        self.repaint()

    def set_zoom(self, sender, target, value) -> None:
        self.zoom = float(sender.value)
        self.cam_x = self._clamp_cam_x(self.px - VIEW_W * 0.5 / self.zoom)
        self.cam_y = self._clamp_cam_y(self.py - VIEW_H * 0.5 / self.zoom)
        self.repaint()

    def _move(self, dx: float, dy: float) -> None:
        self.px = max(AVATAR_RADIUS, min(WORLD_W - AVATAR_RADIUS, self.px + dx))
        self.py = max(AVATAR_RADIUS, min(WORLD_H - AVATAR_RADIUS, self.py + dy))

        a = self._a_from_angle()
        screen_x, screen_y = world_to_source(
            self.px, self.py, self.cam_x, self.cam_y, self.zoom, a)
        if screen_x < EDGE_BAND:
            self.cam_x -= (EDGE_BAND - screen_x) / self.zoom
        elif screen_x > VIEW_W - EDGE_BAND:
            self.cam_x += (screen_x - (VIEW_W - EDGE_BAND)) / self.zoom
        if screen_y < EDGE_BAND:
            self.cam_y -= ((EDGE_BAND - screen_y)
                           * depth_extent_at(a) / self.zoom)
        elif screen_y > VIEW_H - EDGE_BAND:
            self.cam_y += ((screen_y - (VIEW_H - EDGE_BAND))
                           * depth_extent_at(a) / self.zoom)

        self.cam_x = self._clamp_cam_x(self.cam_x)
        self.cam_y = self._clamp_cam_y(self.cam_y)
        self.repaint()

    def _clamp_cam_x(self, x: float) -> float:
        return max(0.0, min(max(0.0, WORLD_W - VIEW_W / self.zoom), x))

    def _clamp_cam_y(self, y: float) -> float:
        return max(0.0, min(max(0.0, WORLD_H - VIEW_H / self.zoom), y))

    def _a_from_angle(self) -> float:
        return MAX_A * math.sin(math.radians(self.angle_deg))

    def repaint(self) -> None:
        a = self._a_from_angle()
        render_perspective(self.context, self.layer, self.model,
                           self.cam_x, self.cam_y, self.zoom, a,
                           self.px, self.py)
        self.status.value = (
            f"avatar=({self.px:.0f},{self.py:.0f})  "
            f"camera=({self.cam_x:.0f},{self.cam_y:.0f})  "
            f"zoom={self.zoom:.2f}x  "
            f"angle={self.angle_deg:.1f} deg  "
            f"depth={depth_extent_at(a):.2f}x  "
            f"a={a:.3f}"
        )


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
def build_ui(context: dcg.Context) -> None:
    model = build_world_model()

    with dcg.Window(context, label="Pan camera + full-screen perspective",
                    width=VIEW_W + 40, height=VIEW_H + 260) as window:
        dcg.Text(
            context,
            value="Arrow keys move the avatar; sliders tilt and zoom. Unlike the "
                  "previous example, world content fills the whole viewport — no "
                "dark corner wedges. Increasing inclination reveals more map "
                "toward the horizon. The mapped world area is still bordered "
                "by the yellow rectangle.",
            wrap=VIEW_W,
        )
        status = dcg.Text(context, value="")

        with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, VIEW_H),
                         fill=(18, 22, 30), color=0, thickness=-1)

            persp_layer = dcg.DrawingList(context, parent=canvas)

            # HUD overlay: edge band + dead-zone outline + viewport border
            band_color = (245, 205, 83, 40)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, EDGE_BAND),
                         fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, VIEW_H - EDGE_BAND), pmax=(VIEW_W, VIEW_H),
                         fill=band_color, color=0, thickness=-1)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, EDGE_BAND),
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
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, VIEW_H),
                         color=(110, 130, 160), thickness=-2)

        controller = PerspectivePanController(context, persp_layer, model, status)

        dcg.Slider(context, label="Inclination angle (degrees)",
                   min_value=0.0, max_value=80.0,
                   value=controller.angle_deg,
                   width=VIEW_W,
                   callback=controller.set_angle)

        dcg.Slider(context, label="Zoom (x world units per viewport pixel)",
                   min_value=ZOOM_MIN, max_value=ZOOM_MAX,
                   value=controller.zoom,
                   width=VIEW_W,
                   callback=controller.set_zoom)

        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW,  callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW,    callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW,  callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Full-screen perspective tilt",
        width=VIEW_W + 80, height=VIEW_H + 300,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
