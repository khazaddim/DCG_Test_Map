from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    Camera3D,
    CpuRenderer3D,
    FieldAssociation,
    FrameContext,
    MeshEdgeStyle,
    OutOfRangePolicy,
    ProjectionPipeline,
    ScalarFieldMaterial,
    Scene3D,
    SolidMaterial,
    TetrahedralMesh3D,
    TriangleMesh3D,
    Vec3,
    Viewport,
    cross,
    dot,
    subtract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_demo_15():
    source = REPO_ROOT / "Animation" / "ported_demos" / "15_engineering_mesh_roofs.py"
    spec = importlib.util.spec_from_file_location("framework_demo_15_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_frame() -> FrameContext:
    return FrameContext(
        camera=Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=0.0, zoom=1.0, near_plane=1.0),
        viewport=Viewport(240.0, 180.0),
    )


def simple_color_map(amount: float) -> tuple[int, int, int]:
    return int(round(amount * 100.0)), 10, 20


def face_normal(points: tuple[Vec3, Vec3, Vec3]) -> Vec3:
    return cross(subtract(points[1], points[0]), subtract(points[2], points[0]))


def test_tetrahedral_mesh_extracts_only_deduplicated_exterior_faces() -> None:
    mesh = TetrahedralMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
        cells=((0, 1, 2, 3), (1, 2, 3, 4)),
        material=SolidMaterial(fill=(120, 140, 160)),
    )

    exterior = mesh.exterior_faces()
    exterior_keys = {tuple(sorted(face.indices)) for face in exterior}

    assert len(exterior) == 6
    assert (1, 2, 3) not in exterior_keys
    assert {face.source_id for face in exterior} == {0, 1}


def test_tetrahedral_exterior_faces_are_wound_away_from_opposite_vertex() -> None:
    mesh = TetrahedralMesh3D(
        vertices=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        cells=((0, 1, 2, 3),),
        material=SolidMaterial(fill=(120, 140, 160)),
    )

    for face in mesh.exterior_faces():
        cell = mesh.cells[face.source_id]
        opposite_index = next(vertex_index for vertex_index in cell if vertex_index not in face.indices)
        points = tuple(mesh.vertices[index] for index in face.indices)
        toward_opposite = subtract(mesh.vertices[opposite_index], points[0])

        assert dot(face_normal(points), toward_opposite) < 0.0


def test_triangle_mesh_scalar_material_clamps_values_and_preserves_source_ids() -> None:
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
        triangles=((0, 1, 2), (1, 3, 2)),
        source_ids=(0, 1),
        material=ScalarFieldMaterial(
            values=(0.25, 2.0),
            association=FieldAssociation.CELL,
            color_map=simple_color_map,
            value_range=(0.0, 1.0),
        ),
    )

    packets = [packet for packet in mesh.collect(make_frame()) if packet.kind == "polygon"]

    assert [packet.source_id for packet in packets] == [0, 1]
    assert [packet.material.fill for packet in packets] == [(25, 10, 20), (100, 10, 20)]


def test_scalar_material_transparent_out_of_range_skips_triangle() -> None:
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        triangles=((0, 1, 2),),
        material=ScalarFieldMaterial(
            values=(5.0,),
            value_range=(0.0, 1.0),
            out_of_range=OutOfRangePolicy.TRANSPARENT,
        ),
    )

    assert list(mesh.collect(make_frame())) == []


def test_tetrahedral_mesh_reuses_exterior_cache_for_vertex_and_material_updates() -> None:
    mesh = TetrahedralMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        cells=((0, 1, 2, 3),),
        material=SolidMaterial(fill=(120, 140, 160)),
    )
    first_exterior = mesh.exterior_faces()

    mesh.update_object(vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0)))
    mesh.update_object(material=SolidMaterial(fill=(200, 80, 60)))

    assert mesh.exterior_faces() is first_exterior


def test_tetrahedral_mesh_invalidates_exterior_cache_on_topology_update() -> None:
    mesh = TetrahedralMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
        cells=((0, 1, 2, 3),),
        material=SolidMaterial(fill=(120, 140, 160)),
    )
    first_exterior = mesh.exterior_faces()

    mesh.update_object(cells=((0, 1, 2, 3), (1, 2, 3, 4)))

    assert mesh.exterior_faces() is not first_exterior
    assert len(mesh.exterior_faces()) == 6


def test_degenerate_tetrahedra_are_ignored_and_inverted_cells_still_orient_outward() -> None:
    mesh = TetrahedralMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        cells=((0, 0, 1, 2), (0, 2, 1, 3)),
        material=SolidMaterial(fill=(120, 140, 160)),
    )

    exterior = mesh.exterior_faces()

    assert len(exterior) == 4
    assert {face.source_id for face in exterior} == {1}
    for face in exterior:
        cell = mesh.cells[face.source_id]
        opposite_index = next(vertex_index for vertex_index in cell if vertex_index not in face.indices)
        points = tuple(mesh.vertices[index] for index in face.indices)
        assert dot(face_normal(points), subtract(mesh.vertices[opposite_index], points[0])) < 0.0


