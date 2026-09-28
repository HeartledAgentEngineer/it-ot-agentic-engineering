"""Pruefungen fuer ``ereignisse_bauen.py`` (N27 Schritt 1, Ereignis-Knoten, 28.09.2026).

Alles OHNE Netz und ohne Bild: das Werkzeug liest nur den lokalen Sortierplan
bzw. erfundene Plandaten; Dateien gehen nach ``tmp_path``. Geprueft werden das
eingefrorene JSONL-Schema, die Zaehl-Invarianten, die feste Sortierung, die
Idempotenz (bei vorgegebenem ``stand`` byte-gleich; im echten Lauf
unterscheiden zwei Laeufe sich ausschliesslich im Feld ``stand``), das
atomare Schreiben nur
ausserhalb des Repos, die Trockenlauf-Garantien und der Quelltext (keine Netz-,
Bild- oder Loeschfunktion).

**Nur erfundene Beispielnamen und erfundene Kennungen** — echte Anlass-,
Ordner- und Dateinamen sowie echte Kennungen liegen ausserhalb des Repos und
kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_ereignisse_bauen.py -q
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "ereignisse_bauen.py"

STAND = "2026-09-28T09:40:00+02:00"
PLAN_STAND = "2026-09-27T13:49:46"

# Erfundene Beispielwerte.
ANLASS = "2014-03-30_Beispiel-01"
ANLASS_ZWEI = "2016-05-04_Beispiel-02"
ANLASS_DREI = "2017-06-05_Beispiel-03"
KATEGORIE = "Beispielkategorie"
THEMA = "Beispielthema"
EVENT = "2014-03-30 Beispielthema"
ZIEL = "Agent/Fotos/2014/Beispielkategorie/2014-03-30 Beispielthema"
KENNUNG = 123456789
KENNUNG_ZWEI = 987654321


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


eb = _laden(WERKZEUG, "ereignisse_bauen")

# Die Schluessel des eingefrorenen Schemas (die Folgeschritte verlassen sich darauf).
SCHEMA_SCHLUESSEL = ("art", "version", "stand", "plan_stand", "zahlen", "ereignisse")
ZAHLEN_SCHLUESSEL = {
    "anlaesse", "dateien", "zuege", "zuege_ohne_anlass", "zuege_ohne_kennung",
    "ohne_datum", "ohne_thema", "kollisionen", "events_wiederverwendet",
    "event_quellen", "kategorien", "jahre", "themen",
}
KNOTEN_SCHLUESSEL = {
    "anlass_id", "anzahl_dateien", "art", "datei_kennungen", "datum", "event",
    "event_quelle", "event_stufe", "jahr", "kategorie", "kennung", "quellen",
    "stand", "thema", "ziel_ordner",
}


# ── kleine Helfer (erfundene Daten) ───────────────────────────────────────

def _anlass(anlass_id: str = ANLASS, **rest) -> dict:
    eintrag = {
        "thema_quelle": anlass_id,
        "jahr": 2014,
        "kategorie": KATEGORIE,
        "kategorie_neu": False,
        "event": EVENT,
        "event_quelle": "neu",
        "event_stufe": None,
        "thema": THEMA,
        "datum": "2014-03-30",
        "dateien": 1,
        "kollision": False,
    }
    eintrag.update(rest)
    return eintrag


def _zug(anlass_id: str = ANLASS, fileid=KENNUNG, ziel_pfad=ZIEL, **rest) -> dict:
    eintrag = {
        "thema_quelle": anlass_id,
        "jahr": 2014,
        "kategorie": KATEGORIE,
        "event": EVENT,
        "event_quelle": "neu",
        "von_ordner": "P:/Beispiel/Ordner",
        "von_name": "2014-03-30_Beispiel-01.jpg",
        "ziel_pfad": ziel_pfad,
        "fileid": fileid,
        "vorbuchung": None,
    }
    eintrag.update(rest)
    return eintrag


def _plan(anlaesse=(), zuege=(), stand=PLAN_STAND, **rest) -> dict:
    plan = {"trocken": True, "anlaesse": list(anlaesse), "ordner": [],
            "zuege": list(zuege), "zusammenfassung": {}, "stand": stand}
    plan.update(rest)
    return plan


def _bauen(anlaesse=(), zuege=(), **rest) -> dict:
    return eb.ereignisse_bauen(_plan(anlaesse, zuege, **rest), stand=STAND)


def _plan_datei(tmp_path: Path, plan=None) -> Path:
    pfad = tmp_path / "sortierplan.json"
    pfad.write_text(json.dumps(plan if plan is not None else
                               _plan([_anlass()], [_zug()]), ensure_ascii=False),
                    encoding="utf-8")
    return pfad


def _datei_hash(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _kennung_von(daten: dict, anlass_id: str) -> dict:
    for knoten in daten["ereignisse"]:
        if knoten["anlass_id"] == anlass_id:
            return knoten
    raise AssertionError(f"Anlass fehlt: {anlass_id}")


class Oeffner:
    """Ein Aufruf, der niemals passieren darf (reine Funktion ohne I/O)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde eine Datei geoeffnet, obwohl nichts "
                             "geoeffnet werden darf!")


# ── Schema und Konstanten ─────────────────────────────────────────────────

def test_version_und_art_sind_fest():
    assert eb.EREIGNISSE_VERSION == 1
    assert eb.EREIGNISSE_ART == "ereignisse"


def test_standard_ausgabe_zeigt_auf_die_jsonl_datei():
    assert eb.STANDARD_AUSGABE.endswith("ereignisse.jsonl")
    assert "foto_sortierung" in eb.STANDARD_AUSGABE


