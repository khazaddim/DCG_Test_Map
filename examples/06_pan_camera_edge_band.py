"""Arrow-key avatar on a map that is larger than the viewport.

The viewport (DrawInWindow) is smaller than the world. A DrawingScale acts as a
camera: its `origin` is set to (-camera_x, -camera_y) so world coordinates are
shifted into viewport space.

The avatar moves freely in world coordinates. The camera only pans when the
avatar pushes into the "edge band" near a viewport edge. Inside that band the
camera catches up enough to keep the avatar at the band boundary. The camera is
clamped to the world bounds so it never reveals empty space past the map edges.

Mental model:
    world_xy            -> position in the full map (0..WORLD_W, 0..WORLD_H)
    DrawingScale.origin -> (-camera_x, -camera_y) shifts world into viewport
    viewport_xy         -> world_xy - camera_xy, visible inside DrawInWindow
"""

import dearcygui as dcg


# Viewport (visible area)
VIEW_W = 800
VIEW_H = 560

# World (full map, larger than viewport so panning is meaningful)
WORLD_W = 2200
WORLD_H = 1500

# Dead-zone band: how close to the viewport edge before the camera starts panning.
EDGE_BAND = 150

# Avatar
AVATAR_RADIUS = 14
MOVE_STEP = 12.0

# Starting position roughly in the middle of the world
START_X = WORLD_W * 0.5
START_Y = WORLD_H * 0.5


def build_world(context: dcg.Context, parent) -> None:
    """Draw the static map contents in world coordinates.

    Everything here is parented under the camera DrawingScale, so positions are
    in world units (0..WORLD_W, 0..WORLD_H), not viewport pixels.
    """
    # Ground
    dcg.DrawRect(
        context, parent=parent,
        pmin=(0, 0), pmax=(WORLD_W, WORLD_H),
        fill=(36, 64, 44), color=0, thickness=-1,
    )

    # Coordinate grid so panning is obvious
    grid_step = 100
    for gx in range(0, WORLD_W + 1, grid_step):
        dcg.DrawLine(context, parent=parent,
                     p1=(gx, 0), p2=(gx, WORLD_H),
                     color=(55, 85, 62), thickness=-1)
    for gy in range(0, WORLD_H + 1, grid_step):
        dcg.DrawLine(context, parent=parent,
                     p1=(0, gy), p2=(WORLD_W, gy),
                     color=(55, 85, 62), thickness=-1)

    # Numeric labels at every 200 units so the camera position is readable
    for gx in range(0, WORLD_W + 1, 200):
        for gy in range(0, WORLD_H + 1, 200):
            dcg.DrawText(context, parent=parent,
                         pos=(gx + 4, gy + 2),
                         text=f"{gx},{gy}", size=-12,
                         color=(120, 160, 130))

    # A river
    dcg.DrawRect(context, parent=parent,
                 pmin=(0, 620), pmax=(WORLD_W, 700),
                 fill=(72, 112, 167), color=0, thickness=-1)
    # A road
    dcg.DrawRect(context, parent=parent,
                 pmin=(900, 0), pmax=(980, WORLD_H),
                 fill=(120, 110, 90), color=0, thickness=-1)

    # Some landmark blobs scattered across the world
    landmarks = [
        (250, 300, (84, 130, 70), "forest"),
        (1700, 250, (84, 130, 70), "forest"),
        (1400, 1100, (140, 100, 70), "hills"),
        (400, 1200, (180, 160, 90), "fields"),
        (1900, 900, (180, 160, 90), "fields"),
    ]
    for cx, cy, color, name in landmarks:
        dcg.DrawCircle(context, parent=parent,
                       center=(cx, cy), radius=140,
                       fill=color, color=(20, 25, 20), thickness=-2)
        dcg.DrawText(context, parent=parent,
                     pos=(cx - 25, cy - 6), text=name, size=-14,
                     color=(20, 25, 20))

    # World border so it is clear when the camera reaches an edge
    dcg.DrawRect(context, parent=parent,
                 pmin=(0, 0), pmax=(WORLD_W, WORLD_H),
                 color=(240, 220, 120), thickness=-3)


