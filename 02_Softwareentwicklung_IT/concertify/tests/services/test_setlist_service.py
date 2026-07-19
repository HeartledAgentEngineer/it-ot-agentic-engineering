"""
tests/services/test_setlist_service.py
=========================================
Tests fuer SetlistService.

Engineering-Konzept: "Mock Object"
    Statt eines echten JsonArtistRepository nutzen wir hier ein einfaches
    Fake-Repo (`_FakeRepo`). So testen wir nur die Service-Logik, ohne
    von der JSON-Datei abhaengig zu sein.

    "Mock" = ein Imitations-Objekt mit kontrollierten Antworten.
    In C# waere das ein Mock mit Moq oder NSubstitute.
"""

from domain.setlist import Setlist
from domain.song import Song
from repositories.base import ArtistRepository
from services.setlist_service import SetlistService


# ─── Fake-Repo fuer Tests ────────────────────────────────────────────────────

class _FakeRepo(ArtistRepository):
    """Ein in-memory Repo das wir fuer Tests befuellen.

    Die ABC-Klasse (ArtistRepository) zwingt uns, alle abstract methods zu
    implementieren — sonst gibt es einen TypeError beim Instanziieren.
    """

    def __init__(self, setlists: dict[str, Setlist] | None = None):
        self._setlists = setlists or {}

    def get(self, name):
        return None  # nicht relevant fuer diese Tests

    def list_names(self):
        return sorted(self._setlists.keys())

    def get_setlist(self, name):
        return self._setlists.get(name)


def _make_setlist_with_songs(artist: str, songs_data: list[dict]) -> Setlist:
    """Hilfsfunktion: baut eine Setlist aus einer Liste von dicts."""
    setlist = Setlist(artist_name=artist, total_concerts_analyzed=10)
    for d in songs_data:
        setlist.add_song(Song(**d))  # **d entpackt das Dict als Keyword-Args
    return setlist


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_get_setlist_returns_none_for_unknown_artist():
    service = SetlistService(_FakeRepo())
    assert service.get_setlist("Unknown") is None


def test_get_setlist_returns_setlist_when_present():
    setlist = _make_setlist_with_songs("LP", [{"title": "Numb"}])
    service = SetlistService(_FakeRepo({"LP": setlist}))

    result = service.get_setlist("LP")
    assert result is setlist


def test_get_display_songs_empty_for_unknown_artist():
    service = SetlistService(_FakeRepo())
    assert service.get_display_songs("Unknown") == []


def test_get_display_songs_orders_played_first_then_unplayed():
    """Reihenfolge: erst gespielt (sortiert nach play_count), dann nicht gespielt."""
    setlist = _make_setlist_with_songs("LP", [
        {"title": "Never Played", "play_count": 0, "score": 0.0},
        {"title": "Sometimes",     "play_count": 5, "score": 0.5},
        {"title": "Always",        "play_count": 10, "score": 1.0},
        {"title": "Predicted",     "play_count": 0, "score": 0.8},
    ])
    service = SetlistService(_FakeRepo({"LP": setlist}))

    songs = service.get_display_songs("LP")
    titles = [s.title for s in songs]

    # Erst die gespielten, hoechster play_count zuerst:
    assert titles[0] == "Always"
    assert titles[1] == "Sometimes"
    # Dann die nicht gespielten, hoechster score zuerst:
    assert titles[2] == "Predicted"
    assert titles[3] == "Never Played"


def test_get_display_songs_with_limit():
    setlist = _make_setlist_with_songs("LP", [
        {"title": f"Song {i}", "play_count": 10 - i, "score": 1.0}
        for i in range(10)
    ])
    service = SetlistService(_FakeRepo({"LP": setlist}))

    songs = service.get_display_songs("LP", limit=3)
    assert len(songs) == 3
    assert songs[0].title == "Song 0"  # hoechster play_count


def test_get_display_songs_only_likely_filters_by_score():
    setlist = _make_setlist_with_songs("LP", [
        {"title": "Sure",   "play_count": 0, "score": 0.9},
        {"title": "Maybe",  "play_count": 0, "score": 0.4},
        {"title": "Likely", "play_count": 0, "score": 0.7},
    ])
    service = SetlistService(_FakeRepo({"LP": setlist}))

    songs = service.get_display_songs("LP", only_likely=True)
    titles = {s.title for s in songs}

    # Nur Songs mit score >= 0.5 (default threshold von is_likely_played)
    assert titles == {"Sure", "Likely"}


def test_setlist_summary_returns_eck_data():
    setlist = _make_setlist_with_songs("LP", [
        {"title": "A", "play_count": 5},
        {"title": "B", "play_count": 0},  # nicht gespielt
        {"title": "C", "play_count": 3},
    ])
    setlist.set_type = "From Zero Tour"
    service = SetlistService(_FakeRepo({"LP": setlist}))

    summary = service.setlist_summary("LP")

    assert summary is not None
    assert summary["artist_name"] == "LP"
    assert summary["total_songs"] == 3
    assert summary["played_songs"] == 2  # nur A und C
    assert summary["total_concerts"] == 10
    assert summary["set_type"] == "From Zero Tour"
    assert summary["has_real_data"] is True


def test_setlist_summary_returns_none_for_unknown():
    service = SetlistService(_FakeRepo())
    assert service.setlist_summary("Unknown") is None