def test_standard_plan_zeigt_auf_den_sortierplan():
    assert eb.STANDARD_PLAN.endswith("sortierplan.json")


def test_quellen_konstanten_zeigen_auf_den_plan():
    assert eb.QUELLE_DATUM == "sortierplan.json:anlaesse"
    assert eb.QUELLE_DATEIEN == "sortierplan.json:zuege"


def test_bauen_liefert_die_schema_schluessel():
    assert set(_bauen([_anlass()], [_zug()])) == set(SCHEMA_SCHLUESSEL)


def test_schema_schluessel_reihenfolge_ist_fest():
    assert tuple(_bauen([_anlass()], [_zug()])) == SCHEMA_SCHLUESSEL


def test_zahlen_hat_genau_die_schema_schluessel():
    assert set(_bauen([_anlass()], [_zug()])["zahlen"]) == ZAHLEN_SCHLUESSEL


def test_zahlen_schluessel_reihenfolge_ist_fest():
    assert tuple(_bauen([_anlass()], [_zug()])["zahlen"]) == eb.ZAHLEN_SCHLUESSEL


def test_knoten_hat_genau_die_schema_schluessel():
    assert set(_bauen([_anlass()], [_zug()])["ereignisse"][0]) == KNOTEN_SCHLUESSEL


def test_knoten_schluessel_reihenfolge_ist_fest():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    assert tuple(knoten) == eb.KNOTEN_SCHLUESSEL


def test_knoten_art_ist_ereignis():
    assert _bauen([_anlass()], [_zug()])["ereignisse"][0]["art"] == "ereignis"


def test_quellen_des_knotens_sind_die_drei_schema_schluessel():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    assert set(knoten["quellen"]) == {"datum", "dateien", "ziel_ordner"}


def test_quellen_werte_nennen_plan_und_block():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    assert knoten["quellen"]["datum"] == "sortierplan.json:anlaesse"
    assert knoten["quellen"]["dateien"] == "sortierplan.json:zuege"
    assert knoten["quellen"]["ziel_ordner"] == "sortierplan.json:zuege"


def test_kennung_ist_E_plus_anlass_id():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    assert knoten["anlass_id"] == ANLASS
    assert knoten["kennung"] == "E-" + ANLASS


def test_felder_kommen_aus_dem_anlass():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    assert knoten["datum"] == "2014-03-30"
    assert knoten["jahr"] == 2014
    assert knoten["kategorie"] == KATEGORIE
    assert knoten["thema"] == THEMA
    assert knoten["event"] == EVENT
    assert knoten["event_quelle"] == "neu"
    assert knoten["event_stufe"] is None
    assert knoten["stand"] == STAND


def test_version_und_art_stehen_in_der_ausgabe():
    daten = _bauen([_anlass()], [_zug()])
    assert daten["version"] == 1
    assert daten["art"] == "ereignisse"


# ── Stand und Plan-Stand ──────────────────────────────────────────────────

def test_stand_wird_uebernommen():
    assert _bauen([_anlass()], [_zug()])["stand"] == STAND


def test_stand_ohne_angabe_wird_gefuellt():
    daten = eb.ereignisse_bauen(_plan([_anlass()], [_zug()]))
    assert isinstance(daten["stand"], str)
    assert daten["stand"].strip()
    assert "T" in daten["stand"]


def test_stand_muss_text_sein():
    with pytest.raises(ValueError):
        eb.ereignisse_bauen(_plan([_anlass()], [_zug()]), stand=12345)


def test_leerer_stand_ist_fehler():
    with pytest.raises(ValueError):
        eb.ereignisse_bauen(_plan([_anlass()], [_zug()]), stand="   ")


def test_plan_stand_wird_uebernommen():
    assert _bauen([_anlass()], [_zug()])["plan_stand"] == PLAN_STAND


def test_plan_stand_fehlt_dann_null():
    assert _bauen([_anlass()], [_zug()], stand=None)["plan_stand"] is None


def test_plan_stand_ist_kein_text_dann_null():
    assert _bauen([_anlass()], [_zug()], stand=1234)["plan_stand"] is None


# ── Reine Funktionen (kein Datei-, kein Netzzugriff) ──────────────────────

def test_bauen_oeffnet_keine_datei(monkeypatch):
    monkeypatch.setattr("builtins.open", Oeffner())
    daten = eb.ereignisse_bauen(_plan([_anlass()], [_zug()]), stand=STAND)
    assert daten["zahlen"]["dateien"] == 1


def test_bauen_veraendert_den_plan_nicht():
    plan = _plan([_anlass()], [_zug(), _zug(fileid=KENNUNG_ZWEI)])
    vorher = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    eb.ereignisse_bauen(plan, stand=STAND)
    assert json.dumps(plan, ensure_ascii=False, sort_keys=True) == vorher


def test_knoten_zeile_ist_rein(monkeypatch):
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    monkeypatch.setattr("builtins.open", Oeffner())
    assert eb.knoten_zeile(knoten) == eb.knoten_zeile(knoten)


def test_knoten_zeile_gleiche_eingabe_gleiche_ausgabe():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    erst = eb.knoten_zeile(dict(knoten))
    zweit = eb.knoten_zeile(json.loads(json.dumps(knoten)))
    assert erst == zweit


def test_knoten_zeile_ist_ascii_und_sortiert():
    knoten = _bauen([_anlass()], [_zug()])["ereignisse"][0]
    zeile = eb.knoten_zeile(knoten)
    assert zeile == json.dumps(knoten, ensure_ascii=True, sort_keys=True)
    assert zeile.isascii()
    assert "\n" not in zeile
    assert json.loads(zeile)["kennung"] == "E-" + ANLASS


def test_knoten_zeile_ohne_woerterbuch_ist_fehler():
    with pytest.raises(ValueError):
        eb.knoten_zeile(["kein", "Knoten"])


