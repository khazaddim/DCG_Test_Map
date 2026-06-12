import dearcygui as dcg


def build_ui(context: dcg.Context) -> None:
    with dcg.Window(context, label="DrawInWindow + DrawingScale", width=960, height=720):
        dcg.Text(
            context,
            value="DrawInWindow gives you a root surface in pixel space. "
            "DrawingScale lets you nest a world-space coordinate system inside it.",
            wrap=900,
        )

        with dcg.DrawInWindow(context, width=900, height=580, orig_x=0, orig_y=0) as canvas:
            dcg.DrawRect(
                context,
                pmin=(0, 0),
                pmax=(900, 580),
                fill=(26, 33, 46),
                color=(70, 84, 105),
                thickness=-1,
            )

            world = dcg.DrawingScale(context, parent=canvas, origin=(50, 40), scales=(8.0, 8.0))

            terrain = dcg.DrawingList(context, parent=world)
            dcg.DrawRect(context, parent=terrain, pmin=(0, 0), pmax=(100, 60), fill=(34, 84, 52), color=0)
            dcg.DrawRect(context, parent=terrain, pmin=(0, 18), pmax=(100, 24), fill=(72, 112, 167), color=0)
            dcg.DrawLine(context, parent=terrain, p1=(5, 44), p2=(92, 10), color=(194, 171, 118), thickness=0.35)
            dcg.DrawText(context, parent=terrain, pos=(2, 2), text="World coordinates: 0..100 x 0..60", size=-14)

            city = dcg.DrawingScale(context, parent=world, origin=(68, 20), scales=(1.0, 1.0))
            dcg.DrawCircle(context, parent=city, center=(0, 0), radius=6, fill=(84, 84, 94), color=(220, 220, 230), thickness=-2)
            dcg.DrawRect(context, parent=city, pmin=(-8, -8), pmax=(8, 8), color=(230, 230, 240), thickness=-2)
            dcg.DrawText(context, parent=city, pos=(-6, -13), text="City local space", size=-13)

            party = dcg.DrawingList(context, parent=world)
            dcg.DrawCircle(context, parent=party, center=(24, 38), radius=1.4, fill=(245, 205, 83), color=(35, 35, 40), thickness=-1)
            dcg.DrawCircle(context, parent=party, center=(27, 38.7), radius=1.4, fill=(117, 190, 120), color=(35, 35, 40), thickness=-1)
            dcg.DrawCircle(context, parent=party, center=(30, 39.3), radius=1.4, fill=(110, 173, 232), color=(35, 35, 40), thickness=-1)
            dcg.DrawText(context, parent=party, pos=(20, 42), text="Nested DrawingList party token", size=-13)

        dcg.Text(
            context,
            value="Why it is useful: DrawInWindow is a good candidate if you want to own the "
            "camera math yourself while still using DrawingScale to create city-, room-, or token-local coordinates.",
            wrap=900,
        )


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - DrawInWindow world", width=1000, height=760)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
