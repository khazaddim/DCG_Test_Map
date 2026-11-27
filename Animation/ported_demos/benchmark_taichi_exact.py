"""Compare Python and Taichi exact tests on fixed projected scenes, without a GUI."""

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter_ns

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework import Camera3D, CpuRenderer3D, FrameContext, OverlapDepthSorter, Viewport
from Animation.draw_in_window_3d_framework.scene import overlapping_polygon_depths
from Animation.ported_demos import organic_frozen_temple_hot_reload_world as temple
from Animation.ported_demos.benchmark_pipeline import build_fixture
from Animation.ported_demos.taichi_exact_eval import evaluate, ti


DEPTH_RTOL = 1e-10
DEPTH_ATOL = 1e-9


def verify_depths(entries, pairs, frame, area_epsilon, result, *, rtol=DEPTH_RTOL, atol=DEPTH_ATOL):
    for row, (a, b) in enumerate(pairs):
        baseline = overlapping_polygon_depths(entries[a], entries[b], frame, area_epsilon)
        if baseline is None:
            matches = result.statuses[row] == 0
        else:
            matches = result.statuses[row] == 1 and all(
                math.isclose(actual, expected, rel_tol=rtol, abs_tol=atol)
                for actual, expected in zip(result.depths[row], baseline)
            )
        if not matches:
            raise RuntimeError(
                f"Pair {row} ({a}, {b}): Python {baseline}, "
                f"Taichi status={result.statuses[row]}, depths={result.depths[row]}"
            )


def summarize(rows):
    summary = {}
    for key in rows[0]:
        values = sorted(row[key] for row in rows)
        summary[key.removesuffix("_ns") + "_ms"] = {
            "median": median(values) / 1e6,
            "p95": values[math.ceil(0.95 * len(values)) - 1] / 1e6,
        }
    return summary


def build_cases():
    world, avatar = temple.build_scene()
    view = Viewport(900, 600)
    for yaw, zoom in ((0, 3.5), (0, 1.0), (0, 0.25), (90, 1.0)):
        yield (f"temple-yaw{yaw}-zoom{zoom:g}", world, FrameContext(Camera3D(avatar.center, yaw, 52, zoom), view))
    for count in (100, 500, 2000):
        fixture = build_fixture(count, include_lines=False)
        yield (f"synthetic-{count}", fixture.scene, fixture.frame)


def prepare_cases(sorter):
    renderer = CpuRenderer3D(sorter)
    cases = []
    for name, scene, frame in build_cases():
        entries, _ = renderer.project_packets(renderer.collect_packets(scene, frame), frame)
        pairs, _, _ = sorter.generate_candidates(entries)
        cases.append((name, entries, pairs, frame))
    return cases


