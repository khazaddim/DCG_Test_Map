from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable, Protocol, runtime_checkable

from .terrain import TerrainSample, TerrainSurface


@runtime_checkable
class CollisionShape2D(Protocol):
    def contains_point(self, x: float, y: float) -> bool:
        ...

    def conflicts(self, other: "CollisionShape2D", gap: float = 0.0) -> bool:
        ...


class TraversalRole(Enum):
    LEGACY = "legacy"
    BOUNDARY = "boundary"
    TRAVERSABLE = "traversable"


class TerrainMode(Enum):
    FLAT = "flat"
    FOLLOW_SURFACE = "follow_surface"


class OutOfBoundsPolicy(Enum):
    USE_FALLBACK_GROUND = "use_fallback_ground"
    REJECT = "reject"


class TraversalRejectionReason(Enum):
    BLOCKED = "blocked"
    OUT_OF_BOUNDS = "out_of_bounds"
    TOO_STEEP = "too_steep"


@dataclass(frozen=True)
class TraversalSettings:
    mode: TerrainMode = TerrainMode.FLAT
    fallback_ground_z: float = 0.0
    max_slope_degrees: float | None = None
    out_of_bounds_policy: OutOfBoundsPolicy = OutOfBoundsPolicy.USE_FALLBACK_GROUND


@dataclass(frozen=True)
class TraversalResolution:
    position: tuple[float, float, float]
    blocker: "Collider" | None = None
    support: TerrainSample | None = None
    rejection_reason: TraversalRejectionReason | None = None

    @property
    def accepted(self) -> bool:
        return self.blocker is None and self.rejection_reason is None


@dataclass(frozen=True)
class AabbFootprint:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.min_x > self.max_x or self.min_y > self.max_y:
            raise ValueError("AABB minimum coordinates must not exceed maximum coordinates")

    @classmethod
    def from_center(cls, center_x: float, center_y: float, width: float, depth: float) -> "AabbFootprint":
        if width < 0.0 or depth < 0.0:
            raise ValueError("AABB dimensions must be non-negative")
        half_width = width * 0.5
        half_depth = depth * 0.5
        return cls(
            min_x=center_x - half_width,
            min_y=center_y - half_depth,
            max_x=center_x + half_width,
            max_y=center_y + half_depth,
        )

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def conflicts(self, other: CollisionShape2D, gap: float = 0.0) -> bool:
        if gap < 0.0:
            raise ValueError("Collision gap must be non-negative")
        if not isinstance(other, AabbFootprint):
            raise TypeError("AabbFootprint only supports AabbFootprint collisions")
        return not (
            self.max_x <= other.min_x - gap
            or self.min_x >= other.max_x + gap
            or self.max_y <= other.min_y - gap
            or self.min_y >= other.max_y + gap
        )


@dataclass(frozen=True)
class Collider:
    owner: object
    shape: CollisionShape2D
    role: TraversalRole = TraversalRole.LEGACY
    terrain: TerrainSurface | None = None


@dataclass
class CollisionWorld:
    gap: float = 2.0
    colliders: list[Collider] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.gap < 0.0:
            raise ValueError("Collision gap must be non-negative")

    def add(
        self,
        owner: object,
        shape: CollisionShape2D,
        *,
        role: TraversalRole = TraversalRole.LEGACY,
        terrain: TerrainSurface | None = None,
    ) -> Collider:
        collider = Collider(owner=owner, shape=shape, role=role, terrain=terrain)
        self.colliders.append(collider)
        return collider

    def extend(self, colliders: Iterable[Collider]) -> None:
        self.colliders.extend(colliders)

    def remove(self, collider: Collider) -> None:
        self.colliders.remove(collider)

    def first_blocker(self, candidate: CollisionShape2D, *, ignore: object | None = None) -> Collider | None:
        for collider in self.colliders:
            if collider is ignore or collider.owner is ignore:
                continue
            if collider.role is TraversalRole.TRAVERSABLE:
                continue
            if candidate.conflicts(collider.shape, self.gap):
                return collider
        return None

    def support_sample(self, x: float, y: float) -> TerrainSample | None:
        best_sample: TerrainSample | None = None
        for collider in self.colliders:
            if collider.role is not TraversalRole.TRAVERSABLE or collider.terrain is None:
                continue
            if not collider.shape.contains_point(x, y):
                continue
            sample = collider.terrain.sample(x, y)
            if sample is None:
                continue
            if best_sample is None or sample.height > best_sample.height:
                best_sample = sample
        return best_sample

    def resolve_movement(
        self,
        candidate: CollisionShape2D,
        *,
        x: float,
        y: float,
        ignore: object | None = None,
        settings: TraversalSettings = TraversalSettings(),
    ) -> TraversalResolution:
        blocker = self.first_blocker(candidate, ignore=ignore)
        if blocker is not None:
            return TraversalResolution(
                position=(x, y, settings.fallback_ground_z),
                blocker=blocker,
                rejection_reason=TraversalRejectionReason.BLOCKED,
            )
        if settings.mode is TerrainMode.FLAT:
            return TraversalResolution(position=(x, y, settings.fallback_ground_z))

        support = self.support_sample(x, y)
        if support is None:
            if settings.out_of_bounds_policy is OutOfBoundsPolicy.REJECT:
                return TraversalResolution(
                    position=(x, y, settings.fallback_ground_z),
                    rejection_reason=TraversalRejectionReason.OUT_OF_BOUNDS,
                )
            return TraversalResolution(position=(x, y, settings.fallback_ground_z))

        if settings.max_slope_degrees is not None and support.normal is not None:
            slope = _slope_degrees(support.normal)
            if slope > settings.max_slope_degrees + 1e-7:
                return TraversalResolution(
                    position=(x, y, settings.fallback_ground_z),
                    support=support,
                    rejection_reason=TraversalRejectionReason.TOO_STEEP,
                )
        return TraversalResolution(position=support.position, support=support)


def _slope_degrees(normal: tuple[float, float, float]) -> float:
    clamped = max(-1.0, min(1.0, normal[2]))
    return math.degrees(math.acos(clamped))