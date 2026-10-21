"""Opt-in CPU wall-clock telemetry for successfully published scene rebuilds."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
import cProfile
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from threading import get_ident, RLock
from time import perf_counter_ns
from typing import Callable, ParamSpec, Sequence, TYPE_CHECKING, TypedDict, TypeVar

if TYPE_CHECKING:
    from .scene import RenderStats

STAGES = (
    "scene_collection", "projection_clipping", "broad_phase", "exact_tests",
    "topological_ordering", "line_occlusion", "node_creation",
    "back_layer_cleanup", "publication_cleanup",
)
HISTORY_SIZE = 120
P = ParamSpec("P")
T = TypeVar("T")


class StageMeasurements:
    """Sequential exclusive regions; skipped stages are zero nanoseconds."""

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
class DurationSummary:
    latest_ms: float
    mean_ms: float
    p95_ms: float


class TelemetrySample(TypedDict):
    scene_generation: int
    configuration_id: str
    effective_flags: dict[str, bool]
    camera: dict
    viewport: dict
    strategy: str
    capture_mode: str
    durations_ns: dict[str, int]
    counters: dict


def summarize(samples: Sequence[TelemetrySample]) -> dict[str, DurationSummary]:
    """P95 is nearest rank: sorted[ceil(0.95 * N) - 1]."""
    result = {}
    if not samples:
        return result
    for stage in (*STAGES, "unaccounted", "total_rebuild"):
        values = [sample["durations_ns"][stage] for sample in samples]
        result[stage] = DurationSummary(
            values[-1] / 1e6, sum(values) / len(values) / 1e6,
            sorted(values)[math.ceil(0.95 * len(values)) - 1] / 1e6,
        )
    return result


class RenderTelemetry:
    """Owned by one viewport; controls serialize with rebuilds, not GUI frames."""

    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled
        self.paused = False
        self.samples: deque[TelemetrySample] = deque(maxlen=HISTORY_SIZE)
        self.failure_count = 0
        self.last_failure = ""
        self.scene_generation = 0
        self.configuration_id = ""
        self.effective_flags: dict[str, bool] = {}
        self._window_key: str | None = None
        self._lock = RLock()
        self._profile: cProfile.Profile | None = None
        self.capture_active = False
        self._capture_thread: int | None = None
        self._capture_context: deque[dict] = deque(maxlen=HISTORY_SIZE)
        self._capture_attempts = 0

    @property
    def recording(self) -> bool:
        return (self.enabled and not self.paused) or self.capture_active

    @property
    def capture_pending(self) -> bool:
        return self._profile is not None

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = enabled

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self.paused = paused

    def reset(self) -> None:
        with self._lock:
            self.samples.clear()
            self.failure_count = 0
            self.last_failure = ""
            self._window_key = None

    def set_scene(self, generation: int, flags: dict[str, bool]) -> None:
        with self._lock:
            self.scene_generation = generation
            self.effective_flags = dict(flags)
            self.configuration_id = hashlib.sha256(
                json.dumps(flags, sort_keys=True).encode("utf-8")
            ).hexdigest()[:16]
            self.reset()

    def rebuild(
        self,
        action: Callable[[StageMeasurements | None], RenderStats],
        *,
        camera: dict,
        viewport: dict,
        strategy: str,
    ) -> RenderStats:
        with self._lock:
            collect = self.enabled and not self.paused
            profile = self._profile if self.capture_active else None
            if not collect and profile is None:
                return action(None)
            mode = "cprofile" if profile is not None else "baseline"
            context = {
                "scene_generation": self.scene_generation,
                "configuration_id": self.configuration_id,
                "effective_flags": dict(self.effective_flags),
                "camera": camera, "viewport": viewport,
                "strategy": strategy, "capture_mode": mode,
            }
            if profile is not None:
                thread = get_ident()
                if self._capture_thread not in (None, thread):
                    raise RuntimeError("Detailed capture must remain on one render thread")
                self._capture_thread = thread
                self._capture_attempts += 1
                profile.enable()
            stats = None
            try:
                timing = StageMeasurements() if collect else None
                stats = action(timing)
                durations = timing.finish() if timing is not None else None
            except Exception as error:
                self.failure_count += 1
                self.last_failure = f"{type(error).__name__}: {error}"
                context["failure"] = self.last_failure
                raise
            finally:
                if profile is not None:
                    profile.disable()
                    if stats is not None:
                        context["counters"] = asdict(stats)
                    self._capture_context.append(context)
            if durations is not None:
                # Camera motion belongs to a window; changed workloads/modes do not.
                key = json.dumps({k: v for k, v in context.items() if k != "camera"}, sort_keys=True)
                if self._window_key != key:
                    self.samples.clear()
                    self._window_key = key
                self.samples.append({
                    "scene_generation": self.scene_generation,
                    "configuration_id": self.configuration_id,
                    "effective_flags": dict(self.effective_flags),
                    "camera": camera, "viewport": viewport,
                    "strategy": strategy, "capture_mode": mode,
                    "durations_ns": durations, "counters": asdict(stats),
                })
            return stats

    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy({
                "schema_version": 1, "timing_unit": "nanoseconds",
                "history_limit": HISTORY_SIZE, "percentile": "nearest-rank P95",
                "scene_generation": self.scene_generation,
                "configuration_id": self.configuration_id,
                "effective_flags": self.effective_flags,
                "enabled": self.enabled, "paused": self.paused,
                "capture_active": self.capture_active,
                "failure_count": self.failure_count, "last_failure": self.last_failure,
                "samples": list(self.samples),
            })

    def export(self, path: Path) -> None:
        snapshot = self.snapshot()
        if path.suffix.lower() not in (".json", ".csv"):
            raise ValueError("Telemetry export must use .json or .csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            return
        fields = (
            "schema_version", "timing_unit", "scene_generation", "configuration_id",
            "effective_flags", "camera", "viewport", "strategy", "capture_mode",
            "counters", *STAGES, "total_rebuild", "unaccounted",
        )
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for sample in snapshot["samples"]:
                row = {key: value for key, value in sample.items() if key != "durations_ns"}
                row.update(sample["durations_ns"])
                row.update(schema_version=1, timing_unit="nanoseconds")
                for key in ("effective_flags", "camera", "viewport", "counters"):
                    row[key] = json.dumps(row[key], sort_keys=True)
                writer.writerow(row)

    def start_capture(self) -> None:
        with self._lock:
            if self._profile is not None:
                raise RuntimeError("Stop and save the pending capture before starting another")
            self._profile = cProfile.Profile()
            self._capture_thread = None
            self._capture_context.clear()
            self._capture_attempts = 0
            self.capture_active = True

    def stop_and_save(self, path: Path) -> None:
        with self._lock:
            self.capture_active = False
            if self._profile is None:
                raise RuntimeError("No detailed capture to save")
            if self._capture_attempts == 0:
                self._profile = None
                raise RuntimeError("No rebuilds captured; no capture file written")
            if path.suffix.lower() != ".prof":
                raise ValueError("Detailed capture must use .prof")
            path.parent.mkdir(parents=True, exist_ok=True)
            self._profile.dump_stats(str(path))
            metadata = {
                "schema_version": 1, "timing_unit": "seconds",
                "capture_mode": "cprofile", "render_thread": self._capture_thread,
                "attempt_count": self._capture_attempts,
                "context_limit": HISTORY_SIZE,
                "omitted_context_count": max(0, self._capture_attempts - HISTORY_SIZE),
                "contexts": list(self._capture_context),
            }
            path.with_suffix(".prof.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            self._profile = None