class PanCameraController:
    """Holds avatar position + camera offset, and drives both from arrow keys.

    Layering:
      canvas (DrawInWindow, pixel space)
        camera (DrawingScale, origin = -camera_xy)   <-- this object pans
          world drawings (in world coordinates)
          avatar (a DrawingScale at the avatar's world position)
    """

    def __init__(self, camera: dcg.DrawingScale,
                 avatar: dcg.DrawingScale,
                 status: dcg.Text) -> None:
        self.camera = camera
        self.avatar = avatar
        self.status = status
        self.px = START_X
        self.py = START_Y
        # Camera is the world coordinate shown at the viewport's top-left.
        self.cam_x = self._clamp_cam_x(self.px - VIEW_W * 0.5)
        self.cam_y = self._clamp_cam_y(self.py - VIEW_H * 0.5)
        self._apply()

    # --- key handlers --------------------------------------------------
    def move_left(self, *_):  self._move(-MOVE_STEP, 0)
    def move_right(self, *_): self._move(+MOVE_STEP, 0)
    def move_up(self, *_):    self._move(0, -MOVE_STEP)
    def move_down(self, *_):  self._move(0, +MOVE_STEP)

    # --- internals -----------------------------------------------------
    def _move(self, dx: float, dy: float) -> None:
        # Move avatar inside the world (clamped to world bounds).
        self.px = max(AVATAR_RADIUS, min(WORLD_W - AVATAR_RADIUS, self.px + dx))
        self.py = max(AVATAR_RADIUS, min(WORLD_H - AVATAR_RADIUS, self.py + dy))

        # Avatar position projected into the viewport (before any camera pan).
        screen_x = self.px - self.cam_x
        screen_y = self.py - self.cam_y

        # Edge-band rule: if the avatar enters the band, push the camera just
        # enough to put it back at the band boundary. This creates a dead zone
        # in the middle where the camera does not move at all.
        if screen_x < EDGE_BAND:
            self.cam_x -= (EDGE_BAND - screen_x)
        elif screen_x > VIEW_W - EDGE_BAND:
            self.cam_x += (screen_x - (VIEW_W - EDGE_BAND))

        if screen_y < EDGE_BAND:
            self.cam_y -= (EDGE_BAND - screen_y)
        elif screen_y > VIEW_H - EDGE_BAND:
            self.cam_y += (screen_y - (VIEW_H - EDGE_BAND))

        # Stop the camera from revealing space past the world edges.
        self.cam_x = self._clamp_cam_x(self.cam_x)
        self.cam_y = self._clamp_cam_y(self.cam_y)

        self._apply()

    def _clamp_cam_x(self, x: float) -> float:
        max_cam = max(0.0, WORLD_W - VIEW_W)
        return max(0.0, min(max_cam, x))

    def _clamp_cam_y(self, y: float) -> float:
        max_cam = max(0.0, WORLD_H - VIEW_H)
        return max(0.0, min(max_cam, y))

    def _apply(self) -> None:
        # The camera DrawingScale lives directly under the canvas. Setting its
        # origin to -camera_xy shifts every world drawing by that amount, which
        # is exactly what a 2D camera pan is.
        self.camera.origin = (-self.cam_x, -self.cam_y)
        # The avatar is itself a DrawingScale parented to the camera, so its
        # origin is in WORLD coordinates.
        self.avatar.origin = (self.px, self.py)
        self.status.value = (
            f"avatar world=({self.px:.0f}, {self.py:.0f})   "
            f"camera=({self.cam_x:.0f}, {self.cam_y:.0f})   "
            f"viewport={VIEW_W}x{VIEW_H}   world={WORLD_W}x{WORLD_H}"
        )


def build_ui(context: dcg.Context) -> None:
    with dcg.Window(context, label="Pan camera with edge band",
                    width=VIEW_W + 40, height=VIEW_H + 120) as window:
        dcg.Text(
            context,
            value="Arrow keys move the avatar. The camera only pans once the avatar "
                  "enters the shaded edge band; inside the central dead zone the "
                  "camera holds still. The camera also stops at the world edges.",
            wrap=VIEW_W,
        )
        status = dcg.Text(context, value="")

        with dcg.DrawInWindow(context, width=VIEW_W, height=VIEW_H) as canvas:
            # Viewport background (drawn directly in pixel space so it never moves).
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, VIEW_H),
                         fill=(18, 22, 30), color=0, thickness=-1)

            # ---- the camera --------------------------------------------------
            # A single DrawingScale whose origin we move to pan the world. With
            # scales=(1,1) world units == viewport pixels, so origin=(-cx,-cy)
            # means "the world point (cx,cy) lands at viewport (0,0)".
            camera = dcg.DrawingScale(context, parent=canvas,
                                      origin=(0, 0), scales=(1.0, 1.0))

            # World content lives under the camera.
            build_world(context, parent=camera)

            # Avatar: its own DrawingScale so its world position is just its origin.
            avatar = dcg.DrawingScale(context, parent=camera,
                                      origin=(START_X, START_Y), scales=(1.0, 1.0))
            dcg.DrawCircle(context, parent=avatar, center=(0, 0),
                           radius=AVATAR_RADIUS,
                           fill=(245, 205, 83), color=(30, 30, 35), thickness=-2)
            dcg.DrawCircle(context, parent=avatar, center=(0, -3),
                           radius=AVATAR_RADIUS * 0.45,
                           fill=(30, 30, 35), color=0, thickness=-1)

            # ---- edge-band overlay ------------------------------------------
            # Parented to the canvas, NOT the camera, so it stays fixed on the
            # viewport. It just visualises where panning kicks in.
            band_color = (245, 205, 83, 40)
            # top band
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, EDGE_BAND),
                         fill=band_color, color=0, thickness=-1)
            # bottom band
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, VIEW_H - EDGE_BAND), pmax=(VIEW_W, VIEW_H),
                         fill=band_color, color=0, thickness=-1)
            # left band
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, EDGE_BAND), pmax=(EDGE_BAND, VIEW_H - EDGE_BAND),
                         fill=band_color, color=0, thickness=-1)
            # right band
            dcg.DrawRect(context, parent=canvas,
                         pmin=(VIEW_W - EDGE_BAND, EDGE_BAND),
                         pmax=(VIEW_W, VIEW_H - EDGE_BAND),
                         fill=band_color, color=0, thickness=-1)
            # dead-zone outline
            dcg.DrawRect(context, parent=canvas,
                         pmin=(EDGE_BAND, EDGE_BAND),
                         pmax=(VIEW_W - EDGE_BAND, VIEW_H - EDGE_BAND),
                         color=(245, 205, 83, 120), thickness=-1)

            # Viewport border on top so the visible region is obvious.
            dcg.DrawRect(context, parent=canvas,
                         pmin=(0, 0), pmax=(VIEW_W, VIEW_H),
                         color=(110, 130, 160), thickness=-2)

        controller = PanCameraController(camera=camera, avatar=avatar, status=status)
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW,  callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
            dcg.KeyDownHandler(context, key=dcg.Key.UPARROW,    callback=controller.move_up),
            dcg.KeyDownHandler(context, key=dcg.Key.DOWNARROW,  callback=controller.move_down),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DCG Test Map - Pan camera with edge band",
        width=VIEW_W + 80, height=VIEW_H + 160,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
