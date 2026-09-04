"""Demo 13.1: collision-safe overlap ordering with bitmap, water, and sprite.

This builds on Demo 13's overlap-aware painter ordering and inherited Demo 12
collision detection. It adds Demo 11.1's textured player face, animated river
shimmer, and persistent billboard sprite without changing movement logic.
"""

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg


def load_demo(module_name, filename):
    source = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo13 = load_demo("dcg_demo_13_for_13_1", "13_dearcygui_cpu_3d_overlap_sort.py")
bitmap_demo = load_demo("dcg_demo_11_1_for_13_1", "11_1_dearcygui_cpu_3d_bitmap.py")
demo = demo13.demo


@dataclass
class RenderFace:
    world_points: tuple
    screen_points: list
    average_depth: float
    fill: tuple[int, int, int]
    stable_index: int
    textured_points: tuple | None = None


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
    bitmap_demo.build_water_shimmer(context, parent, camera)
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
            textured_points = None
            if (box is piece and face.normal == (0.0, 1.0, 0.0)
                    and bitmap_demo.project_complete_quad(face.points,
                                                          camera) is not None):
                textured_points = face.points
            render_faces.append(RenderFace(
                world_points=face.points,
                screen_points=screen_points,
                average_depth=average_depth,
                fill=demo.shade_color(face.color, face.normal),
                stable_index=len(render_faces),
                textured_points=textured_points,
            ))

    ordered_faces, cycle_detected = demo13.order_render_faces(
        render_faces, camera)
    for face in ordered_faces:
        if face.textured_points is None:
            dcg.DrawPolygon(
                context, parent=parent, points=face.screen_points,
                fill=face.fill, color=(24, 27, 25), thickness=-2,
            )
            continue
        bitmap_demo.draw_tessellated_face(
            context, parent, player_texture, face.textured_points, camera)
        dcg.DrawPolyline(
            context,
            parent=parent,
            points=bitmap_demo.project_complete_quad(face.textured_points,
                                                      camera),
            closed=True,
            color=(24, 27, 25),
            thickness=-2,
        )
    return cycle_detected


class BitmapOverlapCpu3DController(demo13.OverlapCpu3DController):
    def __init__(self, context, layer, world, status, player_texture,
                 sprite_transform):
        self.player_texture = player_texture
        self.sprite_transform = sprite_transform
        super().__init__(context, layer, world, status)

    def repaint(self) -> None:
        camera = self.camera()
        cycle_detected = render_scene(
            self.context, self.back_layer, self.world, camera,
            self.piece_x, self.piece_y, self.player_texture,
        )
        with self.layer.mutex:
            self.displayed_layer.show = False
            self.back_layer.show = True
            self.displayed_layer, self.back_layer = (
                self.back_layer, self.displayed_layer)
        bitmap_demo.update_star_billboard(
            self.sprite_transform,
            (self.piece_x, self.piece_y, bitmap_demo.SPRITE_HEIGHT),
            camera,
        )
        blocked_status = (
            f"  blocked by={self.blocked_by}" if self.blocked_by else ""
        )
        cycle_status = "  occlusion cycle fallback" if cycle_detected else ""
        self.status.value = (
            f"piece=({self.piece_x:.0f},{self.piece_y:.0f},0)  "
            f"target=({self.target_x:.0f},{self.target_y:.0f})  "
            f"pitch={self.pitch_deg:.1f} deg  yaw={self.yaw_deg:.1f} deg  "
            f"zoom={self.zoom:.2f}x  overlap sort + bitmap + water"
            f"{blocked_status}{cycle_status}"
        )


def build_ui(context: dcg.Context) -> None:
    world = demo.build_world()
    player_texture = bitmap_demo.create_player_bitmap(context)
    sprite_texture = bitmap_demo.create_star_sprite(context)
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 13.1",
                    width=demo.VIEW_W + 40,
                    height=demo.VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="Arrow keys move the textured piece with collision. The "
                "river shimmers and the floating star remains billboarded.",
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
            sprite_transform = dcg.DrawingScale(
                context, parent=canvas, show=False)
            bitmap_demo.build_star_animation(
                context, sprite_transform, sprite_texture)

            band_color = (245, 205, 83, 35)
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.EDGE_BAND_Y), fill=band_color,
                color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas,
                pmin=(0, demo.VIEW_H - demo.EDGE_BAND_Y),
                pmax=(demo.VIEW_W, demo.VIEW_H), fill=band_color,
                color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, demo.EDGE_BAND_Y),
                pmax=(demo.EDGE_BAND_X,
                      demo.VIEW_H - demo.EDGE_BAND_Y),
                fill=band_color, color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas,
                pmin=(demo.VIEW_W - demo.EDGE_BAND_X, demo.EDGE_BAND_Y),
                pmax=(demo.VIEW_W, demo.VIEW_H - demo.EDGE_BAND_Y),
                fill=band_color, color=0, thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas,
                pmin=(demo.EDGE_BAND_X, demo.EDGE_BAND_Y),
                pmax=(demo.VIEW_W - demo.EDGE_BAND_X,
                      demo.VIEW_H - demo.EDGE_BAND_Y),
                color=(245, 205, 83, 115), thickness=-1,
            )
            dcg.DrawRect(
                context, parent=canvas, pmin=(0, 0),
                pmax=(demo.VIEW_W, demo.VIEW_H), color=(112, 132, 155),
                thickness=-2,
            )

        controller = BitmapOverlapCpu3DController(
            context, scene_layer, world, status, player_texture,
            sprite_transform)
        dcg.Slider(
            context, label="Camera pitch from overhead (degrees)",
            min_value=0.0, max_value=78.0, value=controller.pitch_deg,
            width=demo.VIEW_W, callback=controller.set_pitch,
        )
        dcg.Slider(
            context, label="Camera yaw (degrees)",
            min_value=-180.0, max_value=180.0,
            value=controller.yaw_deg, width=demo.VIEW_W,
            callback=controller.set_yaw,
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
        title="DCG Test Map - Demo 13.1 bitmap collision CPU 3D",
        width=demo.VIEW_W + 80,
        height=demo.VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()