"""Pruefungen fuer ``foto_uebersicht.py`` (Nachtlauf-Schritt N11, Teil A).

Alles OHNE Netz und ohne Bild: das Werkzeug liest nur den lokalen Sortierplan
bzw. erfundene Plandaten; Dateien gehen nach ``tmp_path``. Geprueft wird das
eingefrorene Schema der Uebersichtsdatei, die Zaehlregeln, die Sortierungen,
das atomare Schreiben (nur ausserhalb des Repos) und die Trockenlauf-Garantien
im Quelltext.

**Nur erfundene Beispielnamen** — die echten Event- und Ordnernamen liegen
ausserhalb des Repos und kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_uebersicht_werkzeug.py -q
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "foto_uebersicht.py"

STAND = "2026-09-27T22:30:00+02:00"
PLAN_STAND = "2026-09-27T13:49:46+02:00"

# Erfundene Beispielnamen.
KATEGORIE = "Beispiel-Kategorie"
KATEGORIE_ZWEI = "Beispiel-Kategorie-Zwei"
THEMA = "Konzert Beispiel"
THEMA_ZWEI = "Beispiel-Thema-Zwei"
EVENT = "2019-11-25 Beispiel-Event"
EVENT_ZWEI = "2019-11-26 Beispiel-Event"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


fu = _laden(WERKZEUG, "foto_uebersicht")

# Die Schluessel des eingefrorenen Schemas (Teil B verlaesst sich darauf).
SCHEMA_SCHLUESSEL = {"version", "art", "stand", "quelle", "zahlen", "jahre",
                     "themen", "kategorien", "events"}
ZAHLEN_SCHLUESSEL = {"zeilen", "anlaesse", "zuege", "events", "events_neu",
                     "events_wiederverwendet", "ordner_neu", "ordner_vorhanden",
                     "themen", "kategorien", "doppelung_gesamt",
                     "doppelung_ohne_anlass", "doppelung_uebersprungen",
                     "ohne_thema", "ohne_jahr", "ohne_datum", "jahre"}


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _anlass(jahr=2019, kategorie=KATEGORIE, event=EVENT, thema=THEMA,
            dateien=1, quelle="neu", **rest) -> dict:
    anlass = {"thema_quelle": f"{jahr}-Beispiel-Anlass", "jahr": jahr,
              "kategorie": kategorie, "kategorie_neu": False, "event": event,
              "event_quelle": quelle, "event_stufe": None, "thema": thema,
              "datum": "2019-11-25", "dateien": dateien, "kollision": False}
    anlass.update(rest)
    return anlass


def _plan(anlaesse=(), zusammenfassung=None, stand=PLAN_STAND, trocken=True,
          **rest) -> dict:
    plan = {"trocken": trocken, "anlaesse": list(anlaesse),
            "zusammenfassung": dict(zusammenfassung or {}), "stand": stand,
            "ordner": [], "zuege": []}
    plan.update(rest)
    return plan


def _bauen(anlaesse=(), zusammenfassung=None, **rest) -> dict:
    return fu.uebersicht_bauen(_plan(anlaesse, zusammenfassung, **rest),
                               stand=STAND)


def _plan_datei(tmp_path: Path, plan=None) -> Path:
    pfad = tmp_path / "sortierplan.json"
    pfad.write_text(json.dumps(plan if plan is not None else _plan([_anlass()]),
                               ensure_ascii=False), encoding="utf-8")
    return pfad


def _datei_hash(pfad: Path) -> str:
    return hashlib.md5(pfad.read_bytes()).hexdigest()


class Schreiber:
    """Ein Aufruf, der niemals passieren darf (reine Funktion ohne I/O)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde eine Datei geoeffnet, obwohl nichts "
                             "geoeffnet werden darf!")


# ── Schema und Konstanten ──────────────────────────────────────────────────

def test_version_und_art_sind_fest():
    assert fu.UEBERSICHT_VERSION == 1
    assert fu.UEBERSICHT_ART == "foto_uebersicht"


def test_standard_ausgabe_zeigt_auf_die_uebersichtsdatei():
    assert fu.STANDARD_AUSGABE.endswith("fotos_uebersicht.json")
    assert "foto_sortierung" in fu.STANDARD_AUSGABE


