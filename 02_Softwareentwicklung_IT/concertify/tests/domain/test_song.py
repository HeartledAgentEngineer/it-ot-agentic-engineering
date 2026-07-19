"""
tests/domain/test_song.py
==========================
Unit-Tests fuer die Song-Klasse.

Engineering-Konzept: "Unit Test"
    Ein Test pruefte EIN konkretes Verhalten in Isolation.
    Wenn der Test fehlschlaegt, weisst du genau was kaputt ist —
    du musst nicht durch den Browser klicken.

Brueckenwissen:
    C#:           Wie NUnit/xUnit-Tests mit `[Test]`-Attribut.
    TwinCAT:      Wie eine Simulation eines FB mit definierten Inputs
                  und erwarteten Outputs.

Konvention von pytest:
    - Dateinamen beginnen mit `test_`
    - Funktionen beginnen mit `test_`
    - Mit `assert` pruefst du eine Bedingung
    - Wenn `assert` False ist → Test fehlgeschlagen
"""

import pytest  # noqa: F401 — pytest wird fuer manche Tests gebraucht

from domain.song import Song


# ─── Test 1: Standard-Werte beim Anlegen ─────────────────────────────────────
# Test-Funktionsname ist eine selbstbeschreibende Saetze:
# "test_song_with_default_values_has_empty_uri"
# = "ein Song mit Default-Werten hat eine leere URI"

def test_song_with_default_values_has_empty_uri():
    """Ein neuer Song ohne URI hat None als spotify_uri."""
    song = Song(title="Test Song")
    assert song.spotify_uri is None
    assert song.has_uri() is False


def test_song_with_uri_returns_true_from_has_uri():
    """Ein Song mit echter URI gibt True bei has_uri()."""
    song = Song(title="Numb", spotify_uri="spotify:track:2nLtzopw4rPReszdYBJU6h")
    assert song.has_uri() is True


def test_song_with_empty_string_uri_returns_false():
    """Ein leerer String zaehlt nicht als gueltige URI."""
    song = Song(title="Test", spotify_uri="")
    assert song.has_uri() is False


# ─── Test 2: position_range ──────────────────────────────────────────────────

def test_position_range_with_empty_history_returns_none():
    """Ohne positions_hist soll position_range() None liefern."""
    song = Song(title="Test")
    assert song.position_range() is None


def test_position_range_returns_min_and_max():
    """Bei mehreren Positionen liefert position_range() (min, max)."""
    song = Song(title="Faint", positions_hist={26: 50, 27: 10, 25: 5})
    assert song.position_range() == (25, 27)


def test_position_range_with_single_position():
    """Bei nur einer Position: min == max."""
    song = Song(title="Opener", positions_hist={1: 83})
    assert song.position_range() == (1, 1)


# ─── Test 3: is_likely_played ────────────────────────────────────────────────

def test_song_with_score_above_threshold_is_likely_played():
    song = Song(title="Numb", score=0.95)
    assert song.is_likely_played() is True


def test_song_with_score_below_default_threshold():
    """Default-Threshold ist 0.5 — Score 0.3 liegt drunter."""
    song = Song(title="Rare Song", score=0.3)
    assert song.is_likely_played() is False


def test_custom_threshold():
    """Mit hoeherem Threshold faellt ein 0.6-Song raus."""
    song = Song(title="Maybe", score=0.6)
    assert song.is_likely_played(threshold=0.5) is True
    assert song.is_likely_played(threshold=0.7) is False


# ─── Test 4: average_position ────────────────────────────────────────────────

def test_average_position_with_empty_history_returns_none():
    song = Song(title="No Data")
    assert song.average_position() is None


def test_average_position_simple_case():
    """4x Position 3, 1x Position 5 → Durchschnitt 3.4

    Berechnung: (3*4 + 5*1) / (4+1) = 17/5 = 3.4
    """
    song = Song(title="Test", positions_hist={3: 4, 5: 1})
    avg = song.average_position()
    # pytest.approx fuer Float-Vergleiche (wegen Rundungsfehlern bei Floats)
    assert avg == pytest.approx(3.4)


def test_average_position_single_value():
    """Bei nur einer Position ist der Durchschnitt diese Position selbst."""
    song = Song(title="Test", positions_hist={1: 83})
    assert song.average_position() == pytest.approx(1.0)
