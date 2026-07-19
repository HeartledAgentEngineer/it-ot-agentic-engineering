"""
db/connection.py
================
SQLite-Verbindung und Schema-Initialisierung fuer Concertify.

Engineering-Konzept: "Keimzelle der Datenbank"
    Diese Datei legt die neue concertify.db an. Erste Tabelle: setlist_snapshots.
    concert_data.json bleibt davon vollkommen unberuehrt.

    user_id ist ab Tag 1 dabei (Default 'local'), damit spaeteres Multi-User
    keine Schema-Migration der Bestandsdaten erzwingt.
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS setlist_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL DEFAULT 'local',
    artist     TEXT NOT NULL,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_user_artist
    ON setlist_snapshots (user_id, artist, created_at);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Legt Tabellen + Index an (idempotent) und setzt schema_version einmalig."""
    conn.executescript(_SCHEMA_SQL)
    count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    if count == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
        )
    conn.commit()


def create_connection(db_path: "str | Path") -> sqlite3.Connection:
    """Oeffnet eine SQLite-Verbindung und stellt das Schema sicher.

    check_same_thread=False, weil Flask Requests in mehreren Threads bedient.
    Der Repository-Layer serialisiert Schreibzugriffe ueber ein Lock.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn
