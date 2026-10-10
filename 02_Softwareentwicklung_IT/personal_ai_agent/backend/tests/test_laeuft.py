"""Tests: Statusleiste — was laeuft gerade? (GET /api/laeuft, 10.10.2026).

Deckt die drei Quellen ab (app/services/laufende_arbeiten.py):
- leerer Zustand -> "keine Hintergrundarbeit", keine Fehler
- eine laufende Arbeit (Protokolldatei frisch beschrieben) -> Eintrag mit
  Name, Startzeit, Zustand, letzter Zeile und erkanntem Fortschritt
- fehlende Ordner/Dateien duerfen nicht stoeren
- laufender Auftrag aus dem Buch (Track C, Status 'laeuft')
- angemeldete Backend-Arbeit + asyncio-Task (meldet sich beim Ende selbst ab)

Offline: alles in tmp_path, kein Netz, kein Geraet, kein echtes Buch.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_laeuft.py -q
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import laeuft as laeuft_router  # noqa: E402
from app.services import laufende_arbeiten as la  # noqa: E402
from app.services.auftrag_service import auftrag_service  # noqa: E402


@pytest.fixture(autouse=True)
def _sauber(tmp_path, monkeypatch):
    """Isoliert: eigene Protokoll-Basis, eigenes Buch, leeres Register."""
    monkeypatch.setenv("LAEUFT_LOG_BASIS", str(tmp_path / "basis"))
    monkeypatch.setattr(auftrag_service, "_pfad", tmp_path / "auftraege.json")
    with la._REGISTER_SPERRE:
        la._REGISTER.clear()
    yield
    with la._REGISTER_SPERRE:
        la._REGISTER.clear()


def _client():
    app = FastAPI()
    app.include_router(laeuft_router.router)
    return TestClient(app)


def _hole():
    antwort = _client().get("/api/laeuft")
    assert antwort.status_code == 200
    return antwort.json()


def _protokoll(tmp_path, ordner, name, inhalt, alter_sekunden=0):
    verzeichnis = tmp_path / "basis" / ordner
    verzeichnis.mkdir(parents=True, exist_ok=True)
    datei = verzeichnis / name
    datei.write_text(inhalt, encoding="utf-8")
    if alter_sekunden:
        alt = time.time() - alter_sekunden
        os.utime(datei, (alt, alt))
    return datei


# ── Leer ────────────────────────────────────────────────────────────────────

def test_leer_meldet_keine_hintergrundarbeit():
    daten = _hole()
    assert daten["ok"] is True
    assert daten["keine"] is True and daten["anzahl"] == 0
    assert daten["arbeiten"] == []
    assert daten["zeit"]  # Serverzeit fuer die Anzeige


def test_fehlende_ordner_stoeren_nicht():
    """Die Basis existiert gar nicht (frisches Geraet) — kein Fehler."""
    assert _hole()["anzahl"] == 0


def test_leere_protokoll_datei_ist_leer_statt_laufend(tmp_path):
    _protokoll(tmp_path, "hermes_diag", "start.log", "")
    eintrag = _hole()["arbeiten"][0]
    assert eintrag["zustand"] == "leer"
    assert eintrag["letzte_zeile"] == "" and eintrag["fortschritt"] == ""


# ── Eine laufende Arbeit ────────────────────────────────────────────────────

def test_frisches_protokoll_ist_eine_laufende_arbeit(tmp_path):
    _protokoll(
        tmp_path, "hermes_diag", "bildanalyse.log",
        "Starte Lauf\nBild 1234 von 17580 erledigt\n",
    )
    daten = _hole()
    assert daten["anzahl"] == 1 and daten["keine"] is False
    eintrag = daten["arbeiten"][0]
    assert eintrag["name"] == "Protokoll bildanalyse.log"
    assert eintrag["art"] == "protokoll"
    assert eintrag["zustand"] == "laeuft"          # mtime frisch
    assert eintrag["letzte_zeile"] == "Bild 1234 von 17580 erledigt"
    assert eintrag["fortschritt"] == "1234 von 17580"
    assert isinstance(eintrag["dauer_sekunden"], int)
    assert eintrag["dauer_sekunden"] >= 0
    assert eintrag["seit"]                          # ISO-Startzeit der Datei


def test_altes_protokoll_steht_statt_laufend(tmp_path):
    _protokoll(tmp_path, "hermes_diag", "nachtlauf.log", "fertig 100 %\n",
               alter_sekunden=3600)
    eintrag = _hole()["arbeiten"][0]
    assert eintrag["zustand"] == "steht"
    assert eintrag["fortschritt"] == "100 %"
    assert eintrag["dauer_sekunden"] >= 3600


def test_sicherungs_ordner_wird_mitgelesen(tmp_path):
    _protokoll(tmp_path, "termux-sicherung", "sicherung.log",
               "Archive geschrieben 7 von 9\n")
    eintrag = _hole()["arbeiten"][0]
    assert eintrag["name"] == "Protokoll sicherung.log"
    assert eintrag["fortschritt"] == "7 von 9"


def test_laufende_arbeiten_stehen_vor_stehenden(tmp_path):
    _protokoll(tmp_path, "hermes_diag", "alt.log", "alt\n", alter_sekunden=3600)
    la.merke_start("Werkzeug fotos_mit_person (Person „Anna“)", art="werkzeug")
    daten = _hole()
    assert [a["zustand"] for a in daten["arbeiten"]] == ["laeuft", "steht"]


# ── Buch (Track C) ──────────────────────────────────────────────────────────

def test_laufender_auftrag_aus_dem_buch(tmp_path):
    eintrag = auftrag_service.anlegen_als_arbeitender(
        "Beschreibe alle Bilder von Papa", hinweis="Test", kategorie="bilder",
    )
    auftrag_service.statusmeldung_hinzufuegen(
        eintrag["id"], "[2026-10-10T10:00:00+02:00] Schritt 3 von 10",
    )
    daten = _hole()
    assert daten["anzahl"] == 1
    arbeit = daten["arbeiten"][0]
    assert arbeit["art"] == "hermes" and arbeit["zustand"] == "laeuft"
    assert "Beschreibe alle Bilder von Papa" in arbeit["name"]
    assert arbeit["letzte_zeile"] == "Schritt 3 von 10"   # [ISO]-Praefix weg
    assert arbeit["fortschritt"] == "3 von 10"
    assert arbeit["seit"]


def test_offene_auftraege_zaehlen_nicht_als_laufend():
    """'offen' ist eine Warteschlange, kein laufender Prozess."""
    auftrag_service.anlegen("Warte auf Abholung")
    assert _hole()["anzahl"] == 0


# ── Register / asyncio ──────────────────────────────────────────────────────

def test_angemeldete_backend_arbeit_erscheint_und_verschwindet():
    kennung = la.merke_start("Bildanalyse Papas Fotos")
    daten = _hole()
    namen = [a["name"] for a in daten["arbeiten"]]
    assert "Bildanalyse Papas Fotos" in namen
    eintrag = daten["arbeiten"][0]
    assert eintrag["art"] == "arbeit" and eintrag["zustand"] == "laeuft"
    la.beende(kennung)
    assert _hole()["anzahl"] == 0


def test_asyncio_task_meldet_sich_beim_ende_selbst_ab():
    async def langer_lauf():
        await asyncio.sleep(30)

    async def pruefen():
        task = asyncio.create_task(langer_lauf())
        la.merke_task(task, "Asyncio-Testlauf")
        assert "Asyncio-Testlauf" in [e["name"] for e in la.backend_arbeiten()]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0)  # done-Callback ausfuehren lassen
        assert "Asyncio-Testlauf" not in [e["name"] for e in la.backend_arbeiten()]

    asyncio.run(pruefen())


# ── Bausteine ───────────────────────────────────────────────────────────────

def test_fortschritt_erkennung():
    assert la.fortschritt_aus_text("Bild 1234 von 17580 erledigt") == "1234 von 17580"
    assert la.fortschritt_aus_text("Zeile 3/10") == "3 von 10"
    assert la.fortschritt_aus_text("kosten 7,5 % erreicht") == "7,5 %"
    assert la.fortschritt_aus_text("keine Zahlen hier") == ""


def test_letzte_zeile_bei_fehlender_datei_ist_leer(tmp_path):
    assert la.letzte_zeile(str(tmp_path / "gibtsnicht.log")) == ""


def test_route_im_backend_mit_schluessel_geschuetzt():
    quelle = open(os.path.join(BACKEND, "app", "main.py"), encoding="utf-8").read()
    assert ("app.include_router(laeuft.router, "
            "dependencies=[Depends(auth.require_api_key)])") in quelle
