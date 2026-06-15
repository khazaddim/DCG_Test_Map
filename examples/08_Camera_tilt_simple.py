"""Pan-camera map with a runtime-adjustable perspective tilt.

Builds on `06_pan_camera_edge_band.py`: same world, same avatar, same
edge-band follow camera. Adds a perspective transform that runs AFTER the
camera pan so the map appears tilted away from the viewer — parallel grid
lines on the world plane converge toward a vanishing point above the top of
the viewport. A slider changes the inclination angle at runtime.

How the perspective works
-------------------------
DCG's `DrawingScale` is affine only, so it can't fake a vanishing point on
its own. Instead we apply a true projective homography in Python before the
draw items are created. The transform maps the viewport rectangle to a
symmetric trapezoid:

    bottom corners stay at (0, VIEW_H) and (VIEW_W, VIEW_H)   (nearest to camera)
    top corners pull inward to ((1-w')/2, 0) and ((1+w')/2, 0) (farthest from camera)

For a single tilt parameter `a` in [0, 0.5) and viewport-local coords
(u = x/W, v = y/H), the homography reduces to

    sx = W * ((1-2a)*u - a*v + a) / (1 - 2a*v)
    sy = H * ((1-2a)*v)           / (1 - 2a*v)

A homography preserves straight lines, so grid lines stay straight and
genuinely converge. Circles, however, become ellipses, so the avatar and
landmark disks are approximated by small polygons.

Render pipeline
---------------
Because the transform is non-affine, we can't just set `DrawingScale.origin`
on a single subtree. The world is kept as plain Python data
(`WorldModel`) and the visible draw items are rebuilt every time the avatar
moves OR the slider changes. The rebuild flow is:

    world_xy  --(camera pan)-->  viewport_xy  --(perspective)-->  pixel_xy
    then create DrawLine / DrawPolygon / DrawText under a pixel-space layer.

HUD overlays (the edge band and viewport border) stay in pixel space so
they remain undistorted regardless of tilt.

Pattern reference: see the `dcg-animation-patterns` skill — this file uses
Pattern 6 (edge-band pan camera) plus a custom rebuild step driven by a
slider callback.
"""

import math

import dearcygui as dcg


# --- Viewport (visible area) -------------------------------------------------
VIEW_W = 800
VIEW_H = 560

# --- World (full map, larger than viewport so panning is meaningful) ---------
WORLD_W = 2200
WORLD_H = 1500

# --- Edge-band follow camera -------------------------------------------------
EDGE_BAND = 150

# --- Avatar ------------------------------------------------------------------
AVATAR_RADIUS = 14
MOVE_STEP = 12.0
START_X = WORLD_W * 0.5
START_Y = WORLD_H * 0.5

# --- Perspective -------------------------------------------------------------
# Slider exposes an inclination angle in degrees. It is mapped to the
# homography parameter `a` via a = MAX_A * sin(angle). MAX_A stays just under
# 0.5 because at a = 0.5 the top edge of the trapezoid collapses to a point.
MAX_A = 0.49
CIRCLE_SEGMENTS = 24


# -----------------------------------------------------------------------------
# Perspective projection (viewport rect -> trapezoid)
# -----------------------------------------------------------------------------
def project_xy(x: float, y: float, a: float) -> tuple[float, float]:
    """Map a viewport-pixel point through the perspective homography.

    `a` is the tilt parameter in [0, 0.5). a = 0 returns (x, y) unchanged
    (the original top-down view).
    """
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
    """Linear shrink factor at viewport row y (used to scale text size with depth)."""
    if a <= 0.0:
        return 1.0
    v = y / VIEW_H
    return (1.0 - 2.0 * a) / (1.0 - 2.0 * a * v)


# -----------------------------------------------------------------------------
# Clipping to the viewport rect (in viewport-pixel space, BEFORE projection)
# -----------------------------------------------------------------------------
def clip_line(x0: float, y0: float, x1: float, y1: float):
    """Clip segment to (0,0)-(VIEW_W, VIEW_H). Returns (x0', y0', x1', y1') or None."""
    dx = x1 - x0
    dy = y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0, VIEW_W - x0, y0, VIEW_H - y0)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
        else:
            t = qi / pi
            if pi < 0:
                if t > u2:
                    return None
                if t > u1:
                    u1 = t
            else:
                if t < u1:
                    return None
                if t < u2:
                    u2 = t
    return (x0 + u1 * dx, y0 + u1 * dy, x0 + u2 * dx, y0 + u2 * dy)


