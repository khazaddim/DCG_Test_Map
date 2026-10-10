from __future__ import annotations

from dataclasses import asdict, replace
import json

import dearcygui as dcg
import pytest

from Animation.draw_in_window_3d_framework import (
    AverageDepthSorter, CpuRenderer3D, LineRenderLayer, OverlapDepthSorter,
    WorldRenderPacket,
)
from Animation.draw_in_window_3d_framework.widget import FramePublisher
from Animation.ported_demos.benchmark_pipeline import (
    FACE_COUNTS, STAGES, StageMeasurements, build_fixture, measure_fixture, run_benchmark,
)


@pytest.mark.parametrize("count", FACE_COUNTS)
def test_fixture_has_exact_face_count_and_real_local_overlaps(count: int) -> None:
    fixture = build_fixture(count)
    renderer = CpuRenderer3D()
    packets = renderer.collect_packets(fixture.scene, fixture.frame)
    entries, clipped = renderer.project_packets(packets, fixture.frame)
    sorter = OverlapDepthSorter(use_sweep_and_prune=True)
    pairs, metrics, bounds = sorter.generate_candidates(entries)

    assert fixture.scene.object_count == count + 8
    assert sum(packet.kind == "polygon" for packet in packets) == count
    assert sum(entry.kind == "polygon" for entry in entries) == count
    assert sum(entry.kind == "line" for entry in entries) == 8
    assert clipped == 0
    assert len(bounds) == count
    assert len(pairs) == metrics.bounds_candidate_pair_count == count * 3 // 2
    assert packets == renderer.collect_packets(build_fixture(count).scene, fixture.frame)


def test_projection_boundary_clips_and_rejects_without_collection(monkeypatch) -> None:
    fixture = build_fixture(100, include_lines=False)
    renderer = CpuRenderer3D()
    frame = fixture.frame
    distance = frame.camera.distance(frame.viewport)
    # Zero-yaw/pitch camera, with the first line crossing the near plane.
    packets = (
        WorldRenderPacket(kind="line", points=((0.0, 0.0, distance), (0.0, 1.0, distance - 80.0))),
        WorldRenderPacket(kind="polygon", points=(
            (-100.0, -10.0, distance - 80.0), (10.0, -10.0, distance - 80.0),
            (10.0, 10.0, distance - 80.0), (-100.0, 10.0, distance - 80.0),
        ), cull_back_face=False),
        WorldRenderPacket(kind="line", points=((0.0, 0.0, distance + 1.0), (1.0, 0.0, distance + 2.0))),
    )
    monkeypatch.setattr(renderer, "collect_packets", forbidden)
    entries, clipped = renderer.project_packets(packets, frame)
    assert clipped == 1
    assert [entry.stable_index for entry in entries] == [0, 1]
    assert all(point[2] >= frame.camera.near_plane for entry in entries for point in entry.camera_points)
    assert all(frame.viewport.contains(point) for entry in entries for point in entry.points)
    assert min(point[0] for point in entries[1].points) == pytest.approx(0.0)


def forbidden(*_args, **_kwargs):
    raise AssertionError("An isolated stage called another pipeline stage")


@pytest.mark.parametrize("sweep", (False, True))
def test_exact_and_ordering_boundaries_match_sort_and_detect_cycles(monkeypatch, sweep: bool) -> None:
    fixture = build_fixture(100)
    renderer = CpuRenderer3D()
    entries, _ = renderer.project_packets(renderer.collect_packets(fixture.scene, fixture.frame), fixture.frame)
    sorter = OverlapDepthSorter(use_sweep_and_prune=sweep)
    combined = sorter.sort(entries, fixture.frame)
    pairs, _, _ = sorter.generate_candidates(entries)
    monkeypatch.setattr(sorter, "generate_candidates", forbidden)
    edges = sorter.test_overlaps(entries, pairs, fixture.frame)
    monkeypatch.setattr(sorter, "test_overlaps", forbidden)
    result, edge_count = sorter.order_entries(entries, edges)
    assert result.entries == combined.entries
    assert combined.sort_stats is not None
    assert edge_count == combined.sort_stats.accepted_edge_count == 150
    assert not result.cycle_detected
    assert result == sorter.order_entries(entries, edges)[0]

    cycle_entries = entries[:4]
    timing = StageMeasurements()
    cycle, edge_count = timing.measure("topological_ordering", sorter.order_entries,
                                      cycle_entries, ((0, 1), (1, 2), (2, 0), (0, 1)))
    assert cycle.cycle_detected
    assert edge_count == 3
    assert cycle.entries == AverageDepthSorter().sort(cycle_entries).entries
    assert timing.finish()["topological_ordering"] >= 0


