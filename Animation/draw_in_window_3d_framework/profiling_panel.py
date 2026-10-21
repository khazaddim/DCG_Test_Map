"""DearCyGui telemetry controls; never owns or invalidates a scene."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from time import perf_counter
import traceback
from uuid import uuid4

import dearcygui as dcg

from .profiling import RenderTelemetry, STAGES, summarize


class ProfilingPanel:
    def __init__(
        self, context: dcg.Context, telemetry: RenderTelemetry, *,
        output_directory: Path, parent: dcg.baseItem | None = None,
    ) -> None:
        self.telemetry = telemetry
        self.output_directory = output_directory
        self._actions: SimpleQueue[str] = SimpleQueue()
        self._last_refresh = float("-inf")
        self._rebuilt_since_refresh = False
        self._capture_path: Path | None = None
        self.last_update_ms = 0.0
        self.window = dcg.Window(
            context, parent=parent, label="CPU rebuild profiling",
            width=660, height=750,
        )
        self.status = dcg.Text(context, parent=self.window, value="Telemetry disabled")
        self.message = dcg.Text(context, parent=self.window, value="Outputs: " + str(output_directory))
        controls = (
            ("Enable / disable telemetry", "enable"),
            ("Pause / resume telemetry", "pause"),
            ("Reset rolling window", "reset"),
            ("Start capture", "start"),
            ("Stop and save / retry save", "stop"),
            ("Export JSON", "json"),
            ("Export CSV", "csv"),
        )
        for start in range(0, len(controls), 3):
            row = dcg.HorizontalLayout(context, parent=self.window)
            for label, action in controls[start:start + 3]:
                dcg.Button(
                    context, parent=row, label=label,
                    callback=lambda *_, action=action: self.request(action),
                )
        self.configuration = dcg.Text(context, parent=self.window, value="")
        self.counters = dcg.Text(context, parent=self.window, value="")
        self.total = dcg.Text(context, parent=self.window, value="No successful rebuild samples")
        dcg.Text(context, parent=self.window, value="Ranked mean bars; latest / mean / P95 (ms)")
        self.bars = [
            dcg.ProgressBar(context, parent=self.window, width="fillx", overlay=stage, value=0.0)
            for stage in (*STAGES, "unaccounted")
        ]

    def request(self, action: str) -> None:
        self._actions.put(action)

    def _new_path(self, suffix: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.output_directory / f"town-{stamp}-{uuid4().hex[:8]}{suffix}"

    def process_actions(self) -> None:
        """Call on the host render thread, outside any measured rebuild."""
        while True:
            try:
                action = self._actions.get_nowait()
            except Empty:
                return
            try:
                if action == "enable":
                    self.telemetry.set_enabled(not self.telemetry.enabled)
                elif action == "pause":
                    self.telemetry.set_paused(not self.telemetry.paused)
                elif action == "reset":
                    self.telemetry.reset()
                elif action == "start":
                    self.telemetry.start_capture()
                    self._capture_path = self._new_path(".prof")
                    self.message.value = "Detailed capture started; telemetry is marked cprofile."
                elif action == "stop":
                    self.save_capture()
                elif action in ("json", "csv"):
                    path = self._new_path("." + action)
                    self.telemetry.export(path)
                    self.message.value = "Saved " + str(path)
                else:
                    raise ValueError(f"Unknown profiling action: {action}")
            except (OSError, ValueError, RuntimeError) as error:
                self.message.value = f"Profiling action failed: {type(error).__name__}: {error}"
                traceback.print_exc()

    def save_capture(self) -> None:
        if self._capture_path is None:
            raise RuntimeError("No capture has been started")
        self.telemetry.stop_and_save(self._capture_path)
        self.message.value = "Saved " + str(self._capture_path)
        self._capture_path = None

    def shutdown(self) -> None:
        self.process_actions()
        if self.telemetry.capture_pending:
            self.request("stop")
            self.process_actions()

    def refresh(self, *, rebuilt: bool = False, now: float | None = None) -> bool:
        self._rebuilt_since_refresh |= rebuilt
        now = perf_counter() if now is None else now
        if now - self._last_refresh < 0.2:
            return False
        start = perf_counter()
        self._last_refresh = now
        snapshot = self.telemetry.snapshot()
        samples = snapshot["samples"]
        summaries = summarize(samples)
        state = "enabled" if snapshot["enabled"] else "disabled"
        if snapshot["paused"]:
            state += " / paused"
        activity = "rebuilt" if self._rebuilt_since_refresh else "idle"
        mode = samples[-1]["capture_mode"] if samples else "no samples"
        self.status.value = (
            f"Telemetry {state} | {activity} | {len(samples)}/120 samples ({mode})\n"
            f"Capture: {'ACTIVE' if snapshot['capture_active'] else 'off'} | "
            f"failed rebuilds: {snapshot['failure_count']} | panel: {self.last_update_ms:.2f} ms\n"
            f"{snapshot['last_failure']}"
        )
        self._rebuilt_since_refresh = False
        flag_values = [
            f"{key.removesuffix('_ENABLED')}: {'on' if value else 'off'}"
            for key, value in sorted(snapshot["effective_flags"].items())
        ]
        flags = "\n".join(
            " | ".join(flag_values[start:start + 3])
            for start in range(0, len(flag_values), 3)
        )
        self.configuration.value = (
            f"Scene generation {snapshot['scene_generation']} | config {snapshot['configuration_id']}\n"
            f"Effective flags (_ENABLED):\n{flags}"
        )
        if samples:
            sample = samples[-1]
            counts = sample["counters"]
            sort = counts["sort_stats"] or {}
            self.counters.value = (
                f"Strategy: {sample['strategy']} | packets {counts['packet_count']} | "
                f"projected {counts['projected_count']} | emitted {counts['emitted_count']}\n"
                f"candidates {sort.get('bounds_candidate_pair_count', 0)} | "
                f"exact {sort.get('exact_test_count', 0)} | edges {sort.get('accepted_edge_count', 0)} | "
                f"cycle {counts['cycle_detected']}"
            )
            total = summaries["total_rebuild"]
            self.total.value = (
                f"Total latest / mean / P95: {total.latest_ms:.3f} / {total.mean_ms:.3f} / {total.p95_ms:.3f} ms"
            )
        else:
            self.counters.value = ""
            self.total.value = "No successful rebuild samples"
        ranked = sorted(
            ((stage, value) for stage, value in summaries.items() if stage != "total_rebuild"),
            key=lambda item: item[1].mean_ms, reverse=True,
        )
        maximum = ranked[0][1].mean_ms if ranked else 0.0
        for index, bar in enumerate(self.bars):
            if index < len(ranked):
                stage, value = ranked[index]
                bar.value = value.mean_ms / maximum if maximum else 0.0
                bar.overlay = f"{stage}: {value.latest_ms:.3f} / {value.mean_ms:.3f} / {value.p95_ms:.3f} ms"
            else:
                bar.value = 0.0
                bar.overlay = "No samples"
        self.last_update_ms = (perf_counter() - start) * 1000.0
        return True