def test_standard_plan_zeigt_auf_den_sortierplan():
    assert fu.STANDARD_PLAN.endswith("sortierplan.json")


def test_bauen_liefert_die_schema_schluessel():
    assert set(_bauen([_anlass()])) == SCHEMA_SCHLUESSEL


def test_zahlen_hat_genau_die_schema_schluessel():
    assert set(_bauen([_anlass()])["zahlen"]) == ZAHLEN_SCHLUESSEL


def test_quellenblock_hat_plan_stand_und_trocken():
    daten = _bauen([_anlass()])
    assert daten["quelle"] == {"plan_stand": PLAN_STAND, "trocken": True}


def test_quelle_ohne_plan_stand_ist_leer():
    daten = _bauen([_anlass()], stand="")
    assert daten["quelle"]["plan_stand"] == ""


def test_trocken_nur_bei_echtem_true():
    assert _bauen([_anlass()], trocken=None)["quelle"]["trocken"] is False
    assert _bauen([_anlass()], trocken="ja")["quelle"]["trocken"] is False
    assert _bauen([_anlass()], trocken=True)["quelle"]["trocken"] is True


def test_version_und_art_stehen_in_der_ausgabe():
    daten = _bauen([_anlass()])
    assert daten["version"] == 1
    assert daten["art"] == "foto_uebersicht"


# ── Stand ──────────────────────────────────────────────────────────────────

def test_stand_wird_uebernommen():
    assert _bauen([_anlass()])["stand"] == STAND


def test_stand_ohne_angabe_wird_gefuellt():
    daten = fu.uebersicht_bauen(_plan([_anlass()]))
    assert isinstance(daten["stand"], str)
    assert daten["stand"].strip()
    assert "T" in daten["stand"]


def test_stand_muss_text_sein():
    with pytest.raises(ValueError):
        fu.uebersicht_bauen(_plan([_anlass()]), stand=12345)


def test_leerer_stand_ist_fehler():
    with pytest.raises(ValueError):
        fu.uebersicht_bauen(_plan([_anlass()]), stand="   ")


# ── Reine Funktion (kein Datei-, kein Netzzugriff) ─────────────────────────

def test_bauen_oeffnet_keine_datei(tmp_path, monkeypatch, capsys):
    verboten = Schreiber()
    monkeypatch.setattr("builtins.open", verboten)
    daten = fu.uebersicht_bauen(_plan([_anlass()]), stand=STAND)
    assert daten["zahlen"]["anlaesse"] == 1
    assert capsys.readouterr().out == ""


def test_bauen_veraendert_den_plan_nicht():
    plan = _plan([_anlass(), _anlass(event=EVENT_ZWEI)])
    vorher = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    fu.uebersicht_bauen(plan, stand=STAND)
    assert json.dumps(plan, ensure_ascii=False, sort_keys=True) == vorher


def test_bauen_zweimal_ist_gleich():
    plan = _plan([_anlass(), _anlass(jahr=2021, kategorie=KATEGORIE_ZWEI)])
    erst = json.dumps(fu.uebersicht_bauen(plan, stand=STAND), sort_keys=True)
    zweit = json.dumps(fu.uebersicht_bauen(plan, stand=STAND), sort_keys=True)
    assert erst == zweit


# ── Zaehler aus der Zusammenfassung ───────────────────────────────────────

def test_zeilen_anlaesse_zuege_aus_der_zusammenfassung():
    daten = _bauen([_anlass()], zusammenfassung={"zeilen": 9430, "anlaesse": 99,
                                                 "zuege": 7616})
    # ``anlaesse`` gewinnt gegen die Zusammenfassung: die echte Liste hat 1.
    assert daten["zahlen"]["zeilen"] == 9430
    assert daten["zahlen"]["zuege"] == 7616
    assert daten["zahlen"]["anlaesse"] == 1


def test_anlaesse_gewinnt_gegen_die_liste():
    anlaesse = [_anlass(), _anlass(event=EVENT_ZWEI)]
    daten = _bauen(anlaesse, zusammenfassung={"anlaesse": 77})
    assert daten["zahlen"]["anlaesse"] == 2


