import json
import random
import unittest
from unittest.mock import patch

from gbcforge.generator import (
    OpenAICompatibleGenerator,
    _endpoint_url,
    extract_json_object,
    offline_seed,
)
from gbcforge.models import ContentValidationError


VALID_ITEM = {
    "kind": "item",
    "name": "Moss Compass",
    "description": "A pocket compass that points toward the nearest safe camp after dusk.",
    "rarity": "uncommon",
    "tags": ["travel", "moss", "utility"],
    "stats": {"range": 8, "charges": 3},
    "hook": "A lost courier traded it for one warm meal.",
}


class FakeJSONResponse:
    def __init__(self, model_text: str) -> None:
        self.payload = json.dumps(
            {"choices": [{"message": {"content": model_text}}]}
        ).encode("utf-8")

    def __enter__(self) -> "FakeJSONResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class GeneratorTests(unittest.TestCase):
    def test_extracts_fenced_json(self) -> None:
        payload = extract_json_object('```json\n{"kind": "item"}\n```')
        self.assertEqual(payload, {"kind": "item"})

    def test_endpoint_normalization(self) -> None:
        self.assertEqual(
            _endpoint_url("http://127.0.0.1:8080"),
            "http://127.0.0.1:8080/v1/chat/completions",
        )
        self.assertEqual(
            _endpoint_url("http://127.0.0.1:8080/v1"),
            "http://127.0.0.1:8080/v1/chat/completions",
        )

    def test_offline_seed_is_deterministic_and_valid(self) -> None:
        first = offline_seed("creature", random.Random(11))
        second = offline_seed("creature", random.Random(11))
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(first.source, "offline-seed")

    @patch("gbcforge.generator.request.urlopen")
    def test_invalid_response_is_repaired_with_validation_feedback(
        self, mock_urlopen: object
    ) -> None:
        mock_urlopen.side_effect = [  # type: ignore[attr-defined]
            FakeJSONResponse('{"kind": "item"}'),
            FakeJSONResponse(json.dumps(VALID_ITEM)),
        ]
        repairs: list[tuple[int, str]] = []
        generator = OpenAICompatibleGenerator(
            endpoint="http://127.0.0.1:8080",
            model="tiny-local",
            stream=False,
            repair_attempts=1,
            on_repair=lambda attempt, problem: repairs.append((attempt, problem)),
        )

        content = generator.generate("item", [])

        self.assertEqual(content.name, "Moss Compass")
        self.assertEqual(mock_urlopen.call_count, 2)  # type: ignore[attr-defined]
        self.assertEqual(repairs[0][0], 1)
        self.assertIn("rarity must be one of", repairs[0][1])
        second_request = mock_urlopen.call_args_list[1].args[0]  # type: ignore[attr-defined]
        request_body = json.loads(second_request.data.decode("utf-8"))
        self.assertEqual(request_body["messages"][-2]["role"], "assistant")
        self.assertIn("failed local validation", request_body["messages"][-1]["content"])
        self.assertIn("rarity must be one of", request_body["messages"][-1]["content"])

    @patch("gbcforge.generator.request.urlopen")
    def test_repair_loop_is_bounded(self, mock_urlopen: object) -> None:
        mock_urlopen.side_effect = [  # type: ignore[attr-defined]
            FakeJSONResponse("not json"),
            FakeJSONResponse("still not json"),
            FakeJSONResponse("also not json"),
        ]
        generator = OpenAICompatibleGenerator(
            endpoint="http://127.0.0.1:8080",
            model="tiny-local",
            stream=False,
            repair_attempts=2,
        )

        with self.assertRaisesRegex(
            ContentValidationError, "stayed invalid after 3 response"
        ):
            generator.generate("item", [])
        self.assertEqual(mock_urlopen.call_count, 3)  # type: ignore[attr-defined]
        final_request = mock_urlopen.call_args_list[2].args[0]  # type: ignore[attr-defined]
        final_body = json.loads(final_request.data.decode("utf-8"))
        self.assertEqual(len(final_body["messages"]), 4)
        self.assertEqual(final_body["messages"][-2]["content"], "still not json")


if __name__ == "__main__":
    unittest.main()