# ── Zaehl-Invarianten ─────────────────────────────────────────────────────

def _gemischter_plan():
    """Ein Plan mit zwei Anlaessen, zwei erkannten Zuegen und zwei Sonderfaellen."""
    anlaesse = [_anlass(), _anlass(ANLASS_ZWEI, jahr=2016, datum="2016-05-04",
                                   event="2016-05-04 Beispielthema")]
    zuege = [_zug(), _zug(fileid=KENNUNG_ZWEI),
             _zug(fileid=None),                       # ohne Kennung
             _zug(anlass_id="2019-01-01_Beispiel-99")]  # unbekannter Anlass
    return _plan(anlaesse, zuege)


def test_invariante_anlaesse_ist_die_knotenzahl():
    daten = eb.ereignisse_bauen(_gemischter_plan(), stand=STAND)
    assert daten["zahlen"]["anlaesse"] == len(daten["ereignisse"])
    assert daten["zahlen"]["anlaesse"] == 2


def test_invariante_dateien_ist_die_summe_der_anzahlen():
    daten = eb.ereignisse_bauen(_gemischter_plan(), stand=STAND)
    summe = sum(knoten["anzahl_dateien"] for knoten in daten["ereignisse"])
    assert daten["zahlen"]["dateien"] == summe
    assert daten["zahlen"]["dateien"] == 2


def test_invariante_jede_zug_zeile_genau_einmal():
    daten = eb.ereignisse_bauen(_gemischter_plan(), stand=STAND)
    zahlen = daten["zahlen"]
    assert (zahlen["dateien"] + zahlen["zuege_ohne_anlass"]
            + zahlen["zuege_ohne_kennung"] == zahlen["zuege"])
    assert zahlen["zuege"] == 4


def test_invariante_haelt_auch_bei_leerem_und_kaputtem_plan():
    for plan in (_plan(), _plan([_anlass()], []), _plan([], [_zug()]),
                 _plan([_anlass(), "kaputt"], [_zug(), 42, None])):
        daten = eb.ereignisse_bauen(plan, stand=STAND)
        zahlen = daten["zahlen"]
        assert zahlen["anlaesse"] == len(daten["ereignisse"])
        assert zahlen["dateien"] == sum(k["anzahl_dateien"]
                                        for k in daten["ereignisse"])
        assert (zahlen["dateien"] + zahlen["zuege_ohne_anlass"]
                + zahlen["zuege_ohne_kennung"] == zahlen["zuege"])


def test_anzahl_dateien_ist_die_laenge_der_kennungsliste():
    daten = _bauen([_anlass()], [_zug(), _zug(fileid=KENNUNG_ZWEI)])
    for knoten in daten["ereignisse"]:
        assert knoten["anzahl_dateien"] == len(knoten["datei_kennungen"])


def test_leerer_plan_ergibt_null_zahlen():
    daten = _bauen()
    assert daten["ereignisse"] == []
    assert daten["zahlen"] == {
        "anlaesse": 0, "dateien": 0, "zuege": 0, "zuege_ohne_anlass": 0,
        "zuege_ohne_kennung": 0, "ohne_datum": 0, "ohne_thema": 0,
        "kollisionen": 0, "events_wiederverwendet": 0, "event_quellen": {},
        "kategorien": 0,
        "jahre": 0, "themen": 0,
    }


# ── Kennungen, Zuege, Sonderfaelle ────────────────────────────────────────

def test_zug_mit_gueltiger_kennung_wird_aufgenommen():
    daten = _bauen([_anlass()], [_zug()])
    assert daten["zahlen"]["dateien"] == 1
    assert daten["zahlen"]["zuege_ohne_kennung"] == 0


def test_datei_kennungen_sind_die_fileid_werte():
    daten = _bauen([_anlass()], [_zug(fileid=KENNUNG)])
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == [KENNUNG]


def test_datei_kennungen_sind_aufsteigend_sortiert():
    zuege = [_zug(fileid=555), _zug(fileid=99999), _zug(fileid=11)]
    daten = _bauen([_anlass()], zuege)
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == [11, 555, 99999]


def test_gleiche_kennung_zweimal_zaehlt_zweimal():
    """Jeder Zug zaehlt: zwei Zuege derselben Datei sind zwei Eintraege."""
    daten = _bauen([_anlass()], [_zug(), _zug()])
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == [KENNUNG, KENNUNG]
    assert daten["zahlen"]["dateien"] == 2


def test_zug_ohne_fileid_wird_gezaehlt_nicht_aufgenommen():
    daten = _bauen([_anlass()], [_zug(), _zug(fileid=None)])
    assert daten["zahlen"]["zuege_ohne_kennung"] == 1
    assert daten["zahlen"]["dateien"] == 1
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == [KENNUNG]


def test_bool_ist_keine_kennung():
    daten = _bauen([_anlass()], [_zug(fileid=True)])
    assert daten["zahlen"]["zuege_ohne_kennung"] == 1
    assert daten["zahlen"]["dateien"] == 0


def test_unsinnige_kennung_wird_gezaehlt():
    daten = _bauen([_anlass()], [_zug(fileid="keine Zahl")])
    assert daten["zahlen"]["zuege_ohne_kennung"] == 1


def test_kennung_als_text_wird_gelesen():
    daten = _bauen([_anlass()], [_zug(fileid="456789123")])
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == [456789123]


def test_nicht_woerterbuch_zug_wird_gezaehlt():
    daten = _bauen([_anlass()], [_zug(), "kaputt", 42, None])
    assert daten["zahlen"]["dateien"] == 1
    assert daten["zahlen"]["zuege_ohne_kennung"] == 3


