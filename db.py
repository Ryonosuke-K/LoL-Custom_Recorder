import sqlite3
from datetime import datetime, timezone
from typing import Any


class DB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS link_codes (
                    code TEXT PRIMARY KEY,
                    discord_user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS organizers (
                    discord_user_id TEXT PRIMARY KEY,
                    encrypted_refresh_token TEXT NOT NULL,
                    riot_puuid TEXT,
                    region_base TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            con.execute(
                "DROP TABLE IF EXISTS match_records"
            )
            con.commit()

    def insert_link_code(self, code: str, discord_user_id: str, expires_at_iso: str) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO link_codes(code, discord_user_id, expires_at, used_at) VALUES (?, ?, ?, NULL)",
                (code, discord_user_id, expires_at_iso),
            )
            con.commit()

    def get_link_code(self, code: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM link_codes WHERE code = ?", (code,)).fetchone()
            return dict(row) if row else None

    def consume_link_code(self, code: str) -> dict[str, Any] | None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as con:
            row = con.execute(
                """
                SELECT * FROM link_codes
                WHERE code = ? AND used_at IS NULL AND expires_at > ?
                """,
                (code, now_iso),
            ).fetchone()
            if not row:
                return None
            con.execute(
                "UPDATE link_codes SET used_at = ? WHERE code = ? AND used_at IS NULL",
                (now_iso, code),
            )
            con.commit()
            return dict(row)

    def upsert_organizer(
        self,
        discord_user_id: str,
        encrypted_refresh_token: str,
        riot_puuid: str | None,
        region_base: str,
        platform: str,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO organizers(
                    discord_user_id,
                    encrypted_refresh_token,
                    riot_puuid,
                    region_base,
                    platform,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(discord_user_id) DO UPDATE SET
                    encrypted_refresh_token = excluded.encrypted_refresh_token,
                    riot_puuid = excluded.riot_puuid,
                    region_base = excluded.region_base,
                    platform = excluded.platform,
                    updated_at = excluded.updated_at
                """,
                (
                    discord_user_id,
                    encrypted_refresh_token,
                    riot_puuid,
                    region_base,
                    platform,
                    now_iso,
                ),
            )
            con.commit()

    def get_organizer(self, discord_user_id: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM organizers WHERE discord_user_id = ?", (discord_user_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_organizers(self) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM organizers").fetchall()
            return [dict(row) for row in rows]

    def count_organizers(self) -> int:
        with self._conn() as con:
            row = con.execute("SELECT COUNT(*) AS c FROM organizers").fetchone()
            return int(row["c"])
