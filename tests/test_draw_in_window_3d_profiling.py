from __future__ import annotations

import csv
from dataclasses import asdict, replace
import json
from pathlib import Path
import pstats
from types import SimpleNamespace

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import (
    AverageDepthSorter, DrawInWindow3D, OverlapDepthSorter, RenderStats,
    TerrainMode, TriangleMesh3D,
)
from Animation.draw_in_window_3d_framework.profiling import (
    HISTORY_SIZE, RenderTelemetry, STAGES, summarize,
)
from Animation.draw_in_window_3d_framework.profiling_panel import ProfilingPanel
from Animation.ported_demos.benchmark_pipeline import build_fixture
from Animation.ported_demos import town_hot_reload as host
from Animation.ported_demos import town_hot_reload_profiling as profiling_host
from Animation.ported_demos import open_room_hot_reload_world
from Animation.ported_demos import town_hot_reload_world


@pytest.fixture
def viewport():
    fixture = build_fixture(100)
    context = dcg.Context()
    widget = DrawInWindow3D(
        context, width=fixture.frame.viewport.width, height=fixture.frame.viewport.height,
        scene=fixture.scene, camera=fixture.frame.camera, telemetry=RenderTelemetry(enabled=True),
    )
    yield widget
    widget.delete_item()


def rebuild(telemetry: RenderTelemetry, yaw: float = 0, width: int = 900):
    return telemetry.rebuild(
        lambda _: RenderStats(2, 0, 2, 3), camera={"yaw_deg": yaw},
        viewport={"width": width, "height": 600}, strategy="test",
    )


def test_production_regions_and_uninstrumented_output_match(viewport) -> None:
    telemetry = viewport.telemetry
    telemetry.set_enabled(False)
    baseline = viewport.render_now()
    children = [type(child) for child in viewport.displayed_layer.children]
    telemetry.set_enabled(True)
    actual = viewport.render_now()
    assert [type(child) for child in viewport.displayed_layer.children] == children
    assert replace(actual, sort_stats=None) == replace(baseline, sort_stats=None)
    assert replace(actual.sort_stats, sort_duration_seconds=0) == replace(baseline.sort_stats, sort_duration_seconds=0)
    sample = telemetry.samples[-1]
    times = sample["durations_ns"]
    assert all(times[stage] > 0 for stage in STAGES)
    assert times["total_rebuild"] == sum(times[stage] for stage in STAGES) + times["unaccounted"]
    assert times["unaccounted"] >= 0
    assert sample["counters"] == asdict(actual)
    assert sample["camera"] == asdict(viewport.camera)
    assert sample["viewport"] == asdict(viewport.viewport)
    assert sample["strategy"] == "sweep_and_prune"
    assert not viewport.back_layer.children


@pytest.mark.parametrize("sweep", [False, True])
def test_overlap_strategy_counts_are_exported(viewport, sweep) -> None:
    viewport.renderer.sorter = OverlapDepthSorter(use_sweep_and_prune=sweep)
    viewport.render_now()
    sample = viewport.telemetry.samples[-1]
    stats = sample["counters"]["sort_stats"]
    expected = 150 if sweep else 4950
    assert stats["bounds_candidate_pair_count"] == stats["exact_test_count"] == expected
    assert stats["accepted_edge_count"] == 150
    assert not stats["cycle_detected"]
    assert sample["strategy"] == ("sweep_and_prune" if sweep else "all_pairs")


def test_skipped_sort_stages_and_strategy_window(viewport) -> None:
    viewport.render_now()
    viewport.renderer.sorter = AverageDepthSorter()
    viewport.render_now()
    assert len(viewport.telemetry.samples) == 1
    sample = viewport.telemetry.samples[-1]
    assert sample["durations_ns"]["broad_phase"] == 0
    assert sample["durations_ns"]["exact_tests"] == 0
    assert sample["durations_ns"]["topological_ordering"] > 0
    assert sample["strategy"] == "AverageDepthSorter"


