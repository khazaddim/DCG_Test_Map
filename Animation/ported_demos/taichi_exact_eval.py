"""Experimental, headless CPU implementation of the exact overlap stage."""

from dataclasses import dataclass
from time import perf_counter_ns

import numpy as np
import taichi as ti

from Animation.draw_in_window_3d_framework.math3d import dot
from Animation.draw_in_window_3d_framework.scene import (
    _SCREEN_OVERLAP_EPSILON,
    _plane_from_camera_points,
    overlapping_polygon_depths,
)


MAX_VERTICES = 16
CLIP_CAPACITY = 2 * MAX_VERTICES
BATCH_SIZE = 8192


@ti.func
def axis_bounds(points: ti.template(), index, count, ax, ay):
    low = points[index, 0, 0] * ax + points[index, 0, 1] * ay
    high = low
    for i in range(1, count):
        value = points[index, i, 0] * ax + points[index, i, 1] * ay
        low = ti.min(low, value)
        high = ti.max(high, value)
    return low, high


@ti.func
def separated(points: ti.template(), a, b, na, nb, epsilon):
    reject = False
    for source in range(2):
        index, count = a, na
        if source == 1:
            index, count = b, nb
        for i in range(count):
            j = (i + 1) % count
            ax = -(points[index, j, 1] - points[index, i, 1])
            ay = points[index, j, 0] - points[index, i, 0]
            lo_a, hi_a = axis_bounds(points, a, na, ax, ay)
            lo_b, hi_b = axis_bounds(points, b, nb, ax, ay)
            if hi_a < lo_b + epsilon or hi_b < lo_a + epsilon:
                reject = True
                break
        if reject:
            break
    return reject


@ti.func
def cross2(ax, ay, bx, by):
    return ax * by - ay * bx


@ti.func
def clip_polygon(points: ti.template(), scratch: ti.template(), row, a, b, na, nb):
    count, slot = na, 0
    for i in range(na):
        scratch[row, slot, i, 0] = points[a, i, 0]
        scratch[row, slot, i, 1] = points[a, i, 1]
    area = 0.0
    for i in range(nb):
        j = (i + 1) % nb
        area += cross2(points[b, i, 0], points[b, i, 1], points[b, j, 0], points[b, j, 1])
    orientation = 1.0 if area >= 0.0 else -1.0
    for i in range(nb):
        if count <= 0:
            break
        j = (i + 1) % nb
        cx, cy = points[b, i, 0], points[b, i, 1]
        ex, ey = points[b, j, 0] - cx, points[b, j, 1] - cy
        px, py = scratch[row, slot, count - 1, 0], scratch[row, slot, count - 1, 1]
        previous_inside = orientation * cross2(ex, ey, px - cx, py - cy) >= -1e-7
        next_count, next_slot = 0, 1 - slot
        for k in range(count):
            x, y = scratch[row, slot, k, 0], scratch[row, slot, k, 1]
            inside = orientation * cross2(ex, ey, x - cx, y - cy) >= -1e-7
            if inside != previous_inside:
                if next_count == CLIP_CAPACITY:
                    next_count = -1
                    break
                dx, dy = x - px, y - py
                denominator = cross2(dx, dy, ex, ey)
                ix, iy = x, y
                if ti.abs(denominator) > 1e-12:
                    amount = cross2(cx - px, cy - py, ex, ey) / denominator
                    ix, iy = px + amount * dx, py + amount * dy
                scratch[row, next_slot, next_count, 0] = ix
                scratch[row, next_slot, next_count, 1] = iy
                next_count += 1
            if inside:
                if next_count == CLIP_CAPACITY:
                    next_count = -1
                    break
                scratch[row, next_slot, next_count, 0] = x
                scratch[row, next_slot, next_count, 1] = y
                next_count += 1
            px, py, previous_inside = x, y, inside
        count, slot = next_count, next_slot
    return count, slot


