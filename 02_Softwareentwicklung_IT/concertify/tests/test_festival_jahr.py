"""
tests/test_festival_jahr.py
===========================
Tests fuer die Ableitung des Festival-Zieljahres aus dem UI-Zeitraum.
Reine Logik, kein IO. Behebt: RIP 2027 wurde nie gesucht, weil das Jahr
hartkodiert 2026 war (Festival-Datum fiel aus dem Zeitraum-Filter).
"""

from datetime import date

from festival_jahr import ziel_jahr, festival_datum, jahr_aus_daten


def test_zeitraum_innerhalb_eines_jahres():
    # User waehlt 01.06.2027 - 01.07.2027 -> Zieljahr 2027
    assert ziel_jahr("2027-06-01", "2027-07-01") == 2027


def test_offenes_ende_faellt_auf_startjahr_zurueck():
    # "bis" offen (9999) -> Jahr aus "von"
    assert ziel_jahr("2027-06-01", "9999-12-31") == 2027


def test_beide_leer_ergibt_aktuelles_jahr():
    assert ziel_jahr("", "") == date.today().year


def test_bis_jahr_hat_vorrang_bei_jahreswechsel():
    # Bereich ueber den Jahreswechsel -> das "bis"-Jahr zaehlt
    assert ziel_jahr("2026-12-01", "2027-02-28") == 2027


def test_festival_datum_baut_jahr_plus_monat_tag():
    # Monat-Tag "06-05" + Zieljahr -> volles ISO-Datum
    assert festival_datum("06-05", 2027) == "2027-06-05"


def test_festival_datum_akzeptiert_volles_altdatum():
    # Abwaertskompatibel: altes volles Datum "2026-06-05" -> Jahr getauscht
    assert festival_datum("2026-06-05", 2027) == "2027-06-05"


def test_jahr_aus_daten_liest_gespeichertes_jahr():
    rip = {"Volbeat": {"dates": ["2027-06-05"]}}
    assert jahr_aus_daten(rip) == 2027


def test_jahr_aus_daten_leer_ergibt_aktuelles_jahr():
    assert jahr_aus_daten({}) == date.today().year
    assert jahr_aus_daten({"X": {"dates": []}}) == date.today().year
