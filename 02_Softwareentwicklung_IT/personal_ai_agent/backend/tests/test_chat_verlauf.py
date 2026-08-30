"""Tests für den Chat-Verlauf (TDD-Basis für das Refactoring von chat.py).

Dient als Prüf-Schwelle: mit `python -m pytest -q` grün (Exit 0) laufen lassen.
"""
import builtins
import importlib
import json
import os
import sys
from types import ModuleType
from unittest import mock

import pytest

# chat.py als Modul einlesen (ohne FastAPI-App zu starten) — wir greifen nur
# auf die Verlauf-Funktionen zu. Systempfad: Backend-Root.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


@pytest.fixture()
def chat_mod():
    """Liefert das chat-Modul mit isoliertem Verlauf-Dateispeicherort."""
    with mock.patch("app.router.chat.VERLAUF_DATEI", new=os.path.join(
        BACKEND, "tests", "_tmp_verlauf.json"
    )):
        # frisches Modul, damit der globale Verlauf-Topf sauber startet
        if "app.router.chat" in sys.modules:
            del sys.modules["app.router.chat"]
        mod = importlib.import_module("app.router.chat")
        # Konversationen-Topf leeren
        mod.conversations.clear()
        yield mod
    # Aufräumen: Temp-Datei löschen
    try:
        os.remove(os.path.join(BACKEND, "tests", "_tmp_verlauf.json"))
    except OSError:
        pass


def test_verlauf_nachricht_anhaengen_fuegt_mit_zeit_hinzu(chat_mod):
    """Eine angehängte Nachricht landet im Verlauf mit Zeitstempel + role/content."""
    mod = chat_mod
    conv_id = "conv_test"
    mod.conversations[conv_id] = []
    mod.verlauf_nachricht_anhaengen(conv_id, "assistant", "Hallo")
    entries = mod.conversations[conv_id]
    assert len(entries) == 1
    e = entries[0]
    assert e["role"] == "assistant"
    assert e["content"] == "Hallo"
    assert "zeit" in e and e["zeit"]  # nicht leer


def test_verlauf_nachricht_ohne_content_ignoriert(chat_mod):
    """Leerer/None-Content erzeugt keinen Eintrag (kein Müll im Verlauf)."""
    mod = chat_mod
    conv_id = "conv_leer"
    mod.conversations[conv_id] = []
    mod.verlauf_nachricht_anhaengen(conv_id, "assistant", "")
    mod.verlauf_nachricht_anhaengen(conv_id, "assistant", None)
    assert mod.conversations[conv_id] == []


def test_finish_exchange_persistiert_bild_pfad(chat_mod):
    """Ein über die Dateisuche gezeigtes Bild überlebt im Verlauf: Der Pfad
    wird am Assistant-Eintrag mitgespeichert (nicht die Datei selbst), damit
    das Frontend das Bild nach einem Reload wieder anzeigen kann."""
    mod = chat_mod
    conv_id = "conv_img"
    mod.conversations[conv_id] = []
    mod._finish_exchange(
        conv_id, "Zeig den letzten Screenshot", "Hier ist er:",
        bild_pfad="/storage/shared/Pictures/Screenshots/Screenshot_1.png",
    )
    eintraege = mod.conversations[conv_id]
    # user ohne, assistant mit Bildpfad
    assert eintraege[0].get("bild_pfad") is None
    assert eintraege[1].get("bild_pfad") == \
        "/storage/shared/Pictures/Screenshots/Screenshot_1.png"

    # Ohne Angabe bleibt es beim alten Verhalten (kein bild_pfad-Schlüssel).
    mod.conversations[conv_id] = []
    mod._finish_exchange(conv_id, "Frage?", "Antwort")
    assert "bild_pfad" not in mod.conversations[conv_id][1]


def test_finish_exchange_fuegt_user_und_assistant_hinzu(chat_mod):
    """_finish_exchange hängt user- und assistant-Nachricht an (mit Zeiten)."""
    mod = chat_mod
    conv_id = "conv_ex"
    mod.conversations[conv_id] = []
    # Rückgabewert ist 'Anzahl neuer Erinnerungen' (hier 0, da kein Memory), die
    # eigentliche Prüfung: beide Nachrichten landen im Verlauf.
    mod._finish_exchange(conv_id, "Frage?", "Antwort")
    roles = [e["role"] for e in mod.conversations[conv_id]]
    assert roles == ["user", "assistant"]
    assert all("zeit" in e for e in mod.conversations[conv_id])
