"""
tests/repositories/test_saved_playlist_repo.py
================================================
Tests fuer JsonSavedPlaylistRepository.
"""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from domain.saved_playlist import (
    PLAYLIST_TYPE_KONZERTABEND,
    PLAYLIST_TYPE_SETLIST_MIX,
    SavedPlaylist,
)
from repositories.saved_playlist_repo import JsonSavedPlaylistRepository


# ─── Hilfsfunktion ──────────────────────────────────────────────────────────

def _make_playlist(spotify_id: str = "abc", name: str = "Test") -> SavedPlaylist:
    return SavedPlaylist(
        spotify_id=spotify_id,
        name=name,
        playlist_type=PLAYLIST_TYPE_SETLIST_MIX,
    )


def _make_konzertabend(spotify_id: str = "xyz") -> SavedPlaylist:
    pl = SavedPlaylist(
        spotify_id=spotify_id,
        name="Rock im Park Tag 1",
        playlist_type=PLAYLIST_TYPE_KONZERTABEND,
        event_date=date(2026, 6, 5),
        venue="Zeppelinfeld",
        city="Nuernberg",
        festival="Rock im Park",
        stages=["Mandora", "Utopia"],
        config={"limit_per_artist": 22},
    )
    pl.add_artist("Linkin Park")
    pl.add_artist("Spiritbox", is_support=True)
    pl.set_songs_for_artist("Linkin Park", ["Numb", "In the End"])
    pl.set_songs_for_artist("Spiritbox", ["Holy Roller"])
    return pl


# ─── Basis-Operationen ──────────────────────────────────────────────────────

def test_get_returns_none_when_no_file(tmp_path):
    repo = JsonSavedPlaylistRepository(tmp_path / "nofile.json")
    assert repo.get("anything") is None


def test_list_all_returns_empty_for_no_file(tmp_path):
    repo = JsonSavedPlaylistRepository(tmp_path / "nofile.json")
    assert repo.list_all() == []


def test_save_then_get_returns_equal_playlist(tmp_path):
    """Roundtrip: speichern + lesen → identisches Objekt-Verhalten."""
    repo = JsonSavedPlaylistRepository(tmp_path / "playlists.json")
    original = _make_konzertabend()
    repo.save(original)

    loaded = repo.get("xyz")

    assert loaded is not None
    assert loaded.spotify_id == original.spotify_id
    assert loaded.name == original.name
    assert loaded.event_date == date(2026, 6, 5)
    assert loaded.festival == "Rock im Park"
    assert loaded.artists == ["Linkin Park"]
    assert loaded.support_acts == ["Spiritbox"]
    assert loaded.songs_for_artist("Linkin Park") == ["Numb", "In the End"]
    assert loaded.config == {"limit_per_artist": 22}


def test_save_overwrites_existing(tmp_path):
    repo = JsonSavedPlaylistRepository(tmp_path / "playlists.json")
    pl1 = _make_playlist("abc", "Erster Name")
    repo.save(pl1)

    pl2 = _make_playlist("abc", "Zweiter Name")
    repo.save(pl2)

    loaded = repo.get("abc")
    assert loaded.name == "Zweiter Name"


def test_save_persists_to_disk(tmp_path):
    """Nach save() existiert die JSON-Datei und enthaelt die Daten."""
    file = tmp_path / "playlists.json"
    repo = JsonSavedPlaylistRepository(file)
    repo.save(_make_playlist("abc", "Test"))

    assert file.exists()
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert "playlists" in raw
    assert len(raw["playlists"]) == 1
    assert raw["playlists"][0]["spotify_id"] == "abc"


def test_load_from_existing_file(tmp_path):
    """Repo das eine bestehende Datei findet, kann die Daten lesen."""
    file = tmp_path / "playlists.json"
    file.write_text(json.dumps({
        "playlists": [
            {
                "spotify_id": "preexist",
                "name": "Vorhanden",
                "playlist_type": "setlist_mix",
                "created_at": "2026-05-26T10:00:00",
                "updated_at": "2026-05-26T10:00:00",
            }
        ]
    }), encoding="utf-8")

    repo = JsonSavedPlaylistRepository(file)
    loaded = repo.get("preexist")
    assert loaded is not None
    assert loaded.name == "Vorhanden"


# ─── delete ──────────────────────────────────────────────────────────────────

def test_delete_returns_true_for_existing(tmp_path):
    repo = JsonSavedPlaylistRepository(tmp_path / "p.json")
    repo.save(_make_playlist("abc"))

    assert repo.delete("abc") is True
    assert repo.get("abc") is None


def test_delete_returns_false_for_unknown(tmp_path):
    repo = JsonSavedPlaylistRepository(tmp_path / "p.json")
    assert repo.delete("unknown") is False


# ─── list_by_type ────────────────────────────────────────────────────────────

def test_list_by_type_filters_correctly(tmp_path):
    repo = JsonSavedPlaylistRepository(tmp_path / "p.json")

    pl_mix = _make_playlist("mix1")
    pl_ka = SavedPlaylist(
        spotify_id="ka1",
        name="Konzertabend",
        playlist_type=PLAYLIST_TYPE_KONZERTABEND,
    )
    repo.save(pl_mix)
    repo.save(pl_ka)

    mixes = repo.list_by_type(PLAYLIST_TYPE_SETLIST_MIX)
    abends = repo.list_by_type(PLAYLIST_TYPE_KONZERTABEND)

    assert len(mixes) == 1
    assert mixes[0].spotify_id == "mix1"
    assert len(abends) == 1
    assert abends[0].spotify_id == "ka1"


# ─── list_all Sortierung ─────────────────────────────────────────────────────

def test_list_all_sorts_by_updated_at_descending(tmp_path):
    """Zuletzt geaendert → ganz oben."""
    repo = JsonSavedPlaylistRepository(tmp_path / "p.json")

    pl_old = _make_playlist("old", "Alt")
    pl_old.updated_at = datetime(2026, 1, 1, 12, 0, 0)
    repo.save(pl_old)

    pl_new = _make_playlist("new", "Neu")
    pl_new.updated_at = datetime(2026, 5, 26, 12, 0, 0)
    repo.save(pl_new)

    all_pl = repo.list_all()
    assert len(all_pl) == 2
    assert all_pl[0].spotify_id == "new"  # neueste zuerst
    assert all_pl[1].spotify_id == "old"


# ─── Atomares Schreiben ──────────────────────────────────────────────────────

def test_save_uses_atomic_replace(tmp_path):
    """Wenn save() laeuft, ist die Zieldatei nie in einem halben Zustand."""
    file = tmp_path / "playlists.json"
    repo = JsonSavedPlaylistRepository(file)
    repo.save(_make_playlist("abc"))

    # Die .tmp-Datei sollte nach save() weg sein (durch os.replace)
    tmp_file = file.with_suffix(".tmp")
    assert not tmp_file.exists()
    assert file.exists()