def test_zug_mit_unbekannter_thema_quelle_zaehlt_ohne_anlass():
    daten = _bauen([_anlass()], [_zug(anlass_id="2019-01-01_Beispiel-99")])
    assert daten["zahlen"]["zuege_ohne_anlass"] == 1
    assert daten["zahlen"]["dateien"] == 0
    assert daten["zahlen"]["zuege_ohne_kennung"] == 0


def test_kennung_ohne_anlass_zaehlt_als_ohne_anlass():
    daten = _bauen([_anlass()], [_zug(anlass_id="gibt-es-nicht")])
    assert daten["zahlen"]["zuege_ohne_anlass"] == 1
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == []


def test_anlass_ohne_dateien_ist_trotzdem_ein_knoten():
    daten = _bauen([_anlass(), _anlass(ANLASS_ZWEI, datum="2016-05-04")], [_zug()])
    assert daten["zahlen"]["anlaesse"] == 2
    assert _kennung_von(daten, ANLASS_ZWEI)["anzahl_dateien"] == 0
    assert _kennung_von(daten, ANLASS_ZWEI)["datei_kennungen"] == []


def test_anlass_ohne_thema_quelle_ergibt_keinen_knoten():
    """Ohne stabile Kennung kein Anker — es wird kein Name erfunden."""
    anlass = _anlass()
    anlass["thema_quelle"] = ""
    daten = _bauen([anlass], [_zug()])
    assert daten["ereignisse"] == []
    assert daten["zahlen"]["anlaesse"] == 0


def test_anlass_kein_woerterbuch_wird_uebersprungen():
    daten = _bauen([_anlass(), "kaputt", None], [_zug()])
    assert daten["zahlen"]["anlaesse"] == 1
    assert len(daten["ereignisse"]) == 1


def test_gleiche_kennung_ergibt_einen_knoten():
    """Im Bestand ist thema_quelle eindeutig; ein Doppel ergibt keinen zweiten Knoten."""
    daten = _bauen([_anlass(), _anlass()], [_zug()])
    assert daten["zahlen"]["anlaesse"] == 1


# ── Ohne Datum und ohne Thema (nichts geht verloren) ─────────────────────

def test_anlass_ohne_datum_ist_trotzdem_ein_knoten():
    daten = _bauen([_anlass(datum=None)], [_zug()])
    knoten = _kennung_von(daten, ANLASS)
    assert knoten["datum"] is None
    assert knoten["kennung"] == "E-" + ANLASS
    assert knoten["anzahl_dateien"] == 1


def test_anlass_ohne_datum_zaehlt_in_ohne_datum():
    daten = _bauen([_anlass(), _anlass(ANLASS_ZWEI, datum="kein Datum")], [_zug()])
    assert daten["zahlen"]["ohne_datum"] == 1
    assert daten["zahlen"]["anlaesse"] == 2


def test_unmoegliches_datum_ist_kein_datum():
    daten = _bauen([_anlass(datum="2014-13-45")], [_zug()])
    assert _kennung_von(daten, ANLASS)["datum"] is None
    assert daten["zahlen"]["ohne_datum"] == 1


def test_datum_als_zahl_ist_kein_datum():
    daten = _bauen([_anlass(datum=20140330)], [_zug()])
    assert daten["zahlen"]["ohne_datum"] == 1


def test_anlass_ohne_thema_zaehlt_in_ohne_thema():
    daten = _bauen([_anlass(thema=""), _anlass(ANLASS_ZWEI, datum="2016-05-04",
                                                 thema=THEMA)], [_zug()])
    assert daten["zahlen"]["ohne_thema"] == 1
    assert daten["zahlen"]["themen"] == 1
    assert _kennung_von(daten, ANLASS)["thema"] == ""


# ── ziel_ordner aus den Zuegen (auch der null-Fall) ──────────────────────

def test_ziel_ordner_kommt_aus_dem_zug():
    daten = _bauen([_anlass()], [_zug(ziel_pfad=ZIEL)])
    assert _kennung_von(daten, ANLASS)["ziel_ordner"] == ZIEL


def test_ziel_ordner_ist_null_ohne_zug():
    daten = _bauen([_anlass()], [])
    assert _kennung_von(daten, ANLASS)["ziel_ordner"] is None


def test_ziel_ordner_ist_null_bei_zug_ohne_zielpfad():
    daten = _bauen([_anlass()], [_zug(ziel_pfad=None)])
    knoten = _kennung_von(daten, ANLASS)
    assert knoten["ziel_ordner"] is None
    assert knoten["anzahl_dateien"] == 1


def test_ziel_ordner_ist_null_bei_leerem_zielpfad():
    daten = _bauen([_anlass()], [_zug(ziel_pfad="   ")])
    assert _kennung_von(daten, ANLASS)["ziel_ordner"] is None


def test_ziel_ordner_nur_aus_zugeordneten_zuegen():
    """Der Zug eines fremden Anlasses darf den ziel_ordner nicht liefern."""
    daten = _bauen([_anlass()], [_zug(anlass_id="gibt-es-nicht")])
    assert _kennung_von(daten, ANLASS)["ziel_ordner"] is None


# ── Weitere Zaehler ──────────────────────────────────────────────────────

def test_kollisionen_werden_gezaehlt():
    daten = _bauen([_anlass(kollision=True),
                    _anlass(ANLASS_ZWEI, datum="2016-05-04")], [_zug()])
    assert daten["zahlen"]["kollisionen"] == 1


def test_events_wiederverwendet_zaehlt_vorschlag_quelle():
    # Im echten Plan heisst der wiederverwendete Event-Name "vorschlag"
    # (Event-Abgleich N6e) — nicht "ordner".
    daten = _bauen([_anlass(event_quelle="vorschlag"),
                    _anlass(ANLASS_ZWEI, datum="2016-05-04")], [_zug()])
    assert daten["zahlen"]["events_wiederverwendet"] == 1