def test_line_occlusion_is_precomputed_and_utility_lines_bypass_faces(monkeypatch) -> None:
    fixture = build_fixture(100)
    renderer = CpuRenderer3D()
    entries, _ = renderer.project_packets(renderer.collect_packets(fixture.scene, fixture.frame), fixture.frame)
    polygons = tuple(entry for entry in entries if entry.kind == "polygon")
    line = next(entry for entry in entries if entry.kind == "line")
    utility = replace(line, line_render_layer=LineRenderLayer.UTILITY)
    prepared = renderer.prepare_line_occlusion((line, utility), polygons, fixture.frame)
    assert len(prepared[0].line_segments) == 2
    assert prepared[1].line_segments == (tuple(line.points),)
    monkeypatch.setattr(renderer, "_visible_line_segments", forbidden)
    context = dcg.Context()
    target = dcg.DrawingList(context)
    try:
        assert renderer.emit_entries(context, target, fixture.scene, fixture.frame, prepared) == 4
        assert len(target.children) == 4
    finally:
        target.delete_item()


def test_staged_fixture_matches_renderer_and_cleans_obsolete_nodes() -> None:
    fixture = build_fixture(100)
    sorter = OverlapDepthSorter(use_sweep_and_prune=True)
    renderer = CpuRenderer3D(sorter)
    context = dcg.Context()
    parent = dcg.DrawingList(context)
    publisher = FramePublisher(context, parent)
    try:
        reference = renderer.render(context, publisher.back_layer, fixture.scene,
                                    fixture.frame.camera, fixture.frame.viewport)
        publisher.publish_back_layer()
        old_layer = publisher.displayed_layer
        node_types = [type(child) for child in old_layer.children]
        sample = measure_fixture(fixture, renderer, sorter, context, publisher)
        assert [type(child) for child in publisher.displayed_layer.children] == node_types
        assert sample.counters["emitted_count"] == reference.emitted_count == 117
        assert sample.counters["projected_count"] == reference.projected_count
        assert sample.counters["line_fragments"] == 16
        assert publisher.published_revision == 2
        assert old_layer is publisher.back_layer
        assert not old_layer.show and not old_layer.children
        assert publisher.displayed_layer.show
        durations = sample.durations_ns
        assert all(value >= 0 for value in durations.values())
        assert durations["total_rebuild"] == sum(durations[stage] for stage in STAGES) + durations["unaccounted"]
    finally:
        parent.delete_item()


def test_failed_emission_never_publishes_a_successful_sample(monkeypatch) -> None:
    fixture = build_fixture(100)
    sorter = OverlapDepthSorter(use_sweep_and_prune=True)
    renderer = CpuRenderer3D(sorter)
    context = dcg.Context()
    parent = dcg.DrawingList(context)
    publisher = FramePublisher(context, parent)
    try:
        measure_fixture(fixture, renderer, sorter, context, publisher)
        displayed = publisher.displayed_layer
        children = list(displayed.children)
        monkeypatch.setattr(renderer, "emit_entries", forbidden)
        with pytest.raises(AssertionError, match="isolated stage"):
            measure_fixture(fixture, renderer, sorter, context, publisher)
        assert publisher.published_revision == 1
        assert publisher.displayed_layer is displayed
        assert list(displayed.children) == children
        assert displayed.show
    finally:
        parent.delete_item()


def test_timing_accounting_skipped_regions_nesting_and_failures() -> None:
    ticks = iter((0, 10, 20, 30, 40, 50))
    timing = StageMeasurements(lambda: next(ticks))
    assert timing.measure("scene_collection", lambda: 42) == 42
    timing.measure("node_creation", lambda: None)
    values = timing.finish()
    assert values["scene_collection"] == values["node_creation"] == 10
    assert values["total_rebuild"] == 50
    assert values["unaccounted"] == 30
    assert values["exact_tests"] == 0
    with pytest.raises(ValueError, match="Unknown"):
        StageMeasurements().measure("typo", lambda: None)
    nested = StageMeasurements()
    with pytest.raises(RuntimeError, match="must not overlap"):
        nested.measure("scene_collection", nested.measure, "exact_tests", lambda: None)
    with pytest.raises(RuntimeError, match="Failed rebuilds"):
        nested.finish()


def test_runner_summary_and_raw_measurements_are_serializable() -> None:
    report = run_benchmark((100,), samples=2, warmups=0, include_lines=False)
    exported = json.loads(json.dumps(asdict(report)))
    assert exported["metadata"]["timing_unit"] == "nanoseconds"
    assert [row["sample"] for row in exported["rows"]] == [0, 1]
    assert all(row.counters["line_fragments"] == 0 for row in report.rows)
    assert all(row.counters["emitted_count"] == 101 for row in report.rows)
    for summary in report.summary:
        values = [row.durations_ns[summary.stage] for row in report.rows]
        assert summary.median_ms == sum(values) / 2 / 1_000_000
        assert summary.p95_ms == max(values) / 1_000_000
    with pytest.raises(ValueError):
        build_fixture(101)
    with pytest.raises(ValueError, match="sweep_and_prune"):
        run_benchmark((10000,), use_sweep_and_prune=False)
