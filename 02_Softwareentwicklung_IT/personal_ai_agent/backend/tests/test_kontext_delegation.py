"""Tests: Kontext-Transfer an Hermes bei der Delegation (Variante C)."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _baue_kontext  # noqa: E402


def test_baue_kontext_leer_ohne_verlauf():
    """Ohne Verlauf/Erinnerungen ist der Kontext leer (kein Bruch)."""
    from app.router import chat as chat_modul
    with mock.patch.object(chat_modul, "conversations", {}), \
         mock.patch.object(chat_modul, "_get_or_create_conversation", return_value="keine"), \
         mock.patch("app.router.chat.memory_service.retrieve_relevant_memories", return_value=[]):
        assert _baue_kontext("Testfrage") == ""


def test_kontext_wird_an_buch_weitergegeben():
    """route_auftrag gibt den Kontext als Teil des Hermes-Auftrags weiter."""
    from app.services import chat_routing

    called = {}
    def fake_anlegen(auftrag, hinweis=None, kategorie=None, komplexitaet=None):
        called["auftrag"] = auftrag
        return {"id": "abc12345"}
    def fake_status(_id):
        pass

    with mock.patch.object(chat_routing, "hermes_gateway") as gw, \
         mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(chat_routing, "anlegen_im_buch", side_effect=fake_anlegen), \
         mock.patch.object(chat_routing, "statusmeldung_wartet", side_effect=fake_status), \
         mock.patch.object(chat_routing, "verknuepfe_chat", return_value=None):
        gw.sende_auftrag.return_value = None
        r = chat_routing.route_auftrag(
            "Baue ein Skript",
            "Testbegründung", "feature", "mittel",
            finish_exchange=lambda *a, **k: None,
            get_or_create_conversation=lambda _: "conv1",
            starte_lokale_hermes=lambda *a, **k: None,
            kontext="user: Was ist mein Ziel?\nErinnerung: AI-Engineering",
        )
    assert r["art"] == "buch"
    assert "[Kontext aus dem Gespräch" in called["auftrag"]
    assert "AI-Engineering" in called["auftrag"]
