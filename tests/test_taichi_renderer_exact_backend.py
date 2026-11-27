from __future__ import annotations

from types import SimpleNamespace

import pytest

import dearcygui as dcg
from Animation.draw_in_window_3d_framework import CpuRenderer3D, OverlapDepthSorter
from Animation.ported_demos import taichi_exact_backend
from Animation.ported_demos import town_hot_reload_profiling
from Animation.ported_demos import town_hot_reload_world
from Animation.ported_demos.benchmark_pipeline import build_fixture


class FakeTaichiRuntimeError(RuntimeError):
    pass


class FakeTaichi:
    cpu = object()
    f64 = object()
    TaichiRuntimeError = FakeTaichiRuntimeError
    TaichiCompilationError = type("FakeTaichiCompilationError", (Exception,), {})

    def __init__(self, *, init_error: Exception | None = None) -> None:
        self.init_error = init_error
        self.init_calls = 0

    def init(self, **_kwargs) -> None:
        self.init_calls += 1
        if self.init_error is not None:
            raise self.init_error


class FakeEvaluation:
    def __init__(self, edges, fallback_pairs: int) -> None:
        self.fallback_pairs = fallback_pairs
        self._edges = edges

    def edges(self, _pairs, _depth_epsilon):
        return self._edges


def projected_fixture():
    fixture = build_fixture(100, include_lines=False)
    renderer = CpuRenderer3D()
    entries, _ = renderer.project_packets(
        renderer.collect_packets(fixture.scene, fixture.frame),
        fixture.frame,
    )
    expected_edges = OverlapDepthSorter().test_overlaps(
        entries,
        OverlapDepthSorter().generate_candidates(entries)[0],
        fixture.frame,
    )
    return fixture, entries, expected_edges


def install_fake_evaluator(monkeypatch, evaluator) -> None:
    monkeypatch.setattr(taichi_exact_backend, "import_module", lambda _name: evaluator)


def test_default_profiling_option_keeps_python_backend_without_initializing_taichi(monkeypatch) -> None:
    def unexpected_import(_name):
        raise AssertionError("Taichi evaluator must not be imported by the default launch path")

    monkeypatch.setattr(taichi_exact_backend, "import_module", unexpected_import)

    assert not town_hot_reload_profiling.parse_args([]).taichi_exact_tests
    assert town_hot_reload_profiling.parse_args(["--taichi-exact-tests"]).taichi_exact_tests
    assert not town_hot_reload_profiling.parse_args([]).no_reuse_camera_transforms
    assert town_hot_reload_profiling.parse_args(["--no-reuse-camera-transforms"]).no_reuse_camera_transforms
    assert OverlapDepthSorter().exact_test_backend is None


@pytest.mark.parametrize("argv,expected", (([], True), (["--no-reuse-camera-transforms"], False)))
def test_profiling_main_routes_camera_transform_option(monkeypatch, argv, expected) -> None:
    received = {}
    context = SimpleNamespace(viewport=SimpleNamespace(initialize=lambda **_kwargs: None), running=False)
    panel = SimpleNamespace(shutdown=lambda: None)
    monkeypatch.setattr(town_hot_reload_profiling.dcg, "Context", lambda: context)

    def build_ui(_context, **kwargs):
        received.update(kwargs)
        return object(), panel

    monkeypatch.setattr(town_hot_reload_profiling, "build_ui", build_ui)
    town_hot_reload_profiling.main(argv=argv)

    assert received["reuse_camera_transforms"] is expected


def test_taichi_backend_reports_mixed_pair_counts_and_reuses_runtime(monkeypatch) -> None:
    fixture, entries, expected_edges = projected_fixture()
    fake_ti = FakeTaichi()
    evaluate_calls = 0

    def evaluate(*_args):
        nonlocal evaluate_calls
        evaluate_calls += 1
        return FakeEvaluation(expected_edges, fallback_pairs=1)

    install_fake_evaluator(monkeypatch, SimpleNamespace(ti=fake_ti, evaluate=evaluate))
    backend = taichi_exact_backend.TaichiExactBackend()
    sorter = OverlapDepthSorter(exact_test_backend=backend)

    first = sorter.sort(entries, fixture.frame)
    first_stats = first.sort_stats
    second = sorter.sort(entries, fixture.frame)
    second_stats = second.sort_stats

    assert fake_ti.init_calls == 1
    assert evaluate_calls == 2
    assert first_stats is not None and second_stats is not None
    assert first_stats.exact_backend == "mixed"
    assert first_stats.taichi_pair_count + first_stats.python_pair_count == first_stats.exact_test_count
    assert first_stats.taichi_pair_count > 0
    assert first_stats.python_pair_count == first_stats.fallback_pair_count == 1
    assert "unsupported pair" in first_stats.backend_diagnostic
    assert second_stats.backend_first_use_ns == first_stats.backend_first_use_ns


