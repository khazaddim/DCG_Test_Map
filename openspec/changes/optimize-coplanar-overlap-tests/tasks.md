## 1. Correctness and implementation

- [x] 1.1 Add focused baseline-versus-experimental cases for adjacent and overlapping coplanar polygons, folded and nearly coplanar neighbors, clipping, and order-sensitive materials.
- [x] 1.2 Implement opt-in automatic conservative plane recognition and pair filtering, preserving the baseline for uncertain cases.
- [x] 1.3 Report candidate pairs, executed detailed tests, and skipped pairs accurately, without changing scene collision or rendering semantics.

## 2. Validation and measurement

- [x] 2.1 Run focused tests and relevant existing sorter and temple tests, including differential ordering and cycle checks.
- [x] 2.2 Measure baseline and experimental sorters sequentially on matching organic temple camera views and a non-floor workload, with warmups and multiple samples.
- [x] 2.3 Document commands, settings, counts, timing distributions, correctness results, limitations, and whether the experiment is worthwhile.
