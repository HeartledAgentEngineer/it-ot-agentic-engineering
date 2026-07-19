"""
tests/db/test_connection.py
===========================
Tests fuer die SQLite-Verbindung und das Schema.
"""

from db.connection import SCHEMA_VERSION, create_connection, init_schema


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def test_create_connection_builds_schema():
    conn = create_connection(":memory:")
    names = _table_names(conn)
    assert "setlist_snapshots" in names
    assert "schema_version" in names


def test_schema_version_is_set_once():
    conn = create_connection(":memory:")
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_init_schema_is_idempotent():
    conn = create_connection(":memory:")
    # Zweiter Aufruf darf weder Fehler werfen noch eine zweite Versionszeile anlegen
    init_schema(conn)
    count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert count == 1


def test_snapshots_table_has_expected_columns():
    conn = create_connection(":memory:")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(setlist_snapshots)")}
    assert cols == {"id", "user_id", "artist", "name", "created_at", "payload"}
