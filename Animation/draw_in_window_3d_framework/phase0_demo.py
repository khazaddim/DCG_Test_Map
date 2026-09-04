from __future__ import annotations

import dearcygui as dcg

from widget import DrawInWindow3D, PolygonStyle


VIEW_W = 560
VIEW_H = 360

TRIANGLE = ((110.0, 285.0), (280.0, 70.0), (450.0, 285.0))
PENTAGON = (
    (160.0, 285.0),
    (245.0, 110.0),
    (360.0, 85.0),
    (430.0, 220.0),
    (315.0, 300.0),
)


class PolygonSwapDemo:
    def __init__(self, viewport: DrawInWindow3D, status: dcg.Text) -> None:
        self.viewport = viewport
        self.status = status
        self.showing_first = True
        self._publish_current()

    def swap(self, *_args) -> None:
        self.showing_first = not self.showing_first
        self._publish_current()

    def _publish_current(self) -> None:
        if self.showing_first:
            revision = self.viewport.replace_polygon(
                TRIANGLE,
                PolygonStyle(fill=(214, 164, 74), outline=(24, 27, 25)),
            )
            shape_name = "triangle"
        else:
            revision = self.viewport.replace_polygon(
                PENTAGON,
                PolygonStyle(fill=(82, 171, 205), outline=(17, 24, 31)),
            )
            shape_name = "pentagon"
        self.status.value = (
            f"published revision={revision} shape={shape_name} "
            f"displayed_children={len(self.viewport.displayed_layer.children)}"
        )


def build_ui(context: dcg.Context) -> None:
    with dcg.Window(
        context,
        label="DrawInWindow3D Phase 0",
        width=VIEW_W + 40,
        height=VIEW_H + 140,
    ) as window:
        dcg.Text(
            context,
            value=(
                "Phase 0 spike: DrawInWindow3D subclasses dcg.DrawInWindow "
                "and swaps hidden/visible DrawingList children under a mutex."
            ),
            wrap=VIEW_W,
        )
        status = dcg.Text(context, value="")
        with DrawInWindow3D(context, width=VIEW_W, height=VIEW_H) as viewport:
            dcg.DrawRect(
                context,
                parent=viewport,
                pmin=(0, 0),
                pmax=(VIEW_W, VIEW_H),
                fill=(19, 24, 31),
                color=(112, 132, 155),
                thickness=-2,
            )

        controller = PolygonSwapDemo(viewport, status)
        dcg.Button(
            context,
            label="Swap Polygon",
            callback=controller.swap,
        )
        window.handlers += [
            dcg.KeyDownHandler(
                context,
                key=dcg.Key.SPACE,
                callback=controller.swap,
            )
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title="DrawInWindow3D Phase 0",
        width=VIEW_W + 80,
        height=VIEW_H + 200,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()