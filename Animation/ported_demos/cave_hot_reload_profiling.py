"""Launch the reloadable cave with the shared CPU profiling panel."""

from __future__ import annotations

from pathlib import Path
import sys

import dearcygui as dcg

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Animation.draw_in_window_3d_framework.profiling_panel import ProfilingPanel
from Animation.ported_demos import cave_hot_reload_world as world
from Animation.ported_demos import town_hot_reload as host
from Animation.ported_demos import town_hot_reload_profiling as profiling_host


OUTPUT_DIRECTORY = REPO_ROOT / "profiling-output" / "cave"


def build_ui(context: dcg.Context) -> tuple[host.HotReloadTownController, ProfilingPanel]:
    return profiling_host.build_ui(context, world_module=world, output_directory=OUTPUT_DIRECTORY)


def main() -> None:
    profiling_host.main(
        world_module=world, output_directory=OUTPUT_DIRECTORY,
        title="DCG Test Map - Cave CPU profiling",
    )


if __name__ == "__main__":
    main()
