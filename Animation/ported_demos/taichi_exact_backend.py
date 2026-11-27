"""Launch-owned Taichi backend adapter for renderer exact overlap tests."""

from __future__ import annotations

from importlib import import_module
from time import perf_counter_ns
from typing import Sequence
import warnings

from Animation.draw_in_window_3d_framework.scene import (
    ExactTestOutcome,
    FrameContext,
    ProjectedRenderEntry,
    _python_exact_test_outcome,
)


class TaichiExactBackend:
    """Initialize Taichi once and fall back to complete Python batches on backend failure."""

    def __init__(self) -> None:
        self._evaluator = None
        self._taichi_errors: tuple[type[BaseException], ...] = ()
        self._disabled_diagnostic = ""
        self._initialization_ns = 0
        self._first_use_ns = 0
        start = perf_counter_ns()
        try:
            evaluator = import_module("Animation.ported_demos.taichi_exact_eval")
        except ImportError as error:
            self._initialization_ns = perf_counter_ns() - start
            self._disable(
                f"Taichi exact tests unavailable: {type(error).__name__}: {error}"
            )
            return

        self._taichi_errors = tuple(
            error_type
            for error_type in (
                getattr(evaluator.ti, "TaichiRuntimeError", None),
                getattr(evaluator.ti, "TaichiCompilationError", None),
                getattr(evaluator.ti, "TaichiSyntaxError", None),
                getattr(evaluator.ti, "TaichiTypeError", None),
                getattr(evaluator.ti, "TaichiAssertionError", None),
            )
            if isinstance(error_type, type) and issubclass(error_type, BaseException)
        )
        try:
            evaluator.ti.init(
                arch=evaluator.ti.cpu,
                cpu_max_num_threads=1,
                default_fp=evaluator.ti.f64,
                fast_math=False,
                offline_cache=False,
                enable_fallback=False,
            )
        except (ImportError, RuntimeError) as error:
            self._initialization_ns = perf_counter_ns() - start
            self._disable(
                f"Taichi exact tests could not initialize: {type(error).__name__}: {error}"
            )
            return
        except self._taichi_errors as error:
            self._initialization_ns = perf_counter_ns() - start
            self._disable(
                f"Taichi exact tests could not initialize: {type(error).__name__}: {error}"
            )
            return

        self._initialization_ns = perf_counter_ns() - start
        self._evaluator = evaluator

    @property
    def enabled(self) -> bool:
        return self._evaluator is not None

    def _disable(self, diagnostic: str) -> None:
        self._evaluator = None
        self._disabled_diagnostic = diagnostic
        warnings.warn(diagnostic, RuntimeWarning, stacklevel=2)

    @staticmethod
    def _python_outcome(
        entries: Sequence[ProjectedRenderEntry],
        candidate_pairs: Sequence[tuple[int, int]],
        frame: FrameContext,
        *,
        overlap_area_epsilon: float,
        depth_epsilon: float,
        diagnostic: str,
        initialization_ns: int,
        first_use_ns: int,
        fallback: bool,
    ) -> ExactTestOutcome:
        pair_count = len(candidate_pairs)
        return _python_exact_test_outcome(
            entries,
            candidate_pairs,
            frame,
            overlap_area_epsilon=overlap_area_epsilon,
            depth_epsilon=depth_epsilon,
            fallback_pair_count=pair_count if fallback else 0,
            diagnostic=diagnostic,
            initialization_ns=initialization_ns,
            first_use_ns=first_use_ns,
        )

    def test_overlaps(
        self,
        entries: Sequence[ProjectedRenderEntry],
        candidate_pairs: Sequence[tuple[int, int]],
        frame: FrameContext,
        *,
        overlap_area_epsilon: float,
        depth_epsilon: float,
    ) -> ExactTestOutcome:
        if self._evaluator is None:
            return self._python_outcome(
                entries,
                candidate_pairs,
                frame,
                overlap_area_epsilon=overlap_area_epsilon,
                depth_epsilon=depth_epsilon,
                diagnostic=self._disabled_diagnostic,
                initialization_ns=self._initialization_ns,
                first_use_ns=self._first_use_ns,
                fallback=bool(self._disabled_diagnostic),
            )

        start = perf_counter_ns()
        try:
            result = self._evaluator.evaluate(
                entries,
                candidate_pairs,
                frame,
                overlap_area_epsilon,
            )
        except self._taichi_errors as error:
            first_use_ns = perf_counter_ns() - start
            if not self._first_use_ns:
                self._first_use_ns = first_use_ns
            diagnostic = (
                f"Taichi exact tests disabled after {type(error).__name__}: {error}; "
                "the incomplete batch was discarded and evaluated in Python"
            )
            self._disable(diagnostic)
            return self._python_outcome(
                entries,
                candidate_pairs,
                frame,
                overlap_area_epsilon=overlap_area_epsilon,
                depth_epsilon=depth_epsilon,
                diagnostic=diagnostic,
                initialization_ns=self._initialization_ns,
                first_use_ns=self._first_use_ns,
                fallback=True,
            )

        elapsed_ns = perf_counter_ns() - start
        if not self._first_use_ns:
            self._first_use_ns = elapsed_ns
        edges = result.edges(candidate_pairs, depth_epsilon)
        python_pairs = result.fallback_pairs
        taichi_pairs = len(candidate_pairs) - python_pairs
        diagnostic = (
            f"{python_pairs} unsupported pair(s) evaluated in Python"
            if python_pairs
            else ""
        )
        return ExactTestOutcome(
            edges=edges,
            exact_backend=(
                "mixed" if taichi_pairs and python_pairs
                else "taichi" if taichi_pairs
                else "python"
            ),
            taichi_pair_count=taichi_pairs,
            python_pair_count=python_pairs,
            fallback_pair_count=python_pairs,
            diagnostic=diagnostic,
            initialization_ns=self._initialization_ns,
            first_use_ns=self._first_use_ns,
        )
