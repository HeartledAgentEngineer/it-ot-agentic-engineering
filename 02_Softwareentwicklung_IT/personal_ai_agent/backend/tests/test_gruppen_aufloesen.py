"""Vertragstests für „Gruppe auflösen" (To-do Punkt 14, 18.10.2026).

Sebastian: „Die Gruppen sind nicht wichtig nach der Zuordnung." → Sobald eine
Gruppe einer benannten Person zugeordnet ist, wird der **Gruppeneintrag**
aufgelöst (Stand-Liste ``aufgeloest``). Harte Vorgabe: Bilder und Zuordnungen
bleiben unangetastet, vor dem Schreiben zaehlt ein Trockenlauf, und das Ganze
ist rückholbar (``rueckgaengig`` / ``art='offen'``).
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import gruppen as gruppen_router  # noqa: E402
from app.services import gruppen_quiz as gq  # noqa: E402


def _gruppe(kennung, groesse, **extra):
    return {"kennung": kennung, "groesse": groesse, "bilder": groesse - 1,
            "videos": 1, "von": "2018-01-01", "bis": "2024-12-31",
            "beispiele": [], "zwilling_kandidaten": [], **extra}


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(json.dumps({"gruppen": [
        _gruppe("G-a", 40), _gruppe("G-b", 30), _gruppe("G-c", 20)]}), encoding="utf-8")
    yield tmp_path
    gq._CACHE.clear()


def _dateien(basis):
    """Alle Dateien der Basis mit Pruefsumme — fuer „nichts angefasst"-Belege."""
    stand = {}
    for name in sorted(os.listdir(basis)):
        pfad = basis / name
        if pfad.is_file():
            stand[name] = pfad.read_bytes()
    ordner = basis / gq.UNTERORDNER
    for name in sorted(os.listdir(ordner)):
        pfad = ordner / name
        if pfad.is_file():
            stand[gq.UNTERORDNER + "/" + name] = pfad.read_bytes()
    return stand


def _stand(basis):
    pfad = basis / gq.STAND_DATEINAME
    return json.loads(pfad.read_text(encoding="utf-8")) if pfad.is_file() else None


# Dateien, die eine Auflösung NIEMALS anfassen darf (Bilder, Gesichter, Zuordnungen).
GESCHUETZT = ("personen_bestaetigt.json", "personen_vorgaben.json",
              "personen_beispiele.json", "gesicht_zuordnung.jsonl", "personen_profile.json")


def _geschuetzte_zeilen(basis):
    zeilen = {}
    for name in GESCHUETZT:
        for pfad in (basis / name, basis / gq.UNTERORDNER / name):
            if pfad.is_file():
                zeilen[pfad.name] = pfad.read_bytes()
    return zeilen


def _neu_geaendert_weg(vorher, nachher):
    return (sorted(set(nachher) - set(vorher)), sorted(set(vorher) - set(nachher)),
            sorted(n for n in vorher if n in nachher and vorher[n] != nachher[n]))


# ── Automatisch beim Benennen ───────────────────────────────────────────────

def test_benennen_loest_die_gruppe_automatisch_auf(basis):
    r = gq.antworten("G-a", "name", "Mustermann")
    assert r["ok"] is True
    # Aus der Gruppenliste verschwunden, aber weiter als benannt gezaehlt:
    assert [g["kennung"] for g in gq.liste("aufgeloest")["gruppen"]] == ["G-a"]
    assert [g["kennung"] for g in gq.liste("benannt")["gruppen"]] == []
    s = gq.stand()
    assert (s["benannt"], s["aufgeloest"], s["offen"]) == (1, 1, 2)
    assert _stand(basis) == {"spaeter": [], "unbekannt": [], "aufgeloest": ["G-a"]}


def test_die_person_behaelt_ihre_gesichter_und_die_gruppe(basis):
    gq.antworten("G-a", "name", "Mustermann")
    personen = gq.personen()["personen"]
    assert [(p["name"], p["vorschlaege"], p["gesichter"]) for p in personen] == [
        ("Mustermann", 1, 40)]
    assert [g["kennung"] for g in personen[0]["gruppen"]] == ["G-a"]
    # Der Vorschlag ist weiterhin aufrufbar (Detailansicht der Gruppe):
    assert gq.detail("G-a")["gruppe"]["groesse"] == 40


