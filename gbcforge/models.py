"""Validated interchange model for generated game content."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping


ALLOWED_KINDS = (
    "biome",
    "creature",
    "event",
    "item",
    "npc",
    "quest",
    "recipe",
)
ALLOWED_RARITIES = ("common", "uncommon", "rare", "legendary")
_SAFE_TEXT = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]+$")


class ContentValidationError(ValueError):
    """Raised when model output is not safe, bounded, game-ready content."""


def _bounded_text(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ContentValidationError(f"{field} must be a string")
    cleaned = " ".join(value.split()).strip()
    if not minimum <= len(cleaned) <= maximum:
        raise ContentValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if not _SAFE_TEXT.match(cleaned):
        raise ContentValidationError(f"{field} contains control characters")
    return cleaned


@dataclass(frozen=True, slots=True)
class GeneratedContent:
    """One engine-neutral content record produced by a model or seed generator."""

    kind: str
    name: str
    description: str
    rarity: str
    tags: tuple[str, ...]
    stats: dict[str, int]
    hook: str
    source: str = "model"

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, Any], *, source: str = "model"
    ) -> "GeneratedContent":
        if not isinstance(payload, Mapping):
            raise ContentValidationError("content must be a JSON object")

        kind = str(payload.get("kind", "")).strip().lower()
        if kind not in ALLOWED_KINDS:
            raise ContentValidationError(
                f"kind must be one of: {', '.join(ALLOWED_KINDS)}"
            )

        rarity = str(payload.get("rarity", "")).strip().lower()
        if rarity not in ALLOWED_RARITIES:
            raise ContentValidationError(
                f"rarity must be one of: {', '.join(ALLOWED_RARITIES)}"
            )

        raw_tags = payload.get("tags")
        if not isinstance(raw_tags, list) or not 1 <= len(raw_tags) <= 6:
            raise ContentValidationError("tags must be a list containing 1 to 6 values")
        tags: list[str] = []
        for raw_tag in raw_tags:
            tag = _bounded_text(raw_tag, "tag", 2, 24).lower()
            if tag not in tags:
                tags.append(tag)

        raw_stats = payload.get("stats")
        if not isinstance(raw_stats, Mapping) or not 1 <= len(raw_stats) <= 8:
            raise ContentValidationError("stats must contain 1 to 8 integer values")
        stats: dict[str, int] = {}
        for raw_key, raw_value in raw_stats.items():
            key = _bounded_text(raw_key, "stat name", 1, 24).lower().replace(" ", "_")
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                raise ContentValidationError(f"stat {key!r} must be an integer")
            if not -999 <= raw_value <= 9999:
                raise ContentValidationError(f"stat {key!r} is outside the safe range")
            stats[key] = raw_value

        return cls(
            kind=kind,
            name=_bounded_text(payload.get("name"), "name", 2, 64),
            description=_bounded_text(
                payload.get("description"), "description", 20, 320
            ),
            rarity=rarity,
            tags=tuple(tags),
            stats=stats,
            hook=_bounded_text(payload.get("hook"), "hook", 8, 180),
            source=_bounded_text(source, "source", 2, 40),
        )

    @property
    def signature(self) -> str:
        """Stable identity used to stop a model from repeating near-identical names."""
        normalized = re.sub(r"[^a-z0-9]+", "", f"{self.kind}:{self.name.lower()}")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def quality_score(self) -> float:
        """Transparent structural score; it is a filter, not a claim of creativity."""
        score = 0.0
        score += 0.20 if len(self.name.split()) >= 2 else 0.10
        score += min(len(self.description.split()) / 32.0, 1.0) * 0.30
        score += min(len(self.tags) / 4.0, 1.0) * 0.20
        score += min(len(self.stats) / 4.0, 1.0) * 0.15
        score += min(len(self.hook.split()) / 18.0, 1.0) * 0.15
        return round(min(score, 1.0), 4)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        payload["quality_score"] = self.quality_score()
        payload["signature"] = self.signature
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
