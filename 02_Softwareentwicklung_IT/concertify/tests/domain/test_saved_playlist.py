"""
tests/domain/test_saved_playlist.py
=====================================
Unit-Tests fuer die SavedPlaylist-Klasse.
"""

from datetime import date

import pytest

from domain.saved_playlist import (
    PLAYLIST_TYPE_KONZERTABEND,
    PLAYLIST_TYPE_SETLIST_MIX,
    SavedPlaylist,
)


# ─── Validierung ─────────────────────────────────────────────────────────────

def test_create_setlist_mix_with_minimum_fields():
    pl = SavedPlaylist(
        spotify_id="abc123",
        name="Mein Mix",
        playlist_type=PLAYLIST_TYPE_SETLIST_MIX,
    )
    assert pl.spotify_id == "abc123"
    assert pl.is_setlist_mix() is True
    assert pl.is_konzertabend() is False


def test_create_konzertabend_with_event_data():
    pl = SavedPlaylist(
        spotify_id="xyz789",
        name="Rock im Park Tag 1",
        playlist_type=PLAYLIST_TYPE_KONZERTABEND,
        event_date=date(2026, 6, 5),
        venue="Zeppelinfeld",
        city="Nuernberg",
        festival="Rock im Park",
    )
    assert pl.is_konzertabend() is True
    assert pl.festival == "Rock im Park"
    assert pl.event_date == date(2026, 6, 5)


def test_invalid_playlist_type_raises():
    with pytest.raises(ValueError, match="playlist_type"):
        SavedPlaylist(
            spotify_id="abc",
            name="Test",
            playlist_type="something_invalid",
        )


def test_empty_spotify_id_raises():
    with pytest.raises(ValueError, match="spotify_id"):
        SavedPlaylist(spotify_id="", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)


def test_empty_name_raises():
    with pytest.raises(ValueError, match="name"):
        SavedPlaylist(spotify_id="abc", name="", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)


# ─── Kuenstler-Management ────────────────────────────────────────────────────

def test_add_artist_appends_to_artists():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    pl.add_artist("Linkin Park")
    assert pl.artists == ["Linkin Park"]
    assert pl.support_acts == []
    assert pl.has_artist("Linkin Park") is True


def test_add_support_act_appends_to_support_list():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_KONZERTABEND)
    pl.add_artist("Linkin Park", is_support=False)
    pl.add_artist("Spiritbox", is_support=True)
    assert pl.artists == ["Linkin Park"]
    assert pl.support_acts == ["Spiritbox"]
    assert pl.has_artist("Spiritbox") is True


def test_add_duplicate_artist_raises():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    pl.add_artist("LP")
    with pytest.raises(ValueError, match="bereits"):
        pl.add_artist("LP")


def test_all_artists_orders_supports_first():
    """Support Acts kommen ZUERST (Vorgruppe vor Headliner)."""
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_KONZERTABEND)
    pl.add_artist("Headliner")
    pl.add_artist("Support 1", is_support=True)
    pl.add_artist("Support 2", is_support=True)

    # Bei einem Konzert: Support 1 → Support 2 → Headliner
    assert pl.all_artists() == ["Support 1", "Support 2", "Headliner"]


# ─── Song-Selections ─────────────────────────────────────────────────────────

def test_songs_for_unknown_artist_returns_empty():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    assert pl.songs_for_artist("Unknown") == []


def test_set_songs_for_artist():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    pl.add_artist("LP")
    pl.set_songs_for_artist("LP", ["Numb", "In the End", "Faint"])
    assert pl.songs_for_artist("LP") == ["Numb", "In the End", "Faint"]


def test_set_songs_for_unknown_artist_raises():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    with pytest.raises(ValueError, match="nicht in Playlist"):
        pl.set_songs_for_artist("Unknown", ["Song"])


def test_total_song_count_sums_across_artists():
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_KONZERTABEND)
    pl.add_artist("LP")
    pl.add_artist("BB")
    pl.set_songs_for_artist("LP", ["S1", "S2", "S3"])
    pl.set_songs_for_artist("BB", ["S1", "S2"])
    assert pl.total_song_count() == 5


# ─── touch / updated_at ──────────────────────────────────────────────────────

def test_touch_updates_timestamp():
    """`touch()` aktualisiert updated_at — wichtig fuer Sync/Sortierung."""
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    original = pl.updated_at

    # Kurz warten damit der Zeitstempel sich aendert
    import time
    time.sleep(0.001)
    pl.touch()

    assert pl.updated_at > original


def test_add_artist_calls_touch():
    """Beim Hinzufuegen eines Kuenstlers wird updated_at aktualisiert."""
    pl = SavedPlaylist(spotify_id="abc", name="Test", playlist_type=PLAYLIST_TYPE_SETLIST_MIX)
    original = pl.updated_at

    import time
    time.sleep(0.001)
    pl.add_artist("LP")

    assert pl.updated_at > original