def test_fehlende_zusammenfassung_schluessel_sind_null():
    daten = _bauen([_anlass()], zusammenfassung={})
    for name in ("zeilen", "zuege", "doppelung_gesamt", "doppelung_ohne_anlass",
                 "doppelung_uebersprungen", "ohne_thema", "ohne_jahr",
                 "ordner_neu", "ordner_vorhanden", "events_neu"):
        assert daten["zahlen"][name] == 0, name


def test_unbrauchbare_werte_ergeben_null():
    daten = _bauen([_anlass()], zusammenfassung={"zeilen": "keine Zahl",
                                                 "zuege": None,
                                                 "doppelung_ohne_anlass": True})
    assert daten["zahlen"]["zeilen"] == 0
    assert daten["zahlen"]["zuege"] == 0
    assert daten["zahlen"]["doppelung_ohne_anlass"] == 0


def test_event_zaehler_kommen_aus_der_zusammenfassung():
    daten = _bauen([_anlass()], zusammenfassung={"events_neu": 2088,
                                                 "events_wiederverwendet": 39})
    assert daten["zahlen"]["events_neu"] == 2088
    assert daten["zahlen"]["events_wiederverwendet"] == 39


def test_doppelungen_kommen_aufgeschluesselt_an():
    daten = _bauen([_anlass()], zusammenfassung={"doppelung_gesamt": 1534,
                                                 "doppelung_ohne_anlass": 866,
                                                 "doppelung_uebersprungen": 668})
    assert daten["zahlen"]["doppelung_gesamt"] == 1534
    assert daten["zahlen"]["doppelung_ohne_anlass"] == 866
    assert daten["zahlen"]["doppelung_uebersprungen"] == 668


def test_ordner_zaehler_kommen_an():
    daten = _bauen([_anlass()], zusammenfassung={"ordner_neu": 2108,
                                                 "ordner_vorhanden": 82})
    assert daten["zahlen"]["ordner_neu"] == 2108
    assert daten["zahlen"]["ordner_vorhanden"] == 82


def test_unbekannte_zusammenfassungsschluessel_tauchen_nicht_auf():
    daten = _bauen([_anlass()], zusammenfassung={"zeilen": 5,
                                                 "je_jahr": {"2019": 1},
                                                 "erfunden": 12})
    assert "erfunden" not in daten["zahlen"]
    assert "je_jahr" not in daten["zahlen"]


# ── Ungueltiger Plan ──────────────────────────────────────────────────────

def test_plan_ohne_anlaesse_und_zusammenfassung_ist_fehler():
    with pytest.raises(ValueError) as fehler:
        fu.uebersicht_bauen({}, stand=STAND)
    assert "leer" in str(fehler.value)


def test_plan_kein_woerterbuch_ist_fehler():
    for wert in (None, [], "Plan", 42):
        with pytest.raises(ValueError):
            fu.uebersicht_bauen(wert, stand=STAND)


def test_minimaler_plan_ist_erlaubt():
    daten = _bauen([], zusammenfassung={})
    assert daten["zahlen"]["anlaesse"] == 0
    assert daten["zahlen"]["events"] == 0
    assert daten["jahre"] == []
    assert daten["themen"] == []
    assert daten["kategorien"] == []
    assert daten["events"] == []


def test_plan_nur_mit_zusammenfassung_ist_erlaubt():
    daten = fu.uebersicht_bauen({"zusammenfassung": {"zeilen": 7}}, stand=STAND)
    assert daten["zahlen"]["zeilen"] == 7
    assert daten["zahlen"]["anlaesse"] == 0


# ── Jahre ─────────────────────────────────────────────────────────────────

def test_jahre_zaehlt_nur_verschiedene_jahre():
    anlaesse = [_anlass(jahr=2019), _anlass(jahr=2019, event=EVENT_ZWEI),
                _anlass(jahr=2022, kategorie=KATEGORIE_ZWEI)]
    daten = _bauen(anlaesse)
    assert daten["zahlen"]["jahre"] == 2
    assert daten["zahlen"]["jahre"] == len(daten["jahre"])


def test_jahre_liste_ist_aufsteigend_sortiert():
    anlaesse = [_anlass(jahr=2022), _anlass(jahr=2014), _anlass(jahr=2019)]
    jahre = [eintrag["jahr"] for eintrag in _bauen(anlaesse)["jahre"]]
    assert jahre == [2014, 2019, 2022]


