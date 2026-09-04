from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol, runtime_checkable


@runtime_checkable
class CollisionShape2D(Protocol):
    def conflicts(self, other: "CollisionShape2D", gap: float = 0.0) -> bool:
        ...


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


@dataclass
class CollisionWorld:
    gap: float = 2.0
    colliders: list[Collider] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.gap < 0.0:
            raise ValueError("Collision gap must be non-negative")

    def add(self, owner: object, shape: CollisionShape2D) -> Collider:
        collider = Collider(owner=owner, shape=shape)
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
            if candidate.conflicts(collider.shape, self.gap):
                return collider
        return None