def test_taichi_runtime_failure_discards_batch_and_disables_future_calls(monkeypatch) -> None:
    fixture, entries, expected_edges = projected_fixture()
    fake_ti = FakeTaichi()
    evaluate_calls = 0

    def fail_evaluate(*_args):
        nonlocal evaluate_calls
        evaluate_calls += 1
        raise FakeTaichiRuntimeError("kernel launch failed")

    install_fake_evaluator(
        monkeypatch,
        SimpleNamespace(ti=fake_ti, evaluate=fail_evaluate),
    )
    with pytest.warns(RuntimeWarning, match="incomplete batch was discarded"):
        backend = taichi_exact_backend.TaichiExactBackend()
        sorter = OverlapDepthSorter(exact_test_backend=backend)
        first = sorter.sort(entries, fixture.frame)
        second = sorter.sort(entries, fixture.frame)

    assert evaluate_calls == 1
    assert fake_ti.init_calls == 1
    for result in (first, second):
        assert result.sort_stats is not None
        assert result.sort_stats.exact_backend == "python"
        assert result.sort_stats.taichi_pair_count == 0
        assert result.sort_stats.python_pair_count == result.sort_stats.exact_test_count
        assert result.sort_stats.fallback_pair_count == result.sort_stats.exact_test_count
        assert "kernel launch failed" in result.sort_stats.backend_diagnostic
        assert [entry.stable_index for entry in result.entries] == [
            entry.stable_index for entry in OverlapDepthSorter().sort(entries, fixture.frame).entries
        ]
    assert first.sort_stats is not None
    assert first.sort_stats.backend_first_use_ns > 0


def test_taichi_initialization_failure_uses_python(monkeypatch) -> None:
    fixture, entries, _ = projected_fixture()
    fake_ti = FakeTaichi(init_error=RuntimeError("CPU runtime unavailable"))
    evaluate_calls = 0

    def unexpected_evaluate(*_args):
        nonlocal evaluate_calls
        evaluate_calls += 1
        raise AssertionError("failed initialization must not run Taichi")

    install_fake_evaluator(
        monkeypatch,
        SimpleNamespace(ti=fake_ti, evaluate=unexpected_evaluate),
    )
    with pytest.warns(RuntimeWarning, match="could not initialize"):
        backend = taichi_exact_backend.TaichiExactBackend()
    result = OverlapDepthSorter(exact_test_backend=backend).sort(entries, fixture.frame)

    assert evaluate_calls == 0
    assert result.sort_stats is not None
    assert result.sort_stats.exact_backend == "python"
    assert result.sort_stats.python_pair_count == result.sort_stats.exact_test_count
    assert result.sort_stats.fallback_pair_count == result.sort_stats.exact_test_count
    assert "CPU runtime unavailable" in result.sort_stats.backend_diagnostic


def test_missing_taichi_dependency_is_reported_and_uses_python(monkeypatch) -> None:
    fixture, entries, _ = projected_fixture()

    def missing_dependency(_name):
        raise ModuleNotFoundError("No module named 'taichi'", name="taichi")

    monkeypatch.setattr(taichi_exact_backend, "import_module", missing_dependency)
    with pytest.warns(RuntimeWarning, match="Taichi exact tests unavailable"):
        backend = taichi_exact_backend.TaichiExactBackend()
    result = OverlapDepthSorter(exact_test_backend=backend).sort(entries, fixture.frame)

    assert result.sort_stats is not None
    assert result.sort_stats.exact_backend == "python"
    assert result.sort_stats.python_pair_count == result.sort_stats.exact_test_count
    assert result.sort_stats.fallback_pair_count == result.sort_stats.exact_test_count
    assert "ModuleNotFoundError" in result.sort_stats.backend_diagnostic


def test_unrecognized_evaluator_error_is_not_swallowed(monkeypatch) -> None:
    fixture, entries, _ = projected_fixture()
    fake_ti = FakeTaichi()

    def fail_with_application_error(*_args):
        raise ValueError("invalid projected entry")

    install_fake_evaluator(
        monkeypatch,
        SimpleNamespace(ti=fake_ti, evaluate=fail_with_application_error),
    )
    backend = taichi_exact_backend.TaichiExactBackend()
    sorter = OverlapDepthSorter(exact_test_backend=backend)

    with pytest.raises(ValueError, match="invalid projected entry"):
        sorter.sort(entries, fixture.frame)


def test_backend_instance_survives_world_reload(monkeypatch, tmp_path) -> None:
    fake_ti = FakeTaichi()
    install_fake_evaluator(
        monkeypatch,
        SimpleNamespace(ti=fake_ti, evaluate=lambda *_args: None),
    )
    backend = taichi_exact_backend.TaichiExactBackend()
    context = dcg.Context()
    controller, panel = town_hot_reload_profiling.build_ui(
        context,
        world_module=town_hot_reload_world,
        exact_test_backend=backend,
        reuse_camera_transforms=False,
        output_directory=tmp_path,
    )
    sorter = controller.viewport.renderer.sorter

    assert controller.viewport.telemetry is not None
    assert controller.viewport.telemetry.enabled
    controller._reload_world()

    assert controller.reload_status.value == "Reloaded world definition."
    assert controller.viewport.renderer.sorter is sorter
    assert sorter.exact_test_backend is backend
    assert not controller.viewport.renderer.reuse_camera_transforms
    assert fake_ti.init_calls == 1
    panel.window.delete_item()
