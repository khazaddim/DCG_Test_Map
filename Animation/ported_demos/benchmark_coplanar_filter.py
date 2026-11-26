"""Compare the opt-in coplanar edge filter on real and synthetic scenes."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import gc
import json
import math
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter_ns

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import Camera3D, CpuRenderer3D, FrameContext, OverlapDepthSorter, Viewport
from Animation.draw_in_window_3d_framework.profiling import StageMeasurements
from Animation.ported_demos import organic_frozen_temple_hot_reload_world as temple
from Animation.ported_demos.benchmark_pipeline import build_fixture


def measure_case(name, scene, frame, enabled, samples, warmups):
    sorter = OverlapDepthSorter(use_coplanar_edge_filter=enabled)
    renderer = CpuRenderer3D(sorter)
    rows = []
    orders = []
    for iteration in range(warmups + samples):
        start = perf_counter_ns()
        packets = renderer.collect_packets(scene, frame)
        collected = perf_counter_ns()
        entries, rejected = renderer.project_packets(packets, frame)
        projected = perf_counter_ns()
        timing = StageMeasurements()
        result = sorter.sort(entries, frame, measurements=timing)
        finished = perf_counter_ns()
        stages = timing.finish()
        if result.sort_stats is None:
            raise RuntimeError(f"Sorter did not provide statistics: {name}, filter={enabled}")
        stats = asdict(result.sort_stats)
        stats.pop("sort_duration_seconds")
        if iteration >= warmups:
            rows.append({
                "collection_ns": collected - start,
                "projection_ns": projected - collected,
                "sort_ns": finished - projected,
                "combined_ns": finished - start,
                "broad_phase_ns": stages["broad_phase"],
                "exact_ns": stages["exact_tests"],
                "stats": stats,
                "packets": len(packets),
                "projected": len(entries),
                "rejected": rejected,
            })
            orders.append(([entry.stable_index for entry in result.entries], result.cycle_detected))
    if not all(
        all(row[key] == rows[0][key] for key in ("stats", "packets", "projected", "rejected"))
        for row in rows
    ):
        raise RuntimeError(f"Inconsistent sorter counts: {name}, filter={enabled}")
    if not all(order == orders[0] for order in orders):
        raise RuntimeError(f"Inconsistent ordering: {name}, filter={enabled}")
    summary = {}
    for key in ("collection_ns", "projection_ns", "sort_ns", "combined_ns", "broad_phase_ns", "exact_ns"):
        values = sorted(row[key] / 1e6 for row in rows)
        summary[key.replace("_ns", "_ms")] = {
            "median": median(values),
            "p95": values[math.ceil(0.95 * len(values)) - 1],
        }
    return {
        "enabled": enabled,
        "counts": {key: rows[0][key] for key in ("packets", "projected", "rejected", "stats")},
        "summary": summary,
        "raw": rows,
    }, orders[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1 or args.warmups < 0:
        parser.error("samples must be positive and warmups must be nonnegative")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    scene, avatar = temple.build_scene()
    viewport = Viewport(900, 600)
    cases = [
        (f"temple-yaw{yaw}-pitch52-zoom{zoom}", scene,
         FrameContext(Camera3D(avatar.center, yaw, 52, zoom), viewport))
        for yaw, zoom in ((0, 3.5), (0, 1.0), (0, 0.25), (90, 1.0))
    ]
    fixture = build_fixture(500, include_lines=False)
    cases.append(("synthetic-500", fixture.scene, fixture.frame))
    report = {
        "python": sys.executable, "python_version": platform.python_version(),
        "platform": platform.platform(), "gc_enabled": gc.isenabled(),
        "samples": args.samples, "warmups": args.warmups, "cases": [],
        "scope": "scene collection, projection, and instrumented sorting; excludes node emission and publication",
    }
    for name, case_scene, frame in cases:
        print(f"Running {name}", flush=True)
        baseline, baseline_order = measure_case(name, case_scene, frame, False, args.samples, args.warmups)
        experimental, experimental_order = measure_case(name, case_scene, frame, True, args.samples, args.warmups)
        if baseline_order != experimental_order:
            raise RuntimeError(f"Different polygon ordering or cycle state: {name}")
        if baseline["counts"]["stats"]["accepted_edge_count"] != experimental["counts"]["stats"]["accepted_edge_count"]:
            raise RuntimeError(f"Different ordering edge count: {name}")
        report["cases"].append({
            "name": name, "camera": asdict(frame.camera), "viewport": asdict(frame.viewport),
            "baseline": baseline, "experimental": experimental,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, indent=2))
    for case in report["cases"]:
        baseline = case["baseline"]
        experimental = case["experimental"]
        print(
            case["name"], "candidates", baseline["counts"]["stats"]["bounds_candidate_pair_count"],
            "skipped", experimental["counts"]["stats"]["skipped_pair_count"],
            "sort median ms", round(baseline["summary"]["sort_ms"]["median"], 2),
            "->", round(experimental["summary"]["sort_ms"]["median"], 2),
            "collection+projection+sort median ms", round(baseline["summary"]["combined_ms"]["median"], 2),
            "->", round(experimental["summary"]["combined_ms"]["median"], 2),
            flush=True,
        )
    print("Report:", args.output)


if __name__ == "__main__":
    main()