def test_events_wiederverwendet_zaehlt_jeden_wert_ausser_neu():
    # Jeder Wert ausser "neu" gilt als wiederverwendet — ein unbekannter Wert
    # wird also nicht stillschweigend als "neu" verbucht.
    daten = _bauen([_anlass(event_quelle="unbekannterWert")], [_zug()])
    assert daten["zahlen"]["events_wiederverwendet"] == 1
    assert daten["zahlen"]["event_quellen"] == {"unbekannterWert": 1}


def test_event_quelle_neu_zaehlt_nicht_als_wiederverwendet():
    daten = _bauen([_anlass(event_quelle="neu")], [_zug()])
    assert daten["zahlen"]["events_wiederverwendet"] == 0


def test_event_quellen_zaehlt_die_volle_verteilung():
    daten = _bauen([_anlass(event_quelle="neu"),
                    _anlass(ANLASS_ZWEI, datum="2016-05-04",
                            event_quelle="vorschlag"),
                    _anlass(ANLASS_DREI, datum="2017-06-05",
                            event_quelle="neu")], [_zug()])
    assert daten["zahlen"]["event_quellen"] == {"neu": 2, "vorschlag": 1}
    assert daten["zahlen"]["events_wiederverwendet"] == 1


def test_leere_event_quelle_zaehlt_in_keine_verteilung():
    # Ein fehlender Wert ist kein Wert: er taucht nicht als "" in der
    # Verteilung auf und gilt auch nicht als wiederverwendet.
    daten = _bauen([_anlass(event_quelle="")], [_zug()])
    assert daten["zahlen"]["event_quellen"] == {}
    assert daten["zahlen"]["events_wiederverwendet"] == 0


def test_konsolenbericht_nennt_die_event_quellen():
    daten = _bauen([_anlass(event_quelle="vorschlag"),
                    _anlass(ANLASS_ZWEI, datum="2016-05-04")], [_zug()])
    text = eb.zahlen_text(daten)
    assert "Event-Quellen: neu=1, vorschlag=1" in text
    assert "Events wiederverwendet: 1" in text


def test_verteilung_text_ist_ehrlich_bei_leerer_angabe():
    assert eb._verteilung_text(None) == "keine"
    assert eb._verteilung_text({}) == "keine"
    assert eb._verteilung_text("neu") == "keine"
    assert eb._verteilung_text({"neu": 2000}) == "neu=2.000"


def test_kategorien_jahre_themen_zaehlen_verschiedene_werte():
    anlaesse = [_anlass(),
                _anlass(ANLASS_ZWEI, jahr=2016, datum="2016-05-04",
                        kategorie="Beispielkategorie-Zwei", thema="Beispielthema-Zwei")]
    daten = _bauen(anlaesse, [_zug()])
    assert daten["zahlen"]["kategorien"] == 2
    assert daten["zahlen"]["jahre"] == 2
    assert daten["zahlen"]["themen"] == 2


def test_jahr_ohne_zahl_zaehlt_nicht_als_jahr():
    daten = _bauen([_anlass(jahr="keine Zahl")], [_zug()])
    assert _kennung_von(daten, ANLASS)["jahr"] is None
    assert daten["zahlen"]["jahre"] == 0


def test_unbekannte_plan_schluessel_werden_ignoriert():
    daten = _bauen([_anlass()], [_zug()], fremd={"egal": 1}, ordner=[1, 2, 3])
    assert daten["zahlen"]["anlaesse"] == 1
    assert set(daten) == set(SCHEMA_SCHLUESSEL)


# ── Feste Sortierung (macht die Datei reproduzierbar) ────────────────────

def test_sortierung_nach_datum_aufsteigend():
    anlaesse = [_anlass("2016-05-04_Beispiel-02", jahr=2016, datum="2016-05-04"),
                _anlass("2014-03-30_Beispiel-01", jahr=2014, datum="2014-03-30"),
                _anlass("2018-07-09_Beispiel-03", jahr=2018, datum="2018-07-09")]
    daten = _bauen(anlaesse, [_zug()])
    assert [k["datum"] for k in daten["ereignisse"]] == [
        "2014-03-30", "2016-05-04", "2018-07-09"]


def test_sortierung_gleichstand_nach_anlass_id():
    anlaesse = [_anlass("2014-03-30_Beispiel-B"), _anlass("2014-03-30_Beispiel-A"),
                _anlass("2014-03-30_Beispiel-C")]
    daten = _bauen(anlaesse, [_zug()])
    assert [k["anlass_id"] for k in daten["ereignisse"]] == [
        "2014-03-30_Beispiel-A", "2014-03-30_Beispiel-B",
        "2014-03-30_Beispiel-C"]


def test_sortierung_stellt_anlaesse_ohne_datum_hinten_an():
    anlaesse = [_anlass(datum=None), _anlass("2014-03-30_Beispiel-01"),
                _anlass("2013-01-02_Beispiel-03", datum="2013-01-02")]
    daten = _bauen(anlaesse, [_zug()])
    assert daten["ereignisse"][0]["datum"] == "2013-01-02"
    assert daten["ereignisse"][-1]["datum"] is None
    assert daten["ereignisse"][-1]["anlass_id"] == ANLASS


def test_kennungen_werden_nicht_erfunden():
    daten = _bauen([_anlass()], [_zug(fileid=1), _zug(fileid=KENNUNG_ZWEI)])
    assert _kennung_von(daten, ANLASS)["datei_kennungen"] == [1, KENNUNG_ZWEI]


