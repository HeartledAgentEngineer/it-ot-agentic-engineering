"""Tests für den extrahierten Verlauf-Service (Refactoring chat.py)."""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import chat_verlauf  # noqa: E402


@pytest.fixture()
def verlauf():
    chat_verlauf.conversations.clear()
    chat_verlauf.next_conversation_id = 1
    chat_verlauf.setze_memory_extractor(None)
    chat_verlauf.init(
        verlauf_datei=os.path.join(BACKEND, "tests", "_tmp_verlauf2.json"),
        persist_dir=os.path.join(BACKEND, "tests", "_tmp_persist"),
    )
    yield chat_verlauf
    chat_verlauf.conversations.clear()
    try:
        os.remove(os.path.join(BACKEND, "tests", "_tmp_verlauf2.json"))
        os.remove(os.path.join(BACKEND, "tests", "_tmp_verlauf2_alt.json"))
    except OSError:
        pass


def test_anhaengen_mit_zeit(verlauf):
    verlauf.conversations["c"] = []
    verlauf.verlauf_nachricht_anhaengen("c", "assistant", "hi")
    e = verlauf.conversations["c"][0]
    assert e["role"] == "assistant" and e["content"] == "hi" and e["zeit"]


def test_anhaengen_ignoriert_leer(verlauf):
    verlauf.conversations["c"] = []
    verlauf.verlauf_nachricht_anhaengen("c", "assistant", "")
    assert verlauf.conversations["c"] == []


def test_get_or_create(verlauf):
    """ES GIBT NUR EINE durchlaufende Conversation (seit 2026-08-30).
    _get_or_create liefert IMMER conv_main — nie eine neue ID, egal ob eine
    (unbekannte) conversation_id mitgegeben wird oder nicht."""
    c = verlauf._get_or_create_conversation(None)
    assert c == "conv_main"
    c2 = verlauf._get_or_create_conversation(None)
    assert c2 == "conv_main"          # nie neue ID bei fehlender
    c3 = verlauf._get_or_create_conversation("conv_schrott_x")
    assert c3 == "conv_main"          # unbekannte id wird gemappt, kein neuer Chat
    assert list(verlauf.conversations.keys()) == ["conv_main"]


def test_finish_exchange_ohne_memory_fuegt_eintraege(verlauf):
    verlauf.conversations["c"] = []
    n = verlauf.finish_exchange("c", "Frage?", "Antwort")
    assert n == 0  # kein Extractor injiziert -> 0 Erinnerungen


def test_leerer_verlauf_restauriert_aus_backup():
    """Datenverlust-Schutz (2026-08-30): Wurde die Hauptdatei von einem Server
    mit leerem Stand ueberschrieben, startet _lade_verlauf NICHT leer weiter,
    sondern holt den juengsten nicht-leeren Rotations-Backup zurueck. So kann
    ein leerer Server den Verlauf nicht dauerhaft kassieren."""
    BASE = os.path.join(BACKEND, "tests")
    haupt = os.path.join(BASE, "_tmp_restore.json")
    persist = os.path.join(BASE, "_tmp_restore_persist")
    os.makedirs(persist, exist_ok=True)
    try:
        # 1) Intakten Stand mit Inhalt + zugehoeriges Backup simulieren.
        chat_verlauf.conversations.clear()
        chat_verlauf.init(haupt, persist)
        chat_verlauf.conversations["conv_main"] = [
            {"role": "user", "content": "echte frage", "zeit": "2026-08-30T10:00:00"},
            {"role": "assistant", "content": "echte antwort", "zeit": "2026-08-30T10:00:01"},
        ]
        chat_verlauf._speichere_verlauf()
        # Zweiter Save erzeugt das Rotations-Backup (beim ersten gibt es noch
        # nichts zu sichern).
        chat_verlauf.conversations["conv_main"].append(
            {"role": "user", "content": "weitere frage", "zeit": "2026-08-30T10:00:02"}
        )
        chat_verlauf._speichere_verlauf()
        # Das Backup-artige File erzeugen: Zeitstempel-Rotation ist in
        # _speichere_verlauf automatisch abgelegt.
        import glob
        backups = glob.glob(haupt + ".bak-*")
        assert backups, "kein Backup angelegt"

        # 2) Hauptdatei mit LEEREM Stand ueberschreiben (simulierter feu):
        import json as _json
        with open(haupt, "w", encoding="utf-8") as f:
            _json.dump({"next_id": 1, "conversations": {}, "summarys": {}}, f)

        # 3) Neu laden: leeres conversations -> wird aus Backup restauriert.
        chat_verlauf.conversations.clear()
        chat_verlauf.init(haupt, persist)
        assert any(chat_verlauf.conversations.values()), \
            "leerer Verlauf wurde nicht aus Backup restauriert"
        assert chat_verlauf.conversations["conv_main"][0]["content"] == "echte frage"
    finally:
        chat_verlauf.conversations.clear()
        for f2 in glob.glob(haupt + "*"):
            try:
                os.remove(f2)
            except OSError:
                pass


def test_finish_exchange_mit_memory_extractor(verlauf):
    verlauf.conversations["c"] = []
    verlauf.setze_memory_extractor(lambda **kw: [1, 2])  # 2 Erinnerungen
    n = verlauf.finish_exchange("c", "q", "a")
    assert n == 2
