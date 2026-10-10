"""Opt-in, CPU-side pipeline fixtures; no work or UI construction at import."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import gc
import json
import math
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter_ns
from typing import Callable, ParamSpec, TypeVar


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dearcygui as dcg

from Animation.draw_in_window_3d_framework import (
    CpuRenderer3D, FrameContext, Line3D, OverlapDepthSorter, Polygon3D,
    Scene3D, SolidMaterial, Vec2, Vec3, Viewport,
)
from Animation.draw_in_window_3d_framework.widget import FramePublisher
from Animation.ported_demos.benchmark_overlap_sort import make_frame, quad, screen_plane_entry


FACE_COUNTS = (100, 500, 2000, 10000)
STAGES = (
    "scene_collection", "projection_clipping", "broad_phase", "exact_tests",
    "topological_ordering", "line_occlusion", "node_creation",
    "back_layer_cleanup", "publication_cleanup",
)
P = ParamSpec("P")
T = TypeVar("T")


class StageMeasurements:
    """Sequential regions only: a parent duration must never include a child."""

    def __init__(self, clock: Callable[[], int] = perf_counter_ns) -> None:
        self.clock = clock
        self.durations_ns = dict.fromkeys(STAGES, 0)
        self._active = False
        self._failed = False
        self._start = clock()

    def measure(self, stage: str, action: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        if stage not in self.durations_ns:
            raise ValueError(f"Unknown pipeline stage: {stage}")
        if self._active:
            raise RuntimeError("Timing regions must not overlap")
        if self._failed:
            raise RuntimeError("Cannot reuse a failed rebuild measurement")
        self._active = True
        self._failed = True
        start = self.clock()
        try:
            result = action(*args, **kwargs)
        finally:
            duration = self.clock() - start
            self._active = False
        self.durations_ns[stage] += duration
        self._failed = False
        return result

    def finish(self) -> dict[str, int]:
        if self._active:
            raise RuntimeError("Cannot finish inside a timing region")
        if self._failed:
            raise RuntimeError("Failed rebuilds are not successful timing samples")
        total = self.clock() - self._start
        unaccounted = total - sum(self.durations_ns.values())
        if unaccounted < 0:
            raise RuntimeError("Exclusive stages exceed total rebuild duration")
        return {**self.durations_ns, "total_rebuild": total, "unaccounted": unaccounted}


@dataclass(frozen=True)
class PipelineFixture:
    scene: Scene3D
    frame: FrameContext
    face_count: int
    line_count: int


@dataclass(frozen=True)
class FixtureMeasurement:
    face_count: int
    line_count: int
    strategy: str
    durations_ns: dict[str, int]
    counters: dict[str, int | bool]
    sample: int = 0


@dataclass(frozen=True)
class StageSummary:
    face_count: int
    stage: str
    median_ms: float
    p95_ms: float


@dataclass(frozen=True)
class BenchmarkReport:
    metadata: dict[str, object]
    rows: list[FixtureMeasurement]
    summary: list[StageSummary]


def build_fixture(face_count: int, *, include_lines: bool = True) -> PipelineFixture:
    if face_count not in FACE_COUNTS:
        raise ValueError(f"face_count must be one of {FACE_COUNTS}")
    frame = make_frame(Viewport(4096.0, 4096.0))
    scene = Scene3D()
    columns = math.ceil(math.sqrt(face_count // 4))
    material = SolidMaterial(fill=(130, 160, 190), outline=None, shaded=False)
    distance = frame.camera.distance(frame.viewport)

    def world_point(point: Vec3) -> Vec3:
        # make_frame uses zero yaw/pitch: invert its camera transform exactly.
        return point[0], point[1], distance - point[2]

    def point_at_depth(screen: Vec2, depth: float) -> Vec3:
        center_x, center_y = frame.viewport.center
        focal = frame.camera.focal_length(frame.viewport)
        return world_point(((screen[0] - center_x) * depth / focal,
                            (screen[1] - center_y) * depth / focal, depth))

    for index in range(face_count):
        cell, member = divmod(index, 4)
        x = 40.0 + (cell % columns) * 64.0
        y = 40.0 + (cell // columns) * 64.0
        dx, dy = ((0.0, 0.0), (6.0, 0.0), (0.0, 6.0), (6.0, 6.0))[member]
        entry = screen_plane_entry(frame, index, quad(x + dx, y + dy, 24.0, 24.0),
                                   1.0 / (80.0 + 20.0 * member))
        scene.add(Polygon3D(tuple(world_point(p) for p in entry.camera_points),
                            material, cull_back_face=False))
    line_count = 8 if include_lines else 0
    for cell in range(line_count):
        x = 40.0 + (cell % columns) * 64.0
        y = 52.0 + (cell // columns) * 64.0
        scene.add(Line3D(point_at_depth((x - 8.0, y), 160.0),
                         point_at_depth((x + 38.0, y), 160.0), (255, 220, 60)))
    return PipelineFixture(scene, frame, face_count, line_count)


def measure_fixture(
    fixture: PipelineFixture,
    renderer: CpuRenderer3D,
    sorter: OverlapDepthSorter,
    context: dcg.Context,
    publisher: FramePublisher,
) -> FixtureMeasurement:
    """Time each real boundary, with setup excluded and publication included."""
    if fixture.face_count > 2000 and not sorter.use_sweep_and_prune:
        raise ValueError("The 10000-face fixture requires sweep-and-prune to avoid 49,995,000 pairs")
    scene, frame = fixture.scene, fixture.frame
    timing = StageMeasurements()
    timing.measure("back_layer_cleanup", publisher.prepare_back_layer)
    packets = timing.measure("scene_collection", renderer.collect_packets, scene, frame)
    entries, clipped = timing.measure("projection_clipping", renderer.project_packets, packets, frame)
    pairs, metrics, bounds = timing.measure("broad_phase", sorter.generate_candidates, entries)
    edges = timing.measure("exact_tests", sorter.test_overlaps, entries, pairs, frame)
    ordered, edge_count = timing.measure("topological_ordering", sorter.order_entries, entries, edges)
    polygons = tuple(entry for entry in ordered.entries if entry.kind == "polygon")
    prepared = timing.measure("line_occlusion", renderer.prepare_line_occlusion,
                              ordered.entries, polygons, frame)
    emitted = timing.measure("node_creation", renderer.emit_entries,
                             context, publisher.back_layer, scene, frame, prepared)
    timing.measure("publication_cleanup", publisher.publish_back_layer)
    durations = timing.finish()
    return FixtureMeasurement(
        face_count=fixture.face_count,
        line_count=fixture.line_count,
        strategy="sweep_and_prune" if sorter.use_sweep_and_prune else "all_pairs",
        durations_ns=durations,
        counters={
            "packet_count": len(packets), "projected_count": len(entries),
            "clipped_count": clipped, "polygon_count": len(bounds),
            "possible_polygon_pairs": len(bounds) * (len(bounds) - 1) // 2,
            "x_active_pairs": metrics.x_active_pair_count,
            "candidate_pairs": len(pairs), "exact_tests": len(pairs),
            "accepted_edges": edge_count, "cycle_detected": ordered.cycle_detected,
            "line_fragments": sum(len(draw.line_segments) for draw in prepared),
            "emitted_count": emitted,
        },
    )


def run_benchmark(
    face_counts: tuple[int, ...] = FACE_COUNTS,
    *,
    samples: int = 5,
    warmups: int = 1,
    use_sweep_and_prune: bool = True,
    include_lines: bool = True,
) -> BenchmarkReport:
    if samples < 1 or warmups < 0:
        raise ValueError("samples must be positive and warmups must be nonnegative")
    if not face_counts or any(count not in FACE_COUNTS for count in face_counts):
        raise ValueError(f"face_counts must be a nonempty selection from {FACE_COUNTS}")
    if not use_sweep_and_prune and max(face_counts) > 2000:
        raise ValueError("Use sweep_and_prune for 10000 faces; all_pairs is limited to 2000")
    context = dcg.Context()
    parent = dcg.DrawingList(context)
    publisher = FramePublisher(context, parent)
    sorter = OverlapDepthSorter(use_sweep_and_prune=use_sweep_and_prune)
    renderer = CpuRenderer3D(sorter)
    rows: list[FixtureMeasurement] = []
    summaries: list[StageSummary] = []
    try:
        for count in face_counts:
            fixture = build_fixture(count, include_lines=include_lines)
            # Seed an obsolete frame even when the caller requests no warmups.
            renderer.render(context, publisher.back_layer, fixture.scene,
                            fixture.frame.camera, fixture.frame.viewport)
            publisher.publish_back_layer()
            for _ in range(warmups):
                measure_fixture(fixture, renderer, sorter, context, publisher)
            measured = [
                measure_fixture(fixture, renderer, sorter, context, publisher)
                for _ in range(samples)
            ]
            for index, row in enumerate(measured):
                expected_pairs = count * 3 // 2 if use_sweep_and_prune else count * (count - 1) // 2
                expected = {
                    "packet_count": count + fixture.line_count,
                    "projected_count": count + fixture.line_count,
                    "clipped_count": 0, "polygon_count": count,
                    "candidate_pairs": expected_pairs, "exact_tests": expected_pairs,
                    "accepted_edges": count * 3 // 2, "cycle_detected": False,
                    "line_fragments": fixture.line_count * 2,
                    "emitted_count": 1 + count + fixture.line_count * 2,
                }
                if any(row.counters[key] != value for key, value in expected.items()):
                    raise RuntimeError(f"Fixture workload mismatch: expected {expected}, got {row.counters}")
                if row.counters != measured[0].counters:
                    raise RuntimeError("Fixture counters changed between repeated samples")
                rows.append(replace(row, sample=index))
            for stage in (*STAGES, "total_rebuild", "unaccounted"):
                durations = [row.durations_ns[stage] for row in measured]
                summaries.append(StageSummary(
                    face_count=count, stage=stage,
                    median_ms=median(durations) / 1_000_000,
                    p95_ms=sorted(durations)[math.ceil(0.95 * samples) - 1] / 1_000_000,
                ))
        return BenchmarkReport(metadata={
            "schema_version": 1, "fixture_version": 1, "timing_unit": "nanoseconds",
            "percentile": "nearest-rank ceil(0.95 * N)",
            "scope": "synthetic retained rebuild through publication and obsolete-node cleanup",
            "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "gc_enabled": gc.isenabled(), "samples": samples, "warmups": warmups,
            "viewport": asdict(fixture.frame.viewport), "camera": asdict(fixture.frame.camera),
        }, rows=rows, summary=summaries)
    finally:
        parent.delete_item()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", nargs="+", type=int, choices=FACE_COUNTS, default=FACE_COUNTS)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--strategy", choices=("sweep_and_prune", "all_pairs"), default="sweep_and_prune")
    parser.add_argument("--no-lines", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_benchmark(tuple(args.counts), samples=args.samples, warmups=args.warmups,
                           use_sweep_and_prune=args.strategy == "sweep_and_prune",
                           include_lines=not args.no_lines)
    print("| Faces | Stage | Median ms | P95 ms |")
    print("| ---: | --- | ---: | ---: |")
    for row in report.summary:
        print(f"| {row.face_count} | {row.stage} | {row.median_ms:.3f} | {row.p95_ms:.3f} |")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
