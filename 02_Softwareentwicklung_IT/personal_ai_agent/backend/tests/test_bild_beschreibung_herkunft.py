"""Tests G2: Vorrang und Herkunft der Bildbeschreibung (02.11.2026).

Plan: ``.hermes/plans/2026-11-02_geschichte-sprachmodell.md``, Schritt G2
(Punkte 2, 2b, 3, Teil von 5/6; Prüfkriterien (d), (e) Übernehmen, (g)).

Alles offline: erfundene Beschreibungsdateien in ``tmp_path``, Pfade über
``ERZAEHL_*_PFAD``; kein echter Ordner ``~/foto_sortierung``, kein Netz.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bild_beschreibung_herkunft.py -q
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import erzaehlen as erzaehlen_router  # noqa: E402
from app.services import erzaehl_service as es  # noqa: E402


@pytest.fixture(autouse=True)
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "ereignisse.jsonl"))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    monkeypatch.delenv("ERZAEHL_ORDNER_EREIGNISSE_PFAD", raising=False)
    es._BILDINFO_SPEICHER.clear()
    return tmp_path


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(erzaehlen_router.router)
    return TestClient(app)


def _jsonl(pfad, zeilen):
    with open(pfad, "w", encoding="utf-8") as datei:
        for z in zeilen:
            datei.write((z if isinstance(z, str) else json.dumps(z, ensure_ascii=False)) + "\n")


def _zeilen(pfad):
    with open(pfad, "r", encoding="utf-8") as datei:
        return [json.loads(z) for z in datei if z.strip()]


# ── (d) Vorrang: Hand-Text schlägt *_reich ───────────────────────────────────

def test_d_hand_text_schlaegt_reich(umgebung):
    _jsonl(umgebung / "bild_beschreibungen_reich.jsonl",
           [{"fileid": 1, "beschreibung_reich": "Maschinenbeschreibung eins"}])
    assert es.beschreibung_holen(1) == "Maschinenbeschreibung eins"
    assert es.beschreibung_speichern(1, "Mein eigener Text")["ok"] is True
    assert es.beschreibung_holen(1) == "Mein eigener Text"
    assert es._beschreibungen_gesamt_lesen()[1] == "Mein eigener Text"


def test_d_hand_text_schlaegt_alle_reich_dateien_und_sqlite(umgebung):
    for name in ("bild_beschreibungen_reich.jsonl", "bild_beschreibungen_papa_reich.jsonl",
                 "bild_beschreibungen_rest_reich.jsonl", "bild_beschreibungen_altbestand_reich.jsonl"):
        _jsonl(umgebung / name, [{"fileid": 2, "beschreibung_reich": f"aus {name}"}])
    db = umgebung / "life_archive.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE photos (fileid INTEGER PRIMARY KEY, beschreibung TEXT, beschreibung_reich TEXT)")
        conn.execute("INSERT INTO photos VALUES (2, 'Basis', 'Reich aus der Datenbank')")
    # Handzeile direkt anhängen (SQLite behält absichtlich den alten Stand)
    _jsonl(umgebung / "bild_beschreibungen.jsonl",
           [{"fileid": 2, "beschreibung": "Handtext", "quelle": "hand"}])
    assert es.beschreibung_holen(2) == "Handtext"
    assert es._beschreibungen_mit_herkunft()[2] == ("Handtext", "hand")


def test_d_neueste_app_zeile_gewinnt(umgebung):
    es.beschreibung_speichern(3, "Hand zuerst")
    es.beschreibung_uebernehmen_ki(3, "KI danach")
    assert es._beschreibungen_mit_herkunft()[3] == ("KI danach", "einzel_ki")
    es.beschreibung_speichern(3, "Hand zuletzt")
    assert es._beschreibungen_mit_herkunft()[3] == ("Hand zuletzt", "hand")


def test_d_werkzeugzeile_nach_app_zeile_ueberschreibt_nicht(umgebung):
    """App-Zeilen werden zuletzt angewendet — auch gegen eine spätere Werkzeugzeile derselben Datei."""
    es.beschreibung_speichern(4, "Meine Fassung")
    with open(es.beschreibungen_pfad(), "a", encoding="utf-8") as datei:
        datei.write(json.dumps({"fileid": 4, "beschreibung": "Neuer Werkzeuglauf"}) + "\n")
    assert es.beschreibung_holen(4) == "Meine Fassung"


def test_d_leerer_hand_text_loescht_nicht(umgebung):
    _jsonl(umgebung / "bild_beschreibungen_reich.jsonl",
           [{"fileid": 5, "beschreibung_reich": "Bleibt stehen"}])
    es.beschreibung_speichern(5, "   ")
    assert es.beschreibung_holen(5) == "Bleibt stehen"
    assert es._beschreibungen_mit_herkunft()[5] == ("Bleibt stehen", "ki")


# ── (2b) Herkunft ────────────────────────────────────────────────────────────

def test_herkunft_ki_aus_allen_maschinenquellen(umgebung):
    _jsonl(umgebung / "bild_beschreibungen.jsonl", [{"fileid": 10, "beschreibung": "Werkzeugzeile"}])
    _jsonl(umgebung / "bild_beschreibungen_reich.jsonl", [{"fileid": 11, "beschreibung_reich": "Reich"}])
    db = umgebung / "life_archive.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE photos (fileid INTEGER PRIMARY KEY, beschreibung TEXT, beschreibung_reich TEXT)")
        conn.execute("INSERT INTO photos VALUES (12, 'Nur Basis', NULL)")
    herkunft = es._beschreibungen_mit_herkunft()
    assert herkunft[10] == ("Werkzeugzeile", "ki")
    assert herkunft[11] == ("Reich", "ki")
    assert herkunft[12] == ("Nur Basis", "ki")


def test_herkunft_hand_trotz_sqlite_kopie(umgebung):
    """beschreibung_speichern schreibt den Text auch in SQLite — die Herkunft bleibt „hand“."""
    db = umgebung / "life_archive.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE photos (fileid INTEGER PRIMARY KEY, beschreibung TEXT, beschreibung_reich TEXT)")
    es.beschreibung_speichern(13, "Von Hand")
    assert es._beschreibungen_mit_herkunft()[13] == ("Von Hand", "hand")


def test_gesamt_lesen_bleibt_duenne_huelle(umgebung):
    es.beschreibung_speichern(14, "Hand")
    _jsonl(umgebung / "bild_beschreibungen_reich.jsonl", [{"fileid": 15, "beschreibung_reich": "Reich"}])
    gesamt = es._beschreibungen_gesamt_lesen()
    assert gesamt[14] == "Hand" and gesamt[15] == "Reich"
    assert all(isinstance(t, str) for t in gesamt.values())


def test_speichern_schreibt_quelle_hand_und_uebernehmen_einzel_ki(umgebung):
    es.beschreibung_speichern(16, "Hand")
    es.beschreibung_uebernehmen_ki(16, "Vorschlag")
    zeilen = _zeilen(es.beschreibungen_pfad())
    assert [z["quelle"] for z in zeilen] == ["hand", "einzel_ki"]
    assert [z["fileid"] for z in zeilen] == [16, 16]


# ── (g) GET /bild-beschreibung: gefunden + quelle ───────────────────────────

def test_g_get_nicht_gefunden(client):
    r = client.get("/api/erzaehlen/bild-beschreibung?fileid=777")
    j = r.json()
    assert r.status_code == 200
    assert j["ok"] is True and j["beschreibung"] == ""
    assert j["gefunden"] is False and j["quelle"] is None


def test_g_get_quellen_ki_hand_einzel_ki(client, umgebung):
    _jsonl(umgebung / "bild_beschreibungen_reich.jsonl", [{"fileid": 20, "beschreibung_reich": "Reiche KI"}])
    j = client.get("/api/erzaehlen/bild-beschreibung?fileid=20").json()
    assert (j["gefunden"], j["quelle"], j["beschreibung"]) == (True, "ki", "Reiche KI")
    assert isinstance(j["beschreibung"], str)

    client.post("/api/erzaehlen/bild-beschreibung", json={"fileid": "20", "beschreibung": "Meine Worte"})
    j = client.get("/api/erzaehlen/bild-beschreibung?fileid=20").json()
    assert (j["gefunden"], j["quelle"], j["beschreibung"]) == (True, "hand", "Meine Worte")

    r = client.post("/api/erzaehlen/bild-beschreibung/uebernehmen",
                    json={"fileid": "20", "beschreibung": "Übernommener Vorschlag"})
    assert r.status_code == 200 and r.json()["ok"] is True
    j = client.get("/api/erzaehlen/bild-beschreibung?fileid=20").json()
    assert (j["gefunden"], j["quelle"], j["beschreibung"]) == (True, "einzel_ki", "Übernommener Vorschlag")


def test_g_get_ungueltige_fileid_wirft_nicht(client):
    j = client.get("/api/erzaehlen/bild-beschreibung?fileid=abc").json()
    assert j["gefunden"] is False and j["quelle"] is None and j["beschreibung"] == ""


# ── (e) Übernehmen: genau eine Zeile einzel_ki ──────────────────────────────

def test_e_uebernehmen_speichert_genau_eine_zeile(client):
    r = client.post("/api/erzaehlen/bild-beschreibung/uebernehmen",
                    json={"fileid": "30", "beschreibung": "Zwei Personen am Steg."})
    assert r.json() == {"ok": True, "fileid": 30, "beschreibung": "Zwei Personen am Steg."}
    zeilen = _zeilen(es.beschreibungen_pfad())
    assert len(zeilen) == 1
    assert zeilen[0]["quelle"] == "einzel_ki" and zeilen[0]["fileid"] == 30
    assert zeilen[0]["beschreibung"] == "Zwei Personen am Steg."


def test_e_uebernehmen_leer_oder_ungueltig_speichert_nichts(client):
    j = client.post("/api/erzaehlen/bild-beschreibung/uebernehmen",
                    json={"fileid": "31", "beschreibung": "   "}).json()
    assert j["ok"] is False and j.get("fehler")
    j = client.post("/api/erzaehlen/bild-beschreibung/uebernehmen",
                    json={"fileid": "abc", "beschreibung": "Text"}).json()
    assert j["ok"] is False
    assert not os.path.exists(es.beschreibungen_pfad())


def test_alter_post_schreibt_quelle_hand(client):
    client.post("/api/erzaehlen/bild-beschreibung", json={"fileid": "32", "beschreibung": "Alt-POST"})
    assert _zeilen(es.beschreibungen_pfad())[0]["quelle"] == "hand"


# ── Punkt 5: ki-geschichte meldet beschreibung_gefunden ─────────────────────

def test_ki_geschichte_meldet_beschreibung_gefunden(umgebung):
    ohne = es.ki_geschichte_generieren(fileid="40", personen=[])
    assert ohne["ok"] is True and ohne["daten"]["beschreibung_gefunden"] is False

    es.beschreibung_speichern(40, "Ein Boot auf dem See")
    mit = es.ki_geschichte_generieren(fileid="40", personen=[])
    assert mit["daten"]["beschreibung_gefunden"] is True

    uebergeben = es.ki_geschichte_generieren(fileid="41", personen=[], beschreibung="Direkt übergeben")
    assert uebergeben["daten"]["beschreibung_gefunden"] is True


def test_ki_geschichte_endpunkt_reicht_beschreibung_gefunden_durch(client):
    j = client.post("/api/erzaehlen/ki-geschichte", json={"fileid": "42", "personen": []}).json()
    assert j["daten"]["beschreibung_gefunden"] is False
