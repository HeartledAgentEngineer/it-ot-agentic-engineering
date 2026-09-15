"""Tests: Start-Aufraeumung verwaister 'laeuft'-Auftraege im Buch.

Fund 2026-09-15: 45 Buch-Eintraege standen dauerhaft auf 'laeuft', obwohl kein
Hermes-Lauf und keine tmux-Session existierte. Ursache: Der Worker eines
Auftrags lebt IM Serverprozess; wird der Server neu gestartet (Widget, Skript)
oder bricht der 900s-Deckel ab, kann der Thread den Status nie finalisieren.
Beim Start kann kein Worker laufen -> solche Eintraege sind eindeutig verwaist
und werden jetzt automatisch geschlossen (app/main.py -> lifespan).
"""
import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.auftrag_service import auftrag_service  # noqa: E402


def _buch(tmp_path, eintraege):
    p = tmp_path / "auftraege.json"
    p.write_text(json.dumps(eintraege, ensure_ascii=False), encoding="utf-8")
    return p


def test_verwaiste_laeuft_werden_geschlossen(tmp_path, monkeypatch):
    p = _buch(tmp_path, [
        {"id": "aaa", "status": "laeuft", "ergebnis": "", "status_meldungen": ["x"]},
        {"id": "bbb", "status": "fertig", "ergebnis": "ok"},
        {"id": "ccc", "status": "offen"},
        {"id": "ddd", "status": "fehler", "ergebnis": "frueher schon"},
    ])
    monkeypatch.setattr(auftrag_service, "_pfad", p)

    assert auftrag_service.verwaiste_auftraege_schliessen() == 1

    daten = json.loads(p.read_text(encoding="utf-8"))
    nach = {e["id"]: e for e in daten}
    assert nach["aaa"]["status"] == "fehler"
    assert "verwaist" in nach["aaa"]["ergebnis"]
    assert nach["aaa"].get("beendet")
    # Bestehende Zustaende bleiben unangetastet.
    assert nach["bbb"]["status"] == "fertig" and nach["bbb"]["ergebnis"] == "ok"
    assert nach["ccc"]["status"] == "offen"
    assert nach["ddd"]["ergebnis"] == "frueher schon"
    # Die Gedanken-Spur bleibt erhalten (nur der Status wird geschlossen).
    assert nach["aaa"]["status_meldungen"] == ["x"]


def test_ohne_verwaiste_keine_aenderung(tmp_path, monkeypatch):
    p = _buch(tmp_path, [{"id": "bbb", "status": "fertig", "ergebnis": "ok"}])
    vorher = p.read_text(encoding="utf-8")
    monkeypatch.setattr(auftrag_service, "_pfad", p)

    assert auftrag_service.verwaiste_auftraege_schliessen() == 0
    assert p.read_text(encoding="utf-8") == vorher


def test_leeres_buch_ist_harmlos(tmp_path, monkeypatch):
    p = tmp_path / "gibtsnicht.json"
    monkeypatch.setattr(auftrag_service, "_pfad", p)
    assert auftrag_service.verwaiste_auftraege_schliessen() == 0


def test_verwaister_auftrag_meldet_sich_ehrlich_im_chat(tmp_path, monkeypatch):
    """Wunsch Sebastian 2026-09-15: nie still abbrechen.

    Bisher wurde beim Serverstart nur das Buch bereinigt — im Coding-Chat
    endete der Verlauf nach der letzten Gedankenblase wortlos, und der Nutzer
    wartete auf ein Ergebnis, das nie mehr kommt. Jetzt schreibt die
    Aufraeumung in GENAU das verknuepfte Gespraech eine ehrliche Meldung.
    """
    p = _buch(tmp_path, [
        {"id": "aaa", "status": "laeuft", "aufgabe": "Baue Knopf X ein",
         "conversation_id": "conv_code", "ergebnis": ""},
        {"id": "bbb", "status": "laeuft", "aufgabe": "Ohne Chat-Verknuepfung",
         "ergebnis": ""},
    ])
    monkeypatch.setattr(auftrag_service, "_pfad", p)

    gemeldet = []
    monkeypatch.setattr(
        auftrag_service, "_in_verlauf_anhaengen",
        lambda cid, role, content: gemeldet.append((cid, role, content)),
    )

    assert auftrag_service.verwaiste_auftraege_schliessen() == 2

    # Nur der VERKNUEPFTE Auftrag meldet sich — kein Fluten fremder Verlaeufe.
    assert len(gemeldet) == 1, gemeldet
    cid, role, content = gemeldet[0]
    assert cid == "conv_code"
    assert role == "assistant"
    assert "Server-Neustart" in content
    assert "Unterbrochen" in content
    assert "Baue Knopf X ein" in content          # Aufgabe ist erkennbar
    assert "erneut senden" in content             # klarer naechster Schritt
    assert "Kein Ergebnis" not in content