def test_benennen_laesst_bilder_und_zuordnungen_unberuehrt(basis):
    vorher = _geschuetzte_zeilen(basis)                 # Gruppendatei + Gesichts-Zuordnung
    gq.antworten("G-a", "name", "Mustermann")
    nachher = _geschuetzte_zeilen(basis)
    assert set(nachher) - set(vorher) == {"personen_bestaetigt.json"}
    for name, inhalt in vorher.items():
        assert nachher[name] == inhalt, name            # wortgleich, nichts geloescht
    # Die Zuordnung selbst steht unveraendert in der Namen-Datei:
    assert json.loads((basis / gq.BESTAETIGT_DATEINAME).read_text(encoding="utf-8")) == {
        "bestaetigt": {"G-a": "Mustermann"}}


def test_aufloesen_fasst_nur_stand_protokoll_und_namen_an(basis):
    """Gemessen: ausser Stand-Datei, Protokoll und Namen-Datei wird nichts geschrieben."""
    vorher = _dateien(basis)
    gq.antworten("G-a", "name", "Mustermann")
    neu, weg, geaendert = _neu_geaendert_weg(vorher, _dateien(basis))
    assert weg == [] and geaendert == []
    assert neu == sorted([gq.STAND_DATEINAME, gq.PROTOKOLL_DATEINAME,
                          gq.BESTAETIGT_DATEINAME])


def test_benennen_einer_verbundenen_gruppe_loest_alle_benannten_auf(basis):
    gq.antworten("G-a", "name", "Mustermann")
    gq.antworten("G-b", "gleich", ziel="G-a")
    assert sorted(k for k in _stand(basis)["aufgeloest"]) == ["G-a", "G-b"]
    assert gq.stand()["aufgeloest"] == 2


# ── Knopf „Auflösen" (Trockenlauf, Schreiben, Idempotenz) ────────────────────

def test_trockenlauf_zaehlt_und_schreibt_nichts(basis):
    gq.antworten("G-a", "name", "Mustermann")
    gq.antworten("G-b", "name", "Zweitname")            # G-b ist ebenfalls aufgeloest
    vorher = _dateien(basis)
    r = gq.aufloesen("G-b", trocken=True)
    assert r == {"ok": True, "kennung": "G-b", "name": "Zweitname", "gesichter": 30,
                 "gruppen": 0, "schon_aufgeloest": True, "trocken": True}
    assert _dateien(basis) == vorher


def test_aufloesen_zaehlt_zuvor_und_schreibt_dann_nur_die_stand_liste(basis):
    gq.antworten("G-a", "name", "Mustermann")
    gq.antworten("G-a", "offen")                        # wieder in die Liste (Umkehrweg)
    assert _stand(basis)["aufgeloest"] == []
    vorher = _dateien(basis)
    geschuetzt = _geschuetzte_zeilen(basis)
    trocken = gq.aufloesen("G-a", trocken=True)
    assert (trocken["ok"], trocken["gesichter"], trocken["gruppen"], trocken["trocken"]) == (
        True, 40, 1, True)
    assert _dateien(basis) == vorher                    # Trockenlauf schreibt nichts

    echt = gq.aufloesen("G-a")
    assert (echt["ok"], echt["aufgeloest"], echt["trocken"]) == (True, 1, False)
    assert _stand(basis) == {"spaeter": [], "unbekannt": [], "aufgeloest": ["G-a"]}
    assert _geschuetzte_zeilen(basis) == geschuetzt     # nichts anderes angefasst


def test_zweiter_lauf_ist_idempotent(basis):
    gq.antworten("G-a", "name", "Mustermann")
    vorher = _dateien(basis)
    r = gq.aufloesen("G-a")
    assert (r["ok"], r["schon_aufgeloest"], r["gruppen"]) == (True, True, 0)
    assert _dateien(basis) == vorher


def test_aufloesen_zieht_abgeschlossene_gesichter_ab(basis):
    """Ausgeschlossene Gesichter zaehlen nicht mit (wie in der Liste)."""
    (basis / gq.VORGABEN_DATEINAME).write_text(json.dumps({
        "gleich": [], "verschieden": [], "ausgeschlossen": [
            {"kennung": "G-a", "bild_id": "1", "index": 0},
            {"kennung": "G-a", "bild_id": "2", "index": 0}]}), encoding="utf-8")
    gq._CACHE.clear()
    gq.antworten("G-a", "name", "Mustermann")
    r = gq.aufloesen("G-a", trocken=True)
    assert r["gesichter"] == 38


def test_aufloesen_nur_fuer_zugeordnete_gruppen(basis):
    vorher = _dateien(basis)
    r = gq.aufloesen("G-c")                             # noch offen: nicht erlaubt
    assert r["ok"] is False and "zugeordnete Gruppen" in r["fehler"]
    fehlt = gq.aufloesen("G-gibt-es-nicht")
    assert fehlt["ok"] is False and "nicht (mehr)" in fehlt["fehler"]
    leer = gq.aufloesen("")
    assert leer["ok"] is False and "Gruppe angeben" in leer["fehler"]
    assert _dateien(basis) == vorher                    # nichts geschrieben


