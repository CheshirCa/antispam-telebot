from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import logging
from pathlib import Path
import sqlite3

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChallengeRecord:
    chat_id: int
    user_id: int
    answer: int
    challenge_message_id: int
    expires_at: float


DEFAULT_BOT_SETTINGS: dict[str, str] = {
    "challenge_timeout_minutes": "5",
    "mute_hours": "24",
    "success_delete_seconds": "10",
    "failure_delete_seconds": "30",
}


class Database:
    """SQLite storage with short, serialized operations for this small bot."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: sqlite3.Connection | None = None
        self.lock = asyncio.Lock()

    async def connect(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.executescript(
                """
            CREATE TABLE IF NOT EXISTS verified (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                verified_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS challenge (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    answer INTEGER NOT NULL,
                    challenge_message_id INTEGER NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_challenge_expires_at ON challenge(expires_at);
            CREATE TABLE IF NOT EXISTS bot_settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS known_groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admin_context (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL
            );
                """
            )
            columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(verified)")}
            if "name" not in columns:
                self.connection.execute("ALTER TABLE verified ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            self.connection.executemany(
                "INSERT OR IGNORE INTO bot_settings (name, value) VALUES (?, ?)",
                DEFAULT_BOT_SETTINGS.items(),
            )
            self.connection.commit()
        except sqlite3.Error:
            logger.exception("SQLite error while initializing database %s", self.path)
            raise

    async def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _db(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("Database is not connected")
        return self.connection

    async def is_verified(self, chat_id: int, user_id: int) -> bool:
        async with self.lock:
            row = self._db().execute(
                "SELECT 1 FROM verified WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
            return row is not None

    async def get_challenge(self, chat_id: int, user_id: int) -> ChallengeRecord | None:
        async with self.lock:
            row = self._db().execute(
                "SELECT chat_id, user_id, answer, challenge_message_id, expires_at "
                "FROM challenge WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
            ).fetchone()
            return ChallengeRecord(**dict(row)) if row else None

    async def add_challenge(
        self, chat_id: int, user_id: int, answer: int, message_id: int, expires_at: float
    ) -> bool:
        async with self.lock:
            cursor = self._db().execute(
                "INSERT OR IGNORE INTO challenge "
                "(chat_id, user_id, answer, challenge_message_id, expires_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, answer, message_id, expires_at),
            )
            self._db().commit()
            return cursor.rowcount == 1

    async def delete_challenge(self, chat_id: int, user_id: int) -> None:
        async with self.lock:
            self._db().execute(
                "DELETE FROM challenge WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
            )
            self._db().commit()

    async def mark_verified(self, chat_id: int, user_id: int, name: str) -> None:
        async with self.lock:
            self._db().execute(
                "INSERT OR IGNORE INTO verified (chat_id, user_id, name, verified_at) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, name, datetime.now(timezone.utc).isoformat()),
            )
            self._db().commit()

    async def expired_challenges(self, now: float) -> list[ChallengeRecord]:
        async with self.lock:
            rows = self._db().execute(
                "SELECT chat_id, user_id, answer, challenge_message_id, expires_at "
                "FROM challenge WHERE expires_at <= ?", (now,)
            ).fetchall()
            return [ChallengeRecord(**dict(row)) for row in rows]

    async def list_verified(self) -> list[dict[str, str | int]]:
        async with self.lock:
            rows = self._db().execute(
                "SELECT chat_id, user_id, name, verified_at FROM verified "
                "ORDER BY verified_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    async def list_verified_for_chat(self, chat_id: int) -> list[dict[str, str | int]]:
        async with self.lock:
            rows = self._db().execute(
                "SELECT chat_id, user_id, name, verified_at FROM verified "
                "WHERE chat_id = ? ORDER BY verified_at DESC", (chat_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    async def delete_verified(self, users: list[tuple[int, int]]) -> int:
        if not users:
            return 0
        async with self.lock:
            cursor = self._db().executemany(
                "DELETE FROM verified WHERE chat_id = ? AND user_id = ?", users
            )
            self._db().commit()
            return cursor.rowcount

    async def delete_verified_by_index(self, chat_id: int, index: int) -> str | None:
        users = await self.list_verified_for_chat(chat_id)
        if index < 1 or index > len(users):
            return None
        user = users[index - 1]
        await self.delete_verified([(chat_id, int(user["user_id"]))])
        return str(user["name"] or user["user_id"])

    async def remember_group(self, chat_id: int, title: str) -> None:
        async with self.lock:
            self._db().execute(
                "INSERT INTO known_groups (chat_id, title) VALUES (?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title",
                (chat_id, title),
            )
            self._db().commit()

    async def list_known_groups(self) -> list[dict[str, int | str]]:
        async with self.lock:
            rows = self._db().execute(
                "SELECT chat_id, title FROM known_groups ORDER BY title"
            ).fetchall()
            return [dict(row) for row in rows]

    async def set_admin_context(self, user_id: int, chat_id: int) -> None:
        async with self.lock:
            self._db().execute(
                "INSERT INTO admin_context (user_id, chat_id) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id",
                (user_id, chat_id),
            )
            self._db().commit()

    async def get_admin_context(self, user_id: int) -> int | None:
        async with self.lock:
            row = self._db().execute(
                "SELECT chat_id FROM admin_context WHERE user_id = ?", (user_id,)
            ).fetchone()
            return int(row["chat_id"]) if row else None

    async def get_bot_settings(self) -> dict[str, str]:
        async with self.lock:
            rows = self._db().execute("SELECT name, value FROM bot_settings").fetchall()
            result = DEFAULT_BOT_SETTINGS.copy()
            result.update({row["name"]: row["value"] for row in rows})
            return result

    async def update_bot_settings(self, values: dict[str, str]) -> None:
        allowed = set(DEFAULT_BOT_SETTINGS)
        values = {name: value for name, value in values.items() if name in allowed}
        async with self.lock:
            self._db().executemany(
                "INSERT INTO bot_settings (name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                values.items(),
            )
            self._db().commit()
