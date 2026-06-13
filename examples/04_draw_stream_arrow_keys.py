import math

import dearcygui as dcg


CANVAS_WIDTH = 820
CANVAS_HEIGHT = 260
CHARACTER_START_X = 120.0
CHARACTER_Y = 175.0
MOVE_STEP = 5.0


class CharacterController:
    def __init__(self, mover: dcg.DrawingScale, status: dcg.Text) -> None:
        self.mover = mover
        self.status = status
        self.x = CHARACTER_START_X
        self.update_position()

    def move_left(self, *_args) -> None:
        self.x = max(35.0, self.x - MOVE_STEP)
        self.update_position()

    def move_right(self, *_args) -> None:
        self.x = min(CANVAS_WIDTH - 35.0, self.x + MOVE_STEP)
        self.update_position()

    def update_position(self) -> None:
        self.mover.origin = (self.x, CHARACTER_Y)
        self.status.value = f"x = {self.x:.0f}"


def build_walker_pose_stream(context: dcg.Context, parent: dcg.DrawingScale) -> None:
    stream = dcg.utils.DrawStream(context, parent=parent)
    stream.time_modulus = 1.0

    frame_count = 16
    for frame in range(frame_count):
        t = frame / frame_count
        bob = 4 * math.sin(t * 2 * math.pi)
        swing = 10 * math.sin(t * 2 * math.pi)

        with dcg.DrawingList(context) as drawing:
            dcg.DrawCircle(context, center=(0, -32 + bob), radius=10, fill=(245, 216, 162), color=(30, 30, 35), thickness=-1)
            dcg.DrawLine(context, p1=(0, -22 + bob), p2=(0, 8), color=(240, 240, 250), thickness=-4)
            dcg.DrawLine(context, p1=(0, -12 + bob), p2=(-swing, 1), color=(255, 214, 102), thickness=-3)
            dcg.DrawLine(context, p1=(0, -12 + bob), p2=(swing, 1), color=(255, 214, 102), thickness=-3)
            dcg.DrawLine(context, p1=(0, 8), p2=(-swing, 33), color=(112, 194, 120), thickness=-4)
            dcg.DrawLine(context, p1=(0, 8), p2=(swing, 33), color=(112, 194, 120), thickness=-4)

        stream.push(drawing, (frame + 1) * stream.time_modulus / frame_count)


def build_ui(context: dcg.Context) -> None:
    with dcg.Window(context, label="DrawStream pose + arrow-key movement", width=900, height=420) as window:
        dcg.Text(context, value="DrawStream cycles the pose. Arrow-key handlers move the parent transform.", wrap=860)
        status = dcg.Text(context, value="")

        with dcg.DrawInWindow(context, width=CANVAS_WIDTH, height=CANVAS_HEIGHT) as canvas:
            dcg.DrawRect(
                context,
                pmin=(0, 0),
                pmax=(CANVAS_WIDTH, CANVAS_HEIGHT),
                fill=(26, 33, 46),
                color=(70, 84, 105),
                thickness=-1,
            )
            dcg.DrawLine(context, p1=(20, CHARACTER_Y + 34), p2=(CANVAS_WIDTH - 20, CHARACTER_Y + 34), color=(98, 118, 144), thickness=-2)
            dcg.DrawText(context, pos=(24, 22), text="Left / Right arrows", size=-16)

            mover = dcg.DrawingScale(context, parent=canvas, origin=(CHARACTER_START_X, CHARACTER_Y), scales=(1.0, 1.0))
            build_walker_pose_stream(context, parent=mover)

        controller = CharacterController(mover=mover, status=status)
        window.handlers += [
            dcg.KeyDownHandler(context, key=dcg.Key.LEFTARROW, callback=controller.move_left),
            dcg.KeyDownHandler(context, key=dcg.Key.RIGHTARROW, callback=controller.move_right),
        ]


def main() -> None:
    context = dcg.Context()
    context.viewport.initialize(title="DCG Test Map - DrawStream arrow-key movement", width=940, height=470)
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()