# ── Idempotenz (zweiter Aufruf: derselbe Text) ───────────────────────────

def test_zweiter_aufruf_ergibt_denselben_text():
    plan = _plan([_anlass(), _anlass(ANLASS_ZWEI, jahr=2016, datum="2016-05-04")],
                 [_zug(), _zug(fileid=KENNUNG_ZWEI)])
    erst = eb.ereignisse_bauen(plan, stand=STAND)
    zweit = eb.ereignisse_bauen(plan, stand=STAND)
    assert json.dumps(erst, ensure_ascii=True, sort_keys=True) == \
        json.dumps(zweit, ensure_ascii=True, sort_keys=True)


def test_zweiter_aufruf_ergibt_dieselben_zeilen():
    plan = _gemischter_plan()
    erst = [eb.knoten_zeile(k) for k in
            eb.ereignisse_bauen(plan, stand=STAND)["ereignisse"]]
    zweit = [eb.knoten_zeile(k) for k in
             eb.ereignisse_bauen(plan, stand=STAND)["ereignisse"]]
    assert erst == zweit
    assert len(erst) == 2


# ── Ungueltiger Plan ─────────────────────────────────────────────────────

def test_plan_ohne_anlaesse_ist_fehler():
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_bauen({"zuege": []}, stand=STAND)
    assert "anlaesse" in str(fehler.value)


def test_plan_ohne_zuege_ist_fehler():
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_bauen({"anlaesse": []}, stand=STAND)
    assert "zuege" in str(fehler.value)


def test_plan_kein_woerterbuch_ist_fehler():
    for wert in (None, [], "Plan", 42):
        with pytest.raises(ValueError):
            eb.ereignisse_bauen(wert, stand=STAND)


def test_anlaesse_keine_liste_ist_fehler():
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_bauen({"anlaesse": {}, "zuege": []}, stand=STAND)
    assert "Liste" in str(fehler.value)


# ── Plan lesen ───────────────────────────────────────────────────────────

def test_plan_laden_liest_das_woerterbuch(tmp_path):
    plan = eb.plan_laden(str(_plan_datei(tmp_path)))
    assert plan["anlaesse"][0]["thema_quelle"] == ANLASS


def test_plan_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        eb.plan_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)


def test_plan_laden_ohne_pfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        eb.plan_laden("")
    assert "Kein Pfad" in str(fehler.value)


