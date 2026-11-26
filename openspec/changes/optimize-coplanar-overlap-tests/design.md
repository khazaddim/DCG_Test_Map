## Context

The sorter uses projected bounding boxes to select candidates, then performs exact screen-space overlap and ray-plane depth checks to build ordering edges. The temple has many separate floor polygons on world plane z=0. One diagnostic view produced 2,707 floor-floor candidates and no floor-floor ordering edges; this is not yet a performance benchmark.

## Goals / Non-Goals

**Goals:**
- Automatically recognize a conservative class of coplanar pairs without author-provided floor flags.
- Preserve the baseline ordering and report actual detailed-test work.
- Measure both correctness and cost on the real temple and representative synthetic cases.

**Non-Goals:**
- Approximate near-coplanar geometry as coplanar.
- Change back-face culling, collision, polygon visibility, line occlusion, or transparency semantics.
- Enable an unproven optimization by default or merge it to main.

## Decisions

- Keep a baseline path and make the experimental path explicitly selectable so the same projected scene can be compared under identical conditions.
- Recognize exactly horizontal world-space planes when projecting with the experiment enabled. For pairs on the same plane, use identical projected edges and the existing separating-axis comparison to prove that the baseline would reject the pair. Do not skip overlapping coplanar faces or infer safety from plane equality alone. Cache projected edge maps per sort.
- Skip a detailed pair test only when the proof is sufficient to preserve the baseline's ordering constraints, including floating-point behavior. Fall back to the existing test for uncertain, degenerate, nearly coplanar, or unsupported geometry. Shared edges alone do not prove safety for folded surfaces.
- Preserve stable ordering, cycle behavior, and all emitted geometry. Tests must compare both paths, including overlapping coplanar faces, edge-adjacent tiles, folded neighbors, nearly coplanar planes, clipped faces, and translucent or otherwise order-sensitive geometry. If the proof cannot maintain compatibility for a case, do not skip it.
- Keep candidate counts distinct from detailed tests actually executed and expose skipped work accurately.
- Benchmark the organic frozen temple at multiple documented camera settings and a non-floor workload, with sequential baseline and experimental runs, matching setup and multiple samples. Report counts and timing as observations, not guaranteed speedups.

## Risks / Trade-offs

- Floating-point calculations in the existing depth test may produce an edge even for mathematically coplanar faces -> compare actual baseline results and fall back whenever equivalence cannot be established.
- Per-face recognition and bookkeeping can cost more than saved pair tests -> measure total sorting and stage cost as well as counts.
- Incorrect assumptions about touching, winding, clipping, or material ordering could create visual regressions -> use conservative eligibility and differential tests; visually inspect representative views where available.

## Experiment results

The filter is disabled by default. From the repository root, the measured
comparison used:

```powershell
.\.venv\Scripts\python.exe Animation\ported_demos\benchmark_coplanar_filter.py --samples 5 --warmups 1 --output profiling-output\coplanar-filter-comparison-20261126.json
```

The interpreter was `.venv\Scripts\python.exe` (Python 3.14.0, Windows 11,
GC enabled). Each case ran the baseline followed by the experiment, without
concurrent tests or benchmarks. Timings are CPU-side wall time in milliseconds
for instrumented sorting; scene construction, drawing-node emission,
publication, display, and interactive FPS are excluded. The temple viewport is
900 by 600, target is the starting avatar position, and pitch is 52 degrees.
The synthetic workload is the existing 500-face pipeline fixture without lines.
The JSON report includes raw samples, camera and viewport details, packet and
projected counts, collection and projection times, and stage timings.

| View | Candidates | Skipped | Sort median baseline / experiment (ms) | Sort P95 baseline / experiment (ms) |
| --- | ---: | ---: | ---: | ---: |
| Temple yaw 0, zoom 3.5 | 2,760 | 287 | 53.87 / 57.07 | 60.16 / 60.15 |
| Temple yaw 0, zoom 1.0 | 25,631 | 1,026 | 1,068.44 / 936.91 | 1,544.57 / 1,306.12 |
| Temple yaw 0, zoom 0.25 | 35,823 | 1,971 | 918.09 / 947.09 | 928.17 / 1,156.11 |
| Temple yaw 90, zoom 1.0 | 20,306 | 1,053 | 482.00 / 526.92 | 774.73 / 547.89 |
| Synthetic 500 | 750 | 0 | 57.53 / 56.62 | 67.07 / 59.91 |

Ordering and cycle state matched for all measured samples; accepted edge counts
also matched. The dedicated differential tests compare actual edge sets for
three temple views. With five samples the nearest-rank P95 is the maximum.
Sequential timing is sensitive to drift, and separate runs varied substantially;
the mixed results do not establish a speedup. Test again on a quiet machine,
including real interactive views, before enabling or merging the optimization.

The relevant regression run passed 158 tests with two pre-existing unrelated
failures excluded: demo 11's road line-occluder expectation and the selected
open-room world-module expectation. The unfiltered run reported those two
failures and 150 passing tests before the additional near-plane test was added.
