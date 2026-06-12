import math

import dearcygui as dcg


def build_walker_frames(context: dcg.Context, parent: dcg.DrawInWindow) -> None:
    stream = dcg.utils.DrawStream(context, parent=parent)
    stream.time_modulus = 1.6

    frame_count = 16
    for frame in range(frame_count):
        t = frame / frame_count
        x = 60 + 520 * t
        y = 118 + 12 * math.sin(t * 2 * math.pi)
        swing = 8 * math.sin(t * 2 * math.pi)

        with dcg.DrawingList(context) as drawing:
            dcg.DrawLine(context, p1=(20, 150), p2=(760, 150), color=(98, 118, 144), thickness=-2)
            dcg.DrawCircle(context, center=(x, y - 26), radius=10, fill=(245, 216, 162), color=(30, 30, 35), thickness=-1)
            dcg.DrawLine(context, p1=(x, y - 16), p2=(x, y + 12), color=(240, 240, 250), thickness=-3)
            dcg.DrawLine(context, p1=(x, y - 6), p2=(x - swing, y + 4), color=(255, 214, 102), thickness=-3)
            dcg.DrawLine(context, p1=(x, y - 6), p2=(x + swing, y + 4), color=(255, 214, 102), thickness=-3)
            dcg.DrawLine(context, p1=(x, y + 12), p2=(x - swing, y + 34), color=(112, 194, 120), thickness=-3)
            dcg.DrawLine(context, p1=(x, y + 12), p2=(x + swing, y + 34), color=(112, 194, 120), thickness=-3)
            dcg.DrawText(context, pos=(26, 22), text="Frame-cycled vector animation via DrawStream", size=-16)
            dcg.DrawText(context, pos=(26, 44), text="Swap each DrawingList frame for SVG- or bitmap-based content later.", size=-14)

        stream.push(drawing, (frame + 1) * stream.time_modulus / frame_count)


def build_ui(context: dcg.Context) -> None:
    with dcg.Window(context, label="DrawStream animation", width=900, height=380):
        dcg.Text(
            context,
            value="This pattern is useful for walk cycles, attack cycles, or swapping between prepared SVG/bitmap frames.",
            wrap=860,
        )
        with dcg.DrawInWindow(context, width=820, height=220) as canvas:
            build_walker_frames(context, parent=canvas)


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - DrawStream animation", width=940, height=430)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
