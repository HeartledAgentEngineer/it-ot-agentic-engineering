"""
tests/services/test_playlist_import_service.py
================================================
Tests fuer PlaylistImportService (Preview-Modus).
"""

from datetime import date

import pytest

from domain.artist import Artist
from domain.saved_playlist import (
    PLAYLIST_TYPE_KONZERTABEND,
    PLAYLIST_TYPE_SETLIST_MIX,
    SavedPlaylist,
)
from domain.setlist import Setlist
from domain.song import Song
from repositories.base import ArtistRepository
from repositories.saved_playlist_repo import SavedPlaylistRepository
from services.playlist_import_service import PlaylistImportService


# ─── Fake-Repos ──────────────────────────────────────────────────────────────

class _FakeArtistRepo(ArtistRepository):
    def __init__(self, artists: dict[str, Artist] | None = None):
        self._artists = artists or {}

    def get(self, name):
        return self._artists.get(name)

    def list_names(self):
        return sorted(self._artists.keys())

    def get_setlist(self, name):
        a = self._artists.get(name)
        return a.setlist if a else None


class _FakePlaylistRepo(SavedPlaylistRepository):
    def __init__(self, playlists: dict[str, SavedPlaylist] | None = None):
        self._playlists = playlists or {}

    def get(self, spotify_id):
        return self._playlists.get(spotify_id)

    def list_all(self):
        return list(self._playlists.values())

    def list_by_type(self, playlist_type):
        return [p for p in self._playlists.values() if p.playlist_type == playlist_type]

    def save(self, playlist):
        self._playlists[playlist.spotify_id] = playlist

    def delete(self, spotify_id):
        return self._playlists.pop(spotify_id, None) is not None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_konzertabend() -> SavedPlaylist:
    pl = SavedPlaylist(
        spotify_id="rip1",
        name="RiP Tag 1",
        playlist_type=PLAYLIST_TYPE_KONZERTABEND,
        event_date=date(2026, 6, 5),
        festival="Rock im Park",
        city="Nuernberg",
    )
    pl.add_artist("Linkin Park")
    pl.add_artist("Spiritbox", is_support=True)
    pl.set_songs_for_artist("Linkin Park", ["Numb", "In the End", "Faint"])
    pl.set_songs_for_artist("Spiritbox", ["Holy Roller"])
    return pl


def _make_artist_with_setlist(name: str, song_titles: list[str]) -> Artist:
    setlist = Setlist(artist_name=name, total_concerts_analyzed=10)
    for t in song_titles:
        setlist.add_song(Song(title=t, play_count=5))
    return Artist(name=name, setlist=setlist)


# ─── Tests: preview() ────────────────────────────────────────────────────────

def test_preview_returns_none_for_unknown_playlist():
    service = PlaylistImportService(_FakePlaylistRepo(), _FakeArtistRepo())
    assert service.preview("unknown") is None


def test_preview_when_no_artist_exists_in_concerts():
    """Wenn die Kuenstler noch nicht in concert_data.json sind, sollen sie als
    'NEU anzulegen' gekennzeichnet sein."""
    playlist_repo = _FakePlaylistRepo({"rip1": _make_konzertabend()})
    artist_repo = _FakeArtistRepo()  # leer
    service = PlaylistImportService(playlist_repo, artist_repo)

    preview = service.preview("rip1")

    assert preview is not None
    assert preview.playlist_type == PLAYLIST_TYPE_KONZERTABEND
    assert preview.festival == "Rock im Park"
    assert preview.event_date == "2026-06-05"

    # 2 Kuenstler: Spiritbox (Support) + LP
    assert len(preview.artists) == 2

    # Reihenfolge: Support zuerst
    assert preview.artists[0].name == "Spiritbox"
    assert preview.artists[0].is_support_act is True

    # Beide muessen neu angelegt werden
    assert all(not a.exists_in_concerts for a in preview.artists)
    assert preview.total_artists_to_create() == 2
    assert preview.is_fully_present() is False


