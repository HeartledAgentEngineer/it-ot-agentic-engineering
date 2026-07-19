"""
tests/domain/test_concert.py
=============================
Unit-Tests fuer die Concert-Klasse.
"""

from datetime import date

from domain.concert import Concert


# ─── is_upcoming ─────────────────────────────────────────────────────────────

def test_concert_in_future_is_upcoming():
    """Ein Konzert in der Zukunft soll als 'upcoming' erkannt werden.

    Wir geben `today` explizit mit — so haengt der Test nicht vom echten
    Datum ab und ist auch in Jahren noch reproduzierbar. Das ist
    Engineering-Konzept: "deterministische Tests".
    """
    concert = Concert(
        artist_name="LP",
        date=date(2026, 6, 1),
        venue="Volksparkstadion",
        city="Hamburg",
    )
    assert concert.is_upcoming(today=date(2026, 5, 26)) is True


def test_concert_in_past_is_not_upcoming():
    concert = Concert(
        artist_name="LP",
        date=date(2025, 6, 1),  # vergangen
        venue="Volksparkstadion",
        city="Hamburg",
    )
    assert concert.is_upcoming(today=date(2026, 5, 26)) is False


def test_concert_today_is_upcoming():
    """Heute zaehlt auch als 'upcoming' (== inklusiv)."""
    today = date(2026, 5, 26)
    concert = Concert(
        artist_name="LP",
        date=today,
        venue="Test",
        city="Hamburg",
    )
    assert concert.is_upcoming(today=today) is True


# ─── is_festival ─────────────────────────────────────────────────────────────

def test_regular_concert_is_not_festival():
    concert = Concert(
        artist_name="LP",
        date=date(2026, 6, 1),
        venue="Volksparkstadion",
        city="Hamburg",
    )
    assert concert.is_festival() is False


def test_festival_concert_is_recognized():
    concert = Concert(
        artist_name="Three Days Grace",
        date=date(2026, 6, 5),
        venue="Zeppelinfeld",
        city="Nuernberg",
        festival="Rock im Park",
    )
    assert concert.is_festival() is True


# ─── display_location ────────────────────────────────────────────────────────

def test_display_location_for_regular_concert():
    concert = Concert(
        artist_name="LP",
        date=date(2026, 6, 1),
        venue="Volksparkstadion",
        city="Hamburg",
    )
    assert concert.display_location() == "Volksparkstadion, Hamburg"


def test_display_location_for_festival():
    """Beim Festival wird der Festival-Name statt der Venue gezeigt."""
    concert = Concert(
        artist_name="Three Days Grace",
        date=date(2026, 6, 5),
        venue="Zeppelinfeld",
        city="Nuernberg",
        festival="Rock im Park",
    )
    assert concert.display_location() == "Rock im Park, Nuernberg"
