"""Pruefungen fuer ``kalender_andocken.py`` (N27 Schritt 3, Kalender-Andockung, 28.09.2026).

Alles OHNE Netz und ohne Bild: das Werkzeug liest nur die lokalen Ereignis-Knoten
bzw. erfundene JSONL-Daten und eine erfundene ICS **in-memory** oder aus einem
kleinen Attrappen-Zip im ``tmp_path``. Geprueft werden das eingefrorene
JSONL-Schema, die Fensterregel (Tag / +-1 Tag), die jaehrliche Wiederkehr ueber
``RRULE`` und den Titel-Rueckfall, Ganztags gegen Zeit, mehrtagige Termine,
defekte Bloecke, die Idempotenz, das atomare Schreiben nur ausserhalb des Repos,
der Repo-Ziel-Exit 2 und der Quelltext (keine Netz-, Bild-, Entpack- oder
Loeschfunktion).

**Nur erfundene Beispielnamen und erfundene Kennungen** — echte Termin-,
Personen-, Orts- und Anlassnamen liegen ausserhalb des Repos und kommen hier
nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_kalender_andockung.py -q
"""

from __future__ import annotations

import ast
import datetime
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "kalender_andocken.py"

STAND = "2026-09-28T09:40:00+02:00"

# Erfundene Beispielwerte (keine echten Namen/Termine/Orte).
ANLASS = "2014-03-30_Beispiel-01"
ANLASS_ZWEI = "2016-05-04_Beispiel-02"
MITGLIED = "Takeout/Kalender/beispiel.ics"

SCHEMA_SCHLUESSEL = ("art", "stand", "zahlen", "ereignisse")
KNOTEN_SCHLUESSEL = {
    "anlass_id", "anzahl_nah", "anzahl_treffer", "art", "datum", "kennung",
    "stand", "treffer",
}
TREFFER_SCHLUESSEL = {
    "beginn", "ende", "ganztags", "quelle", "titel", "wiederkehrend",
}


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


kal = _laden(WERKZEUG, "kalender_andocken")


# ── kleine Helfer (erfundene Daten) ───────────────────────────────────────

def _event(*props) -> list:
    """Ein erfundener VEVENT-Block als Zeilenliste."""
    return ["BEGIN:VEVENT", *props, "END:VEVENT"]


def _ics(*bloecke) -> str:
    """Einen erfundenen ICS-Text aus Bloecken bauen (CRLF wie echte ICS)."""
    zeilen = ["BEGIN:VCALENDAR", "VERSION:2.0",
              "PRODID:-//Beispiel//Beispiel//DE", "CALSCALE:GREGORIAN"]
    for block in bloecke:
        zeilen.extend(block)
    zeilen.append("END:VCALENDAR")
    return "\r\n".join(zeilen) + "\r\n"


def _termine(*bloecke) -> list:
    """Die Termine aus erfundenen Bloecken lesen."""
    return kal.termine_lesen(_ics(*bloecke))["termine"]


def _ereignis(anlass_id: str = ANLASS, datum: str | None = "2014-03-30") -> dict:
    return {"anlass_id": anlass_id, "datum": datum}


def _bauen(ereignisse, termine, **rest) -> dict:
    return kal.andocken(list(ereignisse), list(termine), stand=STAND, **rest)


def _knoten_von(daten: dict, anlass_id: str) -> dict:
    for knoten in daten["ereignisse"]:
        if knoten["anlass_id"] == anlass_id:
            return knoten
    raise AssertionError(f"Anlass fehlt: {anlass_id}")


def _jsonl_datei(tmp_path: Path, eintraege) -> Path:
    pfad = tmp_path / "ereignisse.jsonl"
    pfad.write_text("\n".join(json.dumps(e, ensure_ascii=False)
                              for e in eintraege) + "\n", encoding="utf-8")
    return pfad


def _zip_datei(tmp_path: Path, ics_text: str, mitglied: str = MITGLIED) -> Path:
    pfad = tmp_path / "takeout.zip"
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr(mitglied, ics_text)
    return pfad


