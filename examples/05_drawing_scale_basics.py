"""DrawingScale in isolation.

A DrawingScale node applies an affine transform to every child drawing:
    screen_xy = origin + scales * world_xy

`origin` translates (in the PARENT's coordinate units).
`scales` is a (sx, sy) pair: >1 zooms in, <1 zooms out, negative flips an axis.

This script draws the same unit shape under four different DrawingScale nodes
side-by-side so you can see each parameter's effect on its own.

DrawingScale becomes useful when the image or shapes are part of a larger coordinate system. For example, it helps when you want:

1. Consistent world coordinates instead of raw pixels
2. Zooming and panning without rewriting positions
3. Y-axis flipping, like math coordinates where up is positive
4. Multiple objects drawn in the same logical space
5. A projected/perspective result that you still want to position, center, or scale cleanly

The same drawing code to work in a window, plot, or different viewport size

**DrawingScale is mostly for making drawings/images adapt to different coordinate and display conditions.**

different window sizes
different zoom levels
different coordinate ranges
flipped axes
matching plot/world coordinates
keeping object proportions consistent
moving between screen pixels and model units

"""

import dearcygui as dcg


# The DrawInWindow is the outer fixed-size drawing area, measured in pixels.
CANVAS_W = 880
CANVAS_H = 360

# Each demonstration panel gets one "cell". These are also pixel units because
# they are drawn directly into the DrawInWindow before any DrawingScale is used.
CELL_W = 200
CELL_H = 200
CELL_Y = 90


def draw_unit_shape(context: dcg.Context, parent) -> None:
    """Draw a tiny reference shape in whatever coordinate system `parent` uses.

    This function intentionally does not know anything about pixels, zooming,
    or screen placement. It only draws from (0, 0) to (1, 1).

    If `parent` is the raw DrawInWindow, that square is only 1 pixel by 1 pixel.
    If `parent` is a DrawingScale with scales=(80, 80), the same coordinates
    become an 80 pixel by 80 pixel square on screen.
    """
    # The square outline shows the local coordinate box from (0, 0) to (1, 1).
    dcg.DrawRect(context, parent=parent, pmin=(0, 0), pmax=(1, 1),
                 color=(230, 230, 240), thickness=-2)

    # Yellow dot: the local origin. This is the point moved by DrawingScale.origin.
    dcg.DrawCircle(context, parent=parent, center=(0, 0), radius=0.08,
                   fill=(245, 205, 83), color=0, thickness=-1)

    # Red line: the local +x direction. With positive x scale it points right.
    dcg.DrawLine(context, parent=parent, p1=(0, 0), p2=(1, 0),
                 color=(232, 110, 110), thickness=-2)   # +x in red

    # Green line: the local +y direction. In normal pixel space this points down.
    dcg.DrawLine(context, parent=parent, p1=(0, 0), p2=(0, 1),
                 color=(117, 190, 120), thickness=-2)   # +y in green


def cell(context: dcg.Context, canvas, x: float, label: str,
         origin, scales) -> None:
    """Draw one comparison panel for a single DrawingScale setting.

    `canvas` is the fixed DrawInWindow. Anything parented directly to it uses
    canvas pixels.

    `origin` and `scales` are passed into DrawingScale. The transformed child
    coordinates follow this rule:

        canvas_x = origin_x + local_x * scale_x
        canvas_y = origin_y + local_y * scale_y

    So this function is the bridge between screen pixels and local drawing units.
    """
    # Cell background and label are parented to the canvas, so these coordinates
    # are plain screen pixels inside the DrawInWindow.
    dcg.DrawRect(context, parent=canvas,
                 pmin=(x, CELL_Y - 10), pmax=(x + CELL_W, CELL_Y + CELL_H + 10),
                 fill=(34, 42, 58), color=(70, 84, 105), thickness=-1)
    dcg.DrawText(context, parent=canvas, pos=(x + 10, CELL_Y - 30),
                 text=label, size=-15)

    # Each cell gets its OWN DrawingScale. Think of it as creating a new local
    # coordinate frame inside the canvas. All child drawings are transformed by
    # this one object.
    scale = dcg.DrawingScale(context, parent=canvas, origin=origin, scales=scales)

    # The same 0..1 shape is drawn in every cell. The only reason it appears at
    # different sizes or orientations is the DrawingScale above.
    draw_unit_shape(context, scale)


def build_ui(context: dcg.Context) -> None:
    """Create the window and place four DrawingScale examples side by side.

    This is where the comparison happens. Each call to `cell(...)` draws the
    same unit shape, but gives it a different `origin` or `scales` value.

    The important mental model:
    - DrawInWindow is fixed pixel space.
    - DrawingScale creates a child coordinate system inside that pixel space.
    - Draw commands parented under DrawingScale use the child coordinate system.
    """
    with dcg.Window(context, label="DrawingScale basics", width=CANVAS_W + 40, height=CANVAS_H + 100):
        dcg.Text(
            context,
            value="Same 1x1 unit shape, four different DrawingScale transforms. "
                  "Red = +x, Green = +y. Note dcg's +y points DOWN in pixel space.",
            wrap=CANVAS_W,
        )

        with dcg.DrawInWindow(context, width=CANVAS_W, height=CANVAS_H) as canvas:
          # The dark canvas background is drawn before any scaled coordinate
          # systems exist, so (0, 0) means top-left of the DrawInWindow.
            dcg.DrawRect(context, parent=canvas, pmin=(0, 0), pmax=(CANVAS_W, CANVAS_H),
                         fill=(22, 27, 38), color=0, thickness=-1)

          # 1. Identity scale: local units match canvas pixels exactly.
          #    The unit shape is a 1px square because 1 local unit = 1 pixel.
            cell(context, canvas, x=20,
                 label="origin=(40,40)  scales=(1,1)",
                 origin=(40, CELL_Y + 40), scales=(1, 1))

          # 2. Uniform scale: both axes use the same conversion.
          #    Now 1 local unit = 80 pixels, so the 1x1 square becomes 80x80.
            cell(context, canvas, x=240,
                 label="origin=(40,40)  scales=(80,80)",
                 origin=(240 + 40, CELL_Y + 40), scales=(80, 80))

          # 3. Non-uniform scale: x and y use different conversions.
          #    One local x unit is 80px, but one local y unit is only 40px.
            cell(context, canvas, x=460,
                 label="origin=(40,40)  scales=(80,40)",
                 origin=(460 + 40, CELL_Y + 40), scales=(80, 40))

            # 4. Negative y: flips so +y points UP (math convention).
            #    Origin is at the BOTTOM of the cell so the shape grows upward.
          #    This is useful if your game/world coordinates use y-up, while
          #    screen pixels use y-down.
            cell(context, canvas, x=680,
                 label="origin=(40,170) scales=(80,-80)  (y-up)",
                 origin=(680 + 40, CELL_Y + 170), scales=(80, -80))

        dcg.Text(
            context,
            value="Rule of thumb: use `scales` to pick the units you want to draw in "
                  "(tiles, meters, y-up, etc.), and `origin` to place that coordinate "
                  "system inside its parent. Nest DrawingScale nodes to build "
                  "world -> region -> token local frames.",
            wrap=CANVAS_W,
        )


def main() -> None:
    """Start dearcygui, build the demo UI, and render frames until closed."""
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - DrawingScale basics",
                                width=CANVAS_W + 80, height=CANVAS_H + 160)
    build_ui(context)

    # dearcygui apps redraw one frame at a time. The drawings above are static,
    # but the viewport still needs this loop so the window stays alive.
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
