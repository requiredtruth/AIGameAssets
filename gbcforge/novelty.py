"""CPU-light near-duplicate detection without an embedding model."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any, Mapping

from .models import GeneratedContent


_WORDS = re.compile(r"[a-z0-9]{2,}")
_STOP = {
    "after",
    "around",
    "built",
    "content",
    "from",
    "into",
    "near",
    "one",
    "that",
    "the",
    "their",
    "this",
    "with",
}


def _tokens(text: str) -> set[str]:
    return {word for word in _WORDS.findall(text.lower()) if word not in _STOP}


def _payload_text(payload: Mapping[str, Any]) -> str:
    tags = payload.get("tags", [])
    tag_text = " ".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
    return " ".join(
        (
            str(payload.get("name", "")),
            str(payload.get("description", "")),
            str(payload.get("hook", "")),
            tag_text,
        )
    )


def similarity(content: GeneratedContent, other: Mapping[str, Any]) -> float:
    """Return 0..1 lexical similarity, emphasizing repeated names and hooks."""
    left_name = re.sub(r"\W+", " ", content.name.lower()).strip()
    right_name = re.sub(r"\W+", " ", str(other.get("name", "")).lower()).strip()
    name_score = SequenceMatcher(None, left_name, right_name).ratio()

    left_tokens = _tokens(_payload_text(content.to_dict()))
    right_tokens = _tokens(_payload_text(other))
    union = left_tokens | right_tokens
    token_score = len(left_tokens & right_tokens) / len(union) if union else 0.0

    left_hook = str(content.hook).lower()
    right_hook = str(other.get("hook", "")).lower()
    hook_score = SequenceMatcher(None, left_hook, right_hook).ratio()
    score = max(name_score, 0.72 * token_score + 0.28 * hook_score)

    # A biome and an item can legitimately share world vocabulary. Cross-kind
    # records still contribute to the score, but cannot veto one another solely
    # because a small local model reused part of its prose template.
    other_kind = str(other.get("kind", "")).strip().lower()
    if other_kind and other_kind != content.kind:
        score = min(score, 0.65)
    return round(score, 4)