def test_preview_when_artist_exists_but_setlist_empty():
    """Artist existiert, hat aber noch keine Setlist."""
    artist = Artist(name="Linkin Park")  # ohne Setlist

    playlist_repo = _FakePlaylistRepo({"rip1": _make_konzertabend()})
    artist_repo = _FakeArtistRepo({"Linkin Park": artist})
    service = PlaylistImportService(playlist_repo, artist_repo)

    preview = service.preview("rip1")

    lp_info = next(a for a in preview.artists if a.name == "Linkin Park")
    assert lp_info.exists_in_concerts is True
    assert lp_info.has_setlist_data is False
    # Alle Songs aus der Playlist fehlen (keine Setlist da)
    assert lp_info.songs_missing == ["Numb", "In the End", "Faint"]
    assert lp_info.action_summary() == "Setlist-Daten werden hinzugefuegt"


def test_preview_when_artist_has_partial_setlist():
    """Setlist existiert, aber nicht alle Songs aus der Playlist sind drin."""
    artist = _make_artist_with_setlist("Linkin Park", ["Numb"])  # nur Numb da

    playlist_repo = _FakePlaylistRepo({"rip1": _make_konzertabend()})
    artist_repo = _FakeArtistRepo({"Linkin Park": artist})
    service = PlaylistImportService(playlist_repo, artist_repo)

    preview = service.preview("rip1")

    lp_info = next(a for a in preview.artists if a.name == "Linkin Park")
    assert lp_info.exists_in_concerts is True
    assert lp_info.has_setlist_data is True
    # Numb ist schon da → fehlend: In the End + Faint
    assert lp_info.songs_missing == ["In the End", "Faint"]
    assert "2 Songs werden ergaenzt" in lp_info.action_summary()


def test_preview_when_everything_already_present():
    """Wenn alles schon vorhanden, ist is_fully_present True."""
    lp = _make_artist_with_setlist("Linkin Park", ["Numb", "In the End", "Faint"])
    sb = _make_artist_with_setlist("Spiritbox", ["Holy Roller"])

    playlist_repo = _FakePlaylistRepo({"rip1": _make_konzertabend()})
    artist_repo = _FakeArtistRepo({"Linkin Park": lp, "Spiritbox": sb})
    service = PlaylistImportService(playlist_repo, artist_repo)

    preview = service.preview("rip1")

    assert preview.is_fully_present() is True
    assert preview.total_artists_to_create() == 0
    assert preview.total_songs_to_add() == 0


# ─── Tests: list_importable() ────────────────────────────────────────────────

def test_list_importable_returns_summary_per_playlist():
    pl1 = _make_konzertabend()
    pl2 = SavedPlaylist(
        spotify_id="mix1",
        name="Mein Mix",
        playlist_type=PLAYLIST_TYPE_SETLIST_MIX,
    )
    pl2.add_artist("Bring Me The Horizon")
    pl2.set_songs_for_artist("Bring Me The Horizon", ["Drown"])

    playlist_repo = _FakePlaylistRepo({"rip1": pl1, "mix1": pl2})
    service = PlaylistImportService(playlist_repo, _FakeArtistRepo())

    items = service.list_importable()
    assert len(items) == 2

    by_id = {it["spotify_id"]: it for it in items}
    assert by_id["rip1"]["festival"] == "Rock im Park"
    assert by_id["rip1"]["song_count"] == 4
    assert by_id["mix1"]["playlist_type"] == PLAYLIST_TYPE_SETLIST_MIX


def test_list_importable_marks_fully_present():
    pl = SavedPlaylist(
        spotify_id="abc",
        name="Test",
        playlist_type=PLAYLIST_TYPE_SETLIST_MIX,
    )
    pl.add_artist("LP")
    pl.set_songs_for_artist("LP", ["Numb"])

    lp = _make_artist_with_setlist("LP", ["Numb"])

    playlist_repo = _FakePlaylistRepo({"abc": pl})
    artist_repo = _FakeArtistRepo({"LP": lp})
    service = PlaylistImportService(playlist_repo, artist_repo)

    items = service.list_importable()
    assert items[0]["is_fully_present"] is True
    assert items[0]["artists_to_create"] == 0
    assert items[0]["songs_to_add"] == 0
