"""Command-line entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import random
import sys

from .director import choose_next_kind
from .generator import OpenAICompatibleGenerator, ProviderError, offline_seed
from .manifest import write_manifest
from .models import ALLOWED_KINDS, ContentValidationError, GeneratedContent
from .store import ContentStore, append_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gbcforge",
        description="Generate validated RPG content with a local OpenAI-compatible model.",
    )
    parser.add_argument("--jobs", type=int, default=1, help="records to create (default: 1)")
    parser.add_argument(
        "--kind", choices=("auto", "random", *ALLOWED_KINDS), default="auto"
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8080"),
        help="OpenAI-compatible base URL or chat-completions URL",
    )
    parser.add_argument(
        "--model", default=os.getenv("OPENAI_MODEL", "local-model")
    )
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--db", default=".gbcforge/content.sqlite3")
    parser.add_argument("--out", default="generated/content.jsonl")
    parser.add_argument("--manifest", default="generated/world.manifest.json")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument(
        "--repair-attempts",
        type=int,
        default=2,
        help="validation-feedback repairs per model response (default: 2, max: 5)",
    )
    parser.add_argument("--min-score", type=float, default=0.60)
    parser.add_argument(
        "--max-similarity",
        type=float,
        default=0.82,
        help="reject candidates this similar to ledger content (default: 0.82)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="exercise the pipeline with deterministic seed data and no model",
    )
    parser.add_argument(
        "--no-stream", action="store_true", help="request one JSON response instead of SSE"
    )
    return parser


def _stream_token(token: str) -> None:
    sys.stderr.write(token)
    sys.stderr.flush()


def _repair_notice(attempt: int, validation_error: str) -> None:
    print(
        f"\nrepair attempt={attempt}: {validation_error}",
        file=sys.stderr,
    )


def _choose_kind(
    requested: str, rng: random.Random, store: ContentStore
) -> tuple[str, str]:
    if requested == "auto":
        direction = choose_next_kind(store.kind_counts(), rng)
        return direction.kind, direction.reason
    if requested == "random":
        return rng.choice(ALLOWED_KINDS), "explicit random scheduling"
    return requested, "content kind selected by operator"


def run(args: argparse.Namespace) -> int:
    if args.jobs < 1 or args.jobs > 1000:
        raise ContentValidationError("jobs must be between 1 and 1000")
    if not 0.0 <= args.min_score <= 1.0:
        raise ContentValidationError("min-score must be between 0 and 1")
    if not 0.0 <= args.max_similarity <= 1.0:
        raise ContentValidationError("max-similarity must be between 0 and 1")
    if not 0 <= args.repair_attempts <= 5:
        raise ContentValidationError("repair-attempts must be between 0 and 5")

    rng = random.Random(args.seed)
    generator = None
    if not args.offline:
        generator = OpenAICompatibleGenerator(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
            timeout=args.timeout,
            temperature=args.temperature,
            stream=not args.no_stream,
            on_token=None if args.no_stream else _stream_token,
            repair_attempts=args.repair_attempts,
            on_repair=_repair_notice,
        )

    made = 0
    rejected = 0
    with ContentStore(args.db) as store:
        for _ in range(args.jobs):
            accepted: GeneratedContent | None = None
            for _attempt in range(8):
                kind, reason = _choose_kind(args.kind, rng, store)
                print(f"director kind={kind}: {reason}", file=sys.stderr)
                if args.offline:
                    candidate = offline_seed(kind, rng)
                else:
                    assert generator is not None
                    candidate = generator.generate(kind, store.recent_names())
                    if not args.no_stream:
                        sys.stderr.write("\n")
                if candidate.quality_score() < args.min_score:
                    rejected += 1
                    continue
                closest_score, closest_name = store.closest_match(candidate)
                if closest_score >= args.max_similarity:
                    rejected += 1
                    print(
                        f"rejected near-duplicate similarity={closest_score:.4f} "
                        f"closest={closest_name!r}",
                        file=sys.stderr,
                    )
                    continue
                if not store.add(candidate):
                    rejected += 1
                    continue
                accepted = candidate
                break

            if accepted is None:
                print("unable to create a novel record after 8 attempts", file=sys.stderr)
                return 1
            append_jsonl(args.out, accepted)
            print(accepted.to_json())
            made += 1

        write_manifest(args.manifest, store)
        print(
            f"created={made} rejected={rejected} stored={store.count()} "
            f"output={Path(args.out)} manifest={Path(args.manifest)}",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ContentValidationError, ProviderError) as exc:
        parser.error(str(exc))
    return 2