def test_plan_laden_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "krumm.json"
    pfad.write_text("{das ist kein json", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        eb.plan_laden(str(pfad))
    assert "gueltiges JSON" in str(fehler.value)


def test_plan_laden_liste_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "liste.json"
    pfad.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        eb.plan_laden(str(pfad))
    assert "Woerterbuch" in str(fehler.value)


# ── Schreiben: JSONL, atomar, nur ausserhalb des Repos ───────────────────

def _schreiben(tmp_path: Path, anlaesse=(), zuege=()) -> Path:
    ziel = tmp_path / "ereignisse.jsonl"
    eb.ereignisse_schreiben(str(ziel), _bauen(anlaesse, zuege))
    return ziel


def test_schreiben_legt_die_datei_an_und_gibt_den_pfad_zurueck(tmp_path):
    ziel = tmp_path / "ereignisse.jsonl"
    zurueck = eb.ereignisse_schreiben(str(ziel), _bauen([_anlass()], [_zug()]))
    assert zurueck == str(ziel)
    assert ziel.is_file()


def test_schreiben_ist_reine_jsonl_mit_einer_zeile_je_anlass(tmp_path):
    anlaesse = [_anlass(), _anlass(ANLASS_ZWEI, jahr=2016, datum="2016-05-04")]
    ziel = _schreiben(tmp_path, anlaesse, [_zug()])
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == len(anlaesse)
    assert len(zeilen) == 2


def test_schreiben_jede_zeile_ist_lesbares_json(tmp_path):
    ziel = _schreiben(tmp_path, [_anlass()], [_zug()])
    for zeile in ziel.read_text(encoding="utf-8").splitlines():
        knoten = json.loads(zeile)
        assert set(knoten) == KNOTEN_SCHLUESSEL
        assert knoten["art"] == "ereignis"


def test_schreiben_ist_ascii_und_sortierte_schluessel(tmp_path):
    ziel = _schreiben(tmp_path, [_anlass()], [_zug()])
    roh = ziel.read_text(encoding="utf-8")
    assert roh.isascii()
    for zeile in roh.splitlines():
        assert zeile == json.dumps(json.loads(zeile), ensure_ascii=True,
                                   sort_keys=True)


def test_schreiben_enthaelt_keinen_zahlen_block(tmp_path):
    ziel = _schreiben(tmp_path, [_anlass()], [_zug()])
    roh = ziel.read_text(encoding="utf-8")
    assert '"zahlen"' not in roh
    assert '"art": "ereignisse"' not in roh


def test_schreiben_laesst_keine_temp_datei_zurueck(tmp_path):
    _schreiben(tmp_path, [_anlass()], [_zug()])
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_zweiter_lauf_ist_byte_identisch(tmp_path):
    anlaesse = [_anlass(), _anlass(ANLASS_ZWEI, jahr=2016, datum="2016-05-04")]
    ziel = _schreiben(tmp_path, anlaesse, [_zug(), _zug(fileid=KENNUNG_ZWEI)])
    vorher = _datei_hash(ziel)
    eb.ereignisse_schreiben(str(ziel), _bauen(anlaesse, [_zug(),
                                                         _zug(fileid=KENNUNG_ZWEI)]))
    assert _datei_hash(ziel) == vorher


def test_schreiben_aus_dem_plan_zweimal_ist_byte_identisch(tmp_path):
    ziel = tmp_path / "ereignisse.jsonl"
    plan = _plan([_anlass()], [_zug()])
    eb.ereignisse_schreiben(str(ziel), eb.ereignisse_bauen(plan, stand=STAND))
    vorher = _datei_hash(ziel)
    eb.ereignisse_schreiben(str(ziel), eb.ereignisse_bauen(plan, stand=STAND))
    assert _datei_hash(ziel) == vorher


def test_schreiben_im_repo_wird_mit_valueerror_verweigert():
    ziel = REPO / "ereignisse.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_schreiben(str(ziel), _bauen([_anlass()], [_zug()]))
    assert "IM Repo" in str(fehler.value)
    assert "NICHTS geschrieben" in str(fehler.value)
    assert not ziel.exists()


def test_schreiben_in_den_werkzeugordner_wird_verweigert():
    ziel = WERKZEUG.parent / "ereignisse.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError):
        eb.ereignisse_schreiben(str(ziel), {})
    assert not ziel.exists()


def test_schreiben_ohne_daten_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_schreiben(str(tmp_path / "e.jsonl"), None)
    assert "Ereignis-Knoten" in str(fehler.value)
    assert not (tmp_path / "e.jsonl").exists()


def test_schreiben_ohne_knotenliste_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_schreiben(str(tmp_path / "e.jsonl"), {"art": "ereignisse"})
    assert "ereignisse" in str(fehler.value)


def test_schreiben_ohne_zielpfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        eb.ereignisse_schreiben("", {})
    assert "Kein Zielpfad" in str(fehler.value)


def test_schreiben_scheitert_nicht_zerstoerend(tmp_path):
    ziel = tmp_path / "ereignisse.jsonl"
    eb.ereignisse_schreiben(str(ziel), _bauen([_anlass()], [_zug()]))
    vorher = _datei_hash(ziel)
    with pytest.raises(ValueError):
        eb.ereignisse_schreiben(str(ziel), {"ereignisse": ["kein Knoten"]})
    assert _datei_hash(ziel) == vorher
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_legt_den_zielordner_an(tmp_path):
    ziel = tmp_path / "neu" / "tiefer" / "ereignisse.jsonl"
    eb.ereignisse_schreiben(str(ziel), _bauen([_anlass()], [_zug()]))
    assert ziel.is_file()


# ── Klartext (zahlen_text) ───────────────────────────────────────────────

def test_zahlen_text_nennt_alle_zahlen():
    daten = _bauen([_anlass()], [_zug(), _zug(fileid=None)])
    text = eb.zahlen_text(daten)
    for wort in ("Anlaesse: 1", "Dateien: 1", "Zuege: 2", "ohne Anlass: 0",
                 "ohne Kennung: 1", "ohne Datum: 0", "ohne Thema: 0",
                 "Kollisionen: 0", "Events wiederverwendet: 0",
                 "Kategorien: 1", "Jahre: 1", "Themen: 1"):
        assert wort in text, wort


def test_zahlen_text_nennt_stand_und_plan_stand():
    text = eb.zahlen_text(_bauen([_anlass()], [_zug()]))
    assert STAND in text
    assert PLAN_STAND in text


def test_zahlen_text_spricht_nicht_von_loeschen():
    text = eb.zahlen_text(_bauen([_anlass()], [_zug()]))
    for verboten in ("loesch", "Loesch", "geloescht", "delete", "entfernt"):
        assert verboten not in text


def test_zahlen_text_haelt_fehlende_felder_aus():
    text = eb.zahlen_text({})
    assert "Anlaesse: 0" in text
    assert "unbekannt" in text


def test_zahlen_text_ist_mehrzeilig_und_deutsch():
    text = eb.zahlen_text(_bauen([_anlass()], [_zug()]))
    assert len(text.splitlines()) >= 5
    assert "ohne Personen" in text


# ── Kommandozeile ────────────────────────────────────────────────────────

def test_haupt_trockenlauf_schreibt_nichts(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "ereignisse.jsonl"
    assert eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel)]) == 0
    assert not ziel.exists()
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "wurde NICHT geschrieben" in ausgabe


def test_haupt_trockenlauf_zeigt_die_zahlen(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    eb.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "e.jsonl")])
    ausgabe = capsys.readouterr().out
    assert "Sortierplan:" in ausgabe
    assert "Anlaesse: 1" in ausgabe
    assert "Dateien: 1" in ausgabe


def test_haupt_trockenlauf_zeigt_die_knoten_als_jsonl(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    eb.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "e.jsonl")])
    zeilen = [z for z in capsys.readouterr().out.splitlines()
              if z.startswith("{")]
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["kennung"] == "E-" + ANLASS


def test_haupt_expliziter_trockenlauf_schlaegt_schreiben(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "ereignisse.jsonl"
    assert eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--trocken", "--schreiben"]) == 0
    assert not ziel.exists()
    assert "TROCKENLAUF" in capsys.readouterr().out


def test_haupt_limit_zeigt_nur_die_ersten_knoten(tmp_path, capsys):
    anlaesse = [_anlass(f"2014-03-{tag:02d}_Beispiel-01", datum=f"2014-03-{tag:02d}")
                for tag in (10, 11, 12)]
    plan = _plan_datei(tmp_path, _plan(anlaesse, [_zug()]))
    eb.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "e.jsonl"),
              "--limit", "1"])
    ausgabe = capsys.readouterr().out
    assert len([z for z in ausgabe.splitlines() if z.startswith("{")]) == 1
    assert "2 weitere Knoten" in ausgabe


def test_haupt_limit_null_zeigt_keinen_knoten(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    assert eb.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "e.jsonl"),
                     "--limit", "0"]) == 0
    ausgabe = capsys.readouterr().out
    assert not [z for z in ausgabe.splitlines() if z.startswith("{")]


