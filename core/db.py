"""SQLite-backed storage for local review history."""
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

DB_DIR = Path.home() / ".mergely"
DB_PATH = DB_DIR / "mergely.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    title TEXT,
    url TEXT,
    verdict TEXT,
    notified INTEGER NOT NULL DEFAULT 0,
    user_story TEXT,
    report_markdown TEXT,
    raw_json TEXT
);
"""


@dataclass
class ReviewRecord:
    id: int
    created_at: str
    provider: str
    title: str
    url: str
    verdict: str
    notified: bool
    user_story: str
    report_markdown: str
    raw_json: str


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(SCHEMA)

    @staticmethod
    def _to_record(row: sqlite3.Row) -> ReviewRecord:
        data = dict(row)
        data["notified"] = bool(data["notified"])
        return ReviewRecord(**data)

    def add_review(
        self,
        *,
        provider: str,
        title: str,
        url: str,
        verdict: str,
        user_story: str,
        report_markdown: str,
        raw_json: str,
        notified: bool = False,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reviews
                    (created_at, provider, title, url, verdict, notified, user_story, report_markdown, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    provider,
                    title,
                    url,
                    verdict,
                    int(notified),
                    user_story,
                    report_markdown,
                    raw_json,
                ),
            )
            return int(cursor.lastrowid)

    def set_notified(self, review_id: int, notified: bool = True) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE reviews SET notified = ? WHERE id = ?", (int(notified), review_id))

    def get_all(self) -> List[ReviewRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
        return [self._to_record(row) for row in rows]

    def get(self, review_id: int) -> Optional[ReviewRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return self._to_record(row) if row else None

    def delete(self, review_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