def test_jahreszeile_hat_die_schema_schluessel():
    daten = _bauen([_anlass()])
    assert set(daten["jahre"][0]) == {"jahr", "anlaesse", "dateien", "events"}


def test_jahreszeile_summiert_anlaesse_und_dateien():
    anlaesse = [_anlass(jahr=2019, dateien=2),
                _anlass(jahr=2019, event=EVENT_ZWEI, dateien=3)]
    zeile = _bauen(anlaesse)["jahre"][0]
    assert zeile["anlaesse"] == 2
    assert zeile["dateien"] == 5


def test_jahreszeile_zaehlt_verschiedene_events():
    anlaesse = [_anlass(jahr=2019, event=EVENT, kategorie=KATEGORIE),
                _anlass(jahr=2019, event=EVENT, kategorie=KATEGORIE),
                _anlass(jahr=2019, event=EVENT_ZWEI, kategorie=KATEGORIE)]
    zeile = _bauen(anlaesse)["jahre"][0]
    assert zeile["events"] == 2


def test_anlass_ohne_jahr_zaehlt_nicht_in_jahre():
    anlaesse = [_anlass(), _anlass(jahr=None, kategorie=KATEGORIE_ZWEI)]
    daten = _bauen(anlaesse)
    assert daten["zahlen"]["anlaesse"] == 2
    assert [eintrag["jahr"] for eintrag in daten["jahre"]] == [2019]


def test_jahr_als_text_wird_gelesen():
    daten = _bauen([_anlass(jahr="2019")])
    assert daten["jahre"][0]["jahr"] == 2019


# ── Themen ────────────────────────────────────────────────────────────────

def test_themen_zaehlt_verschiedene_werte():
    anlaesse = [_anlass(thema=THEMA), _anlass(thema=THEMA, event=EVENT_ZWEI),
                _anlass(thema=THEMA_ZWEI, kategorie=KATEGORIE_ZWEI)]
    daten = _bauen(anlaesse)
    assert daten["zahlen"]["themen"] == 2
    assert daten["zahlen"]["themen"] == len(daten["themen"])


def test_themenszeile_hat_die_schema_schluessel():
    assert set(_bauen([_anlass()])["themen"][0]) == {"thema", "anlaesse",
                                                     "dateien"}


def test_themen_sind_absteigend_nach_anlaessen():
    anlaesse = [_anlass(thema=THEMA),
                _anlass(thema=THEMA_ZWEI),
                _anlass(thema=THEMA_ZWEI, event=EVENT_ZWEI)]
    themen = [eintrag["thema"] for eintrag in _bauen(anlaesse)["themen"]]
    assert themen == [THEMA_ZWEI, THEMA]


def test_themen_gleichstand_wird_alphabetisch():
    anlaesse = [_anlass(thema="Beispiel-Thema-B"),
                _anlass(thema="Beispiel-Thema-A", event=EVENT_ZWEI)]
    themen = [eintrag["thema"] for eintrag in _bauen(anlaesse)["themen"]]
    assert themen == ["Beispiel-Thema-A", "Beispiel-Thema-B"]


def test_themenszeile_summiert_dateien():
    anlaesse = [_anlass(thema=THEMA, dateien=4),
                _anlass(thema=THEMA, event=EVENT_ZWEI, dateien=6)]
    zeile = _bauen(anlaesse)["themen"][0]
    assert zeile["anlaesse"] == 2
    assert zeile["dateien"] == 10


def test_leeres_thema_ist_keine_themenszeile():
    daten = _bauen([_anlass(thema="")])
    assert daten["themen"] == []
    assert daten["zahlen"]["themen"] == 0


# ── Kategorien ────────────────────────────────────────────────────────────

def test_kategorien_zaehlt_verschiedene_werte():
    anlaesse = [_anlass(kategorie=KATEGORIE),
                _anlass(kategorie=KATEGORIE_ZWEI, event=EVENT_ZWEI)]
    daten = _bauen(anlaesse)
    assert daten["zahlen"]["kategorien"] == 2
    assert daten["zahlen"]["kategorien"] == len(daten["kategorien"])


def test_kategorienszeile_hat_die_schema_schluessel():
    assert set(_bauen([_anlass()])["kategorien"][0]) == {
        "kategorie", "anlaesse", "dateien", "events"}


