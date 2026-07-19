"""
tests/services/test_song_state_service.py
=========================================
Tests fuer Song-Zustands- und Sortierservice (TDD).
"""

from services.song_state_service import toggle_song_excluded, reorder_songs


def _cd():
    return {
        "setlist_data": {
            "Linkin Park": {
                "setlist_titles": ["Numb", "In the End", "Faint"],
                "spotify_uris": {
                    "Numb": "spotify:track:1",
                    "In the End": "spotify:track:2",
                    "Faint": "spotify:track:3"
                },
                "excluded_songs": [],
                "manual_order": []
            }
        }
    }


def test_toggle_song_excluded_adds_and_removes():
    cd = _cd()
    # 1. Hinzufuegen
    ok, err = toggle_song_excluded(cd, "Linkin Park", "In the End", True)
    assert ok is True
    assert err is None
    assert cd["setlist_data"]["Linkin Park"]["excluded_songs"] == ["In the End"]

    # 2. Erneutes Hinzufuegen (sollte idempotent sein)
    ok, err = toggle_song_excluded(cd, "Linkin Park", "In the End", True)
    assert ok is True
    assert cd["setlist_data"]["Linkin Park"]["excluded_songs"] == ["In the End"]

    # 3. Entfernen
    ok, err = toggle_song_excluded(cd, "Linkin Park", "In the End", False)
    assert ok is True
    assert cd["setlist_data"]["Linkin Park"]["excluded_songs"] == []


def test_toggle_song_excluded_unknown_artist():
    cd = _cd()
    ok, err = toggle_song_excluded(cd, "Unknown", "Numb", True)
    assert ok is False
    assert err == "unknown artist"


def test_reorder_songs_saves_manual_order():
    cd = _cd()
    ok, err = reorder_songs(cd, "Linkin Park", ["Faint", "Numb", "In the End"])
    assert ok is True
    assert err is None
    assert cd["setlist_data"]["Linkin Park"]["manual_order"] == ["Faint", "Numb", "In the End"]


def test_reorder_songs_unknown_artist():
    cd = _cd()
    ok, err = reorder_songs(cd, "Unknown", ["Song 1"])
    assert ok is False
    assert err == "unknown artist"
