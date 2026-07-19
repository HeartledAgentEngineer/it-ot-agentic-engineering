"""
tests/domain/test_artist.py
============================
Unit-Tests fuer die Artist-Klasse.
"""

from datetime import date

from domain.artist import Artist
from domain.concert import Concert
from domain.setlist import Setlist
from domain.song import Song


# ─── Helper: einen Test-Artist mit Defaults aufbauen ─────────────────────────
# "Test-Fixture" — wiederverwendbare Hilfsfunktion fuer Tests.

def _make_artist_with_concerts() -> Artist:
    """Liefert einen LP-Artist mit 2 zukuenftigen + 1 vergangenen Konzert."""
    return Artist(
        name="Linkin Park",
        is_followed=True,
        concerts=[
            Concert(
                artist_name="Linkin Park",
                date=date(2030, 6, 1),  # Zukunft
                venue="Volksparkstadion",
                city="Hamburg",
            ),
            Concert(
                artist_name="Linkin Park",
                date=date(2030, 6, 5),  # Zukunft
                venue="Zeppelinfeld",
                city="Nuernberg",
                festival="Rock im Park",
            ),
            Concert(
                artist_name="Linkin Park",
                date=date(2024, 10, 1),  # Vergangenheit
                venue="Old Venue",
                city="Berlin",
            ),
        ],
    )


# ─── has_upcoming_concerts ───────────────────────────────────────────────────

def test_artist_with_future_concerts_has_upcoming():
    """Bei mindestens einem Konzert in der Zukunft → True."""
    artist = _make_artist_with_concerts()
    # has_upcoming_concerts() vergleicht mit echtem heutigem Datum.
    # Das ist ein Schwachpunkt, aber 2026-06-01 ist noch in der Zukunft
    # selbst wenn der Test in spaeteren 2026er Monaten laeuft.
    # Robusterer Ansatz waere _upcoming_concerts mit `today=...` zu testen.
    assert artist.has_upcoming_concerts() is True


def test_artist_without_concerts_has_no_upcoming():
    artist = Artist(name="No Concerts")
    assert artist.has_upcoming_concerts() is False


# ─── festival_concerts / regular_concerts ────────────────────────────────────

def test_festival_concerts_filters_only_festivals():
    artist = _make_artist_with_concerts()

    festivals = artist.festival_concerts()
    assert len(festivals) == 1
    assert festivals[0].festival == "Rock im Park"


def test_regular_concerts_filters_only_non_festivals():
    artist = _make_artist_with_concerts()

    regular = artist.regular_concerts()
    # 2 Konzerte ohne Festival-Eintrag (eins davon vergangen, aber das
    # zaehlt fuer regular_concerts trotzdem dazu — die Methode filtert
    # nur nach Festival, nicht nach Datum)
    assert len(regular) == 2
    assert all(c.festival is None for c in regular)


# ─── has_setlist_data ────────────────────────────────────────────────────────

def test_artist_without_setlist_has_no_setlist_data():
    artist = Artist(name="No Setlist")
    assert artist.has_setlist_data() is False


def test_artist_with_empty_setlist_has_no_real_data():
    """Setlist-Objekt existiert, aber total_concerts_analyzed=0 → keine echten Daten."""
    artist = Artist(
        name="Empty Setlist",
        setlist=Setlist(artist_name="Empty Setlist", total_concerts_analyzed=0),
    )
    assert artist.has_setlist_data() is False


def test_artist_with_real_setlist_data():
    artist = Artist(
        name="With Data",
        setlist=Setlist(
            artist_name="With Data",
            songs=[Song(title="Numb", play_count=83)],
            total_concerts_analyzed=83,
        ),
    )
    assert artist.has_setlist_data() is True