def _datei_hash(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _als_text(wert) -> str:
    """Einen Wert stabil als Text (fuer ``date``-Objekte ``default=str``)."""
    return json.dumps(wert, ensure_ascii=False, sort_keys=True, default=str)


class Oeffner:
    """Ein Aufruf, der niemals passieren darf (reine Funktion ohne I/O)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde eine Datei geoeffnet, obwohl nichts "
                             "geoeffnet werden darf!")


# ── Konstanten und eingefrorenes Schema ──────────────────────────────────

def test_art_ist_fest():
    assert kal.ANDOCKUNG_ART == "kalender_andockung"


def test_standard_ausgabe_zeigt_auf_die_jsonl_datei():
    assert kal.STANDARD_AUSGABE.endswith("kalender_andockung.jsonl")
    assert "foto_sortierung" in kal.STANDARD_AUSGABE


def test_standard_ereignisse_zeigt_auf_die_jsonl_datei():
    assert kal.STANDARD_EREIGNISSE.endswith("ereignisse.jsonl")


def test_standard_mitglied_ist_leer_und_liest_alle_kalender(tmp_path):
    # Vorgabe ist leer/None (kein Kontoname im Repo); ohne --mitglied werden
    # ALLE 'Takeout/Kalender/*.ics' im Zip gelesen (hier erfundene Namen).
    assert kal.STANDARD_ZIP.endswith(".zip")
    assert not kal.STANDARD_MITGLIED
    a = "Takeout/Kalender/beispiel-a.ics"
    b = "Takeout/Kalender/beispiel-b.ics"
    zip_pfad = tmp_path / "takeout.zip"
    with zipfile.ZipFile(zip_pfad, "w") as archiv:
        archiv.writestr(a, _ics(_event("DTSTART;VALUE=DATE:20140330",
                                       "SUMMARY:Beispiel-A")))
        archiv.writestr(b, _ics(_event("DTSTART;VALUE=DATE:20140331",
                                       "SUMMARY:Beispiel-B")))
    for ohne in (None, ""):                 # None und leer = automatische Vorgabe
        text = kal.zip_ics_lesen(str(zip_pfad), ohne)
        assert "Beispiel-A" in text
        assert "Beispiel-B" in text


def test_bauen_liefert_die_schema_schluessel():
    daten = _bauen([_ereignis()], [])
    assert set(daten) == set(SCHEMA_SCHLUESSEL)


def test_schema_schluessel_reihenfolge_ist_fest():
    daten = _bauen([_ereignis()], [])
    assert tuple(daten) == SCHEMA_SCHLUESSEL


def test_knoten_hat_genau_die_schema_schluessel():
    knoten = _knoten_von(_bauen([_ereignis()], []), ANLASS)
    assert set(knoten) == KNOTEN_SCHLUESSEL


def test_knoten_schluessel_reihenfolge_ist_fest():
    knoten = _knoten_von(_bauen([_ereignis()], []), ANLASS)
    assert tuple(knoten) == kal.KNOTEN_SCHLUESSEL


def test_treffer_schluessel_sind_fest():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330",
                            "DTEND;VALUE=DATE:20140331", "SUMMARY:Beispiel"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert set(knoten["treffer"][0]) == TREFFER_SCHLUESSEL
    assert tuple(knoten["treffer"][0]) == kal.TREFFER_SCHLUESSEL


def test_kennung_ist_K_plus_anlass_id():
    knoten = _knoten_von(_bauen([_ereignis()], []), ANLASS)
    assert knoten["kennung"] == "K-" + ANLASS
    assert knoten["art"] == "kalender_andockung"


def test_treffer_quelle_ist_ics():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["treffer"][0]["quelle"] == "ics"


# ── Fensterregel: Tag und +-1 Tag ────────────────────────────────────────

def test_treffer_am_selben_tag():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 1
    assert knoten["anzahl_nah"] == 0
    assert knoten["treffer"][0]["titel"] == "Beispiel-A"


def test_termin_am_tag_davor_ist_nah_nicht_treffer():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140329", "SUMMARY:Beispiel-B"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 0
    assert knoten["treffer"] == []
    assert knoten["anzahl_nah"] == 1


def test_termin_am_tag_danach_ist_nah():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140331", "SUMMARY:Beispiel-C"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 0
    assert knoten["anzahl_nah"] == 1


def test_zwei_tage_entfernt_ist_weder_treffer_noch_nah():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140328", "SUMMARY:Beispiel-D"),
                     _event("DTSTART;VALUE=DATE:20140401", "SUMMARY:Beispiel-E"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 0
    assert knoten["anzahl_nah"] == 0


def test_auch_nah_ist_standard_aus():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140329", "SUMMARY:Beispiel-B"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["treffer"] == []
    assert knoten["anzahl_nah"] == 1


def test_auch_nah_nimmt_nah_in_treffer():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140329", "SUMMARY:Beispiel-B"))
    knoten = _knoten_von(_bauen([_ereignis()], liste, auch_nah=True), ANLASS)
    assert knoten["anzahl_treffer"] == 1
    assert knoten["anzahl_nah"] == 1        # Nah-Zahl bleibt ehrlich stehen
    assert knoten["treffer"][0]["titel"] == "Beispiel-B"


def test_mehrtagiger_termin_enthaelt_den_tag():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140328",
                            "DTEND;VALUE=DATE:20140402", "SUMMARY:Beispiel-Reise"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 1
    assert knoten["treffer"][0]["beginn"] == "2014-03-28"
    assert knoten["treffer"][0]["ende"] == "2014-04-02"


def test_mehrtagiger_termin_am_rand_ist_nah():
    # Ende ist exclusiv: [28.03, 30.03) enthaelt den 30.03. NICHT -> nah.
    liste = _termine(_event("DTSTART;VALUE=DATE:20140328",
                            "DTEND;VALUE=DATE:20140330", "SUMMARY:Beispiel-Reise"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 0
    assert knoten["anzahl_nah"] == 1


def test_anzahl_treffer_ist_die_laenge_der_liste():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"),
                     _event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-B"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == len(knoten["treffer"]) == 2


def test_treffer_sind_nach_beginn_und_titel_sortiert():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-Z"),
                     _event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert [t["titel"] for t in knoten["treffer"]] == ["Beispiel-A", "Beispiel-Z"]


def test_ereignis_ohne_datum_hat_keine_treffer():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    knoten = _knoten_von(_bauen([_ereignis(datum=None)], liste), ANLASS)
    assert knoten["datum"] is None
    assert knoten["anzahl_treffer"] == 0
    assert knoten["anzahl_nah"] == 0
    assert knoten["treffer"] == []


# ── Jaehrliche Wiederkehr (RRULE und Titel-Rueckfall) ────────────────────

def test_jaehrlich_ueber_rrule_trifft_ueber_monat_tag():
    liste = _termine(_event("DTSTART;VALUE=DATE:19680330",
                            "RRULE:FREQ=YEARLY;UNTIL=20240408",
                            "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 1
    assert knoten["treffer"][0]["wiederkehrend"] is True


def test_jaehrlich_beginn_ist_das_anlass_jahr():
    liste = _termine(_event("DTSTART;VALUE=DATE:19680330",
                            "RRULE:FREQ=YEARLY", "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["treffer"][0]["beginn"] == "2014-03-30"


def test_jaehrlich_trifft_unabhaengig_vom_jahr():
    # Ein anderer Anlass (2016) trifft denselben Tag+Monat.
    liste = _termine(_event("DTSTART;VALUE=DATE:19680330",
                            "RRULE:FREQ=YEARLY", "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis(ANLASS_ZWEI, "2016-03-30")], liste),
                         ANLASS_ZWEI)
    assert knoten["treffer"][0]["beginn"] == "2016-03-30"


def test_jaehrlich_titel_rueckfall_geburtstag():
    liste = _termine(_event("DTSTART;VALUE=DATE:19680330",
                            "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 1
    assert knoten["treffer"][0]["wiederkehrend"] is True


def test_jaehrlich_titel_rueckfall_jahrestag():
    liste = _termine(_event("DTSTART;VALUE=DATE:20050330",
                            "SUMMARY:Beispiel-Jahrestag"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["treffer"][0]["wiederkehrend"] is True


def test_ohne_rrule_und_ohne_keyword_ist_nicht_jaehrlich():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["treffer"][0]["wiederkehrend"] is False


def test_rrule_weekly_ist_nicht_jaehrlich():
    liste = _termine(_event("DTSTART:20140330T180000Z",
                            "RRULE:FREQ=WEEKLY;BYDAY=SU", "SUMMARY:Beispiel-A"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["treffer"][0]["wiederkehrend"] is False


def test_titel_rueckfall_greift_nicht_bei_vorhandener_rrule():
    # Liegt eine (nicht-jaehrliche) RRULE vor, greift der Titel-Rueckfall nicht.
    liste = _termine(_event("DTSTART;VALUE=DATE:19680330",
                            "RRULE:FREQ=MONTHLY", "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 0


def test_jaehrlich_trifft_nicht_bei_anderem_tag_monat():
    liste = _termine(_event("DTSTART;VALUE=DATE:19680329",
                            "RRULE:FREQ=YEARLY", "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis()], liste), ANLASS)
    assert knoten["anzahl_treffer"] == 0
    assert knoten["anzahl_nah"] == 1


def test_jaehrlich_29_februar_wird_geklemmt():
    # 29.02. gibt es 2014 nicht -> beginn wird auf den 28.02. geklemmt.
    liste = _termine(_event("DTSTART;VALUE=DATE:20000229",
                            "RRULE:FREQ=YEARLY", "SUMMARY:Beispiel-Geburtstag"))
    knoten = _knoten_von(_bauen([_ereignis("2014-02-28_Beispiel-01", "2014-02-28")],
                                liste), "2014-02-28_Beispiel-01")
    assert knoten["anzahl_treffer"] == 1
    assert knoten["treffer"][0]["beginn"] == "2014-02-28"


def test_jaehrlich_nah_ueber_den_jahreswechsel():
    # Ein Termin am 31.12. ist fuer einen Anlass am 01.01. "+-1 Tag" (nah).
    liste = _termine(_event("DTSTART;VALUE=DATE:20001231",
                            "RRULE:FREQ=YEARLY", "SUMMARY:Beispiel-Fest"))
    knoten = _knoten_von(_bauen([_ereignis("2014-01-01_Beispiel-01", "2014-01-01")],
                                liste), "2014-01-01_Beispiel-01")
    assert knoten["anzahl_treffer"] == 0
    assert knoten["anzahl_nah"] == 1


# ── Ganztags gegen Zeit ──────────────────────────────────────────────────

def test_ganztags_value_date():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    assert liste[0]["ganztags"] is True


def test_ganztags_ohne_uhrzeit():
    liste = _termine(_event("DTSTART:20140330", "SUMMARY:Beispiel-A"))
    assert liste[0]["ganztags"] is True


def test_zeit_ist_nicht_ganztags():
    liste = _termine(_event("DTSTART:20140330T180000Z",
                            "DTEND:20140330T190000Z", "SUMMARY:Beispiel-A"))
    assert liste[0]["ganztags"] is False
    assert liste[0]["beginn"] == datetime.date(2014, 3, 30)


def test_termin_ohne_ende_hat_spanne_eins():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    assert liste[0]["ende"] is None
    assert liste[0]["spanne"] == 1


def test_zeitgleiches_ende_hat_spanne_eins():
    liste = _termine(_event("DTSTART:20140330T180000Z",
                            "DTEND:20140330T180000Z", "SUMMARY:Beispiel-A"))
    assert liste[0]["spanne"] == 1


# ── ICS-Leser: Entfalten, Bloecke, Defekte, Titel ────────────────────────

def test_zeilen_entfalten_haengt_fortsetzung_an():
    text = "SUMMARY:Beispiel-\r\n Termin\r\nUID:x"
    assert kal.zeilen_entfalten(text) == ["SUMMARY:Beispiel-Termin", "UID:x"]


def test_bloecke_sammeln_zaehlt_die_bloecke():
    bloecke, offen = kal.bloecke_sammeln(
        kal.zeilen_entfalten(_ics(_event("DTSTART;VALUE=DATE:20140330"),
                                  _event("DTSTART;VALUE=DATE:20140331"))))
    assert len(bloecke) == 2
    assert offen == 0


def test_defekter_block_ohne_dtstart_wird_gezaehlt():
    ergebnis = kal.termine_lesen(_ics(
        _event("SUMMARY:Beispiel-ohne-Datum"),
        _event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A")))
    assert ergebnis["bloecke"] == 2
    assert ergebnis["defekt"] == 1
    assert ergebnis["anzahl"] == 1


def test_defekter_block_mit_unsinnigem_datum_wird_gezaehlt():
    ergebnis = kal.termine_lesen(_ics(
        _event("DTSTART;VALUE=DATE:20141345", "SUMMARY:Beispiel-A")))
    assert ergebnis["defekt"] == 1
    assert ergebnis["anzahl"] == 0


def test_ungeschlossener_block_wird_gemeldet():
    text = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20140330\r\n"
    ergebnis = kal.termine_lesen(text)
    assert ergebnis["offen"] == 1
    assert ergebnis["bloecke"] == 0


def test_termin_ohne_titel_wird_gezaehlt():
    ergebnis = kal.termine_lesen(_ics(
        _event("DTSTART;VALUE=DATE:20140330")))
    assert ergebnis["anzahl"] == 1
    assert ergebnis["ohne_titel"] == 1
    assert ergebnis["termine"][0]["titel"] == ""


def test_ics_datum_liest_die_ersten_acht_ziffern():
    assert kal._ics_datum("20200315")[0] == datetime.date(2020, 3, 15)
    assert kal._ics_datum("20200315T180000Z")[0] == datetime.date(2020, 3, 15)
    assert kal._ics_datum("20200315T180000")[0] == datetime.date(2020, 3, 15)


def test_ics_datum_ist_ganztags_ohne_uhrzeit():
    assert kal._ics_datum("20200315")[1] is True
    assert kal._ics_datum("20200315T180000Z")[1] is False


def test_ics_datum_ohne_acht_ziffern_ist_none():
    assert kal._ics_datum("2020")[0] is None
    assert kal._ics_datum("")[0] is None


def test_titel_wird_auf_120_zeichen_gekuerzt():
    lang = "B" * 200
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330",
                            f"SUMMARY:{lang}"))
    assert len(liste[0]["titel"]) == kal.MAX_TITEL == 120


def test_titel_maskierung_wird_geloest():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330",
                            r"SUMMARY:Beispiel\, mit Komma"))
    assert liste[0]["titel"] == "Beispiel, mit Komma"


def test_kein_weiterer_text_wird_gelesen():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A",
                            "DESCRIPTION:Geheimer Beispieltext",
                            "LOCATION:Beispielort"))
    assert "Geheimer Beispieltext" not in _als_text(liste)
    assert "Beispielort" not in _als_text(liste)


# ── Ereignisse lesen ─────────────────────────────────────────────────────

def test_ereignisse_laden_liest_anlass_id_und_datum(tmp_path):
    pfad = _jsonl_datei(tmp_path, [_ereignis(), _ereignis(ANLASS_ZWEI, "2016-05-04")])
    ereignisse = kal.ereignisse_laden(str(pfad))
    assert [e["anlass_id"] for e in ereignisse] == [ANLASS, ANLASS_ZWEI]
    assert ereignisse[1]["datum"] == "2016-05-04"


def test_ereignisse_laden_behaelt_die_reihenfolge(tmp_path):
    pfad = _jsonl_datei(tmp_path, [_ereignis(ANLASS_ZWEI, "2016-05-04"),
                                   _ereignis(ANLASS, "2014-03-30")])
    assert [e["anlass_id"] for e in kal.ereignisse_laden(str(pfad))] == \
        [ANLASS_ZWEI, ANLASS]


def test_ereignisse_laden_ueberspringt_zeile_ohne_anlass_id(tmp_path):
    pfad = _jsonl_datei(tmp_path, [{"datum": "2014-03-30"}, _ereignis()])
    assert len(kal.ereignisse_laden(str(pfad))) == 1


def test_ereignisse_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        kal.ereignisse_laden(str(tmp_path / "gibtsnicht.jsonl"))
    assert "nicht gefunden" in str(fehler.value)


def test_ereignisse_laden_ohne_pfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        kal.ereignisse_laden("")
    assert "Kein Pfad" in str(fehler.value)


def test_ereignisse_laden_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "krumm.jsonl"
    pfad.write_text("{das ist kein json", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        kal.ereignisse_laden(str(pfad))
    assert "gueltiges JSON" in str(fehler.value)


# ── Zip lesen (nur per zipfile) ──────────────────────────────────────────

def test_zip_ics_lesen_liest_das_mitglied(tmp_path):
    zip_pfad = _zip_datei(tmp_path, _ics(_event("DTSTART;VALUE=DATE:20140330")))
    text = kal.zip_ics_lesen(str(zip_pfad), MITGLIED)
    assert "BEGIN:VEVENT" in text


def test_zip_ics_lesen_fehlendes_mitglied_ist_klartextfehler(tmp_path):
    zip_pfad = _zip_datei(tmp_path, _ics(), mitglied="Takeout/Kalender/anders.ics")
    with pytest.raises(ValueError) as fehler:
        kal.zip_ics_lesen(str(zip_pfad), MITGLIED)
    assert "nicht im Takeout-Zip" in str(fehler.value)


def test_zip_ics_lesen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        kal.zip_ics_lesen(str(tmp_path / "gibtsnicht.zip"), MITGLIED)
    assert "nicht gefunden" in str(fehler.value)


def test_zip_ics_lesen_ohne_kalenderdatei_ist_klartextfehler(tmp_path, capsys):
    zip_pfad = tmp_path / "takeout-leer.zip"
    with zipfile.ZipFile(zip_pfad, "w"):
        pass                                # leeres Zip: keine Kalenderdatei
    with pytest.raises(ValueError) as fehler:
        kal.zip_ics_lesen(str(zip_pfad), None)
    assert "Keine Kalenderdateien" in str(fehler.value)

    # Wie die Nachbartests: dieselbe Ursache ergibt auf der Kommandozeile Exit 2
    # mit deutscher Meldung auf stderr (ohne --mitglied = automatische Vorgabe).
    pfad = _jsonl_datei(tmp_path, [_ereignis()])
    assert kal.haupt(["--ereignisse", str(pfad), "--zip", str(zip_pfad),
                      "--mitglied", "", "--ausgabe",
                      str(tmp_path / "aus.jsonl")]) == 2
    assert "Fehler" in capsys.readouterr().err


# ── Reine Funktionen (kein Datei-, kein Netzzugriff) ─────────────────────

def test_andocken_oeffnet_keine_datei(monkeypatch):
    monkeypatch.setattr("builtins.open", Oeffner())
    daten = kal.andocken([_ereignis()], _termine(
        _event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A")), stand=STAND)
    assert daten["zahlen"]["treffer"] == 1


def test_andocken_veraendert_die_eingaben_nicht():
    ereignisse = [_ereignis()]
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    vorher = _als_text([ereignisse, liste])
    kal.andocken(list(ereignisse), list(liste), stand=STAND)
    assert _als_text([ereignisse, liste]) == vorher


def test_knoten_zeile_ist_rein(monkeypatch):
    knoten = _knoten_von(_bauen([_ereignis()], []), ANLASS)
    monkeypatch.setattr("builtins.open", Oeffner())
    assert kal.knoten_zeile(knoten) == kal.knoten_zeile(knoten)


def test_knoten_zeile_gleiche_eingabe_gleiche_ausgabe():
    knoten = _knoten_von(_bauen([_ereignis()], []), ANLASS)
    assert kal.knoten_zeile(json.loads(json.dumps(knoten))) == \
        kal.knoten_zeile(dict(knoten))


def test_knoten_zeile_ist_ascii_und_sortiert():
    knoten = _knoten_von(_bauen([_ereignis()], []), ANLASS)
    zeile = kal.knoten_zeile(knoten)
    assert zeile == json.dumps(knoten, ensure_ascii=True, sort_keys=True)
    assert zeile.isascii()


def test_knoten_zeile_ohne_woerterbuch_ist_fehler():
    with pytest.raises(ValueError):
        kal.knoten_zeile(["kein", "Knoten"])


# ── Stand und Zaehler ────────────────────────────────────────────────────

def test_stand_wird_uebernommen():
    assert _bauen([_ereignis()], [])["stand"] == STAND


def test_stand_ohne_angabe_wird_gefuellt():
    daten = kal.andocken([_ereignis()], [])
    assert isinstance(daten["stand"], str) and "T" in daten["stand"]


def test_leerer_stand_ist_fehler():
    with pytest.raises(ValueError):
        kal.andocken([_ereignis()], [], stand="   ")


def test_ereignisse_muessen_eine_liste_sein():
    with pytest.raises(ValueError):
        kal.andocken("keine Liste", [], stand=STAND)


def test_zahlen_invarianten():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"),
                     _event("DTSTART;VALUE=DATE:20140329", "SUMMARY:Beispiel-B"))
    daten = _bauen([_ereignis(), _ereignis(ANLASS_ZWEI, "2016-05-04")], liste)
    zahlen = daten["zahlen"]
    assert zahlen["ereignisse"] == len(daten["ereignisse"]) == 2
    assert zahlen["treffer"] == sum(k["anzahl_treffer"] for k in daten["ereignisse"])
    assert zahlen["nah"] == sum(k["anzahl_nah"] for k in daten["ereignisse"])
    assert zahlen["mit_treffern"] == 1


def test_leerer_lauf_ergibt_null_zahlen():
    daten = _bauen([], [])
    assert daten["ereignisse"] == []
    assert daten["zahlen"]["ereignisse"] == 0
    assert daten["zahlen"]["treffer"] == 0
    assert daten["zahlen"]["max_treffer"] == 0


# ── Schreiben: JSONL, atomar, nur ausserhalb des Repos ───────────────────

def _schreiben(tmp_path: Path, ereignisse=None, liste=None) -> Path:
    ziel = tmp_path / "kalender_andockung.jsonl"
    kal.andockung_schreiben(
        str(ziel),
        _bauen(ereignisse if ereignisse is not None else [_ereignis()],
               liste if liste is not None else []))
    return ziel


def test_schreiben_legt_die_datei_an_und_gibt_den_pfad_zurueck(tmp_path):
    ziel = tmp_path / "kalender_andockung.jsonl"
    zurueck = kal.andockung_schreiben(str(ziel), _bauen([_ereignis()], []))
    assert zurueck == str(ziel)
    assert ziel.is_file()


def test_schreiben_ist_reine_jsonl_mit_einer_zeile_je_ereignis(tmp_path):
    ziel = _schreiben(tmp_path, [_ereignis(), _ereignis(ANLASS_ZWEI, "2016-05-04")])
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 2
    for zeile in zeilen:
        assert set(json.loads(zeile)) == KNOTEN_SCHLUESSEL


def test_schreiben_behaelt_die_reihenfolge_wie_die_eingabe(tmp_path):
    ziel = _schreiben(tmp_path, [_ereignis(ANLASS_ZWEI, "2016-05-04"),
                                 _ereignis(ANLASS, "2014-03-30")])
    ids = [json.loads(z)["anlass_id"]
           for z in ziel.read_text(encoding="utf-8").splitlines()]
    assert ids == [ANLASS_ZWEI, ANLASS]


def test_schreiben_ist_ascii_und_sortierte_schluessel(tmp_path):
    ziel = _schreiben(tmp_path)
    roh = ziel.read_text(encoding="utf-8")
    assert roh.isascii()
    for zeile in roh.splitlines():
        assert zeile == json.dumps(json.loads(zeile), ensure_ascii=True,
                                   sort_keys=True)


def test_schreiben_enthaelt_keinen_zahlen_block(tmp_path):
    ziel = _schreiben(tmp_path)
    roh = ziel.read_text(encoding="utf-8")
    assert '"zahlen"' not in roh
    # Genau eine Zeile je Ereignis, jede mit den Knoten-Schluesseln (kein
    # Kopfzeilen-Sonderfall):
    assert len(roh.splitlines()) == 1
    assert set(json.loads(roh.splitlines()[0])) == KNOTEN_SCHLUESSEL


def test_schreiben_laesst_keine_temp_datei_zurueck(tmp_path):
    _schreiben(tmp_path)
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_zweiter_lauf_ist_byte_identisch(tmp_path):
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    ziel = _schreiben(tmp_path, [_ereignis()], liste)
    vorher = _datei_hash(ziel)
    _schreiben(tmp_path, [_ereignis()], liste)
    assert _datei_hash(ziel) == vorher


def test_schreiben_im_repo_wird_mit_valueerror_verweigert():
    ziel = REPO / "kalender_andockung.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError) as fehler:
        kal.andockung_schreiben(str(ziel), _bauen([_ereignis()], []))
    assert "IM Repo" in str(fehler.value)
    assert "NICHTS geschrieben" in str(fehler.value)
    assert not ziel.exists()


def test_schreiben_in_den_werkzeugordner_wird_verweigert():
    ziel = WERKZEUG.parent / "kalender_andockung.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError):
        kal.andockung_schreiben(str(ziel), {})
    assert not ziel.exists()


def test_schreiben_ohne_daten_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        kal.andockung_schreiben(str(tmp_path / "k.jsonl"), None)
    assert "Kalender-Andockung" in str(fehler.value)
    assert not (tmp_path / "k.jsonl").exists()


def test_schreiben_ohne_knotenliste_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        kal.andockung_schreiben(str(tmp_path / "k.jsonl"), {"art": "kalender_andockung"})
    assert "ereignisse" in str(fehler.value)


def test_schreiben_scheitert_nicht_zerstoerend(tmp_path):
    ziel = _schreiben(tmp_path)
    vorher = _datei_hash(ziel)
    with pytest.raises(ValueError):
        kal.andockung_schreiben(str(ziel), {"ereignisse": ["kein Knoten"]})
    assert _datei_hash(ziel) == vorher
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_legt_den_zielordner_an(tmp_path):
    ziel = tmp_path / "neu" / "tief" / "kalender_andockung.jsonl"
    kal.andockung_schreiben(str(ziel), _bauen([_ereignis()], []))
    assert ziel.is_file()


# ── Klartext (zahlen_text) ───────────────────────────────────────────────

def test_zahlen_text_nennt_alle_zahlen():
    liste = _termine(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"),
                     _event("DTSTART;VALUE=DATE:20140329", "SUMMARY:Beispiel-B"))
    text = kal.zahlen_text(_bauen([_ereignis()], liste))
    for wort in ("Ereignisse: 1", "Treffer-Zeilen: 1", "Termine am Tag (Treffer): 1",
                 "Nah-Treffer (+-1 Tag): 1", "Maximum Treffer je Ereignis: 1"):
        assert wort in text, wort


def test_zahlen_text_nennt_die_ics_zahlen():
    ics = kal.termine_lesen(_ics(
        _event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"),
        _event("SUMMARY:Beispiel-ohne-Datum")))
    text = kal.zahlen_text(_bauen([_ereignis()], ics["termine"]), ics)
    assert "ICS-Termine: 1" in text
    assert "Bloecke: 2" in text
    assert "defekte Bloecke: 1" in text


def test_zahlen_text_haelt_fehlende_felder_aus():
    text = kal.zahlen_text({})
    assert "Ereignisse: 0" in text
    assert "unbekannt" in text


def test_zahlen_text_spricht_nicht_von_loeschen():
    text = kal.zahlen_text(_bauen([_ereignis()], []))
    for verboten in ("loesch", "Loesch", "geloescht", "delete", "entfernt"):
        assert verboten not in text


# ── Kommandozeile ────────────────────────────────────────────────────────

def _argumente(tmp_path: Path, ereignisse=None, ics_text=None, **rest):
    pfad = _jsonl_datei(tmp_path, ereignisse if ereignisse is not None
                        else [_ereignis()])
    zip_pfad = _zip_datei(tmp_path, ics_text if ics_text is not None else _ics())
    return ["--ereignisse", str(pfad), "--zip", str(zip_pfad),
            "--mitglied", MITGLIED, "--ausgabe", str(tmp_path / "aus.jsonl")]


def test_haupt_trockenlauf_schreibt_nichts(tmp_path, capsys):
    ziel = tmp_path / "aus.jsonl"
    assert kal.haupt(_argumente(tmp_path)) == 0
    assert not ziel.exists()
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "wurde NICHT geschrieben" in ausgabe


def test_haupt_trockenlauf_zeigt_die_zahlen(tmp_path, capsys):
    ics = _ics(_event("DTSTART;VALUE=DATE:20140330", "SUMMARY:Beispiel-A"))
    kal.haupt(_argumente(tmp_path, ics_text=ics))
    ausgabe = capsys.readouterr().out
    assert "Ereignisse:" in ausgabe
    assert "Treffer-Zeilen: 1" in ausgabe
    assert "Termine am Tag (Treffer): 1" in ausgabe


def test_haupt_trockenlauf_zeigt_die_knoten_als_jsonl(tmp_path, capsys):
    kal.haupt(_argumente(tmp_path))
    zeilen = [z for z in capsys.readouterr().out.splitlines()
              if z.startswith("{")]
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["kennung"] == "K-" + ANLASS


def test_haupt_expliziter_trockenlauf_schlaegt_schreiben(tmp_path, capsys):
    ziel = tmp_path / "aus.jsonl"
    assert kal.haupt(_argumente(tmp_path) + ["--trocken", "--schreiben"]) == 0
    assert not ziel.exists()
    assert "TROCKENLAUF" in capsys.readouterr().out


def test_haupt_limit_zeigt_nur_die_ersten_knoten(tmp_path, capsys):
    eintraege = [_ereignis(f"2014-03-{tag:02d}_Beispiel-01",
                           f"2014-03-{tag:02d}") for tag in (10, 11, 12)]
    kal.haupt(_argumente(tmp_path, ereignisse=eintraege) + ["--limit", "1"])
    ausgabe = capsys.readouterr().out
    assert len([z for z in ausgabe.splitlines() if z.startswith("{")]) == 1
    assert "2 weitere Knoten" in ausgabe


def test_haupt_negatives_limit_ergibt_exit_2(tmp_path, capsys):
    assert kal.haupt(_argumente(tmp_path) + ["--limit", "-1"]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_haupt_mit_schreiben_legt_jsonl_an(tmp_path):
    ziel = tmp_path / "aus.jsonl"
    assert kal.haupt(_argumente(tmp_path) + ["--schreiben", "--stand", STAND]) == 0
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["anlass_id"] == ANLASS


def test_haupt_schreiben_ist_byte_gleich_wiederholbar(tmp_path):
    ziel = tmp_path / "aus.jsonl"
    args = _argumente(tmp_path) + ["--schreiben", "--stand", STAND]
    kal.haupt(args)
    vorher = _datei_hash(ziel)
    kal.haupt(args)
    assert _datei_hash(ziel) == vorher


def test_haupt_auch_nah_nimmt_nah_in_treffer(tmp_path, capsys):
    ics = _ics(_event("DTSTART;VALUE=DATE:20140329", "SUMMARY:Beispiel-B"))
    kal.haupt(_argumente(tmp_path, ics_text=ics) + ["--auch-nah"])
    ausgabe = capsys.readouterr().out
    assert "Termine am Tag (Treffer): 1" in ausgabe
    assert "Nah-Treffer (+-1 Tag): 1" in ausgabe


def test_haupt_repo_ziel_ergibt_exit_2(tmp_path, capsys):
    ziel = REPO / "kalender_andockung.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    args = _argumente(tmp_path)[:-1] + [str(ziel)]
    assert kal.haupt(args + ["--schreiben"]) == 2
    fehler = capsys.readouterr().err
    assert "IM Repo" in fehler and "Fehler" in fehler
    assert not ziel.exists()


def test_haupt_repo_ziel_ergibt_auch_im_trockenlauf_exit_2(tmp_path, capsys):
    args = _argumente(tmp_path)[:-1] + [str(REPO / "docs" / "k.jsonl")]
    assert kal.haupt(args) == 2
    assert "IM Repo" in capsys.readouterr().err


def test_haupt_fehlende_ereignisse_ergibt_exit_2(tmp_path, capsys):
    pfad = _jsonl_datei(tmp_path, [_ereignis()])
    zip_pfad = _zip_datei(tmp_path, _ics())
    assert kal.haupt(["--ereignisse", str(tmp_path / "gibtsnicht.jsonl"),
                      "--zip", str(zip_pfad), "--mitglied", MITGLIED,
                      "--ausgabe", str(tmp_path / "aus.jsonl")]) == 2
    assert "Fehler" in capsys.readouterr().err
    assert pfad.is_file()                       # die echte Datei bleibt unberuehrt


def test_haupt_fehlendes_zip_ergibt_exit_2(tmp_path, capsys):
    pfad = _jsonl_datei(tmp_path, [_ereignis()])
    assert kal.haupt(["--ereignisse", str(pfad),
                      "--zip", str(tmp_path / "gibtsnicht.zip"),
                      "--mitglied", MITGLIED,
                      "--ausgabe", str(tmp_path / "aus.jsonl")]) == 2
    assert "Fehler" in capsys.readouterr().err


# ── Quelltext: keine Netz-, Bild-, Entpack- oder Loeschfunktion ──────────

def _quelle() -> str:
    return WERKZEUG.read_text(encoding="utf-8")


def _baum():
    return ast.parse(_quelle())


def _namen_im_quelltext() -> set:
    namen: set = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Name):
            namen.add(knoten.id)
        elif isinstance(knoten, ast.Attribute):
            namen.add(knoten.attr)
        elif isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                namen.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            namen.add((knoten.module or "").split(".")[0])
    return namen


def test_quelltext_importiert_nur_standardbibliothek():
    erlaubt = {"argparse", "datetime", "json", "os", "re", "sys", "zipfile",
               "__future__"}
    importe: set = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                importe.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            importe.add((knoten.module or "").split(".")[0])
    assert importe <= erlaubt, f"unerlaubter Import: {importe - erlaubt}"


def test_quelltext_ohne_netz_und_llm_namen():
    verboten = {"pcloud", "httpx", "requests", "urllib", "openai", "socket",
                "subprocess", "urllib3", "aiohttp"}
    assert _namen_im_quelltext() & verboten == set()


def test_quelltext_ohne_url_und_ohne_schluessel():
    for verboten in ("http://", "https://", "pcloud", "openai", "import requests",
                     "import httpx", "urllib.request", "urlopen(", "sk-", "token"):
        assert verboten not in _quelle(), f"Netz-/Schluesselspur: {verboten}"


def test_quelltext_liest_das_zip_nur_per_zipfile():
    quelle = _quelle()
    assert "zipfile.ZipFile" in quelle
    assert ".read(" in quelle


def test_quelltext_entpackt_nicht():
    quelle = _quelle()
    for verboten in ("extractall", "extract(", "unzip", "shutil", "copytree",
                     "copyfile"):
        assert verboten not in quelle, f"Entpack-/Kopierspur: {verboten}"


def test_quelltext_oeffnet_keine_bilder():
    quelle = _quelle()
    for verboten in ("PIL", "cv2", "imageio", ".jpg", ".jpeg", ".png", ".heic",
                     ".webp", '"rb"', "'rb'"):
        assert verboten not in quelle, f"Bildzugriff im Quelltext: {verboten}"


def test_quelltext_loescht_nur_die_eigene_temp_datei():
    aufrufe = [knoten for knoten in ast.walk(_baum())
               if isinstance(knoten, ast.Call)
               and isinstance(knoten.func, ast.Attribute)
               and knoten.func.attr == "remove"]
    assert len(aufrufe) == 1, "genau eine Loeschung: die eigene temp-Datei"
    argument = aufrufe[0].args[0]
    assert isinstance(argument, ast.Name) and argument.id == "temp_pfad"
    assert isinstance(aufrufe[0].func.value, ast.Name)
    assert aufrufe[0].func.value.id == "os"


def test_quelltext_hat_keine_loeschfunktion():
    quelle = _quelle()
    for verboten in ("def loeschen", "def delete", "def entfernen", "shutil",
                     "rmdir", "rm("):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_schreibt_atomar():
    quelle = _quelle()
    assert "os.replace(" in quelle
    assert ".tmp" in quelle


def test_quelltext_prueft_das_repo_ziel():
    quelle = _quelle()
    assert "_pruefe_ziel_ausserhalb_repo" in quelle
    assert "IM Repo" in quelle


def test_quelltext_setzt_nur_einen_zeitstempel():
    assert _quelle().count("datetime.datetime.now(") == 1


# ── Eingefrorene Funktionsnamen ──────────────────────────────────────────

def test_eingefrorene_funktionsnamen_sind_da():
    for name in ("ereignisse_laden", "zip_ics_lesen", "zeilen_entfalten",
                 "bloecke_sammeln", "termin_bauen", "andocken", "knoten_zeile",
                 "andockung_schreiben", "_pruefe_ziel_ausserhalb_repo",
                 "zahlen_text", "haupt"):
        assert callable(getattr(kal, name)), name