def test_kategorien_sind_absteigend_nach_anlaessen():
    anlaesse = [_anlass(kategorie=KATEGORIE),
                _anlass(kategorie=KATEGORIE_ZWEI, event=EVENT_ZWEI),
                _anlass(kategorie=KATEGORIE_ZWEI, event="2019-11-27 Beispiel")]
    kategorien = [eintrag["kategorie"] for eintrag in _bauen(anlaesse)["kategorien"]]
    assert kategorien == [KATEGORIE_ZWEI, KATEGORIE]


def test_kategorien_gleichstand_wird_alphabetisch():
    anlaesse = [_anlass(kategorie="Beispiel-Kat-B"),
                _anlass(kategorie="Beispiel-Kat-A", event=EVENT_ZWEI)]
    kategorien = [eintrag["kategorie"]
                  for eintrag in _bauen(anlaesse)["kategorien"]]
    assert kategorien == ["Beispiel-Kat-A", "Beispiel-Kat-B"]


def test_kategorienszeile_zaehlt_verschiedene_events():
    anlaesse = [_anlass(kategorie=KATEGORIE, event=EVENT),
                _anlass(kategorie=KATEGORIE, event=EVENT),
                _anlass(kategorie=KATEGORIE, event=EVENT_ZWEI)]
    zeile = _bauen(anlaesse)["kategorien"][0]
    assert zeile["anlaesse"] == 3
    assert zeile["events"] == 2


def test_leere_kategorie_ist_keine_kategorienszeile():
    daten = _bauen([_anlass(kategorie="")])
    assert daten["kategorien"] == []
    assert daten["zahlen"]["kategorien"] == 0
    # Der Event bleibt trotzdem ein Event (er hat ein Jahr und einen Namen).
    assert daten["zahlen"]["events"] == 1


# ── Events ────────────────────────────────────────────────────────────────

def test_events_zaehlt_verschiedene_kombinationen():
    anlaesse = [_anlass(event=EVENT), _anlass(event=EVENT),
                _anlass(event=EVENT_ZWEI)]
    daten = _bauen(anlaesse)
    assert daten["zahlen"]["events"] == 2
    assert daten["zahlen"]["events"] == len(daten["events"])


def test_gleiche_kombination_in_verschiedenen_jahren_ist_zwei_events():
    anlaesse = [_anlass(jahr=2019, event=EVENT),
                _anlass(jahr=2020, event=EVENT)]
    assert _bauen(anlaesse)["zahlen"]["events"] == 2


def test_gleicher_eventname_in_verschiedenen_kategorien_ist_zwei_events():
    anlaesse = [_anlass(kategorie=KATEGORIE, event=EVENT),
                _anlass(kategorie=KATEGORIE_ZWEI, event=EVENT)]
    assert _bauen(anlaesse)["zahlen"]["events"] == 2


def test_events_zeile_hat_die_schema_schluessel():
    assert set(_bauen([_anlass()])["events"][0]) == {
        "jahr", "kategorie", "name", "dateien", "quelle"}


def test_events_sind_nach_jahr_dann_nach_name_sortiert():
    anlaesse = [_anlass(jahr=2019, event="2019-11-25 B-Event"),
                _anlass(jahr=2018, event="2018-01-01 Z-Event",
                        kategorie=KATEGORIE_ZWEI),
                _anlass(jahr=2019, event="2019-11-25 A-Event")]
    namen = [(eintrag["jahr"], eintrag["name"])
             for eintrag in _bauen(anlaesse)["events"]]
    assert namen == [(2018, "2018-01-01 Z-Event"),
                     (2019, "2019-11-25 A-Event"),
                     (2019, "2019-11-25 B-Event")]


def test_events_zeile_summiert_dateien_und_traegt_die_quelle():
    anlaesse = [_anlass(event=EVENT, dateien=3, quelle="neu"),
                _anlass(event=EVENT, dateien=4, quelle="vorschlag")]
    zeile = _bauen(anlaesse)["events"][0]
    assert zeile["dateien"] == 7
    assert zeile["quelle"] == "neu"          # die erste Quelle des Events gilt
    assert zeile["kategorie"] == KATEGORIE


