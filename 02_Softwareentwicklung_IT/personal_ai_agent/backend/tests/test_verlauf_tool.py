"""Tests für das Verlaufs-Tool (Rückblick über Sprache)."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _verlauf_tool  # noqa: E402


def test_verlauf_findet_treffer():
    """Rückblick-Frage → Treffer aus dem Gesprächsverlauf zitiert."""
    nachrichten = [
        {"role": "user", "content": "Wie plane ich die Bewerbung?",
         "zeit": "2026-02-01T09:00:00"},
        {"role": "assistant", "content": "Azure-Kurse starten im September.",
         "zeit": "2026-02-01T09:00:05"},
        {"role": "user", "content": "Noch eine Frage zu Hamburg.",
         "zeit": "2026-02-02T10:00:00"},
    ]
    with mock.patch("app.router.chat.conversations", {"conv1": nachrichten}):
        ausgabe = _verlauf_tool("Was haben wir zu Azure gesagt?")
    assert "Aus dem Gesprächsverlauf" in ausgabe
    assert "Azure-Kurse" in ausgabe


def test_verlauf_kein_signal_leer():
    """Ohne Rückblick-Signal → keine Ausgabe (kein False-Trigger)."""
    assert _verlauf_tool("Wie hübsch ist Hamburg?") == ""


def test_verlauf_kein_treffer():
    """Signal + kein Treffer → Hinweis statt Absturz."""
    with mock.patch("app.router.chat.conversations", {"conv1": []}):
        ausgabe = _verlauf_tool("Was haben wir zu unsichtbar gesagt?")
    assert "nichts gefunden" in ausgabe