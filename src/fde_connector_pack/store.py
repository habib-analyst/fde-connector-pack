from __future__ import annotations
import json
import sqlite3
from pathlib import Path


class SyncStore:
    """SQLite-backed sync state: checkpoints, idempotent destination, dead letters."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            connector TEXT PRIMARY KEY,
            cursor TEXT,
            pages_completed INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS destinations (
            idempotency_key TEXT PRIMARY KEY,
            connector TEXT NOT NULL,
            external_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dead_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connector TEXT NOT NULL,
            external_id TEXT NOT NULL,
            error_class TEXT NOT NULL,
            error_code TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );
        """)
        self.conn.commit()

    # -- checkpoints -----------------------------------------------------
    def get_checkpoint(self, connector: str) -> str | None:
        row = self.conn.execute(
            "SELECT cursor FROM checkpoints WHERE connector=?", (connector,)).fetchone()
        return row["cursor"] if row else None

    def get_pages_completed(self, connector: str) -> int:
        row = self.conn.execute(
            "SELECT pages_completed FROM checkpoints WHERE connector=?", (connector,)).fetchone()
        return int(row["pages_completed"]) if row else 0

    def save_checkpoint(self, connector: str, cursor: str | None) -> None:
        pages = self.get_pages_completed(connector) + 1
        self.conn.execute(
            "INSERT INTO checkpoints(connector,cursor,pages_completed) VALUES(?,?,?) "
            "ON CONFLICT(connector) DO UPDATE SET cursor=excluded.cursor, "
            "pages_completed=excluded.pages_completed",
            (connector, cursor, pages))
        self.conn.commit()

    def clear_checkpoint(self, connector: str) -> None:
        self.conn.execute("DELETE FROM checkpoints WHERE connector=?", (connector,))
        self.conn.commit()

    # -- destination (idempotent) ---------------------------------------
    def put_destination(self, idempotency_key: str, connector: str,
                        external_id: str, payload: dict) -> bool:
        """Insert if absent. Returns True if created, False if duplicate."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO destinations(idempotency_key,connector,external_id,payload_json) "
            "VALUES(?,?,?,?)",
            (idempotency_key, connector, external_id, json.dumps(payload, sort_keys=True)))
        self.conn.commit()
        return cur.rowcount == 1

    def destination_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) c FROM destinations").fetchone()["c"]

    def destination_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT external_id FROM destinations ORDER BY external_id").fetchall()
        return [r["external_id"] for r in rows]

    # -- dead letters ----------------------------------------------------
    def add_dead_letter(self, connector: str, external_id: str, error_class: str,
                        error_code: str, message: str, attempts: int, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO dead_letters(connector,external_id,error_class,error_code,message,attempts,payload_json) "
            "VALUES(?,?,?,?,?,?,?)",
            (connector, external_id, error_class, error_code, message, attempts,
             json.dumps(payload, sort_keys=True, default=str)))
        self.conn.commit()

    def dead_letters(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM dead_letters ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
