"""
tests/repositories/test_snapshot_repository.py
==============================================
Tests fuer SnapshotRepository gegen eine In-Memory-SQLite-DB.
"""

import pytest

from db.connection import create_connection
from repositories.snapshot_repository import SnapshotRepository


@pytest.fixture
def repo():
    conn = create_connection(":memory:")
    return SnapshotRepository(conn)


def _payload(titles):
    return {"setlist_titles": titles, "spotify_uris": {}}


def test_create_returns_id_and_list_finds_it(repo):
    sid = repo.create("Linkin Park", "Stockholm-Stand", _payload(["Numb", "Faint"]))
    assert isinstance(sid, int)
    items = repo.list("Linkin Park")
    assert len(items) == 1
    assert items[0]["id"] == sid
    assert items[0]["name"] == "Stockholm-Stand"
    assert items[0]["payload"]["setlist_titles"] == ["Numb", "Faint"]


def test_list_is_scoped_by_artist_and_user(repo):
    repo.create("Linkin Park", "A", _payload(["Numb"]))
    repo.create("Breaking Benjamin", "B", _payload(["So Cold"]))
    assert len(repo.list("Linkin Park")) == 1
    assert len(repo.list("Breaking Benjamin")) == 1
    assert repo.list("Linkin Park", user_id="someone_else") == []


def test_get_returns_payload_and_meta(repo):
    sid = repo.create("Linkin Park", "A", _payload(["Numb"]))
    snap = repo.get(sid)
    assert snap["artist"] == "Linkin Park"
    assert snap["name"] == "A"
    assert snap["payload"]["setlist_titles"] == ["Numb"]


def test_get_unknown_returns_none(repo):
    assert repo.get(9999) is None


def test_delete_removes_and_reports(repo):
    sid = repo.create("Linkin Park", "A", _payload(["Numb"]))
    assert repo.delete(sid) is True
    assert repo.get(sid) is None
    assert repo.delete(sid) is False  # schon weg


def test_rename_changes_name(repo):
    sid = repo.create("Linkin Park", "Alt", _payload(["Numb"]))
    assert repo.rename(sid, "Neu") is True
    assert repo.get(sid)["name"] == "Neu"
    assert repo.rename(9999, "X") is False
