"""Demo 14: occludable animated tree billboards on the CPU 3D map.

This retains Demo 13.1's textured player, animated water, and always-visible
player marker. Two ground-anchored tree billboards add animated leaf frames
that participate in the same overlap-aware painter ordering as buildings.
"""

from dataclasses import dataclass
import importlib.util
import math
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


TREE_BITMAP_W = 64
TREE_BITMAP_H = 96
TREE_FRAME_COUNT = 8
TREE_LOOP_SECONDS = 1.25


@dataclass(frozen=True)
class Tree:
    center_x: float
    center_y: float
    width: float
    height: float
    name: str
    frame_offset: int = 0


def create_tree_textures(context: dcg.Context) -> list[dcg.Texture]:
    """Create a compact leaf-sway animation with transparent backgrounds."""
    textures = []
    for frame_index in range(TREE_FRAME_COUNT):
        phase = frame_index * 2.0 * math.pi / TREE_FRAME_COUNT
        pixels = bytearray(TREE_BITMAP_W * TREE_BITMAP_H * 4)
        for y in range(TREE_BITMAP_H):
            for x in range(TREE_BITMAP_W):
                color = None
                if y >= 53 and abs(x - TREE_BITMAP_W * 0.5) <= 4:
                    color = (103, 66, 35, 255)
                canopy_y = (y - 36.0) / 34.0
                sway = math.sin(phase + y * 0.18) * 3.0
                canopy_x = (x - TREE_BITMAP_W * 0.5 - sway) / 29.0
                lobe = math.sin((x + y * 0.4) * 0.38 + phase) * 0.10
                if canopy_x * canopy_x + canopy_y * canopy_y < 0.92 + lobe:
                    shade = int(18 * math.sin(x * 0.33 + y * 0.17))
                    color = (45 + shade, 122 + shade, 57 + shade, 255)
                if color is not None:
                    offset = (y * TREE_BITMAP_W + x) * 4
                    pixels[offset:offset + 4] = bytes(color)
        texture = dcg.Texture(context)
        texture.nearest_neighbor_upsampling = True
        texture.set_value(memoryview(pixels).cast(
            "B", shape=(TREE_BITMAP_H, TREE_BITMAP_W, 4)))
        textures.append(texture)
    return textures


def tree_billboard_points(tree: Tree, camera) -> tuple:
    """Return a vertical quad whose horizontal edge follows camera-right."""
    yaw = math.radians(camera.yaw_deg)
    half_width = tree.width * 0.5
    right_x = math.cos(yaw) * half_width
    right_y = -math.sin(yaw) * half_width
    left = (tree.center_x - right_x, tree.center_y - right_y, 0.0)
    right = (tree.center_x + right_x, tree.center_y + right_y, 0.0)
    return (
        left,
        (left[0], left[1], tree.height),
        (right[0], right[1], tree.height),
        right,
    )


def project_image_quad(points, camera):
    """Project an unclipped image quad when all corners remain in front."""
    camera_points = [demo.world_to_camera(point, camera) for point in points]
    if any(point[2] < demo.NEAR_PLANE for point in camera_points):
        return None
    return [demo.project_camera(point, camera) for point in camera_points]


def build_tree_animation(context, parent, textures, screen_points, tree):
    """Place an animated image stream, clipped to the canvas, in draw order."""
    clip = dcg.DrawingClip(
        context,
        parent=parent,
        pmin=(0.0, 0.0),
        pmax=(float(demo.VIEW_W), float(demo.VIEW_H)),
        clip_rendering=True,
    )
    stream = dcg.utils.DrawStream(context, parent=clip)
    stream.time_modulus = TREE_LOOP_SECONDS
    for frame_index in range(TREE_FRAME_COUNT):
        texture = textures[(frame_index + tree.frame_offset) % TREE_FRAME_COUNT]
        with dcg.DrawingList(context) as drawing:
            dcg.DrawImage(
                context,
                texture=texture,
                p1=screen_points[0],
                p2=screen_points[1],
                p3=screen_points[2],
                p4=screen_points[3],
                uv1=(0.0, 1.0),
                uv2=(0.0, 0.0),
                uv3=(1.0, 0.0),
                uv4=(1.0, 1.0),
            )
        stream.push(
            drawing,
            (frame_index + 1) * TREE_LOOP_SECONDS / TREE_FRAME_COUNT,
        )
    return stream


@dataclass
class RenderFace:
    world_points: tuple
    screen_points: list
    average_depth: float
    fill: tuple[int, int, int]
    stable_index: int
    textured_points: tuple | None = None
    tree: Tree | None = None
    image_points: list | None = None


def render_scene(context, parent, world, camera, piece_x, piece_y,
                 player_texture, trees, tree_textures):
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

    for tree in trees:
        points = tree_billboard_points(tree, camera)
        projected = demo.project_world_polygon(points, camera)
        image_quad = project_image_quad(points, camera)
        if projected is None or image_quad is None:
            continue
        screen_points, average_depth = projected
        render_faces.append(RenderFace(
            world_points=points,
            screen_points=screen_points,
            average_depth=average_depth,
            fill=(49, 120, 58),
            stable_index=len(render_faces),
            tree=tree,
            image_points=image_quad,
        ))

    ordered_faces, cycle_detected = demo13.order_render_faces(
        render_faces, camera)
    for face in ordered_faces:
        if face.tree is not None:
            build_tree_animation(
                context, parent, tree_textures, face.image_points, face.tree)
            continue
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
                 sprite_transform, trees, tree_textures):
        self.player_texture = player_texture
        self.sprite_transform = sprite_transform
        self.trees = trees
        self.tree_textures = tree_textures
        super().__init__(context, layer, world, status)

    def repaint(self) -> None:
        camera = self.camera()
        cycle_detected = render_scene(
            self.context, self.back_layer, self.world, camera,
            self.piece_x, self.piece_y, self.player_texture, self.trees,
            self.tree_textures,
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
            f"zoom={self.zoom:.2f}x  overlap sort + bitmap + water + trees"
            f"{blocked_status}{cycle_status}"
        )


def build_ui(context: dcg.Context) -> None:
    world = demo.build_world()
    player_texture = bitmap_demo.create_player_bitmap(context)
    sprite_texture = bitmap_demo.create_star_sprite(context)
    tree_textures = create_tree_textures(context)
    trees = (
        Tree(655.0, 540.0, 150.0, 255.0, "watch tower tree"),
        Tree(1260.0, 650.0, 185.0, 285.0, "high tower tree", 4),
    )
    with dcg.Window(context, label="DearCyGui CPU 3D map - Demo 14",
                    width=demo.VIEW_W + 40,
                    height=demo.VIEW_H + 300) as window:
        dcg.Text(
            context,
            value="Arrow keys move the textured piece with collision. The "
                "river shimmers, the star stays visible, and trees sway "
                "behind or in front of buildings.",
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
            sprite_transform, trees, tree_textures)
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
        title="DCG Test Map - Demo 14 animated tree CPU 3D",
        width=demo.VIEW_W + 80,
        height=demo.VIEW_H + 340,
    )
    build_ui(context)
    while context.running:
        context.viewport.render_frame()


if __name__ == "__main__":
    main()