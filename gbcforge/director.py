"""Coverage-driven scheduler for autonomous world building."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Mapping

from .models import ALLOWED_KINDS


_TARGET_RATIOS = {
    "biome": 1.0,
    "creature": 2.5,
    "event": 1.5,
    "item": 2.5,
    "npc": 1.5,
    "quest": 2.0,
    "recipe": 1.5,
}


@dataclass(frozen=True, slots=True)
class Direction:
    kind: str
    reason: str


def choose_next_kind(counts: Mapping[str, int], rng: random.Random) -> Direction:
    """Fill the largest normalized content gap, with tiny seeded jitter for ties."""
    total = sum(max(0, int(counts.get(kind, 0))) for kind in ALLOWED_KINDS)
    if total == 0:
        return Direction("biome", "the world has no setting yet")

    ratio_total = sum(_TARGET_RATIOS.values())
    horizon = total + 1
    scored: list[tuple[float, str, float, int]] = []
    for kind in ALLOWED_KINDS:
        target = horizon * (_TARGET_RATIOS[kind] / ratio_total)
        current = max(0, int(counts.get(kind, 0)))
        deficit = target - current
        scored.append((deficit + rng.random() * 0.0001, kind, target, current))
    _, kind, target, current = max(scored)
    return Direction(
        kind,
        f"coverage deficit: have {current}, balanced target is {target:.2f}",
    )

