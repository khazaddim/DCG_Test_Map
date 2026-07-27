"""Demo 11.1: map a bitmap onto a 3D face and animate a billboard sprite.

This reuses demo 11's CPU projection pipeline. The bitmap is generated in
memory, uploaded once to a DearCyGui Texture, and drawn through DrawImage's
four independent corners. The south-facing player wall is textured whenever
its complete projected quad is on screen; clipped cases use the normal fill.

The floating star demonstrates the other common 3D-image pattern: a billboard
sprite. Its DrawStream persists outside the rebuilt 3D scene, while a parent
DrawingScale receives the projected position and perspective size.
"""

import importlib.util
import math
from pathlib import Path
import sys

import dearcygui as dcg


TEXTURE_GRID_DIVISIONS = 12
SPRITE_WORLD_SIZE = 72.0
SPRITE_HEIGHT = 185.0
SPRITE_BITMAP_SIZE = 48
SPRITE_FRAME_COUNT = 12
SPRITE_LOOP_SECONDS = 1.2
WATER_FRAME_COUNT = 12
WATER_LOOP_SECONDS = 1.8
WATER_DASH_SPACING = 260.0


def load_demo_11():
    source = Path(__file__).with_name("11_dearcygui_cpu_3d_map.py")
    print('source loaded',source)
    # spec defines how the source is loaded
    spec = importlib.util.spec_from_file_location("dcg_demo_11", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    # this registers the demo 11 module in python's import machinery and 
    # allows this to work like a normal import
    # sys.modules is Python’s registry of modules that have already been loaded.
    # Registering the module before calling spec.loader.exec_module(module) makes the dynamic import behave like a normal import. 
    # While demo 11 is executing, code that looks up its own module, uses decorators such as @dataclass, or imports the same module name can find the existing module object instead of creating another one or failing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

# load the full module from demo 11
demo = load_demo_11()


def create_player_bitmap(context: dcg.Context) -> dcg.Texture:
    """Create a dependency-free 48x48 RGBA checker-and-cross bitmap."""
    size = 48
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            checker = ((x // 8) + (y // 8)) % 2
            color = (238, 72, 54) if checker else (250, 202, 62)
            if abs(x - size // 2) <= 2 or abs(y - size // 2) <= 2:
                color = (34, 214, 220)
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes((*color, 255))

    rgba = memoryview(pixels).cast("B", shape=(size, size, 4))
    texture = dcg.Texture(context)
    texture.nearest_neighbor_upsampling = True
    texture.set_value(rgba)
    return texture


def create_star_sprite(context: dcg.Context) -> dcg.Texture:
    """Create a transparent diamond-shaped four-point star bitmap."""
    size = SPRITE_BITMAP_SIZE
    center = (size - 1) * 0.5
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            dx = abs(x - center)
            dy = abs(y - center)
            distance = dx + dy
            if distance > center:
                continue
            if distance < center * 0.42:
                color = (255, 249, 178, 255)
            elif distance < center * 0.76:
                color = (255, 210, 54, 255)
            else:
                color = (236, 112, 36, 255)
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes(color)

    rgba = memoryview(pixels).cast("B", shape=(size, size, 4))
    texture = dcg.Texture(context)
    texture.nearest_neighbor_upsampling = True
    texture.set_value(rgba)
    return texture


# ---------------------------------------------------------------------------
# Animated billboard sprite
# ---------------------------------------------------------------------------

def build_star_animation(context: dcg.Context, parent: dcg.DrawingScale,
                         texture: dcg.Texture) -> dcg.utils.DrawStream:
    """Build a looping bitmap animation beneath a camera-facing transform.

    DrawStream owns the animation clock and selects one DrawingList frame.
    Every frame uses local coordinates centered on (0, 0), so camera updates
    only need to move and scale ``parent``; they do not rebuild or restart the
    animation. The pulse and spin are baked into these inexpensive frames.
    """
    stream = dcg.utils.DrawStream(context, parent=parent)
    stream.time_modulus = SPRITE_LOOP_SECONDS

    for frame_index in range(SPRITE_FRAME_COUNT):
        phase = frame_index / SPRITE_FRAME_COUNT
        pulse = 1.0 + 0.12 * math.sin(phase * 2.0 * math.pi)
        rotation = phase * 0.5 * math.pi
        frame_size = SPRITE_BITMAP_SIZE * pulse

        with dcg.DrawingList(context) as drawing:
            dcg.DrawImage(
                context,
                texture=texture,
                center=(0.0, 0.0),
                width=frame_size,
                height=frame_size,
                direction=rotation,
            )

        expiry = (frame_index + 1) * (
            SPRITE_LOOP_SECONDS / SPRITE_FRAME_COUNT)
        stream.push(drawing, expiry)

    return stream


def update_star_billboard(transform: dcg.DrawingScale, position,
                          camera) -> None:
    """Project the 3D anchor and update the persistent sprite transform."""
    camera_point = demo.world_to_camera(position, camera)
    if camera_point[2] < demo.NEAR_PLANE:
        transform.show = False
        return

    center = demo.project_camera(camera_point, camera)
    screen_size = SPRITE_WORLD_SIZE * camera.focal_length / camera_point[2]
    half_size = screen_size * 0.6
    transform.show = not (
        center[0] + half_size < 0.0
        or center[0] - half_size > demo.VIEW_W
        or center[1] + half_size < 0.0
        or center[1] - half_size > demo.VIEW_H
    )
    transform.origin = center
    local_scale = screen_size / SPRITE_BITMAP_SIZE
    transform.scales = (local_scale, local_scale)


def project_complete_quad(points, camera):
    """Project a quad only when no near-plane or viewport clipping is needed."""
    camera_points = [demo.world_to_camera(point, camera) for point in points]
    if any(point[2] < demo.NEAR_PLANE for point in camera_points):
        return None
    screen_points = [demo.project_camera(point, camera)
                     for point in camera_points]
    if any(not (0.0 <= point[0] <= demo.VIEW_W
                and 0.0 <= point[1] <= demo.VIEW_H)
           for point in screen_points):
        return None
    return screen_points


def lerp_3d(start, end, amount):
    return tuple(
        start[axis] + (end[axis] - start[axis]) * amount
        for axis in range(3)
    )


def face_point_from_uv(points, u, v):
    """Return a point on demo 11's south face for bitmap coordinates u, v."""
    bottom_right, bottom_left, top_left, top_right = points
    top = lerp_3d(top_left, top_right, u)
    bottom = lerp_3d(bottom_left, bottom_right, u)
    return lerp_3d(top, bottom, v)


def draw_tessellated_face(context, parent, texture, points, camera):
    """Approximate perspective-correct mapping with small projected quads."""
    divisions = TEXTURE_GRID_DIVISIONS
    for row in range(divisions):
        v0 = row / divisions
        v1 = (row + 1) / divisions
        for column in range(divisions):
            u0 = column / divisions
            u1 = (column + 1) / divisions
            world_points = (
                face_point_from_uv(points, u0, v0),
                face_point_from_uv(points, u1, v0),
                face_point_from_uv(points, u1, v1),
                face_point_from_uv(points, u0, v1),
            )
            screen_points = [
                demo.project_camera(demo.world_to_camera(point, camera), camera)
                for point in world_points
            ]
            dcg.DrawImage(
                context,
                parent=parent,
                texture=texture,
                p1=screen_points[0],
                p2=screen_points[1],
                p3=screen_points[2],
                p4=screen_points[3],
                uv1=(u0, v0),
                uv2=(u1, v0),
                uv3=(u1, v1),
                uv4=(u0, v1),
            )


def build_water_shimmer(context, parent, camera) -> dcg.utils.DrawStream:
    """Build looping highlights preprojected onto the river surface.

    DrawStream does not perform the 3D projection itself. When the main CPU
    renderer rebuilds the scene for a camera or player change, this function
    projects every frame's world-space highlight endpoints into screen space
    once and stores the resulting DrawLine items in DrawingList frames.

    Between those scene rebuilds, DearCyGui's native DrawStream clock selects
    the prebuilt frames during normal viewport rendering. The shimmer can
    therefore animate continuously without calling ``repaint``, rerunning the
    CPU projection pipeline, retessellating geometry, or uploading textures.
    A later camera change rebuilds the stream so its cached screen-space
    frames match the new projection.

    In summary:

        1. Projection occurs once during CPU scene reconstruction.
        2. DrawStream stores preprojected DrawingList frames.
        3. DearCyGui cycles those frames without calling repaint().
        4. Camera changes rebuild the cached projection.
        5. No continuous tessellation, texture upload, or CPU projection is required.
    """
    stream = dcg.utils.DrawStream(context, parent=parent)
    stream.time_modulus = WATER_LOOP_SECONDS
    lanes = (
        (634.0, 72.0, 0.00),
        (653.0, 108.0, 0.38),
        (677.0, 84.0, 0.71),
        (697.0, 118.0, 0.19),
    )

    for frame_index in range(WATER_FRAME_COUNT):
        phase = frame_index / WATER_FRAME_COUNT
        with dcg.DrawingList(context) as drawing:
            for lane_index, (world_y, dash_length, lane_phase) in enumerate(
                    lanes):
                offset = ((phase + lane_phase) % 1.0) * WATER_DASH_SPACING
                world_x = offset - WATER_DASH_SPACING
                while world_x < demo.WORLD_W:
                    wave = 3.0 * math.sin(
                        world_x * 0.012 + phase * 2.0 * math.pi)
                    line = demo.project_world_line(
                        (world_x, world_y + wave, 4.0),
                        (world_x + dash_length, world_y - wave, 4.0),
                        camera,
                    )
                    if line is not None:
                        alpha = 105 if lane_index % 2 == 0 else 75
                        dcg.DrawLine(
                            context,
                            p1=line[0],
                            p2=line[1],
                            color=(176, 224, 240, alpha),
                            thickness=-2,
                        )
                    world_x += WATER_DASH_SPACING

        stream.push(
            drawing,
            (frame_index + 1) * WATER_LOOP_SECONDS / WATER_FRAME_COUNT,
        )

    return stream


def render_scene(context, parent, world, camera, piece_x, piece_y,
                 player_texture):
    demo.clear_layer(parent)

    demo.draw_ground_polygon(context, parent, (
        (-demo.GROUND_PAD, -demo.GROUND_PAD, 0.0),
        (demo.WORLD_W + demo.GROUND_PAD, -demo.GROUND_PAD, 0.0),
        (demo.WORLD_W + demo.GROUND_PAD,
         demo.WORLD_H + demo.GROUND_PAD, 0.0),
        (-demo.GROUND_PAD, demo.WORLD_H + demo.GROUND_PAD, 0.0),
    ), camera, (42, 66, 47))

    demo.draw_ground_polygon(context, parent, (
        (0.0, 620.0, 1.0), (demo.WORLD_W, 620.0, 1.0),
        (demo.WORLD_W, 710.0, 1.0), (0.0, 710.0, 1.0),
    ), camera, (68, 116, 168))
    build_water_shimmer(context, parent, camera)
    demo.draw_ground_polygon(context, parent, (
        (910.0, 0.0, 2.0), (995.0, 0.0, 2.0),
        (995.0, demo.WORLD_H, 2.0), (910.0, demo.WORLD_H, 2.0),
    ), camera, (130, 116, 91))

    for grid_x in range(0, int(demo.WORLD_W) + 1, 100):
        line = demo.project_world_line(
            (float(grid_x), 0.0, 3.0),
            (float(grid_x), demo.WORLD_H, 3.0), camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=(65, 91, 68), thickness=-1)
    for grid_y in range(0, int(demo.WORLD_H) + 1, 100):
        line = demo.project_world_line(
            (0.0, float(grid_y), 3.0),
            (demo.WORLD_W, float(grid_y), 3.0), camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=(65, 91, 68), thickness=-1)

    border_color = (235, 214, 116)
    border_points = (
        (0.0, 0.0, 5.0), (demo.WORLD_W, 0.0, 5.0),
        (demo.WORLD_W, demo.WORLD_H, 5.0),
        (0.0, demo.WORLD_H, 5.0),
    )
    for index in range(4):
        line = demo.project_world_line(
            border_points[index], border_points[(index + 1) % 4], camera)
        if line is not None:
            dcg.DrawLine(context, parent=parent, p1=line[0], p2=line[1],
                         color=border_color, thickness=-3)

    for label in world.labels:
        projected_label = demo.project_ground_label(label, camera)
        if projected_label is None:
            continue
        screen, screen_size = projected_label
        dcg.DrawText(context, parent=parent, pos=screen, text=label.text,
                     size=-screen_size, color=label.color)

    piece = demo.Box(
        piece_x, piece_y, demo.PIECE_SIZE, demo.PIECE_SIZE, 115.0,
        (245, 194, 67), "player",
    )
    eye = demo.camera_eye(camera)
    render_faces = []
    for box in [*world.boxes, piece]:
        for face in demo.box_faces(box):
            if not demo.face_is_visible(face, eye):
                continue
            projected = demo.project_world_polygon(face.points, camera)
            if projected is None:
                continue
            screen_points, average_depth = projected
            textured_face = None
            if box is piece and face.normal == (0.0, 1.0, 0.0):
                if project_complete_quad(face.points, camera) is not None:
                    textured_face = face.points
            render_faces.append((
                average_depth,
                screen_points,
                demo.shade_color(face.color, face.normal),
                textured_face,
            ))

    render_faces.sort(key=lambda item: item[0], reverse=True)
    for _, screen_points, fill, textured_face in render_faces:
        if textured_face is None:
            dcg.DrawPolygon(context, parent=parent, points=screen_points,
                            fill=fill, color=(24, 27, 25), thickness=-2)
            continue

        draw_tessellated_face(
            context, parent, player_texture, textured_face, camera)
        outline_points = project_complete_quad(textured_face, camera)
        dcg.DrawPolyline(
            context,
            parent=parent,
            points=outline_points,
            closed=True,
            color=(24, 27, 25),
            thickness=-2,
        )

class BitmapCpu3DController(demo.Cpu3DController):
    def __init__(self, context, layer, world, status, player_texture,
                 sprite_transform):
        self.player_texture = player_texture
        self.sprite_transform = sprite_transform
        super().__init__(context, layer, world, status)

    def repaint(self):
        camera = self.camera()
        render_scene(
            self.context, self.back_layer, self.world, camera,
            self.piece_x, self.piece_y, self.player_texture,
        )
        with self.layer.mutex:
            self.displayed_layer.show = False
            self.back_layer.show = True
            self.displayed_layer, self.back_layer = (
                self.back_layer, self.displayed_layer)
        update_star_billboard(
            self.sprite_transform,
            (self.piece_x, self.piece_y, SPRITE_HEIGHT),
            camera,
        )
        self.status.value = (
            f"piece=({self.piece_x:.0f},{self.piece_y:.0f},0)  "
            f"pitch={self.pitch_deg:.1f} deg  yaw={self.yaw_deg:.1f} deg  "
            f"zoom={self.zoom:.2f}x  bitmap={TEXTURE_GRID_DIVISIONS}x"
            f"{TEXTURE_GRID_DIVISIONS} tessellated face"
        )


def build_ui(context: dcg.Context) -> None:
    world = demo.build_world()
    player_texture = create_player_bitmap(context)
    sprite_texture = create_star_sprite(context)
    with dcg.Window(context, label="DearCyGui CPU 3D bitmap proof",
                    width=demo.VIEW_W + 40, height=demo.VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="The cyan-cross bitmap uses a tessellated projection on "
                "the player's south-facing wall. The floating diamond is a "
                "camera-facing sprite.",
            wrap=demo.VIEW_W,
        )
        status = dcg.Text(context, value="")
        with dcg.DrawInWindow(
                context, width=demo.VIEW_W, height=demo.VIEW_H) as canvas:
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.VIEW_H), fill=(19, 24, 31),
                color=0, thickness=-1,
            )
            scene_layer = dcg.DrawingList(context, parent=canvas)

            # This persistent layer is not cleared by render_scene. DrawStream
            # can therefore advance continuously while the 3D layer is idle.
            sprite_transform = dcg.DrawingScale(
                context, parent=canvas, show=False)
            build_star_animation(
                context, sprite_transform, sprite_texture)

            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.VIEW_H), color=(112, 132, 155),
                thickness=-2,
            )

        controller = BitmapCpu3DController(
            context, scene_layer, world, status, player_texture,
            sprite_transform)
        dcg.Slider(
            context, label="Camera pitch from overhead (degrees)",
            min_value=0.0, max_value=78.0, value=controller.pitch_deg,
            width=demo.VIEW_W, callback=controller.set_pitch,
        )
        dcg.Slider(
            context, label="Camera yaw (degrees)",
            min_value=-180.0, max_value=180.0, value=controller.yaw_deg,
            width=demo.VIEW_W, callback=controller.set_yaw,
        )
        dcg.Slider(
            context, label="Camera zoom", min_value=demo.ZOOM_MIN,
            max_value=demo.ZOOM_MAX, value=controller.zoom,
            width=demo.VIEW_W, callback=controller.set_zoom,
        )
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
        title="DCG Test Map - Demo 11.1 bitmap on 3D face",
        width=demo.VIEW_W + 80,
        height=demo.VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()