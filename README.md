# AIGameAssets — GBCForge

A dependency-free autonomous local-AI content compiler for small RPGs. It turns any OpenAI-compatible local model—including `llama.cpp` servers running GGUF models—into validated, novelty-gated JSON records for creatures, items, quests, biomes, recipes, NPCs, and events.

This is working code, not a model or benchmark claim. The offline mode exercises the complete storage and export pipeline without calling an AI.

## Why it exists

Local models can continuously invent game content, but raw text is difficult to integrate safely. `gbcforge` places a narrow boundary around generation:

- strict bounded schema and integer stats;
- SQLite novelty memory that rejects exact and near-duplicate concepts without running an embedding model;
- a coverage director that selects the next content type by measuring gaps in the world, instead of blindly rolling a random type;
- transparent structural quality filter;
- append-only JSONL plus an atomically replaced world manifest for safe game-engine hot loading;
- streaming support for OpenAI-compatible local endpoints;
- bounded self-repair that feeds exact schema failures back to small models instead of aborting the job;
- deterministic offline mode for CI and development;
- Python standard library only at runtime.

## Try it without a model

```bash
git clone https://github.com/requiredtruth/AIGameAssets.git
cd AIGameAssets
python -m gbcforge --offline --jobs 5
```

Records are printed to standard output, stored in `.gbcforge/content.sqlite3`, appended to `generated/content.jsonl`, and compiled to `generated/world.manifest.json`. The default `--kind auto` director builds a balanced world in dependency-friendly order.

## Use a local model

Start an OpenAI-compatible server such as `llama-server`, then run:

```bash
python -m gbcforge \
  --endpoint http://127.0.0.1:8080 \
  --model local-gguf \
  --jobs 10
```

The endpoint may be a base URL, `/v1`, or the complete `/v1/chat/completions` URL. Set `OPENAI_BASE_URL`, `OPENAI_MODEL`, and optionally `OPENAI_API_KEY` instead of command-line flags when preferred.

To generate one specific type:

```bash
python -m gbcforge --kind creature --jobs 3
```

## Small-model repair loop

Local models often return almost-correct JSON: a missing rarity, a string where an integer belongs, or prose around the object. GBCForge validates the response locally and, when it fails, sends the exact error back to the same model for a bounded correction. The rejected response is never stored.

Two repair attempts are enabled by default. Tune or disable them without changing the model server:

```bash
python -m gbcforge --jobs 10 --repair-attempts 3
python -m gbcforge --jobs 10 --repair-attempts 0
```

Repairs are limited to five. Network and provider errors still stop immediately; they are not hidden behind retries.

## Output contract

Each accepted line is self-contained JSON:

```json
{
  "kind": "creature",
  "name": "Rune Moth",
  "description": "A compact creature built around rune signals and careful timing.",
  "rarity": "uncommon",
  "tags": ["gbc", "creature", "rune"],
  "stats": {"power": 11, "cost": 3, "tier": 2},
  "hook": "Players discover it after following a repeating three-note signal.",
  "source": "local-gguf",
  "quality_score": 0.74,
  "signature": "sha256..."
}
```

Text and collection sizes are bounded before anything reaches the database. Records with an invalid kind, rarity, tag list, integer range, or unsafe control character are rejected.

The novelty gate compares normalized names, descriptive tokens, and gameplay hooks against the existing ledger. It is intentionally lightweight enough for CPU-only and mobile development: no embedding model, vector database, or external service is required.

## Test

```bash
python -m unittest discover -s tests -v
```

CI runs the test suite and an offline end-to-end generation job on Python 3.11, 3.12, and 3.13.

## Privacy and scope

No telemetry is collected. By default the live path calls `127.0.0.1`; data leaves the machine only if you explicitly provide a remote endpoint. Generated content is data only—this tool does not execute model-written commands or code.

## Fund more development

Donations increase the amount of RequiredTruth development that can be produced. Bitcoin, Ethereum/EVM, and Dogecoin receiving addresses are in [`SUPPORT.md`](SUPPORT.md).

After a confirmed donation, a donor may open an issue with the asset, network, public transaction hash, and the specific feature or direction they want expanded. The first issue claiming an unclaimed confirmed inbound hash receives its operational request attribution. Never post a private key or seed phrase.

Apache-2.0 licensed.