def clip_polygon(points):
    """Sutherland-Hodgman clip a polygon to the viewport rect.

    Returns a list of (x, y) (possibly empty if fully outside). The input
    polygon must be in viewport-pixel space (NOT world space). Each clip
    against a single edge inserts the true intersection at the boundary,
    so the output never contains the degenerate vertex pile-ups that an
    independent per-vertex clamp would produce.
    """
    # Edges as (inside_test, intersect): clip against x=0, x=VIEW_W, y=0, y=VIEW_H.
    def clip_against(poly, inside, intersect):
        out = []
        n = len(poly)
        if n == 0:
            return out
        prev = poly[-1]
        prev_in = inside(prev)
        for cur in poly:
            cur_in = inside(cur)
            if cur_in:
                if not prev_in:
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif prev_in:
                out.append(intersect(prev, cur))
            prev, prev_in = cur, cur_in
        return out

    def isect(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    # left:   x >= 0
    poly = clip_against(
        list(points),
        lambda p: p[0] >= 0.0,
        lambda a, b: isect(a, b, (0.0 - a[0]) / (b[0] - a[0])),
    )
    # right:  x <= VIEW_W
    poly = clip_against(
        poly,
        lambda p: p[0] <= VIEW_W,
        lambda a, b: isect(a, b, (VIEW_W - a[0]) / (b[0] - a[0])),
    )
    # top:    y >= 0
    poly = clip_against(
        poly,
        lambda p: p[1] >= 0.0,
        lambda a, b: isect(a, b, (0.0 - a[1]) / (b[1] - a[1])),
    )
    # bottom: y <= VIEW_H
    poly = clip_against(
        poly,
        lambda p: p[1] <= VIEW_H,
        lambda a, b: isect(a, b, (VIEW_H - a[1]) / (b[1] - a[1])),
    )
    return poly


# -----------------------------------------------------------------------------
# World model (plain data, in WORLD coordinates — never touches DCG nodes)
# -----------------------------------------------------------------------------
class WorldModel:
    def __init__(self) -> None:
        self.rects: list = []    # (pmin, pmax, fill_rgb, edge_rgb, thickness)
        self.lines: list = []    # (p1, p2, color, thickness)
        self.circles: list = []  # (center, radius, fill, edge, thickness)
        self.texts: list = []    # (pos, text, size, color)


def build_world_model() -> WorldModel:
    m = WorldModel()
    # Ground
    m.rects.append(((0, 0), (WORLD_W, WORLD_H), (36, 64, 44), 0, -1))
    # Grid so the perspective convergence is obvious
    step = 100
    for gx in range(0, WORLD_W + 1, step):
        m.lines.append(((gx, 0), (gx, WORLD_H), (55, 85, 62), -1))
    for gy in range(0, WORLD_H + 1, step):
        m.lines.append(((0, gy), (WORLD_W, gy), (55, 85, 62), -1))
    # Coordinate labels at every 200 units
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
    # World border (as four line segments so clipping is straightforward)
    border = (240, 220, 120)
    m.lines.append(((0, 0), (WORLD_W, 0), border, -3))
    m.lines.append(((WORLD_W, 0), (WORLD_W, WORLD_H), border, -3))
    m.lines.append(((WORLD_W, WORLD_H), (0, WORLD_H), border, -3))
    m.lines.append(((0, WORLD_H), (0, 0), border, -3))
    return m


# -----------------------------------------------------------------------------
# Renderer: world + camera + tilt -> draw items in the pixel-space layer
# -----------------------------------------------------------------------------
def _circle_polygon(cx: float, cy: float, r: float, n: int = CIRCLE_SEGMENTS):
    return [
        (cx + r * math.cos(2 * math.pi * i / n),
         cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _project_world_polygon(pts, cam_x, cam_y, a):
    """World-space polygon -> projected pixel polygon, clipped to the viewport.

    Returns a list of (x, y) of length >= 3, or None if the polygon is fully
    outside the viewport (or collapses to a degenerate shape after clipping).
    """
    # Move to viewport-pixel space, then clip BEFORE projecting. Clipping in
    # the un-projected rect keeps the math simple and, more importantly,
    # produces real intersection vertices instead of pile-ups at corners
    # (which is what crashed DCG's polygon triangulator).
    view_pts = [(wx - cam_x, wy - cam_y) for (wx, wy) in pts]
    clipped = clip_polygon(view_pts)
    if len(clipped) < 3:
        return None
    proj = [project_xy(x, y, a) for (x, y) in clipped]
    # Drop near-duplicate consecutive vertices that the projection can produce
    # near the vanishing line; DCG's triangulator rejects degenerate polygons.
    deduped = []
    for p in proj:
        if not deduped or abs(p[0] - deduped[-1][0]) > 1e-3 or abs(p[1] - deduped[-1][1]) > 1e-3:
            deduped.append(p)
    if len(deduped) >= 2 and abs(deduped[0][0] - deduped[-1][0]) < 1e-3 and abs(deduped[0][1] - deduped[-1][1]) < 1e-3:
        deduped.pop()
    if len(deduped) < 3:
        return None
    return deduped


def _clear(parent) -> None:
    for child in list(parent.children):
        child.delete_item()


def render_perspective(context: dcg.Context, parent: dcg.DrawingList,
                       model: WorldModel,
                       cam_x: float, cam_y: float, a: float,
                       avatar_x: float, avatar_y: float) -> None:
    """Rebuild `parent`'s draw items so the world is drawn under perspective."""
    _clear(parent)

    # Rectangles -> projected quadrilaterals
    for (pmin, pmax, fill, edge, thickness) in model.rects:
        corners = [
            (pmin[0], pmin[1]),
            (pmax[0], pmin[1]),
            (pmax[0], pmax[1]),
            (pmin[0], pmax[1]),
        ]
        proj = _project_world_polygon(corners, cam_x, cam_y, a)
        if proj is None:
            continue
        dcg.DrawPolygon(context, parent=parent, points=proj,
                        fill=fill, color=edge, thickness=thickness)

    # Lines -> clip in viewport space, then project each endpoint
    for (p1, p2, color, thickness) in model.lines:
        vx0 = p1[0] - cam_x
        vy0 = p1[1] - cam_y
        vx1 = p2[0] - cam_x
        vy1 = p2[1] - cam_y
        clipped = clip_line(vx0, vy0, vx1, vy1)
        if clipped is None:
            continue
        sx0, sy0 = project_xy(clipped[0], clipped[1], a)
        sx1, sy1 = project_xy(clipped[2], clipped[3], a)
        dcg.DrawLine(context, parent=parent, p1=(sx0, sy0), p2=(sx1, sy1),
                     color=color, thickness=thickness)

    # Circles -> polygon approximation, projected
    for (center, r, fill, edge, thickness) in model.circles:
        proj = _project_world_polygon(_circle_polygon(*center, r),
                                      cam_x, cam_y, a)
        if proj is None:
            continue
        dcg.DrawPolygon(context, parent=parent, points=proj,
                        fill=fill, color=edge, thickness=thickness)

    # Text -> project anchor, scale glyph size with depth
    for (pos, text, size, color) in model.texts:
        vx, vy = pos[0] - cam_x, pos[1] - cam_y
        if not (0.0 <= vx <= VIEW_W and 0.0 <= vy <= VIEW_H):
            continue
        sx, sy = project_xy(vx, vy, a)
        scale = depth_scale_at(vy, a)
        new_size = -max(8.0, abs(size) * scale)
        dcg.DrawText(context, parent=parent, pos=(sx, sy),
                     text=text, size=new_size, color=color)

    # Avatar (drawn last so it sits on top of everything else)
    body = _project_world_polygon(
        _circle_polygon(avatar_x, avatar_y, AVATAR_RADIUS), cam_x, cam_y, a)
    if body is not None:
        dcg.DrawPolygon(context, parent=parent, points=body,
                        fill=(245, 205, 83), color=(30, 30, 35), thickness=-2)
        eye = _project_world_polygon(
            _circle_polygon(avatar_x, avatar_y - 3, AVATAR_RADIUS * 0.45),
            cam_x, cam_y, a)
        if eye is not None:
            dcg.DrawPolygon(context, parent=parent, points=eye,
                            fill=(30, 30, 35), color=0, thickness=-1)


# -----------------------------------------------------------------------------
# Controller: edge-band camera + tilt slider, both drive a repaint
# -----------------------------------------------------------------------------
class PerspectivePanController:
    def __init__(self, context: dcg.Context, layer: dcg.DrawingList,
                 model: WorldModel, status: dcg.Text) -> None:
        self.context = context
        self.layer = layer
        self.model = model
        self.status = status

        self.px = START_X
        self.py = START_Y
        self.cam_x = self._clamp_cam_x(self.px - VIEW_W * 0.5)
        self.cam_y = self._clamp_cam_y(self.py - VIEW_H * 0.5)
        self.angle_deg = 35.0  # initial inclination
        self.repaint()

    # --- key handlers ---------------------------------------------------
    def move_left(self, *_):  self._move(-MOVE_STEP, 0)
    def move_right(self, *_): self._move(+MOVE_STEP, 0)
    def move_up(self, *_):    self._move(0, -MOVE_STEP)
    def move_down(self, *_):  self._move(0, +MOVE_STEP)

    # --- slider callback ------------------------------------------------
    def set_angle(self, sender, target, value) -> None:
        self.angle_deg = float(sender.value)
        self.repaint()

    # --- internals ------------------------------------------------------
    def _move(self, dx: float, dy: float) -> None:
        self.px = max(AVATAR_RADIUS, min(WORLD_W - AVATAR_RADIUS, self.px + dx))
        self.py = max(AVATAR_RADIUS, min(WORLD_H - AVATAR_RADIUS, self.py + dy))

        screen_x = self.px - self.cam_x
        screen_y = self.py - self.cam_y
        if screen_x < EDGE_BAND:
            self.cam_x -= (EDGE_BAND - screen_x)
        elif screen_x > VIEW_W - EDGE_BAND:
            self.cam_x += (screen_x - (VIEW_W - EDGE_BAND))
        if screen_y < EDGE_BAND:
            self.cam_y -= (EDGE_BAND - screen_y)
        elif screen_y > VIEW_H - EDGE_BAND:
            self.cam_y += (screen_y - (VIEW_H - EDGE_BAND))

        self.cam_x = self._clamp_cam_x(self.cam_x)
        self.cam_y = self._clamp_cam_y(self.cam_y)
        self.repaint()

    def _clamp_cam_x(self, x: float) -> float:
        return max(0.0, min(max(0.0, WORLD_W - VIEW_W), x))

    def _clamp_cam_y(self, y: float) -> float:
        return max(0.0, min(max(0.0, WORLD_H - VIEW_H), y))

    def _a_from_angle(self) -> float:
        return MAX_A * math.sin(math.radians(self.angle_deg))

    def repaint(self) -> None:
        a = self._a_from_angle()
        render_perspective(self.context, self.layer, self.model,
                           self.cam_x, self.cam_y, a,
                           self.px, self.py)
        self.status.value = (
            f"avatar=({self.px:.0f},{self.py:.0f})  "
            f"camera=({self.cam_x:.0f},{self.cam_y:.0f})  "
            f"angle={self.angle_deg:.1f} deg  "
            f"a={a:.3f}"
        )


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
def build_ui(context: dcg.Context) -> None:
    model = build_world_model()

    with dcg.Window(context, label="Pan camera + perspective tilt",
                    width=VIEW_W + 40, height=VIEW_H + 220) as window:
        dcg.Text(
            context,
            value="Arrow keys move the avatar; the edge-band camera follows as before. "
                  "The slider tilts the map plane: parallel grid lines converge toward a "
                  "vanishing point above the viewport.",
            wrap=VIEW_W,
        )
        status = dcg.Text(context, value="")

        with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
            # Viewport background (pixel space, never transformed)
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, VIEW_H),
                         fill=(18, 22, 30), color=0, thickness=-1)

            # All projected world content lands in this layer (also pixel space —
            # the perspective transform is baked into the points we pass in).
            persp_layer = dcg.DrawingList(context, parent=canvas)

            # ---- HUD overlay: edge band + dead-zone outline + viewport border
            # Parented to the canvas, NOT the perspective layer, so HUD is
            # fixed in viewport pixels regardless of tilt.
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

        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW,  callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW,    callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW,  callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Pan camera with perspective tilt",
        width=VIEW_W + 80, height=VIEW_H + 260,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
