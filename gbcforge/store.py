"""SQLite-backed novelty memory and JSONL export."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .models import GeneratedContent
from .novelty import similarity


class ContentStore:
    def __init__(self, database: str | Path) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS content (
                signature TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS content_kind_created "
            "ON content(kind, created_at DESC)"
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "ContentStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def add(self, content: GeneratedContent) -> bool:
        """Persist one record. Return False when its kind/name already exists."""
        try:
            self.connection.execute(
                "INSERT INTO content VALUES (?, ?, ?, ?, ?, ?)",
                (
                    content.signature,
                    content.kind,
                    content.name,
                    content.to_json(),
                    content.source,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) FROM content").fetchone()
        return int(row[0]) if row else 0

    def recent_names(self, limit: int = 40) -> list[str]:
        rows = self.connection.execute(
            "SELECT name FROM content ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [str(row[0]) for row in rows]

    def kind_counts(self) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT kind, COUNT(*) FROM content GROUP BY kind"
        ).fetchall()
        return {str(kind): int(count) for kind, count in rows}

    def closest_match(
        self, content: GeneratedContent, limit: int = 500
    ) -> tuple[float, str | None]:
        rows = self.connection.execute(
            "SELECT payload FROM content ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        best_score = 0.0
        best_name: str | None = None
        for (raw_payload,) in rows:
            payload = json.loads(raw_payload)
            score = similarity(content, payload)
            if score > best_score:
                best_score = score
                best_name = str(payload.get("name", "")) or None
        return best_score, best_name

    def records(self) -> Iterable[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT payload FROM content ORDER BY created_at, signature"
        )
        for (payload,) in rows:
            yield json.loads(payload)


def append_jsonl(path: str | Path, content: GeneratedContent) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(content.to_json())
        handle.write("\n")
