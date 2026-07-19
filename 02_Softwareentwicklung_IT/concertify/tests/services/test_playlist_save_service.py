"""
tests/services/test_playlist_save_service.py
==============================================
Tests fuer PlaylistSaveService.
"""

from datetime import date

import pytest

from domain.saved_playlist import (
    PLAYLIST_TYPE_KONZERTABEND,
    PLAYLIST_TYPE_SETLIST_MIX,
    SavedPlaylist,
)
from repositories.saved_playlist_repo import SavedPlaylistRepository
from services.playlist_save_service import PlaylistSaveService


# ─── Fake-Repo ───────────────────────────────────────────────────────────────

class _FakeRepo(SavedPlaylistRepository):
    def __init__(self):
        self._store: dict[str, SavedPlaylist] = {}

    def get(self, spotify_id):
        return self._store.get(spotify_id)

    def list_all(self):
        return list(self._store.values())

    def list_by_type(self, playlist_type):
        return [pl for pl in self._store.values() if pl.playlist_type == playlist_type]

    def save(self, playlist):
        self._store[playlist.spotify_id] = playlist

    def delete(self, spotify_id):
        if spotify_id not in self._store:
            return False
        del self._store[spotify_id]
        return True


# ─── save_setlist_mix ────────────────────────────────────────────────────────

def test_save_setlist_mix_creates_with_correct_type():
    service = PlaylistSaveService(_FakeRepo())
    pl = service.save_setlist_mix(spotify_id="mix1", name="Mix 1")

    assert pl.spotify_id == "mix1"
    assert pl.is_setlist_mix() is True
    assert pl.is_konzertabend() is False


def test_save_setlist_mix_with_full_data():
    service = PlaylistSaveService(_FakeRepo())
    pl = service.save_setlist_mix(
        spotify_id="mix1",
        name="Mix 1",
        description="Best of 2026",
        artists=["LP", "BB"],
        artist_selections={"LP": ["Numb"], "BB": ["Diary"]},
        config={"limit_per_artist": 22},
    )

    assert pl.description == "Best of 2026"
    assert pl.artists == ["LP", "BB"]
    assert pl.songs_for_artist("LP") == ["Numb"]
    assert pl.config == {"limit_per_artist": 22}


# ─── save_konzertabend ───────────────────────────────────────────────────────

def test_save_konzertabend_creates_with_event_data():
    service = PlaylistSaveService(_FakeRepo())
    pl = service.save_konzertabend(
        spotify_id="ka1",
        name="Rock im Park Tag 1",
        event_date=date(2026, 6, 5),
        festival="Rock im Park",
        city="Nuernberg",
        artists=["Linkin Park"],
        support_acts=["Spiritbox"],
    )

    assert pl.is_konzertabend() is True
    assert pl.event_date == date(2026, 6, 5)
    assert pl.festival == "Rock im Park"
    assert pl.artists == ["Linkin Park"]
    assert pl.support_acts == ["Spiritbox"]


def test_save_konzertabend_persists_via_repo():
    repo = _FakeRepo()
    service = PlaylistSaveService(repo)
    service.save_konzertabend(
        spotify_id="ka1",
        name="Test",
        event_date=date(2026, 6, 5),
    )

    # Direkt aus dem Repo lesen — Service hat es korrekt durchgereicht
    assert repo.get("ka1") is not None


# ─── update ──────────────────────────────────────────────────────────────────

def test_update_refreshes_updated_at():
    """update() ruft touch() auf — updated_at wird neu gesetzt."""
    service = PlaylistSaveService(_FakeRepo())
    pl = service.save_setlist_mix(spotify_id="abc", name="Test")
    original = pl.updated_at

    import time
    time.sleep(0.001)
    pl.description = "geaendert"
    service.update(pl)

    assert pl.updated_at > original


# ─── list_* ──────────────────────────────────────────────────────────────────

def test_list_konzertabende_filters_correctly():
    service = PlaylistSaveService(_FakeRepo())
    service.save_setlist_mix(spotify_id="mix1", name="Mix")
    service.save_konzertabend(spotify_id="ka1", name="KA")

    abende = service.list_konzertabende()
    assert len(abende) == 1
    assert abende[0].spotify_id == "ka1"


def test_list_setlist_mixes_filters_correctly():
    service = PlaylistSaveService(_FakeRepo())
    service.save_setlist_mix(spotify_id="mix1", name="Mix")
    service.save_konzertabend(spotify_id="ka1", name="KA")

    mixes = service.list_setlist_mixes()
    assert len(mixes) == 1
    assert mixes[0].spotify_id == "mix1"


def test_list_all_includes_both_types():
    service = PlaylistSaveService(_FakeRepo())
    service.save_setlist_mix(spotify_id="mix1", name="Mix")
    service.save_konzertabend(spotify_id="ka1", name="KA")

    assert len(service.list_all()) == 2


# ─── delete ──────────────────────────────────────────────────────────────────

def test_delete_existing_returns_true():
    service = PlaylistSaveService(_FakeRepo())
    service.save_setlist_mix(spotify_id="abc", name="Test")
    assert service.delete("abc") is True
    assert service.get("abc") is None


def test_delete_unknown_returns_false():
    service = PlaylistSaveService(_FakeRepo())
    assert service.delete("unknown") is False
