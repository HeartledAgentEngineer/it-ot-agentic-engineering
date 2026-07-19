"""
tests/domain/test_setlist.py
=============================
Unit-Tests fuer die Setlist-Klasse.
"""

import pytest

from domain.setlist import Setlist
from domain.song import Song


# ─── add_song + Duplikat-Schutz ──────────────────────────────────────────────

def test_new_setlist_has_no_songs():
    setlist = Setlist(artist_name="Test")
    assert setlist.songs == []


def test_add_song_appends_to_songs():
    setlist = Setlist(artist_name="Test")
    setlist.add_song(Song(title="A"))
    setlist.add_song(Song(title="B"))
    assert len(setlist.songs) == 2
    assert setlist.songs[0].title == "A"
    assert setlist.songs[1].title == "B"


def test_add_duplicate_song_raises_value_error():
    """Doppelte Songtitel sind nicht erlaubt — Domain-Regel.

    pytest.raises = "der nachfolgende Code WIRD eine Exception werfen".
    Wenn keine Exception kommt → Test schlaegt fehl.
    """
    setlist = Setlist(artist_name="Test")
    setlist.add_song(Song(title="Numb"))

    with pytest.raises(ValueError, match="bereits in Setlist"):
        setlist.add_song(Song(title="Numb"))


# ─── find_song ───────────────────────────────────────────────────────────────

def test_find_song_returns_song_when_present():
    setlist = Setlist(artist_name="Test")
    song = Song(title="Numb", score=1.0)
    setlist.add_song(song)

    found = setlist.find_song("Numb")
    assert found is song  # `is` prueft ob es das gleiche Objekt ist


def test_find_song_returns_none_when_missing():
    setlist = Setlist(artist_name="Test")
    setlist.add_song(Song(title="Numb"))

    assert setlist.find_song("Nonexistent") is None


# ─── played_songs ────────────────────────────────────────────────────────────

def test_played_songs_filters_zero_play_count():
    """Songs mit play_count=0 sind nicht 'gespielt' und werden gefiltert."""
    setlist = Setlist(artist_name="Test")
    setlist.add_song(Song(title="Played", play_count=5))
    setlist.add_song(Song(title="Never", play_count=0))
    setlist.add_song(Song(title="Often", play_count=10))

    played = setlist.played_songs()

    assert len(played) == 2
    # sortiert absteigend: Often (10) vor Played (5)
    assert played[0].title == "Often"
    assert played[1].title == "Played"


def test_played_songs_does_not_modify_original_list():
    """played_songs() darf die songs-Liste nicht veraendern."""
    setlist = Setlist(artist_name="Test")
    setlist.add_song(Song(title="A", play_count=0))
    setlist.add_song(Song(title="B", play_count=5))

    setlist.played_songs()

    # Original-Liste muss noch 2 Songs haben
    assert len(setlist.songs) == 2


# ─── top_songs ───────────────────────────────────────────────────────────────

def test_top_songs_orders_by_score_descending():
    setlist = Setlist(artist_name="Test")
    setlist.add_song(Song(title="Low", score=0.2))
    setlist.add_song(Song(title="High", score=0.9))
    setlist.add_song(Song(title="Mid", score=0.5))

    top = setlist.top_songs()

    assert top[0].title == "High"
    assert top[1].title == "Mid"
    assert top[2].title == "Low"


def test_top_songs_limits_to_n():
    setlist = Setlist(artist_name="Test")
    for i in range(20):
        setlist.add_song(Song(title=f"Song{i}", score=i / 20))

    top5 = setlist.top_songs(n=5)
    assert len(top5) == 5


# ─── has_real_data ───────────────────────────────────────────────────────────

def test_has_real_data_false_when_no_concerts_analyzed():
    setlist = Setlist(artist_name="Test", total_concerts_analyzed=0)
    assert setlist.has_real_data() is False


def test_has_real_data_true_when_concerts_analyzed():
    setlist = Setlist(artist_name="Test", total_concerts_analyzed=83)
    assert setlist.has_real_data() is True