def test_projected_mesh_triangle_preserves_source_id() -> None:
    mesh = TriangleMesh3D(
        vertices=((-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (0.0, 10.0, 0.0)),
        triangles=((0, 1, 2),),
        source_ids=(42,),
        material=SolidMaterial(fill=(120, 140, 160)),
        cull_back_faces=False,
    )
    frame = make_frame()
    packet = next(packet for packet in mesh.collect(frame) if packet.kind == "polygon")

    entry = CpuRenderer3D()._project_packet(packet, 0, frame, ProjectionPipeline(frame.camera, frame.viewport))

    assert entry is not None
    assert entry.source_id == 42


def test_mesh_edges_emit_optional_line_packets() -> None:
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        triangles=((0, 1, 2),),
        material=SolidMaterial(fill=(120, 140, 160)),
        edges=MeshEdgeStyle(color=(10, 20, 30), thickness=-2.0),
    )

    packets = list(mesh.collect(make_frame()))

    assert [packet.kind for packet in packets].count("polygon") == 1
    assert [packet.kind for packet in packets].count("line") == 3


def test_translucent_mesh_material_emits_double_sided_triangles() -> None:
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        triangles=((0, 1, 2),),
        material=SolidMaterial(fill=(120, 140, 160, 100)),
    )

    packets = [packet for packet in mesh.collect(make_frame()) if packet.kind == "polygon"]

    assert len(packets) == 2
    assert packets[1].points == tuple(reversed(packets[0].points))
    assert all(packet.cull_back_face is False for packet in packets)


def test_tetrahedral_fixture_renders_only_exterior_faces_with_pickable_source_ids() -> None:
    scene = Scene3D()
    mesh = TetrahedralMesh3D(
        vertices=((-8.0, -8.0, 0.0), (8.0, -8.0, 0.0), (-8.0, 8.0, 0.0), (-8.0, -8.0, 16.0), (8.0, 8.0, 16.0)),
        cells=((0, 1, 2, 3), (1, 2, 3, 4)),
        material=ScalarFieldMaterial(values=(0.0, 1.0), color_map=simple_color_map, value_range=(0.0, 1.0), shaded=False),
        cull_back_faces=False,
    )
    handle = scene.add(mesh)
    frame = make_frame()
    renderer = CpuRenderer3D()
    entries = []
    for stable_index, packet in enumerate(renderer._collect_packets(scene, frame)):
        entry = renderer._project_packet(packet, stable_index, frame, ProjectionPipeline(frame.camera, frame.viewport))
        if entry is not None:
            entries.append(entry)

    assert scene.object_count == 1
    assert scene.get(handle) is mesh
    assert len(entries) == 6
    assert {entry.source_id for entry in entries} == {0, 1}
    assert {entry.material.fill for entry in entries} == {(0, 10, 20), (100, 10, 20)}


def test_scene_update_object_replaces_mesh_fields_without_adding_scene_objects() -> None:
    scene = Scene3D()
    mesh = TriangleMesh3D(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        triangles=((0, 1, 2),),
        material=SolidMaterial(fill=(120, 140, 160)),
    )
    handle = scene.add(mesh)

    scene.update_object(handle, material=SolidMaterial(fill=(200, 80, 60)))

    assert scene.object_count == 1
    assert mesh.material.fill == (200, 80, 60)


def test_mesh_render_creates_draw_polygons_from_one_retained_scene_object() -> None:
    context = dcg.Context()
    layer = dcg.DrawingList(context)
    scene = Scene3D()
    scene.add(
        TriangleMesh3D(
            vertices=((-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (0.0, 10.0, 0.0), (20.0, 10.0, 0.0)),
            triangles=((0, 1, 2), (1, 3, 2)),
            material=SolidMaterial(fill=(120, 140, 160)),
            cull_back_faces=False,
        )
    )
    frame = make_frame()

    stats = CpuRenderer3D().render(context, layer, scene, frame.camera, frame.viewport)

    assert scene.object_count == 1
    assert stats.packet_count == 2
    assert [type(child).__name__ for child in layer.children].count("DrawPolygon") == 2


def test_demo_15_builds_varied_mesh_roofs() -> None:
    demo = load_demo_15()
    scene = demo.build_scene()
    roof_meshes = [item for item in scene.iter_visible() if isinstance(item, TriangleMesh3D) and item.edges is not None]
    triangle_counts = {len(mesh.triangles) for mesh in roof_meshes}

    assert len(roof_meshes) == 5
    assert len(triangle_counts) >= 3