def test_event_quelle_bleibt_lesbar_als_text():
    zeile = _bauen([_anlass(quelle=None)])["events"][0]
    assert zeile["quelle"] == ""


def test_dateien_als_liste_zaehlt_als_laenge():
    daten = _bauen([_anlass(dateien=["a.jpg", "b.jpg"])])
    assert daten["jahre"][0]["dateien"] == 2
    assert daten["events"][0]["dateien"] == 2


# ── Zeilen ohne Datum ─────────────────────────────────────────────────────

def test_ohne_datum_rechnet_die_invariante():
    # Gegenprobe aus N7: 9.430 Zeilen - 7.616 Zuege - 668 uebersprungene
    # Doppelungen = 1.146 Zeilen ohne Datum im Namen.
    daten = _bauen([_anlass()], zusammenfassung={"zeilen": 9430, "zuege": 7616,
                                                 "doppelung_uebersprungen": 668})
    assert daten["zahlen"]["ohne_datum"] == 1146


def test_ohne_datum_wird_nie_negativ():
    daten = _bauen([_anlass()], zusammenfassung={"zeilen": 5, "zuege": 100,
                                                 "doppelung_uebersprungen": 50})
    assert daten["zahlen"]["ohne_datum"] == 0


def test_ohne_datum_ohne_werte_ist_null():
    assert _bauen([_anlass()], zusammenfassung={})["zahlen"]["ohne_datum"] == 0


# ── Keine Kennungen, keine Bilder in der Ausgabe ──────────────────────────

def test_ausgabe_hat_keine_datei_kennungen():
    text = json.dumps(_bauen([_anlass()]), ensure_ascii=False)
    for verboten in ("fileid", "folderid", "ziel_pfad", "von_ordner",
                     "von_name", "vorbuchung", "kennung"):
        assert verboten not in text, verboten


def test_ausgabe_hat_keine_bildendungen():
    text = json.dumps(_bauen([_anlass()]), ensure_ascii=False)
    for endung in (".jpg", ".jpeg", ".png", ".heic", ".mp4"):
        assert endung not in text, endung


# ── Plan lesen ────────────────────────────────────────────────────────────

def test_plan_laden_liest_das_woerterbuch(tmp_path):
    pfad = _plan_datei(tmp_path)
    plan = fu.plan_laden(str(pfad))
    assert plan["anlaesse"][0]["event"] == EVENT


def test_plan_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        fu.plan_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)


def test_plan_laden_ohne_pfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        fu.plan_laden("")
    assert "Kein Pfad" in str(fehler.value)


def test_plan_laden_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "krumm.json"
    pfad.write_text("{das ist kein json", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        fu.plan_laden(str(pfad))
    assert "gueltiges JSON" in str(fehler.value)


def test_plan_laden_liste_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "liste.json"
    pfad.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        fu.plan_laden(str(pfad))
    assert "Woerterbuch" in str(fehler.value)


# ── Uebersicht lesen und schreiben ────────────────────────────────────────

def test_uebersicht_laden_liest_zurueck(tmp_path):
    ziel = tmp_path / "u.json"
    fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    daten = fu.uebersicht_laden(str(ziel))
    assert daten["art"] == "foto_uebersicht"
    assert daten["zahlen"]["anlaesse"] == 1


def test_uebersicht_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        fu.uebersicht_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)


def test_schreiben_legt_die_datei_an_und_gibt_den_pfad_zurueck(tmp_path):
    ziel = tmp_path / "u.json"
    zurueck = fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    assert zurueck == str(ziel)
    assert ziel.is_file()


def test_schreiben_laesst_keine_temp_datei_zurueck(tmp_path):
    ziel = tmp_path / "u.json"
    fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_inhalt_ist_gueltiges_json_mit_schema(tmp_path):
    ziel = tmp_path / "u.json"
    fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert set(daten) == SCHEMA_SCHLUESSEL
    assert daten["zahlen"]["events"] == 1


def test_schreiben_zweiter_lauf_ist_byte_identisch(tmp_path):
    ziel = tmp_path / "u.json"
    daten = _bauen([_anlass()])
    fu.uebersicht_schreiben(str(ziel), daten)
    vorher = _datei_hash(ziel)
    fu.uebersicht_schreiben(str(ziel), daten)
    assert _datei_hash(ziel) == vorher