def test_bounded_history_statistics_pause_reset_and_context() -> None:
    telemetry = RenderTelemetry()
    rebuild(telemetry)
    assert not telemetry.samples
    telemetry.set_enabled(True)
    telemetry.set_scene(7, {"HILL_ENABLED": True})
    for yaw in range(125):
        rebuild(telemetry, yaw)
    assert len(telemetry.samples) == HISTORY_SIZE
    assert telemetry.samples[0]["camera"]["yaw_deg"] == 5
    assert telemetry.samples[-1]["camera"]["yaw_deg"] == 124
    for index, sample in enumerate(telemetry.samples, 1):
        sample["durations_ns"] = dict.fromkeys((*STAGES, "total_rebuild", "unaccounted"), index * 1_000_000)
    summary = summarize(list(telemetry.samples))["total_rebuild"]
    assert (summary.latest_ms, summary.mean_ms, summary.p95_ms) == (120, 60.5, 114)
    telemetry.set_paused(True)
    rebuild(telemetry)
    telemetry.set_paused(False)
    telemetry.set_enabled(False)
    rebuild(telemetry)
    assert len(telemetry.samples) == HISTORY_SIZE
    telemetry.set_enabled(True)
    rebuild(telemetry, width=1000)
    assert len(telemetry.samples) == 1
    telemetry.reset()
    assert not telemetry.samples
    assert telemetry.scene_generation == 7
    rebuild(telemetry)
    telemetry.set_scene(8, {"HILL_ENABLED": False})
    assert not telemetry.samples
    assert telemetry.effective_flags == {"HILL_ENABLED": False}


def test_idle_failure_and_disabled_fast_path(viewport, monkeypatch) -> None:
    telemetry = viewport.telemetry
    viewport.render_now()
    front = viewport.displayed_layer
    children = list(front.children)
    for _ in range(10):
        assert viewport.render_if_needed() is None
    assert len(telemetry.samples) == 1

    def fail(*args, **kwargs):
        raise ValueError("emission failed")

    monkeypatch.setattr(viewport.renderer, "emit_entries", fail)
    viewport.invalidate()
    with pytest.raises(ValueError, match="emission failed"):
        viewport.render_if_needed()
    assert viewport.displayed_layer is front
    assert list(front.children) == children
    assert len(telemetry.samples) == 1
    assert telemetry.failure_count == 1
    assert "emission failed" in telemetry.last_failure
    telemetry.reset()
    assert telemetry.failure_count == 0
    assert not telemetry.last_failure
    monkeypatch.undo()
    telemetry.set_enabled(False)
    monkeypatch.setattr(telemetry, "rebuild", fail)
    viewport.render_now()


