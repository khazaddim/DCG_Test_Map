"""Opt-in benchmark for all-pairs and sweep-and-prune overlap sorting."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
import math
from pathlib import Path
from statistics import median
import sys
from time import perf_counter_ns
from typing import Callable, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import (
    Camera3D,
    CpuRenderer3D,
    FrameContext,
    OverlapDepthSorter,
    ProjectedRenderEntry,
    ProjectionPipeline,
    SolidMaterial,
    Viewport,
)


FIXTURE_COUNTS = (32, 64, 128, 256, 512)
VIEWPORT = Viewport(2048.0, 2048.0)
FIXTURE_VERSION = 1


def make_frame(viewport: Viewport = VIEWPORT) -> FrameContext:
    return FrameContext(
        camera=Camera3D(target=(0.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=0.0, zoom=1.0, near_plane=1.0),
        viewport=viewport,
    )


def screen_plane_entry(
    frame: FrameContext,
    stable_index: int,
    points: tuple[tuple[float, float], ...],
    inverse_depth: float | Callable[[float, float], float],
) -> ProjectedRenderEntry:
    focal_length = frame.camera.focal_length(frame.viewport)
    center_x, center_y = frame.viewport.center
    camera_points = []
    for screen_x, screen_y in points:
        inverse = inverse_depth(screen_x, screen_y) if callable(inverse_depth) else inverse_depth
        depth = 1.0 / inverse
        camera_points.append(((screen_x - center_x) * depth / focal_length, (screen_y - center_y) * depth / focal_length, depth))
    return ProjectedRenderEntry(
        kind="polygon",
        stable_index=stable_index,
        average_depth=sum(point[2] for point in camera_points) / len(camera_points),
        points=points,
        camera_points=tuple(camera_points),
        material=SolidMaterial(fill=(130, 160, 190)),
    )


def quad(x: float, y: float, width: float, height: float) -> tuple[tuple[float, float], ...]:
    return ((x, y), (x + width, y), (x + width, y + height), (x, y + height))


def build_distributed_entries(count: int) -> tuple[FrameContext, tuple[ProjectedRenderEntry, ...]]:
    if count not in FIXTURE_COUNTS or count % 4:
        raise ValueError(f"count must be one of {FIXTURE_COUNTS}")
    frame = make_frame()
    columns = math.ceil(math.sqrt(count / 4))
    entries = []
    for index in range(count):
        cell, member = divmod(index, 4)
        cell_x = 40.0 + (cell % columns) * 120.0
        cell_y = 40.0 + (cell // columns) * 120.0
        dx, dy = ((0.0, 0.0), (6.0, 0.0), (0.0, 6.0), (6.0, 6.0))[member]
        entries.append(screen_plane_entry(frame, 10000 - index, quad(cell_x + dx, cell_y + dy, 24.0, 24.0), 1.0 / (80.0 + member * 20.0)))
    return frame, tuple(entries)


def build_x_separated_entries(count: int) -> tuple[FrameContext, tuple[ProjectedRenderEntry, ...]]:
    frame = make_frame()
    return frame, tuple(screen_plane_entry(frame, 10000 - index, quad(40.0 + index * 3.0, 100.0, 2.0, 24.0), 1.0 / 100.0) for index in range(count))


def build_y_separated_entries(count: int) -> tuple[FrameContext, tuple[ProjectedRenderEntry, ...]]:
    frame = make_frame()
    return frame, tuple(screen_plane_entry(frame, 10000 - index, quad(100.0, 40.0 + index * 3.0, 24.0, 2.0), 1.0 / 100.0) for index in range(count))


def build_dense_entries(count: int) -> tuple[FrameContext, tuple[ProjectedRenderEntry, ...]]:
    frame = make_frame()
    return frame, tuple(screen_plane_entry(frame, 10000 - index, quad(900.0, 900.0, 200.0, 200.0), 1.0 / (80.0 + 0.1 * index)) for index in range(count))


FIXTURE_BUILDERS: dict[str, Callable[[int], tuple[FrameContext, tuple[ProjectedRenderEntry, ...]]]] = {
    "distributed": build_distributed_entries,
    "x_separated": build_x_separated_entries,
    "y_separated": build_y_separated_entries,
    "dense": build_dense_entries,
}


def collect_target_entries(yaw_deg: float, pitch_deg: float) -> tuple[FrameContext, tuple[ProjectedRenderEntry, ...]]:
    source = Path(__file__).with_name("11_dearcygui_cpu_3d_map.py")
    spec = importlib.util.spec_from_file_location("overlap_benchmark_demo_11", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scene, _player = module.build_scene()
    viewport = Viewport(module.VIEW_W, module.VIEW_H)
    camera = Camera3D(target=(module.WORLD_W * 0.5, module.WORLD_H * 0.5, 0.0), yaw_deg=yaw_deg, pitch_deg=pitch_deg, zoom=0.72)
    frame = FrameContext(camera=camera, viewport=viewport)
    renderer = CpuRenderer3D()
    pipeline = ProjectionPipeline(camera, viewport)
    entries = tuple(
        entry
        for stable_index, packet in enumerate(renderer._collect_packets(scene, frame))
        if (entry := renderer._project_packet(packet, stable_index, frame, pipeline)) is not None
    )
    return frame, entries


def percentile_95_ns(samples: list[int]) -> int:
    return sorted(samples)[math.ceil(0.95 * len(samples)) - 1]


def structural_stats(sort_stats: dict[str, object]) -> dict[str, object]:
    return {
        name: value
        for name, value in sort_stats.items()
        if name != "sort_duration_seconds"
    }


def benchmark_entries(
    fixture_id: str,
    frame: FrameContext,
    entries: tuple[ProjectedRenderEntry, ...],
    *,
    warmup_calls: int = 5,
    sample_count: int = 100,
) -> dict[str, object]:
    sorters = {
        "all_pairs": OverlapDepthSorter(use_sweep_and_prune=False),
        "sweep_and_prune": OverlapDepthSorter(use_sweep_and_prune=True),
    }
    baseline = sorters["all_pairs"].sort(entries, frame)
    accelerated = sorters["sweep_and_prune"].sort(entries, frame)
    if ([entry.stable_index for entry in baseline.entries], baseline.cycle_detected) != ([entry.stable_index for entry in accelerated.entries], accelerated.cycle_detected):
        raise AssertionError(f"{fixture_id}: strategy disagreement before timing")
    for sorter in sorters.values():
        for _ in range(warmup_calls):
            sorter.sort(entries, frame)

    samples: list[dict[str, object]] = []
    for sample_index in range(sample_count):
        order = ("all_pairs", "sweep_and_prune") if (sample_index // 5) % 2 == 0 else ("sweep_and_prune", "all_pairs")
        for strategy in order:
            started = perf_counter_ns()
            result = sorters[strategy].sort(entries, frame)
            outer_duration_ns = perf_counter_ns() - started
            if result.sort_stats is None:
                raise AssertionError("frame-backed benchmark sort must produce statistics")
            samples.append({"fixture_id": fixture_id, "sample_index": sample_index, "strategy": strategy, "outer_duration_ns": outer_duration_ns, "sort_stats": asdict(result.sort_stats)})

    summary = {}
    for strategy in sorters:
        strategy_samples = [sample for sample in samples if sample["strategy"] == strategy]
        durations = [sample["outer_duration_ns"] for sample in strategy_samples]
        counter_values = [sample["sort_stats"] for sample in strategy_samples]
        if any(structural_stats(value) != structural_stats(counter_values[0]) for value in counter_values[1:]):
            raise AssertionError(f"{fixture_id}: non-deterministic counters for {strategy}")
        summary[strategy] = {"median_ms": median(durations) / 1_000_000, "p95_ms": percentile_95_ns(durations) / 1_000_000, "counters": counter_values[0]}
    return {"fixture_id": fixture_id, "sample_count": sample_count, "raw_samples": samples, "summary": summary}


def benchmark_synthetic(sample_count: int, warmup_calls: int) -> list[dict[str, object]]:
    results = []
    for name, builder in FIXTURE_BUILDERS.items():
        for count in FIXTURE_COUNTS:
            frame, entries = builder(count)
            results.append(benchmark_entries(f"{name}-{count}", frame, entries, warmup_calls=warmup_calls, sample_count=sample_count))
    return results


def benchmark_target_scene(sample_count: int, warmup_calls: int) -> list[dict[str, object]]:
    return [
        benchmark_entries(
            f"target-yaw-{yaw_deg:g}-pitch-{pitch_deg:g}",
            *collect_target_entries(yaw_deg, pitch_deg),
            warmup_calls=warmup_calls,
            sample_count=sample_count,
        )
        for yaw_deg in (0.0, 45.0, 90.0, 135.0)
        for pitch_deg in (25.0, 55.0, 80.0)
    ]


def render_markdown(results: Iterable[dict[str, object]]) -> str:
    lines = ["| Fixture | Strategy | Exact tests | Median ms | P95 ms |", "| --- | --- | ---: | ---: | ---: |"]
    for result in results:
        summary = result["summary"]
        for strategy in ("all_pairs", "sweep_and_prune"):
            data = summary[strategy]
            lines.append(f"| {result['fixture_id']} | {strategy} | {data['counters']['exact_test_count']} | {data['median_ms']:.3f} | {data['p95_ms']:.3f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--include-target", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    results = benchmark_synthetic(arguments.samples, arguments.warmup)
    if arguments.include_target:
        results.extend(benchmark_target_scene(arguments.samples, arguments.warmup))
    metadata = {"fixture_version": FIXTURE_VERSION, "python": sys.version, "sample_count": arguments.samples, "warmup_calls": arguments.warmup, "results": results}
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    (arguments.output_dir / "overlap_sort_benchmark.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (arguments.output_dir / "overlap_sort_benchmark.md").write_text(render_markdown(results), encoding="utf-8")


if __name__ == "__main__":
    main()