def test_schreiben_im_repo_wird_mit_valueerror_verweigert(tmp_path):
    ziel = REPO / "fotos_uebersicht.json"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError) as fehler:
        fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    assert "IM Repo" in str(fehler.value)
    assert "NICHTS geschrieben" in str(fehler.value)
    assert not ziel.exists()


def test_schreiben_ohne_daten_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        fu.uebersicht_schreiben(str(tmp_path / "u.json"), None)
    assert "Uebersichtsdaten" in str(fehler.value)
    assert not (tmp_path / "u.json").exists()


def test_schreiben_ohne_zielpfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        fu.uebersicht_schreiben("", {})
    assert "Kein Zielpfad" in str(fehler.value)


def test_schreiben_scheitert_nicht_zerstoerend(tmp_path):
    ziel = tmp_path / "u.json"
    fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    vorher = _datei_hash(ziel)
    with pytest.raises(TypeError):
        # Nicht serialisierbar -> es darf keine halbe Datei entstehen und die
        # alte Datei muss unangetastet bleiben.
        fu.uebersicht_schreiben(str(ziel), {"kaputt": object()})
    assert _datei_hash(ziel) == vorher
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_legt_den_zielordner_an(tmp_path):
    ziel = tmp_path / "neu" / "tiefer" / "u.json"
    fu.uebersicht_schreiben(str(ziel), _bauen([_anlass()]))
    assert ziel.is_file()


# ── Klartext ──────────────────────────────────────────────────────────────

def test_text_nennt_stand_und_kopfzahlen():
    text = fu.uebersicht_text(_bauen([_anlass()], zusammenfassung={"zeilen": 9430,
                                                                   "zuege": 7616}))
    assert STAND in text
    assert "Anlaesse: 1" in text
    assert "Zeilen: 9.430" in text
    assert "Zuege: 7.616" in text


def test_text_nennt_doppelungen_und_zeilen_ohne_datum():
    text = fu.uebersicht_text(_bauen([_anlass()], zusammenfassung={
        "zeilen": 9430, "zuege": 7616, "doppelung_gesamt": 1534,
        "doppelung_ohne_anlass": 866, "doppelung_uebersprungen": 668}))
    assert "Doppelungen: 1.534 gesamt" in text
    assert "866 ohne Anlass-ID" in text
    assert "668 uebersprungen" in text
    assert "Zeilen ohne Datum: 1.146" in text


def test_text_nennt_themen_kategorien_und_jahre():
    text = fu.uebersicht_text(_bauen([_anlass()]))
    assert "Jahre: 1" in text
    assert "Themen: 1" in text
    assert "Kategorien: 1" in text
    assert "Dateien: 1" in text


def test_text_haelt_fehlende_felder_aus():
    text = fu.uebersicht_text({})
    assert "Anlaesse: 0" in text
    assert "Zeilen ohne Datum: 0" in text


def test_text_ist_mehrzeilig_und_deutsch():
    text = fu.uebersicht_text(_bauen([_anlass()]))
    assert len(text.splitlines()) >= 8
    assert "unbekannt" in fu.uebersicht_text({})


# ── Kommandozeile ─────────────────────────────────────────────────────────

def test_haupt_trockenlauf_schreibt_nichts(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "u.json"
    assert fu.haupt(["--plan", str(plan), "--ausgabe", str(ziel)]) == 0
    assert not ziel.exists()
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "wurde NICHT geschrieben" in ausgabe


def test_haupt_trockenlauf_zeigt_die_uebersicht(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    fu.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "u.json")])
    ausgabe = capsys.readouterr().out
    assert "Sortierplan:" in ausgabe
    assert "Anlaesse:" in ausgabe
    assert "ohne Bilddaten, ohne Datei-Kennungen" in ausgabe


def test_haupt_mit_schreiben_legt_die_datei_an(tmp_path):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "u.json"
    assert fu.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--schreiben"]) == 0
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["art"] == "foto_uebersicht"


def test_haupt_repo_ziel_ergibt_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = REPO / "fotos_uebersicht.json"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    assert fu.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--schreiben"]) == 2
    fehler = capsys.readouterr().err
    assert "IM Repo" in fehler
    assert not ziel.exists()


