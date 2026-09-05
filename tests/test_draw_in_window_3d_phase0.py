from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import dearcygui as dcg


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "Animation"
    / "draw_in_window_3d_framework"
    / "widget.py"
)


def load_widget_module():
    spec = importlib.util.spec_from_file_location("dcg_phase0_widget", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_viewport(module):
    context = dcg.Context()
    with dcg.Window(context, label="phase-0", width=320, height=240):
        with module.DrawInWindow3D(context, width=220, height=140) as viewport:
            yielded = viewport
    return context, yielded


def test_draw_in_window_3d_is_draw_in_window_subclass():
    module = load_widget_module()
    _context, viewport = build_viewport(module)

    assert isinstance(viewport, module.DrawInWindow3D)
    assert isinstance(viewport, dcg.DrawInWindow)


def test_replace_polygon_swaps_visible_and_hidden_layers():
    module = load_widget_module()
    _context, viewport = build_viewport(module)

    first_revision = viewport.replace_polygon(((10.0, 110.0), (110.0, 10.0), (210.0, 110.0)))
    assert first_revision == 1
    assert viewport.displayed_layer.show is True
    assert viewport.back_layer.show is False
    assert len(viewport.displayed_layer.children) == 1
    assert len(viewport.back_layer.children) == 0

    second_revision = viewport.replace_polygon(((25.0, 115.0), (115.0, 20.0), (205.0, 115.0)))
    assert second_revision == 2
    assert viewport.displayed_layer.show is True
    assert viewport.back_layer.show is False
    assert len(viewport.displayed_layer.children) == 1
    assert len(viewport.back_layer.children) == 0