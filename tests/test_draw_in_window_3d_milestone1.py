from __future__ import annotations

import math
from pathlib import Path
import subprocess
import sys

from Animation.draw_in_window_3d_framework.math3d import (
    Camera3D,
    ProjectionPipeline,
    Viewport,
    clean_polygon,
    clip_line_near,
    clip_line_to_viewport,
    clip_polygon_near,
    clip_polygon_to_viewport,
    is_face_visible,
    shade_directional,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_VIEWPORT = Viewport(900.0, 600.0)
DEMO_CAMERA = Camera3D(
    target=(1100.0, 750.0, 0.0),
    yaw_deg=35.0,
    pitch_deg=52.0,
    zoom=0.72,
)


def assert_vec_close(actual, expected, *, abs_tol: float = 1e-6) -> None:
    assert len(actual) == len(expected)
    for actual_component, expected_component in zip(actual, expected):
        assert math.isclose(actual_component, expected_component, abs_tol=abs_tol)


def test_package_import_keeps_math_available_without_dearcygui() -> None:
    script = "\n".join(
        [
            "import builtins",
            "import importlib",
            "original_import = builtins.__import__",
            "def blocked(name, globals=None, locals=None, fromlist=(), level=0):",
            "    if name == 'dearcygui':",
            "        raise ModuleNotFoundError(\"No module named 'dearcygui'\")",
            "    return original_import(name, globals, locals, fromlist, level)",
            "builtins.__import__ = blocked",
            "module = importlib.import_module('Animation.draw_in_window_3d_framework')",
            "assert hasattr(module, 'Camera3D')",
            "assert hasattr(module, 'ProjectionPipeline')",
        ]
    )
    command = [
        sys.executable,
        "-c",
        script,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_camera_eye_matches_demo11_baseline() -> None:
    eye = DEMO_CAMERA.eye(DEMO_VIEWPORT)

    assert_vec_close(
        eye,
        (1439.750600827174, 1235.2141433607642, 462.7844594034779),
    )


def test_world_to_camera_uses_demo11_yaw_then_pitch_order() -> None:
    camera_point = DEMO_CAMERA.world_to_camera((820.0, 980.0, 180.0), DEMO_VIEWPORT)

    assert_vec_close(
        camera_point,
        (-361.2851527616583, -124.72434994997954, 618.9579885587302),
    )


def test_camera_to_screen_matches_demo11_projection() -> None:
    camera_point = DEMO_CAMERA.world_to_camera((820.0, 980.0, 180.0), DEMO_VIEWPORT)
    screen = DEMO_CAMERA.camera_to_screen(camera_point, DEMO_VIEWPORT)

    assert_vec_close(screen, (134.09374421182434, 190.94153995222342))


def test_ground_from_screen_round_trips_ground_projection() -> None:
    world_point = (440.0, 400.0, 0.0)
    screen = DEMO_CAMERA.camera_to_screen(
        DEMO_CAMERA.world_to_camera(world_point, DEMO_VIEWPORT),
        DEMO_VIEWPORT,
    )

    recovered = DEMO_CAMERA.ground_from_screen(screen, DEMO_VIEWPORT)

    assert recovered is not None
    assert_vec_close(recovered, world_point)


def test_clip_polygon_near_handles_partial_visibility() -> None:
    clipped = clip_polygon_near(
        [(-10.0, 0.0, 10.0), (20.0, 0.0, 50.0), (0.0, 10.0, 50.0)],
        25.0,
    )

    assert clipped == [
        (-6.25, 3.75, 25.0),
        (1.25, 0.0, 25.0),
        (20.0, 0.0, 50.0),
        (0.0, 10.0, 50.0),
    ]


def test_clip_line_near_handles_one_endpoint_behind_plane() -> None:
    clipped = clip_line_near((-10.0, 5.0, 10.0), (30.0, 25.0, 50.0), 25.0)

    assert clipped == ((5.0, 12.5, 25.0), (30.0, 25.0, 50.0))


def test_clip_polygon_to_viewport_matches_demo11_screen_clipping() -> None:
    clipped = clip_polygon_to_viewport(
        [(-100.0, 50.0), (950.0, 50.0), (950.0, 650.0), (-100.0, 650.0)],
        DEMO_VIEWPORT,
    )

    assert clipped == [
        (0.0, 600.0),
        (0.0, 50.0),
        (900.0, 50.0),
        (900.0, 600.0),
    ]


def test_clip_line_to_viewport_matches_demo11_screen_clipping() -> None:
    clipped = clip_line_to_viewport((-100.0, 100.0), (1000.0, 500.0), DEMO_VIEWPORT)

    assert clipped == ((0.0, 136.36363636363637), (900.0, 463.6363636363636))


def test_clean_polygon_removes_duplicates_and_collinear_vertices() -> None:
    cleaned = clean_polygon(
        [
            (0.0, 0.0),
            (10.0, 0.0),
            (10.0, 0.0),
            (20.0, 0.0),
            (20.0, 10.0),
            (0.0, 10.0),
            (0.0, 0.0),
        ]
    )

    assert cleaned == [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
    assert clean_polygon([(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]) == []


def test_projection_pipeline_project_polygon_reproduces_demo11_baseline() -> None:
    pipeline = ProjectionPipeline(DEMO_CAMERA, DEMO_VIEWPORT)

    projected = pipeline.project_polygon(
        ((-200.0, 620.0, 1.0), (2200.0, 620.0, 1.0), (2200.0, 710.0, 1.0), (-200.0, 710.0, 1.0))
    )

    assert projected is not None
    assert math.isclose(projected.average_depth, 851.1368958848914, abs_tol=1e-6)
    expected_points = (
        (73.22847004670314, 100.10530230361789),
        (900.0, 405.2344334002379),
        (900.0, 463.14101795928354),
        (36.71096506866644, 109.59776927634454),
    )
    for actual, expected in zip(projected.points, expected_points):
        assert_vec_close(actual, expected)


def test_projection_pipeline_project_line_reproduces_demo11_baseline() -> None:
    pipeline = ProjectionPipeline(DEMO_CAMERA, DEMO_VIEWPORT)

    projected = pipeline.project_line((0.0, 0.0, 3.0), (2200.0, 1500.0, 3.0))

    assert projected is not None
    assert math.isclose(projected.average_depth, 878.0739424602458, abs_tol=1e-6)
    assert_vec_close(projected.p0, (302.7857337421477, 59.57064447454246))
    assert_vec_close(projected.p1, (636.0543803910186, 600.0))


def test_project_complete_quad_requires_all_corners_inside_viewport() -> None:
    pipeline = ProjectionPipeline(DEMO_CAMERA, DEMO_VIEWPORT)

    projected_quad = pipeline.project_complete_quad(
        ((900.0, 620.0, 1.0), (995.0, 620.0, 1.0), (995.0, 710.0, 1.0), (900.0, 710.0, 1.0))
    )

    assert projected_quad is not None
    expected_points = (
        (397.7926874604885, 219.88929831291088),
        (442.9800056797002, 236.56617535244007),
        (408.59369888907855, 261.8951164266173),
        (362.08194983025777, 242.8471334234634),
    )
    for actual, expected in zip(projected_quad.points, expected_points):
        assert_vec_close(actual, expected)

    assert (
        pipeline.project_complete_quad(
            ((-1000.0, -1000.0, 0.0), (5000.0, -1000.0, 0.0), (5000.0, 5000.0, 0.0), (-1000.0, 5000.0, 0.0))
        )
        is None
    )


def test_back_face_culling_matches_demo11_visibility_rule() -> None:
    face_points = [(0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (10.0, 10.0, 10.0), (0.0, 10.0, 10.0)]

    assert is_face_visible((0.0, 0.0, 1.0), face_points, (0.0, 0.0, 50.0)) is True
    assert is_face_visible((0.0, 0.0, -1.0), face_points, (0.0, 0.0, 50.0)) is False


def test_directional_shading_matches_demo11_light_model() -> None:
    assert shade_directional((100, 150, 200), (0.0, 0.0, 1.0)) == (86, 129, 172)