def test_haupt_negatives_limit_ergibt_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    assert eb.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "e.jsonl"),
                     "--limit", "-1"]) == 2
    assert "Fehler" in capsys.readouterr().err
    assert not (tmp_path / "ereignisse.jsonl").exists()


def test_haupt_mit_schreiben_legt_jsonl_an(tmp_path):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "ereignisse.jsonl"
    assert eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--schreiben"]) == 0
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["anlass_id"] == ANLASS


def test_haupt_schreiben_ist_byte_gleich_wiederholbar(tmp_path):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "ereignisse.jsonl"
    eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel), "--schreiben"])
    vorher = _datei_hash(ziel)
    eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel), "--schreiben"])
    assert _datei_hash(ziel) == vorher


def test_haupt_repo_ziel_ergibt_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = REPO / "ereignisse.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    assert eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--schreiben"]) == 2
    fehler = capsys.readouterr().err
    assert "IM Repo" in fehler
    assert "Fehler" in fehler
    assert not ziel.exists()


def test_haupt_repo_ziel_ergibt_auch_im_trockenlauf_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    assert eb.haupt(["--plan", str(plan),
                     "--ausgabe", str(REPO / "docs" / "e.jsonl")]) == 2
    assert "IM Repo" in capsys.readouterr().err


def test_haupt_fehlender_plan_ergibt_exit_2(tmp_path, capsys):
    assert eb.haupt(["--plan", str(tmp_path / "gibtsnicht.json"),
                     "--ausgabe", str(tmp_path / "e.jsonl")]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_haupt_kaputter_plan_ergibt_exit_2(tmp_path, capsys):
    pfad = tmp_path / "krumm.json"
    pfad.write_text("kein json", encoding="utf-8")
    assert eb.haupt(["--plan", str(pfad), "--ausgabe",
                     str(tmp_path / "e.jsonl")]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_haupt_plan_ohne_anlaesse_ergibt_exit_2(tmp_path, capsys):
    pfad = tmp_path / "leer.json"
    pfad.write_text("{}", encoding="utf-8")
    assert eb.haupt(["--plan", str(pfad), "--ausgabe",
                     str(tmp_path / "e.jsonl")]) == 2
    assert "anlaesse" in capsys.readouterr().err


# ── Quelltext: keine Netz-, Bild- oder Loeschfunktion ─────────────────────

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
    erlaubt = {"argparse", "datetime", "json", "os", "re", "sys", "__future__"}
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
    namen = _namen_im_quelltext()
    assert namen & verboten == set(), f"Netz-/LLM-Name: {namen & verboten}"


def test_quelltext_ohne_url_und_ohne_pcloud_schluessel():
    quelle = _quelle()
    for verboten in ("http://", "https://", "pcloud", "openai", "import requests",
                     "import httpx", "urllib.request", "urlopen(",
                     "import subprocess", "sk-", "token"):
        assert verboten not in quelle, f"Netz-/Schluesselspur: {verboten}"


def test_quelltext_ohne_loesch_und_systemaufrufe():
    verboten = {"deletefile", "deletefolder", "rmtree", "removefile",
                "removefolder", "renametree", "system", "popen", "unlink",
                "rmdir", "truncate"}
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


def test_quelltext_hat_keine_loeschfunktion():
    quelle = _quelle()
    for verboten in ("def loeschen", "def delete", "def entfernen", "shutil",
                     "rmdir", "rm("):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_oeffnet_keine_bilder():
    quelle = _quelle()
    for verboten in ("PIL", "cv2", "imageio", ".jpg", ".jpeg", ".png", ".heic",
                     ".webp", '"rb"', "'rb'"):
        assert verboten not in quelle, f"Bildzugriff im Quelltext: {verboten}"


def test_quelltext_schreibt_atomar():
    quelle = _quelle()
    assert "os.replace(" in quelle
    assert ".tmp" in quelle


def test_quelltext_prueft_das_repo_ziel():
    quelle = _quelle()
    assert "_pruefe_ziel_ausserhalb_repo" in quelle
    assert "IM Repo" in quelle


def test_quelltext_liest_den_plan_nur_lesend():
    quelle = _quelle()
    assert 'open(pfad, encoding="utf-8")' in quelle
    assert '"r"' not in quelle


def test_quelltext_setzt_nur_einen_zeitstempel():
    # ``datetime.now()`` darf nur ueber den injizierbaren ``stand`` laufen.
    assert _quelle().count("datetime.datetime.now(") == 1


def test_quelltext_haelt_die_invarianten_als_zusicherung():
    quelle = _quelle()
    assert "zahlen[\"anlaesse\"] == len(ereignisse)" in quelle
    assert "zahlen[\"dateien\"] == sum(" in quelle
    assert "zahlen[\"zuege\"]" in quelle


# ── Eingefrorene Funktionsnamen ──────────────────────────────────────────

def test_eingefrorene_funktionsnamen_sind_da():
    for name in ("plan_laden", "ereignisse_bauen", "ereignisse_schreiben",
                 "knoten_zeile", "zahlen_text", "_pruefe_ziel_ausserhalb_repo",
                 "haupt"):
        assert callable(getattr(eb, name)), name
    assert callable(eb.haupt)


def test_schreiben_laeuft_nur_ueber_ereignisse_schreiben(tmp_path):
    """Ohne die Schreibfunktion entsteht keine Datei — der Trockenlauf ist Standard."""
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "ereignisse.jsonl"
    eb.haupt(["--plan", str(plan), "--ausgabe", str(ziel)])
    assert not ziel.exists()
    assert not (tmp_path / "ereignisse.jsonl.tmp").exists()
