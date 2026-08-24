"""OpenAI-compatible and deterministic seed content generators."""

from __future__ import annotations

import json
import random
import re
from typing import Callable, Iterable, Sequence
from urllib import error, request

from .models import ALLOWED_KINDS, ContentValidationError, GeneratedContent


SYSTEM_PROMPT = """You create compact original content for a Game Boy Color-style RPG.
Return exactly one JSON object and no commentary. Never copy an existing game character,
place, item, or story. Keep mechanics small enough for an 8-bit RPG. Required schema:
{"kind":"item|creature|quest|biome|recipe|npc|event","name":"2-64 chars",
"description":"20-320 chars","rarity":"common|uncommon|rare|legendary",
"tags":["1-6 short tags"],"stats":{"one_to_eight_integer_stats":1},
"hook":"8-180 char gameplay or story hook"}.
"""


class ProviderError(RuntimeError):
    """Raised when the local model endpoint cannot produce a usable response."""


def _endpoint_url(endpoint: str) -> str:
    cleaned = endpoint.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


def extract_json_object(text: str) -> dict[str, object]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ContentValidationError("model response did not contain a JSON object")
        try:
            payload = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ContentValidationError(f"model returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContentValidationError("model response JSON must be an object")
    return payload


class OpenAICompatibleGenerator:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        temperature: float = 0.85,
        stream: bool = True,
        on_token: Callable[[str], None] | None = None,
        repair_attempts: int = 2,
        on_repair: Callable[[int, str], None] | None = None,
    ) -> None:
        if not 0 <= repair_attempts <= 5:
            raise ValueError("repair_attempts must be between 0 and 5")
        self.endpoint = _endpoint_url(endpoint)
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.stream = stream
        self.on_token = on_token
        self.repair_attempts = repair_attempts
        self.on_repair = on_repair

    def generate(self, kind: str, avoid_names: Iterable[str]) -> GeneratedContent:
        avoided = ", ".join(list(avoid_names)[-40:]) or "none yet"
        user_prompt = (
            f"Create one {kind}. Existing names to avoid: {avoided}. "
            "Use integer stats that are meaningful for this content type."
        )
        base_messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        messages = list(base_messages)
        for attempt in range(self.repair_attempts + 1):
            text = self._complete(messages)
            try:
                return GeneratedContent.from_mapping(
                    extract_json_object(text), source=self.model
                )
            except ContentValidationError as exc:
                if attempt >= self.repair_attempts:
                    total = self.repair_attempts + 1
                    raise ContentValidationError(
                        f"model output stayed invalid after {total} response(s): {exc}"
                    ) from exc
                repair_number = attempt + 1
                if self.on_repair:
                    self.on_repair(repair_number, str(exc))
                # Keep only the newest rejected response. Accumulating every bad
                # transcript would waste the small context windows this feature
                # is intended to help.
                messages = [
                    *base_messages,
                    {
                        "role": "assistant",
                        "content": text[:4000],
                    },
                    {
                        "role": "user",
                        "content": (
                            "The previous response failed local validation: "
                            f"{exc}. Correct that response. Return exactly one complete "
                            "JSON object matching the original schema, with no markdown or "
                            "commentary. Do not omit fields."
                        ),
                    },
                ]
        raise AssertionError("unreachable repair loop")

    def _complete(self, messages: Sequence[dict[str, str]]) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": list(messages),
                "temperature": self.temperature,
                "max_tokens": 420,
                "stream": self.stream,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = request.Request(
            self.endpoint, data=body, headers=headers, method="POST"
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                text = self._read_stream(response) if self.stream else self._read_json(response)
        except error.HTTPError as exc:
            detail = exc.read(800).decode("utf-8", errors="replace")
            raise ProviderError(f"model endpoint returned HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise ProviderError(f"could not reach model endpoint: {exc}") from exc

        return text

    def _read_json(self, response: object) -> str:
        payload = json.loads(response.read().decode("utf-8"))  # type: ignore[attr-defined]
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("endpoint returned an unexpected response shape") from exc

    def _read_stream(self, response: object) -> str:
        parts: list[str] = []
        for raw_line in response:  # type: ignore[union-attr]
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
                token = event["choices"][0].get("delta", {}).get("content", "")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                continue
            if token:
                token = str(token)
                parts.append(token)
                if self.on_token:
                    self.on_token(token)
        if not parts:
            raise ProviderError("endpoint stream ended without content")
        return "".join(parts)


_PREFIXES = (
    "Ash",
    "Brass",
    "Cinder",
    "Cloud",
    "Dusk",
    "Ember",
    "Frost",
    "Glimmer",
    "Hollow",
    "Moss",
    "Rune",
    "Thorn",
)
_NOUNS = {
    "biome": ("Fen", "Garden", "Hollow", "Marsh", "Mesa", "Vale"),
    "creature": ("Badger", "Moth", "Newt", "Rook", "Slime", "Tortoise"),
    "event": ("Bell", "Bloom", "Eclipse", "Festival", "Rain", "Tide"),
    "item": ("Charm", "Compass", "Flask", "Lantern", "Needle", "Whistle"),
    "npc": ("Cartographer", "Herbalist", "Keeper", "Smith", "Tinker", "Warden"),
    "quest": ("Accord", "Delivery", "Pilgrimage", "Rescue", "Survey", "Trial"),
    "recipe": ("Broth", "Incense", "Oil", "Salve", "Tea", "Tonic"),
}
_MECHANICS = {
    "biome": (
        "Tide marks reveal temporary paths while deep water closes familiar routes.",
        "Wind-shifted bridges reward players who remember shelter locations.",
        "Glowing ground cover marks safe tiles before the terrain changes.",
    ),
    "creature": (
        "Its warning pose exposes a weakness one turn before it attacks.",
        "It copies the last movement pattern but tires after three repeats.",
        "Its shell stores elemental hits and releases them when cracked.",
    ),
    "event": (
        "A short countdown changes shop prices and opens one hidden route.",
        "The town schedule shifts, moving allies and hazards to new locations.",
        "Players choose which district receives a temporary defensive bonus.",
    ),
    "item": (
        "A limited charge converts an environmental hazard into a shortcut.",
        "Careful timing trades a small defense penalty for an extra action.",
        "Its indicator points toward nearby resources but fades during combat.",
    ),
    "npc": (
        "Their routine changes after each favor, exposing different local clues.",
        "They exchange map annotations for evidence gathered outside combat.",
        "Their advice improves when the player returns with contradictory rumors.",
    ),
    "quest": (
        "The objective can be solved by negotiation, navigation, or one compact fight.",
        "Two optional clues reveal a safer route and a different final reward.",
        "The destination moves at dusk, turning preparation into the main puzzle.",
    ),
    "recipe": (
        "Combining ingredients in reverse order changes the effect but not its cost.",
        "A common substitute lowers potency while removing a dangerous side effect.",
        "Preparing it near a heat source adds duration instead of raw strength.",
    ),
}
_DISCOVERY_HOOKS = (
    "A damaged trail sign encodes the location in alternating arrow directions.",
    "A ferryman reveals the route after the player returns a borrowed tool.",
    "Three mismatched map symbols align only when viewed at the town gate.",
    "An optional night patrol leaves a sequence of colored markers behind.",
    "A market receipt names the wrong buyer but the correct meeting place.",
    "A quiet room repeats one sound whenever the player faces the hidden exit.",
    "A rival drops half of a route sketch after fleeing a losing encounter.",
    "Restoring a roadside shrine causes nearby footprints to become visible.",
)


def offline_seed(kind: str, rng: random.Random) -> GeneratedContent:
    """Create valid deterministic seed data for testing without pretending it is AI."""
    if kind not in ALLOWED_KINDS:
        raise ContentValidationError(f"unsupported kind: {kind}")
    prefix = rng.choice(_PREFIXES)
    noun = rng.choice(_NOUNS[kind])
    name = f"{prefix} {noun}"
    power = rng.randint(2, 18)
    mechanic = rng.choice(_MECHANICS[kind])
    discovery = rng.choice(_DISCOVERY_HOOKS)
    payload = {
        "kind": kind,
        "name": name,
        "description": f"{name} is a compact {kind} for a small tile-based world. {mechanic}",
        "rarity": rng.choice(("common", "uncommon", "rare")),
        "tags": ["gbc", kind, prefix.lower(), "seed-data"],
        "stats": {"power": power, "cost": max(1, power // 3), "tier": rng.randint(1, 5)},
        "hook": f"{discovery} This leads to {name}.",
    }
    return GeneratedContent.from_mapping(payload, source="offline-seed")
