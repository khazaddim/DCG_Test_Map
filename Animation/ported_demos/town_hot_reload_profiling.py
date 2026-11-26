"""Town host with optional CPU rebuild telemetry and detailed captures."""

from __future__ import annotations

from pathlib import Path
import sys
import traceback
from types import ModuleType

import dearcygui as dcg

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework.profiling import RenderTelemetry
from Animation.draw_in_window_3d_framework.profiling_panel import ProfilingPanel
from Animation.ported_demos import town_hot_reload as host

USE_SWEEP_AND_PRUNE = host.USE_SWEEP_AND_PRUNE


def build_ui(
    context: dcg.Context, *, world_module: ModuleType | None = None,
    output_directory: Path = REPO_ROOT / "profiling-output" / "town",
) -> tuple[host.HotReloadTownController, ProfilingPanel]:
    telemetry = RenderTelemetry()
    controller = host.build_ui(
        context, telemetry=telemetry, use_sweep_and_prune=USE_SWEEP_AND_PRUNE,
        primary=False, world_module=world_module,
    )
    panel = ProfilingPanel(
        context, telemetry, output_directory=output_directory,
    )
    panel.window.x = host.VIEW_W + 80
    panel.window.y = 0
    panel.window.height = "filly"
    return controller, panel


def main(
    *, world_module: ModuleType | None = None,
    output_directory: Path = REPO_ROOT / "profiling-output" / "town",
    title: str = "DCG Test Map - Town CPU profiling",
) -> None:
    context = dcg.Context()
    context.viewport.initialize(
        title=title,
        width=host.VIEW_W + 740, height=host.VIEW_H + 340,
    )
    controller, panel = build_ui(context, world_module=world_module, output_directory=output_directory)
    try:
        while context.running:
            panel.process_actions()
            revision = controller.viewport.last_render_revision
            try:
                controller.render_if_needed()
            except Exception as error:
                panel.message.value = f"Rebuild failed: {type(error).__name__}: {error}"
                traceback.print_exc()
                # Retry only after the next user invalidation, not every idle frame.
                controller.viewport._dirty = False
            panel.refresh(rebuilt=controller.viewport.last_render_revision != revision)
            context.viewport.render_frame()
    finally:
        panel.shutdown()


if __name__ == "__main__":
    main()