def test_haupt_repo_ziel_ergibt_auch_im_trockenlauf_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    assert fu.haupt(["--plan", str(plan),
                     "--ausgabe", str(REPO / "docs" / "u.json")]) == 2
    assert "IM Repo" in capsys.readouterr().err


def test_haupt_fehlender_plan_ergibt_exit_2(tmp_path, capsys):
    assert fu.haupt(["--plan", str(tmp_path / "gibtsnicht.json"),
                     "--ausgabe", str(tmp_path / "u.json")]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_haupt_kaputter_plan_ergibt_exit_2(tmp_path, capsys):
    pfad = tmp_path / "krumm.json"
    pfad.write_text("kein json", encoding="utf-8")
    assert fu.haupt(["--plan", str(pfad), "--ausgabe",
                     str(tmp_path / "u.json")]) == 2
    assert "Fehler" in capsys.readouterr().err


# ── Quelltext: keine Loesch-, Netz- oder pCloud-Funktion ──────────────────

def _baum():
    return ast.parse(WERKZEUG.read_text(encoding="utf-8"))


def test_quelltext_importiert_nur_standardbibliothek():
    erlaubt = {"argparse", "datetime", "json", "os", "sys", "__future__"}
    namen: set[str] = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                namen.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            namen.add((knoten.module or "").split(".")[0])
    assert namen <= erlaubt, f"unerlaubter Import: {namen - erlaubt}"


def test_quelltext_ohne_loesch_und_systemaufrufe():
    verboten = {"deletefile", "deletefolder", "rmtree", "removefile",
                "removefolder", "renametree", "system", "popen", "unlink"}
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute):
            assert knoten.func.attr not in verboten, knoten.func.attr


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


def test_quelltext_hat_keinen_netzaufruf():
    # Gesucht werden echte Aufrufe/Importe, nicht das Wort in der Begruendung
    # des Modulkopfes ("kein httpx/requests").
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("import requests", "requests.", "import httpx", "httpx.",
                     "import urllib", "urllib.", "import socket", "socket.",
                     "urlopen(", "http://", "https://", "pcloud_service",
                     "pcloud_bewegungen", "import subprocess", "subprocess."):
        assert verboten not in quelle, f"Netz-/Fremdaufruf im Quelltext: {verboten}"


def test_quelltext_oeffnet_keine_bilder():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("PIL", "cv2", "imageio", ".jpg", ".jpeg", ".png", ".heic",
                     '"rb"', "'rb'"):
        assert verboten not in quelle, f"Bildzugriff im Quelltext: {verboten}"


def test_quelltext_schreibt_atomar():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "os.replace(" in quelle
    assert ".tmp" in quelle


def test_quelltext_prueft_das_repo_ziel():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "_pruefe_ziel_ausserhalb_repo" in quelle
    assert "IM Repo" in quelle


def test_quelltext_ohne_datetime_now_in_der_reinen_funktion():
    # ``datetime.now()`` darf nur ueber den injizierbaren ``stand`` laufen: die
    # reine Funktion ``uebersicht_bauen`` muss ohne ``stand`` selbst den
    # Zeitstempel setzen, aber deterministisch pruefbar bleiben — deshalb genau
    # ein Aufruf von ``now`` im Modul.
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert quelle.count("datetime.datetime.now(") == 1


def test_exportierte_schluessel_konstanten_passen_zum_schema():
    assert fu.SCHLUESSEL_JAHRE == ("jahr", "anlaesse", "dateien", "events")
    assert fu.SCHLUESSEL_THEMEN == ("thema", "anlaesse", "dateien")
    assert fu.SCHLUESSEL_KATEGORIEN == ("kategorie", "anlaesse", "dateien",
                                        "events")
    assert fu.SCHLUESSEL_EVENTS == ("jahr", "kategorie", "name", "dateien",
                                    "quelle")


def test_listen_schluessel_stimmen_mit_den_konstanten():
    daten = _bauen([_anlass()])
    assert tuple(daten["jahre"][0]) == fu.SCHLUESSEL_JAHRE
    assert tuple(daten["themen"][0]) == fu.SCHLUESSEL_THEMEN
    assert tuple(daten["kategorien"][0]) == fu.SCHLUESSEL_KATEGORIEN
    assert tuple(daten["events"][0]) == fu.SCHLUESSEL_EVENTS
