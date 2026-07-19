"""
tests/services/test_snapshot_service.py
=======================================
Tests fuer den reinen Snapshot-Service (kein IO).
"""

from services.snapshot_service import (
    apply_snapshot_payload,
    build_snapshot_payload,
    diff_setlists,
    is_list_saved,
)


# --- diff_setlists ---

def test_diff_setlists_detects_added_and_removed():
    old = ["Numb", "In the End", "Faint"]
    new = ["Numb", "In the End", "Lost"]  # Faint weg, Lost neu
    result = diff_setlists(old, new)
    assert result["added"] == ["Lost"]
    assert result["removed"] == ["Faint"]
    assert result["unchanged"] == ["Numb", "In the End"]


def test_diff_setlists_identical():
    same = ["A", "B"]
    result = diff_setlists(same, same)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["unchanged"] == ["A", "B"]


# --- is_list_saved ---

def test_is_list_saved_true_on_exact_match():
    snapshots = [{"payload": {"setlist_titles": ["A", "B", "C"]}}]
    assert is_list_saved(["A", "B", "C"], snapshots) is True


def test_is_list_saved_false_on_order_or_content_diff():
    snapshots = [{"payload": {"setlist_titles": ["A", "B", "C"]}}]
    assert is_list_saved(["A", "C", "B"], snapshots) is False  # andere Reihenfolge
    assert is_list_saved(["A", "B"], snapshots) is False        # weniger Songs


def test_is_list_saved_empty_snapshots():
    assert is_list_saved(["A"], []) is False


# --- Payload-Helfer ---

def test_build_snapshot_payload_copies_known_keys_only():
    entry = {
        "setlist_titles": ["A"],
        "spotify_uris": {"A": "spotify:track:1"},
        "excluded_songs": ["A"],
        "manual_order": ["A"],
        "irrelevant_key": "soll nicht rein",
    }
    payload = build_snapshot_payload(entry)
    assert payload["setlist_titles"] == ["A"]
    assert payload["spotify_uris"] == {"A": "spotify:track:1"}
    assert payload["excluded_songs"] == ["A"]
    assert "irrelevant_key" not in payload


def test_apply_snapshot_payload_overwrites_target_keys():
    entry = {"setlist_titles": ["OLD"], "scores": {"OLD": 0.1}}
    payload = {"setlist_titles": ["NEW1", "NEW2"], "scores": {"NEW1": 0.9}}
    apply_snapshot_payload(entry, payload)
    assert entry["setlist_titles"] == ["NEW1", "NEW2"]
    assert entry["scores"] == {"NEW1": 0.9}


from services.snapshot_service import SnapshotService


class _FakeRepo:
    """In-Memory-Fake des SnapshotRepository (gleiche Signaturen)."""

    def __init__(self):
        self._rows = {}
        self._next = 1

    def create(self, artist, name, payload, user_id="local", created_at=None):
        sid = self._next
        self._next += 1
        self._rows[sid] = {
            "id": sid, "artist": artist, "name": name,
            "user_id": user_id, "created_at": created_at or "2026-06-01T12:00:00",
            "payload": payload,
        }
        return sid

    def list(self, artist, user_id="local"):
        return [
            {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "payload": r["payload"]}
            for r in self._rows.values()
            if r["artist"] == artist and r["user_id"] == user_id
        ]

    def get(self, snapshot_id):
        return self._rows.get(snapshot_id)

    def delete(self, snapshot_id):
        return self._rows.pop(snapshot_id, None) is not None

    def rename(self, snapshot_id, new_name):
        if snapshot_id in self._rows:
            self._rows[snapshot_id]["name"] = new_name
            return True
        return False


def test_create_snapshot_requires_name():
    svc = SnapshotService(_FakeRepo())
    sid, err = svc.create_snapshot("Linkin Park", "   ", {"setlist_titles": ["A"]})
    assert sid is None
    assert err == "missing name"


def test_create_and_list_snapshot():
    svc = SnapshotService(_FakeRepo())
    sid, err = svc.create_snapshot(
        "Linkin Park", "Stand A",
        {"setlist_titles": ["A"], "irrelevant": "weg"},
    )
    assert err is None and sid == 1
    items = svc.list_snapshots("Linkin Park")
    assert items == [{"id": 1, "name": "Stand A", "created_at": "2026-06-01T12:00:00"}]


def test_get_restore_payload_returns_artist_and_payload():
    repo = _FakeRepo()
    svc = SnapshotService(repo)
    sid, _ = svc.create_snapshot("Linkin Park", "A", {"setlist_titles": ["A", "B"]})
    artist, payload, err = svc.get_restore_payload(sid)
    assert err is None
    assert artist == "Linkin Park"
    assert payload["setlist_titles"] == ["A", "B"]


def test_get_restore_payload_unknown():
    svc = SnapshotService(_FakeRepo())
    artist, payload, err = svc.get_restore_payload(999)
    assert err == "unknown snapshot"


def test_is_current_saved_uses_repo_list():
    svc = SnapshotService(_FakeRepo())
    svc.create_snapshot("Linkin Park", "A", {"setlist_titles": ["A", "B"]})
    assert svc.is_current_saved("Linkin Park", ["A", "B"]) is True
    assert svc.is_current_saved("Linkin Park", ["A"]) is False


def test_rename_requires_nonempty():
    repo = _FakeRepo()
    svc = SnapshotService(repo)
    sid, _ = svc.create_snapshot("Linkin Park", "A", {"setlist_titles": ["A"]})
    assert svc.rename_snapshot(sid, "  ") is False
    assert svc.rename_snapshot(sid, "Neu") is True
