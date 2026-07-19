"""
repositories/snapshot_repository.py
===================================
Reiner Datenzugriff fuer Setlist-Schnappschuesse (SQLite).

Engineering-Konzept: "Repository per Aggregate Root"
    Kapselt SQL vollstaendig. Bekommt die Verbindung per Dependency Injection,
    damit Tests eine :memory:-DB injizieren koennen (keine Datei noetig).

    payload wird als JSON-Text gespeichert (1:1-Restore des Setlist-Zustands).
"""

import json
import sqlite3
from datetime import datetime
from threading import Lock


class SnapshotRepository:
    """CRUD fuer die Tabelle setlist_snapshots."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = Lock()  # serialisiert Schreibzugriffe ueber Flask-Threads

    # --- Schreiben ---

    def create(
        self,
        artist: str,
        name: str,
        payload: dict,
        user_id: str = "local",
        created_at: "str | None" = None,
    ) -> int:
        created_at = created_at or datetime.now().isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO setlist_snapshots "
                "(user_id, artist, name, created_at, payload) VALUES (?, ?, ?, ?, ?)",
                (user_id, artist, name, created_at,
                 json.dumps(payload, ensure_ascii=False)),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def delete(self, snapshot_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM setlist_snapshots WHERE id = ?", (snapshot_id,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def rename(self, snapshot_id: int, new_name: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE setlist_snapshots SET name = ? WHERE id = ?",
                (new_name, snapshot_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    # --- Lesen ---

    def list(self, artist: str, user_id: str = "local") -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, name, created_at, payload FROM setlist_snapshots "
            "WHERE user_id = ? AND artist = ? ORDER BY created_at DESC, id DESC",
            (user_id, artist),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, snapshot_id: int) -> "dict | None":
        row = self._conn.execute(
            "SELECT id, user_id, artist, name, created_at, payload "
            "FROM setlist_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        return self._row_to_dict(row, include_meta=True) if row else None

    # --- Mapping ---

    @staticmethod
    def _row_to_dict(row: sqlite3.Row, include_meta: bool = False) -> dict:
        d = {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "payload": json.loads(row["payload"]),
        }
        if include_meta:
            d["artist"] = row["artist"]
            d["user_id"] = row["user_id"]
        return d