def test_export_schema_units_snapshot_and_csv(viewport, tmp_path) -> None:
    telemetry = viewport.telemetry
    flags = {"HOUSES_ENABLED": True}
    telemetry.set_scene(3, flags)
    flags["HOUSES_ENABLED"] = False
    viewport.render_now()
    telemetry.export(tmp_path / "samples.json")
    telemetry.export(tmp_path / "samples.csv")
    data = json.loads((tmp_path / "samples.json").read_text())
    assert data["schema_version"] == 1
    assert data["timing_unit"] == "nanoseconds"
    assert data["history_limit"] == 120
    sample = data["samples"][0]
    assert sample["scene_generation"] == 3
    assert sample["configuration_id"]
    assert sample["effective_flags"] == {"HOUSES_ENABLED": True}
    assert sample["capture_mode"] == "baseline"
    assert set(sample["durations_ns"]) == {*STAGES, "total_rebuild", "unaccounted"}
    with (tmp_path / "samples.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["timing_unit"] == "nanoseconds"
    assert int(rows[0]["total_rebuild"]) == sample["durations_ns"]["total_rebuild"]
    for key in ("effective_flags", "camera", "viewport", "counters"):
        assert json.loads(rows[0][key]) == sample[key]


def outside_capture_marker() -> None:
    sum(range(10))


def test_capture_render_thread_scope_metadata_and_pstats(viewport, tmp_path) -> None:
    telemetry = viewport.telemetry
    panel = ProfilingPanel(viewport.context, telemetry, output_directory=tmp_path)
    viewport.render_now()
    telemetry.start_capture()
    outside_capture_marker()
    panel.refresh(now=0.0)
    assert viewport.render_if_needed() is None
    viewport.render_now()
    assert len(telemetry.samples) == 1
    assert telemetry.samples[0]["capture_mode"] == "cprofile"
    telemetry.export(tmp_path / "captured.json")
    path = tmp_path / "capture.prof"
    telemetry.stop_and_save(path)
    stats = pstats.Stats(str(path))
    functions = {key[2] for key in stats.stats}
    assert {"_render_now", "render", "publish_back_layer", "prepare_line_occlusion"} <= functions
    assert not {"outside_capture_marker", "refresh", "export", "stop_and_save", "build_world"} & functions
    metadata = json.loads(path.with_suffix(".prof.json").read_text())
    assert metadata["capture_mode"] == "cprofile"
    assert metadata["render_thread"]
    assert metadata["attempt_count"] == 1
    context = metadata["contexts"][0]
    assert context["camera"] == json.loads(json.dumps(asdict(viewport.camera)))
    assert context["counters"]["emitted_count"] == viewport.last_render_stats.emitted_count
    assert context["strategy"] == "sweep_and_prune"
    viewport.render_now()
    assert len(telemetry.samples) == 1
    assert telemetry.samples[0]["capture_mode"] == "baseline"
    panel.window.delete_item()


def test_capture_when_telemetry_paused_and_failed_save_retry(viewport, tmp_path) -> None:
    telemetry = viewport.telemetry
    telemetry.set_paused(True)
    telemetry.start_capture()
    viewport.render_now()
    assert not telemetry.samples
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("block")
    with pytest.raises(OSError):
        telemetry.stop_and_save(blocked / "capture.prof")
    assert not telemetry.capture_active
    assert telemetry.capture_pending
    path = tmp_path / "retry.prof"
    telemetry.stop_and_save(path)
    assert pstats.Stats(str(path)).total_calls > 0
    assert not telemetry.capture_pending


def test_empty_capture_has_explicit_error_not_unreadable_profile(tmp_path) -> None:
    telemetry = RenderTelemetry()
    telemetry.start_capture()
    with pytest.raises(RuntimeError, match="No rebuilds captured"):
        telemetry.stop_and_save(tmp_path / "empty.prof")
    assert not (tmp_path / "empty.prof").exists()
    assert not telemetry.capture_active and not telemetry.capture_pending


def test_capture_failure_disables_profiler_and_records_context(viewport, monkeypatch, tmp_path) -> None:
    telemetry = viewport.telemetry
    telemetry.start_capture()

    def failed_emit(*args, **kwargs):
        raise ValueError("capture rebuild failed")

    monkeypatch.setattr(viewport.renderer, "emit_entries", failed_emit)
    with pytest.raises(ValueError, match="capture rebuild failed"):
        viewport.render_now()
    outside_capture_marker()
    path = tmp_path / "failed.prof"
    telemetry.stop_and_save(path)
    stats = pstats.Stats(str(path))
    assert "outside_capture_marker" not in {key[2] for key in stats.stats}
    assert not telemetry.samples
    assert telemetry.failure_count == 1
    metadata = json.loads(path.with_suffix(".prof.json").read_text())
    assert "capture rebuild failed" in metadata["contexts"][0]["failure"]


def test_capture_context_is_bounded_and_survives_resets(tmp_path) -> None:
    telemetry = RenderTelemetry()
    telemetry.start_capture()
    for yaw in range(125):
        rebuild(telemetry, yaw)
        if yaw == 60:
            telemetry.set_scene(2, {"HILL_ENABLED": False})
    telemetry.reset()
    path = tmp_path / "bounded.prof"
    telemetry.stop_and_save(path)
    metadata = json.loads(path.with_suffix(".prof.json").read_text())
    assert metadata["attempt_count"] == 125
    assert len(metadata["contexts"]) == 120
    assert metadata["omitted_context_count"] == 5
    assert metadata["contexts"][0]["camera"]["yaw_deg"] == 5
    assert metadata["contexts"][-1]["scene_generation"] == 2


def test_panel_save_failure_is_visible_and_can_retry(viewport, tmp_path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    panel = ProfilingPanel(viewport.context, viewport.telemetry, output_directory=blocked)
    panel.request("start")
    panel.process_actions()
    viewport.render_now()
    panel.request("stop")
    panel.process_actions()
    assert "failed" in panel.message.value
    assert not viewport.telemetry.capture_active
    assert viewport.telemetry.capture_pending
    blocked.unlink()
    panel.request("stop")
    panel.process_actions()
    assert "Saved" in panel.message.value
    assert not viewport.telemetry.capture_pending
    panel.window.delete_item()


def test_panel_throttle_controls_shutdown_and_no_extra_renders(viewport, tmp_path) -> None:
    telemetry = viewport.telemetry
    panel = ProfilingPanel(viewport.context, telemetry, output_directory=tmp_path)
    viewport.render_now()
    revision = viewport.last_render_revision
    assert panel.refresh(rebuilt=True, now=0.0)
    for now in (0.01, 0.05, 0.1, 0.19):
        assert not panel.refresh(now=now)
    assert panel.refresh(now=0.21)
    assert "idle" in panel.status.value
    assert len(telemetry.samples) == 1
    assert viewport.render_if_needed() is None
    assert viewport.last_render_revision == revision
    panel.request("reset")
    panel.request("pause")
    panel.request("enable")
    panel.process_actions()
    assert not telemetry.samples and telemetry.paused and not telemetry.enabled
    panel.request("start")
    panel.process_actions()
    viewport.render_now()
    panel.shutdown()
    profiles = list(tmp_path.glob("*.prof"))
    assert len(profiles) == 1
    assert pstats.Stats(str(profiles[0])).total_calls > 0
    assert not telemetry.capture_pending
    panel.request("stop")
    panel.process_actions()
    assert "failed" in panel.message.value
    panel.window.delete_item()


def fresh_world():
    return host.load_world_candidate(town_hot_reload_world)


def test_selected_open_room_world_has_a_complete_reload_bundle() -> None:
    assert host.WORLD_MODULE_NAME == "Animation.ported_demos.open_room_hot_reload_world"
    assert host.world is open_room_hot_reload_world
    prepared = host.build_world(dcg.Context(), host.world)

    assert prepared.scene.object_count > 1
    assert prepared.avatar in tuple(prepared.scene.iter_visible())
    assert {str(collider.owner) for collider in prepared.collisions.colliders} == {
        "back wall", "left wall", "table", "chair", "bed",
        "bookcase 1", "bookcase 2", "bookcase 3", "craft table", "crystal ball table",
    }
    assert prepared.terrain is None
    assert prepared.traversal.mode is TerrainMode.FLAT
    assert prepared.flags == {
        "ROOM_ENABLED": True, "FURNITURE_ENABLED": True,
        "BACK_WALL_ENABLED": True, "LEFT_WALL_ENABLED": True,
        "FRONT_WALL_ENABLED": False, "RIGHT_WALL_ENABLED": False,
    }


def test_new_world_defaults_and_all_disabled_geometry() -> None:
    world = fresh_world()
    new_flags = (
        "HOUSES_ENABLED", "ROAD_ENABLED", "FLAT_GRID_ENABLED", "HILL_GRID_ENABLED",
        "BORDER_ENABLED", "MESH_EDGES_ENABLED", "WINDMILL_ENABLED",
    )
    assert all(getattr(world, name) for name in new_flags)
    assert not world.ROAD_TEXTURE_ENABLED
    assert not world.POSITION_LABELS_ENABLED
    assert not world.ARCH_ENABLED
    for name in world.effective_world_flags():
        setattr(world, name, False)
    scene, avatar = world.build_scene()
    assert scene.object_count == 2
    assert avatar in tuple(scene.iter_visible())
    assert not world.build_collision_world().colliders
    assert world.build_terrain_surface() is None
    assert world.build_traversal_settings().mode is TerrainMode.FLAT
    assert world.create_road_texture(dcg.Context()) is None
    assert not world._WINDMILL_TEXTURES


@pytest.mark.parametrize(("flag", "removed"), [
    ("HOUSES_ENABLED", 6), ("ROAD_ENABLED", 10),
    ("FLAT_GRID_ENABLED", 62), ("HILL_GRID_ENABLED", 136), ("BORDER_ENABLED", 1),
])
def test_independent_geometry_switches(flag, removed) -> None:
    world = fresh_world()
    before, _ = world.build_scene()
    setattr(world, flag, False)
    after, _ = world.build_scene()
    assert before.object_count - after.object_count == removed
    if flag == "HOUSES_ENABLED":
        assert not any(str(c.owner).startswith("house") for c in world.build_collision_world().colliders)
    if flag == "HILL_GRID_ENABLED":
        assert world.build_terrain_surface() is not None
        assert sum(isinstance(o, TriangleMesh3D) for o in before.iter_visible()) == sum(
            isinstance(o, TriangleMesh3D) for o in after.iter_visible()
        )


def test_mesh_edges_and_effective_dependencies() -> None:
    world = fresh_world()
    before, _ = world.build_scene()
    world.MESH_EDGES_ENABLED = False
    after, _ = world.build_scene()
    assert before.object_count == after.object_count
    meshes = [o for o in after.iter_visible() if isinstance(o, TriangleMesh3D)]
    assert meshes and all(mesh.edges is None for mesh in meshes)
    world.TOWER_ENABLED = False
    world.HILL_ENABLED = False
    world.ROAD_ENABLED = False
    world.ROAD_TEXTURE_ENABLED = True
    flags = world.effective_world_flags()
    assert all(not flags[name] for name in (
        "WINDMILL_ENABLED", "HILL_GRID_ENABLED", "TERRAIN_FOLLOWING_ENABLED", "ROAD_TEXTURE_ENABLED",
    ))
    assert world.build_terrain_surface() is None
    assert world.build_traversal_settings().mode is TerrainMode.FLAT


def make_controller(context, world):
    prepared = host.build_world(context, world)
    viewport = DrawInWindow3D(
        context, width=500, height=320, scene=prepared.scene,
        camera=host.Camera3D(target=prepared.avatar.center, yaw_deg=0, pitch_deg=52, zoom=3.5),
        telemetry=RenderTelemetry(enabled=True),
    )
    return host.HotReloadTownController(
        viewport, prepared.avatar, context, prepared.road_texture, world,
        prepared.collisions, dcg.Text(context), dcg.Text(context), prepared_world=prepared,
    )


@pytest.mark.parametrize("failure_stage", ["create_road_texture", "build_scene", "build_collision_world",
                                           "build_terrain_surface", "build_traversal_settings", "effective_world_flags"])
def test_failed_reload_preserves_every_active_surface(monkeypatch, failure_stage) -> None:
    context = dcg.Context()
    world = fresh_world()
    world.WINDMILL_ENABLED = False
    controller = make_controller(context, world)
    controller.render_if_needed()
    telemetry = controller.viewport.telemetry
    before = (
        controller.world_module, controller.viewport.scene, controller.avatar,
        controller.road_texture, controller.collisions, controller.terrain,
        controller.traversal_settings, controller.follow, controller.effective_flags,
        controller.scene_generation, controller.viewport.camera, telemetry.snapshot(),
    )
    candidate = fresh_world()
    candidate.WINDMILL_ENABLED = False
    candidate.GRID_STEP = 10
    candidate.HOUSES_ENABLED = False

    def fail(*args, **kwargs):
        raise ValueError("candidate failed")

    setattr(candidate, failure_stage, fail)
    monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
    controller.reload_world()
    after = (
        controller.world_module, controller.viewport.scene, controller.avatar,
        controller.road_texture, controller.collisions, controller.terrain,
        controller.traversal_settings, controller.follow, controller.effective_flags,
        controller.scene_generation, controller.viewport.camera, telemetry.snapshot(),
    )
    assert after == before
    assert controller.world_module.GRID_STEP == 5
    assert "candidate failed" in controller.reload_status.value
    assert controller.viewport.render_if_needed() is None
    controller.viewport.delete_item()


def test_successful_reload_resets_window_preserves_controls_and_resources(monkeypatch) -> None:
    context = dcg.Context()
    world = fresh_world()
    controller = make_controller(context, world)
    controller.render_if_needed()
    textures = world._WINDMILL_TEXTURES
    assert len(textures) == world.WINDMILL_FRAME_COUNT
    generation = controller.scene_generation
    revision = controller.viewport.last_render_revision
    for callback, value in ((controller.set_yaw, 25), (controller.set_pitch, 45), (controller.set_zoom, 2)):
        callback(SimpleNamespace(value=value))
    controller.move_left()
    assert controller.viewport.last_render_revision == revision
    controller.render_if_needed()
    assert controller.viewport.last_render_revision == revision + 1
    candidate = fresh_world()
    candidate.HILL_ENABLED = False
    candidate.HOUSES_ENABLED = False
    candidate.WINDMILL_ENABLED = False
    monkeypatch.setattr(host, "load_world_candidate", lambda _: candidate)
    controller.reload_world()
    assert controller.scene_generation == generation + 1
    assert not controller.viewport.telemetry.samples
    assert controller.viewport.last_render_revision == revision + 1
    assert controller.terrain is controller.viewport.terrain is controller.follow.terrain is None
    assert controller.traversal_settings.mode is TerrainMode.FLAT
    assert controller.avatar.center[2] == 0
    assert not controller.effective_flags["HOUSES_ENABLED"]
    assert not controller.effective_flags["WINDMILL_ENABLED"]
    assert not controller.world_module._WINDMILL_TEXTURES
    assert len(world._WINDMILL_TEXTURES) == len(textures)
    controller.render_if_needed()
    assert len(controller.viewport.telemetry.samples) == 1
    assert controller.viewport.camera.yaw_deg == 25
    assert controller.viewport.camera.pitch_deg == 45
    assert controller.viewport.camera.zoom == 2
    controller.viewport.delete_item()


def test_isolated_source_reload_does_not_mutate_active_globals(tmp_path) -> None:
    original = fresh_world()
    source = Path(original.__file__).read_text()
    path = tmp_path / "world.py"
    path.write_text(source.replace("GRID_STEP = 5\n", "GRID_STEP = 7\n"))
    original.__file__ = str(path)
    candidate = host.load_world_candidate(original)
    assert candidate.GRID_STEP == 7 and original.GRID_STEP == 5
    path.write_text("GRID_STEP = 9\nraise ValueError('broken world')")
    with pytest.raises(ValueError, match="broken world"):
        host.load_world_candidate(original)
    assert original.GRID_STEP == 5


def test_original_and_profiling_hosts_share_defaults(monkeypatch) -> None:
    context = dcg.Context()
    original = host.build_ui(context)
    profiled, panel = profiling_host.build_ui(context)
    assert original.viewport.telemetry is None
    assert not panel.telemetry.enabled
    assert original.viewport.camera == profiled.viewport.camera
    assert original.effective_flags == profiled.effective_flags
    assert original.viewport.scene.object_count == profiled.viewport.scene.object_count
    assert original.viewport.renderer.sorter.use_sweep_and_prune
    assert profiled.viewport.renderer.sorter.use_sweep_and_prune