# ── Rueckholbarkeit ─────────────────────────────────────────────────────────

def test_rueckgaengig_stellt_die_gruppe_wieder_in_die_liste(basis):
    gq.antworten("G-a", "name", "Mustermann")
    gq.antworten("G-a", "offen")                        # zurück in die Liste
    assert _stand(basis)["aufgeloest"] == []
    gq.aufloesen("G-a")
    assert _stand(basis)["aufgeloest"] == ["G-a"]
    r = gq.rueckgaengig()
    assert r["ok"] is True and r["zurueckgenommen"]["art"] == "aufloesen"
    assert _stand(basis)["aufgeloest"] == []
    gq.rueckgaengig()                                   # das „offen" selbst
    assert _stand(basis)["aufgeloest"] == ["G-a"]
    gq.rueckgaengig()                                   # das Benennen selbst
    assert _stand(basis) == {"spaeter": [], "unbekannt": [], "aufgeloest": []}
    assert [g["kennung"] for g in gq.liste("offen")["gruppen"]] == ["G-a", "G-b", "G-c"]


def test_benennen_und_zuruecknehmen_laesst_die_reihenfolge_heil(basis):
    gq.antworten("G-a", "name", "Mustermann")
    gq.antworten("G-b", "name", "Zweitname")
    assert _stand(basis)["aufgeloest"] == ["G-a", "G-b"]
    gq.rueckgaengig()
    assert _stand(basis)["aufgeloest"] == ["G-a"]


def test_wieder_in_die_liste_und_zurueck(basis):
    """``art='offen'" ist der Umkehrweg einer aufgeloesten Gruppe."""
    gq.antworten("G-a", "name", "Mustermann")
    assert gq.antworten("G-a", "offen")["ok"] is True
    assert [g["kennung"] for g in gq.liste("benannt")["gruppen"]] == ["G-a"]
    assert gq.liste("aufgeloest")["gruppen"] == []
    assert gq.stand()["aufgeloest"] == 0
    # Eine nicht aufgeloeste, benannte Gruppe laesst sich weiterhin nicht „offen" setzen.
    r = gq.antworten("G-a", "offen")
    assert r["ok"] is False and "nicht zurück zu Offen" in r["fehler"]


# ── Routen ─────────────────────────────────────────────────────────────────

def test_routen_aufloesen_und_liste_status(basis):
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    c.post("/api/gruppen/antwort", json={"kennung": "G-a", "art": "name", "name": "Mustermann"})

    liste = c.get("/api/gruppen/liste", params={"status": "aufgeloest"}).json()
    assert liste["ok"] is True and [g["kennung"] for g in liste["gruppen"]] == ["G-a"]
    assert liste["gruppen"][0]["name"] == "Mustermann"

    trocken = c.post("/api/gruppen/aufloesen", json={"kennung": "G-a", "trocken": True}).json()
    assert (trocken["ok"], trocken["gesichter"], trocken["schon_aufgeloest"]) == (True, 40, True)
    assert c.get("/api/gruppen/stand").json()["aufgeloest"] == 1

    # Ohne Namen bleibt die Kennung eine ehrliche Fehlermeldung (nie ein Wurf).
    assert c.post("/api/gruppen/aufloesen", json={"kennung": "G-c"}).json() == {
        "ok": False, "fehler": "Nur einer Person zugeordnete Gruppen lassen sich auflösen."}
    assert c.get("/api/gruppen/liste", params={"status": "quatsch"}).status_code == 422


def test_alte_stand_datei_ohne_aufgeloest_bleibt_lesbar(basis):
    """Am Handy liegt noch die alte Fassung mit zwei Listen — sie muss weiter laufen."""
    (basis / gq.STAND_DATEINAME).write_text(
        json.dumps({"spaeter": ["G-b"], "unbekannt": ["G-c"]}), encoding="utf-8")
    gq._CACHE.clear()
    assert gq.stand()["aufgeloest"] == 0
    assert gq.liste("aufgeloest")["gruppen"] == []
    assert [g["kennung"] for g in gq.liste("spaeter")["gruppen"]] == ["G-b"]
    gq.antworten("G-a", "name", "Mustermann")
    assert _stand(basis) == {"spaeter": ["G-b"], "unbekannt": ["G-c"], "aufgeloest": ["G-a"]}