@ti.kernel
def evaluate_kernel(
    points: ti.types.ndarray(dtype=ti.f64, ndim=3),
    counts: ti.types.ndarray(dtype=ti.i32, ndim=1),
    planes: ti.types.ndarray(dtype=ti.f64, ndim=2),
    pairs: ti.types.ndarray(dtype=ti.i32, ndim=2),
    scratch: ti.types.ndarray(dtype=ti.f64, ndim=4),
    statuses: ti.types.ndarray(dtype=ti.i32, ndim=1),
    depths: ti.types.ndarray(dtype=ti.f64, ndim=2),
    center_x: ti.f64, center_y: ti.f64, focal: ti.f64, near: ti.f64, area_epsilon: ti.f64,
    axis_epsilon: ti.f64,
):
    for row in range(pairs.shape[0]):
        a, b = pairs[row, 0], pairs[row, 1]
        na, nb = counts[a], counts[b]
        statuses[row] = 0
        if na < 0 or nb < 0:
            statuses[row] = -1
        elif na >= 3 and nb >= 3 and not separated(points, a, b, na, nb, axis_epsilon):
            count, slot = clip_polygon(points, scratch, row, a, b, na, nb)
            if count < 0:
                statuses[row] = -1
            elif count >= 3:
                area, sum_x, sum_y = 0.0, 0.0, 0.0
                for i in range(count):
                    j = (i + 1) % count
                    x, y = scratch[row, slot, i, 0], scratch[row, slot, i, 1]
                    area += cross2(x, y, scratch[row, slot, j, 0], scratch[row, slot, j, 1])
                    sum_x += x
                    sum_y += y
                if ti.abs(area * 0.5) > area_epsilon:
                    rx = (sum_x / count - center_x) / focal
                    ry = (sum_y / count - center_y) / focal
                    da = planes[a, 0] * rx + planes[a, 1] * ry + planes[a, 2]
                    db = planes[b, 0] * rx + planes[b, 1] * ry + planes[b, 2]
                    if ti.abs(da) > 1e-12 and ti.abs(db) > 1e-12:
                        za, zb = planes[a, 3] / da, planes[b, 3] / db
                        if za >= near and zb >= near:
                            depths[row, 0], depths[row, 1] = za, zb
                            statuses[row] = 1


@dataclass
class Evaluation:
    statuses: np.ndarray
    depths: np.ndarray
    packing_ns: int
    kernel_sync_ns: int
    fallback_ns: int
    fallback_pairs: int

    def edges(self, pairs, depth_epsilon):
        delta = self.depths[:, 0] - self.depths[:, 1]
        rows = np.flatnonzero((self.statuses == 1) & (np.abs(delta) > depth_epsilon))
        return tuple(pairs[i] if delta[i] > 0 else pairs[i][::-1] for i in rows)


def evaluate(entries, pairs, frame, overlap_area_epsilon):
    start = perf_counter_ns()
    statuses = np.zeros(len(pairs), dtype=np.int32)
    depths = np.zeros((len(pairs), 2), dtype=np.float64)
    if not pairs:
        return Evaluation(statuses, depths, perf_counter_ns() - start, 0, 0, 0)
    pair_array = np.asarray(pairs, dtype=np.int32)
    points = np.empty((len(entries), MAX_VERTICES, 2), dtype=np.float64)
    counts = np.zeros(len(entries), dtype=np.int32)
    planes = np.zeros((len(entries), 4), dtype=np.float64)
    for index in {index for pair in pairs for index in pair}:
        entry = entries[index]
        if entry.kind != "polygon" or len(entry.points) < 3:
            continue
        if len(entry.points) > MAX_VERTICES or len(entry.camera_points) > MAX_VERTICES:
            counts[index] = -1
            continue
        points[index, :len(entry.points)] = entry.points
        counts[index] = len(entry.points)
        plane = _plane_from_camera_points(entry.camera_points)
        if plane is not None:
            origin, normal = plane
            planes[index] = (*normal, dot(normal, origin))
    scratch = np.empty((min(BATCH_SIZE, len(pairs)), 2, CLIP_CAPACITY, 2), dtype=np.float64)
    cx, cy = frame.viewport.center
    focal = frame.camera.focal_length(frame.viewport)
    packed = perf_counter_ns()
    for offset in range(0, len(pairs), BATCH_SIZE):
        batch = slice(offset, offset + BATCH_SIZE)
        evaluate_kernel(points, counts, planes, pair_array[batch], scratch, statuses[batch], depths[batch],
                        cx, cy, focal, frame.camera.near_plane, overlap_area_epsilon, _SCREEN_OVERLAP_EPSILON)
    ti.sync()
    computed = perf_counter_ns()
    fallback_rows = np.flatnonzero(statuses < 0)
    for row in fallback_rows:
        a, b = pairs[row]
        result = overlapping_polygon_depths(entries[a], entries[b], frame, overlap_area_epsilon)
        statuses[row] = int(result is not None)
        if result is not None:
            depths[row] = result
    return Evaluation(statuses, depths, packed - start, computed - packed, perf_counter_ns() - computed,
                      len(fallback_rows))
