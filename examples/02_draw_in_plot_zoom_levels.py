import dearcygui as dcg


def build_ui(context: dcg.Context) -> None:
    with dcg.Window(context, label="DrawInPlot + DrawingClip", width=1080, height=760):
        dcg.Text(
            context,
            value="DrawInPlot gives you built-in panning and zooming. "
            "DrawingClip can hide detail layers until the current zoom level is high enough.",
            wrap=1020,
        )

        with dcg.Plot(context, label="Prototype map canvas", width=-1, height=620, equal_aspects=True) as plot:
            plot.X1.label = "map x"
            plot.Y1.label = "map y"
            plot.X1.min = 0
            plot.X1.max = 100
            plot.Y1.min = 0
            plot.Y1.max = 100

            with dcg.DrawInPlot(context, label="map", no_legend=True) as map_layer:
                base = dcg.DrawingList(context, parent=map_layer)
                dcg.DrawRect(context, parent=base, pmin=(0, 0), pmax=(100, 100), fill=(42, 66, 49), color=0)
                dcg.DrawRect(context, parent=base, pmin=(0, 42), pmax=(100, 58), fill=(70, 111, 165), color=0)
                dcg.DrawLine(context, parent=base, p1=(8, 86), p2=(40, 60), color=(204, 188, 128), thickness=0.6)
                dcg.DrawLine(context, parent=base, p1=(40, 60), p2=(74, 25), color=(204, 188, 128), thickness=0.6)
                dcg.DrawLine(context, parent=base, p1=(40, 60), p2=(91, 80), color=(204, 188, 128), thickness=0.6)

                cities = dcg.DrawingClip(
                    context,
                    parent=map_layer,
                    pmin=(0, 0),
                    pmax=(100, 100),
                    scale_min=6.0,
                    clip_rendering=True,
                )
                for x, y, name in ((18, 82, "Port"), (43, 58, "Crossroads"), (78, 24, "Keep")):
                    dcg.DrawCircle(context, parent=cities, center=(x, y), radius=2.0, fill=(196, 116, 85), color=(30, 30, 35), thickness=-2)
                    dcg.DrawText(context, parent=cities, pos=(x + 2.5, y - 2.0), text=name, size=-14)

                people = dcg.DrawingClip(
                    context,
                    parent=map_layer,
                    pmin=(12, 18),
                    pmax=(88, 88),
                    scale_min=18.0,
                    clip_rendering=True,
                )
                for x, y, color in (
                    (16, 79, (255, 222, 89)),
                    (19, 80.2, (142, 214, 126)),
                    (44, 56.5, (110, 186, 245)),
                    (77, 26.8, (229, 132, 132)),
                ):
                    dcg.DrawCircle(context, parent=people, center=(x, y), radius=0.55, fill=color, color=(20, 20, 24), thickness=-1)

        dcg.Text(
            context,
            value="Zoom out and the people layer disappears first. "
            "That makes DrawInPlot + DrawingClip a strong candidate for city/world views.",
            wrap=1020,
        )


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - DrawInPlot zoom levels", width=1120, height=820)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
