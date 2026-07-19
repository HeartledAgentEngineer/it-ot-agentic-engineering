"""
tests/repositories/test_json_repo.py
======================================
Tests fuer JsonArtistRepository.

Es gibt zwei Arten von Tests hier:
1. Unit-Tests mit tmp_path-Fixture: Wir schreiben eine kuenstliche
   Mini-JSON und pruefen das Mapping.
2. Integration-Tests gegen die echte concert_data.json: Pruefen ob
   ein paar bekannte Kuenstler korrekt geladen werden.

Engineering-Konzept: "Test Fixture"
    tmp_path ist ein pytest-Fixture — eine temporaere Verzeichnis-Vorlage
    die fuer jeden Test neu angelegt und nachher geloescht wird.
    So sind Tests sauber und reproduzierbar.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from repositories.json_repo import JsonArtistRepository


# ─── Unit-Tests mit kuenstlichen Daten ───────────────────────────────────────

def _write_test_json(tmp_path: Path, data: dict) -> Path:
    """Helper: schreibt ein Test-JSON und gibt den Pfad zurueck."""
    file = tmp_path / "test_data.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    return file


def test_get_returns_none_for_unknown_artist(tmp_path):
    file = _write_test_json(tmp_path, {})
    repo = JsonArtistRepository(file)
    assert repo.get("Unknown") is None


def test_list_names_returns_empty_for_empty_file(tmp_path):
    file = _write_test_json(tmp_path, {})
    repo = JsonArtistRepository(file)
    assert repo.list_names() == []


def test_list_names_merges_from_all_sections(tmp_path):
    """Namen koennen in hamburg_artists, rip_artists oder setlist_data stehen."""
    file = _write_test_json(tmp_path, {
        "hamburg_artists": {"Artist A": {"dates": []}},
        "rip_artists": {"Artist B": {"dates": []}},
        "setlist_data": {"Artist C": {"setlist_titles": []}},
    })
    repo = JsonArtistRepository(file)
    assert repo.list_names() == ["Artist A", "Artist B", "Artist C"]


def test_list_names_deduplicates(tmp_path):
    """Ein Artist der in mehreren Bereichen vorkommt → nur 1x im Ergebnis."""
    file = _write_test_json(tmp_path, {
        "hamburg_artists": {"LP": {"dates": []}},
        "setlist_data": {"LP": {"setlist_titles": []}},
    })
    repo = JsonArtistRepository(file)
    assert repo.list_names() == ["LP"]


def test_get_with_hamburg_concert(tmp_path):
    """Ein Artist mit Hamburg-Konzert wird mit Concert-Objekt geladen."""
    file = _write_test_json(tmp_path, {
        "hamburg_artists": {
            "LP": {
                "dates": ["2026-06-01"],
                "venues": {"2026-06-01": "Volksparkstadion"},
                "cities": {"2026-06-01": "Hamburg"},
            }
        }
    })
    repo = JsonArtistRepository(file)
    artist = repo.get("LP")

    assert artist is not None
    assert artist.name == "LP"
    assert len(artist.concerts) == 1
    assert artist.concerts[0].date == date(2026, 6, 1)
    assert artist.concerts[0].venue == "Volksparkstadion"
    assert artist.concerts[0].city == "Hamburg"
    assert artist.concerts[0].festival is None


def test_get_with_festival_concert(tmp_path):
    file = _write_test_json(tmp_path, {
        "rip_artists": {
            "LP": {
                "dates": ["2026-06-05"],
                "venue": "Zeppelinfeld",
                "festival": "Rock im Park",
                "cities": {"2026-06-05": "Nuernberg"},
            }
        }
    })
    repo = JsonArtistRepository(file)
    artist = repo.get("LP")

    assert artist is not None
    assert len(artist.concerts) == 1
    assert artist.concerts[0].festival == "Rock im Park"
    assert artist.concerts[0].is_festival() is True


def test_get_setlist_maps_all_song_fields(tmp_path):
    """Eine Setlist mit vollstaendigen Daten wird komplett gemappt."""
    file = _write_test_json(tmp_path, {
        "setlist_data": {
            "LP": {
                "setlist_titles": ["Numb", "Faint"],
                "play_counts": {"Numb": 83, "Faint": 60},
                "scores": {"Numb": 1.0, "Faint": 0.72},
                "spotify_uris": {
                    "Numb": "spotify:track:2nLtzopw4rPReszdYBJU6h",
                },
                "positions_hist": {
                    "Numb": {"24": 75, "25": 8},
                    "Faint": {"26": 50, "27": 10},
                },
                "badges": {"Numb": "setlist", "Faint": "setlist"},
                "total_concerts_analyzed": 83,
                "set_type": "From Zero Tour",
            }
        }
    })
    repo = JsonArtistRepository(file)
    setlist = repo.get_setlist("LP")

    assert setlist is not None
    assert setlist.total_concerts_analyzed == 83
    assert setlist.set_type == "From Zero Tour"
    assert len(setlist.songs) == 2

    numb = setlist.find_song("Numb")
    assert numb is not None
    assert numb.play_count == 83
    assert numb.score == 1.0
    assert numb.spotify_uri == "spotify:track:2nLtzopw4rPReszdYBJU6h"
    assert numb.has_uri() is True
    # positions_hist hat int-Keys nach dem Mapping (in JSON sind sie String)
    assert numb.positions_hist == {24: 75, 25: 8}
    assert numb.badge == "setlist"


def test_get_setlist_returns_none_when_no_data(tmp_path):
    file = _write_test_json(tmp_path, {})
    repo = JsonArtistRepository(file)
    assert repo.get_setlist("LP") is None


def test_get_setlist_with_minimal_data(tmp_path):
    """Setlist mit nur Titles, ohne Statistiken — alle Defaults werden gesetzt."""
    file = _write_test_json(tmp_path, {
        "setlist_data": {
            "Newcomer": {"setlist_titles": ["Song A"]}
        }
    })
    repo = JsonArtistRepository(file)
    setlist = repo.get_setlist("Newcomer")

    assert setlist is not None
    assert len(setlist.songs) == 1
    song = setlist.songs[0]
    assert song.title == "Song A"
    assert song.play_count == 0
    assert song.score == 0.0
    assert song.spotify_uri is None


def test_cache_is_used(tmp_path):
    """Zweiter Aufruf ohne _invalidate_cache liest nicht erneut von Disk."""
    file = _write_test_json(tmp_path, {
        "hamburg_artists": {"A": {"dates": []}}
    })
    repo = JsonArtistRepository(file)

    repo.list_names()
    # Datei aendern — aber repo._cache haelt noch die alten Daten
    file.write_text(json.dumps({
        "hamburg_artists": {"B": {"dates": []}}
    }), encoding="utf-8")

    # Ohne invalidate → alte Liste
    assert repo.list_names() == ["A"]

    # Mit invalidate → frisch geladen
    repo._invalidate_cache()
    assert repo.list_names() == ["B"]


# ─── Integration-Test gegen die echte concert_data.json ─────────────────────

CONCERT_DATA = Path(__file__).resolve().parent.parent.parent / "concert_data.json"


@pytest.mark.skipif(not CONCERT_DATA.exists(), reason="concert_data.json fehlt")
def test_real_data_loads_h_blockx():
    """H-Blockx-Setlist laesst sich laden und hat erwartete Struktur.

    Hinweis: Wir pruefen NICHT die genauen play_counts/total_concerts, weil
    die alte app.py-Logik diese Werte ueber verschiedene Code-Pfade
    aendern kann (siehe save_setlist-Bug). Wir pruefen nur dass die
    Struktur konsistent geladen wird.
    """
    repo = JsonArtistRepository(CONCERT_DATA)
    setlist = repo.get_setlist("H-Blockx")

    assert setlist is not None
    # "Straight Outta Nowhere" soll geladen werden (Opener)
    sotw = setlist.find_song("Straight Outta Nowhere")
    assert sotw is not None
    # Alle Songs sollen valide Felder haben (kein Crash beim Mapping)
    for song in setlist.songs:
        assert isinstance(song.title, str) and song.title
        assert isinstance(song.score, float)
        assert isinstance(song.play_count, int)
        assert isinstance(song.positions_hist, dict)


@pytest.mark.skipif(not CONCERT_DATA.exists(), reason="concert_data.json fehlt")
def test_real_data_has_known_artists():
    """Bekannte Kuenstler sollten in list_names auftauchen."""
    repo = JsonArtistRepository(CONCERT_DATA)
    names = repo.list_names()
    # Die Liste sollte einige bekannte Kuenstler enthalten
    # (wir pruefen nicht alle, da sich die Liste aendern kann)
    expected_some = {"Linkin Park", "H-Blockx", "Three Days Grace"}
    found = expected_some & set(names)  # Schnittmenge
    assert len(found) >= 2, f"Erwartete bekannte Kuenstler, gefunden: {found}"