def measure(sorter, cases, samples, warmups, *, threads=None, gpu=None, float32=False):
    using_taichi = threads is not None or gpu is not None
    mode = f"taichi-{gpu}" if gpu else f"taichi-cpu-{threads}t" if using_taichi else "python"
    rtol, atol = (1e-5, 1e-6) if float32 else (DEPTH_RTOL, DEPTH_ATOL)
    arch = getattr(ti, gpu) if gpu else ti.cpu
    init_ns = None
    if using_taichi:
        start = perf_counter_ns()
        cpu_options = {"cpu_max_num_threads": threads} if threads is not None else {}
        ti.init(arch=arch, default_fp=ti.f32 if float32 else ti.f64,
                **cpu_options,
                fast_math=False, offline_cache=False, enable_fallback=False)
        init_ns = perf_counter_ns() - start
    cold_call_ns = None
    workloads = {}
    try:
        if using_taichi and ti.lang.impl.current_cfg().arch != arch:
            raise RuntimeError(f"{mode}: Taichi did not initialize the requested backend {arch}")
        for name, entries, pairs, frame in cases:
            print(f"{mode}: {name} ({len(pairs):,} pairs)", flush=True)
            expected_edges = sorter.test_overlaps(entries, pairs, frame)
            expected_order = sorter.order_entries(entries, expected_edges)
            rows = []
            fallback_pairs = 0
            for iteration in range(1 + warmups + samples):
                start = perf_counter_ns()
                if not using_taichi:
                    edges = sorter.test_overlaps(entries, pairs, frame)
                    row = {"exact_stage_ns": perf_counter_ns() - start}
                else:
                    result = evaluate(entries, pairs, frame, sorter.overlap_area_epsilon,
                                      dtype=np.float32 if float32 else np.float64)
                    edge_start = perf_counter_ns()
                    edges = result.edges(pairs, sorter.depth_epsilon)
                    end = perf_counter_ns()
                    row = {
                        "exact_stage_ns": end - start,
                        "packing_ns": result.packing_ns,
                        "kernel_sync_ns": result.kernel_sync_ns,
                        "fallback_ns": result.fallback_ns,
                        "edge_collection_ns": end - edge_start,
                    }
                    if cold_call_ns is None and pairs:
                        cold_call_ns = row["exact_stage_ns"]
                    if iteration == 0:
                        try:
                            verify_depths(entries, pairs, frame, sorter.overlap_area_epsilon, result,
                                          rtol=rtol, atol=atol)
                        except RuntimeError as error:
                            raise RuntimeError(f"{mode}: {name}: {error}") from error
                        fallback_pairs = result.fallback_pairs
                        if pairs and fallback_pairs == len(pairs):
                            raise RuntimeError(f"{mode}: {name}: full Python fallback, Taichi not measured")
                    elif fallback_pairs != result.fallback_pairs:
                        raise RuntimeError(f"{mode}: {name}: fallback count changed")
                if edges != expected_edges or sorter.order_entries(entries, edges) != expected_order:
                    raise RuntimeError(f"{mode}: {name}: directed edges, stable order, or cycle state differ")
                if iteration > warmups:
                    rows.append(row)
            workloads[name] = {
                "camera": asdict(frame.camera), "viewport": asdict(frame.viewport),
                "entries": len(entries), "candidate_pairs": len(pairs), "exact_pairs": len(pairs),
                "taichi_pairs": len(pairs) - fallback_pairs if using_taichi else 0,
                "python_pairs": fallback_pairs if using_taichi else len(pairs),
                "accepted_edges": expected_order[1], "cycle_detected": expected_order[0].cycle_detected,
                "parity": "passed" if using_taichi else "reference",
                "summary": summarize(rows), "raw": rows,
            }
    finally:
        if using_taichi:
            ti.reset()
    return {"cpu_threads": threads, "gpu_backend": gpu, "precision": "float32" if float32 else "float64",
            "depth_tolerance": {"relative": rtol, "absolute": atol},
            "init_ns": init_ns, "first_exact_stage_ns": cold_call_ns, "workloads": workloads}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--threads", type=int, default=max(2, min(8, os.cpu_count() or 2)))
    parser.add_argument("--gpu", choices=("vulkan", "cuda", "dx11"),
                        help="Also test this GPU backend, with no silent CPU fallback")
    parser.add_argument("--gpu-float32", action="store_true", help="Probe GPU float32 instead of float64")
    parser.add_argument("--case", action="append", help="Run only this named workload (repeatable)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1 or args.warmups < 0 or args.threads < 2:
        parser.error("require positive samples, nonnegative warmups, and at least two parallel CPU threads")
    if args.gpu_float32 and not args.gpu:
        parser.error("--gpu-float32 requires --gpu")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    sorter = OverlapDepthSorter(use_coplanar_edge_filter=False)
    cases = prepare_cases(sorter)
    if args.case:
        unknown = set(args.case) - {case[0] for case in cases}
        if unknown:
            parser.error(f"unknown workloads: {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case[0] in args.case]
    gpu = measure(sorter, cases, args.samples, args.warmups, gpu=args.gpu,
                  float32=args.gpu_float32) if args.gpu else None
    reference = measure(sorter, cases, args.samples, args.warmups)
    single = measure(sorter, cases, args.samples, args.warmups, threads=1)
    parallel = measure(sorter, cases, args.samples, args.warmups, threads=args.threads)
    modes = {"python": reference, "taichi_cpu_single": single, "taichi_cpu_parallel": parallel}
    if gpu is not None:
        modes[f"taichi_{args.gpu}"] = gpu
    report = {
        "command": [sys.executable, *sys.argv], "python_version": platform.python_version(),
        "platform": platform.platform(), "logical_cpus": os.cpu_count(), "taichi_version": ti.__version__,
        "samples": args.samples, "warmups": args.warmups,
        "precision": "mixed (see modes)" if args.gpu_float32 else "float64", "coplanar_filter": False,
        "depth_tolerance": None if args.gpu_float32 else {"relative": DEPTH_RTOL, "absolute": DEPTH_ATOL},
        "scope": "exact overlap stage on fixed projected entries; excludes collection, projection, broad phase, "
                 "parity checks, ordering validation, and all drawing. CPU NumPy buffers are passed by reference; "
                 "kernel_sync includes dispatch, GPU transfers when applicable, synchronization, and any "
                 "output dtype conversion; it is not isolated kernel compute.",
        "modes": modes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
    for name, *_ in cases:
        totals = [mode["workloads"][name]["summary"]["exact_stage_ms"]["median"]
                  for mode in (reference, single, parallel)]
        print(f"{name}: Python {totals[0]:.2f} / Taichi 1t {totals[1]:.2f} / "
              f"Taichi {args.threads}t {totals[2]:.2f} ms", flush=True)
        if gpu is not None:
            total = gpu["workloads"][name]["summary"]["exact_stage_ms"]["median"]
            print(f"  Taichi {args.gpu} ({gpu['precision']}): {total:.2f} ms", flush=True)
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
