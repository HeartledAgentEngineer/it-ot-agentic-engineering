"""End-to-End-Test für den /api/chat-Endpoint (Weiche mit Mocks).

Sichert das Zusammenspiel: Coding-Anfrage ohne verfügbaren Hermes (weder PC
noch lokal) landet als 'Coding-Auftrag erkannt – wird bearbeitet' im Buch-
Fallback; normale Fragen gehen an den LLM (nicht ins Buch).
"""
import asyncio
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.models import ChatRequest  # noqa: E402
from app.router.chat import chat as chat_endpoint  # noqa: E402
from app.services.hermes_gateway import hermes_gateway as hg_instanz  # noqa: E402
from app.services.memory_service import memory_service as mem_instanz  # noqa: E402


@pytest.fixture()
def _kein_hermes():
    """PC + lokal nicht verfügbar → Buch-Fallback."""
    with mock.patch.object(hg_instanz, "sende_auftrag", return_value=None), \
         mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(mem_instanz, "extract_and_store_memories", return_value=[]):
        yield


def test_coding_ohne_hermes_geht_ins_buch(_kein_hermes):
    """Coding-Anfrage → Buch-Fallback ('wird bearbeitet'), keine LLM-Antwort."""
    req = ChatRequest(message="Baue einen /health-Endpoint in der FastAPI-App",
                      model="deepseek/deepseek-v4-flash", web_search="off")
    resp = asyncio.run(chat_endpoint(req))
    assert "Coding-Auftrag erkannt" in resp.reply
    assert "wird bearbeitet" in resp.reply


def test_grenze_delegiert_statt_normalem_chat(_kein_hermes):
    """Fähigkeits-Grenzthema (z. B. 'Installiere ein Paket') wird NICHT als
    normale Frage beantwortet — es delegiert in die Weiche (Buch-Fallback),
    obwohl ist_auftrag es nicht als Coding einstuft."""
    from app.services import llm_service
    with mock.patch.object(llm_service.llm_service, "chat",
                           side_effect=AssertionError("LLM darf bei Grenzthema nicht gerufen werden")):
        req = ChatRequest(message="Installiere mir bitte das Wetterpaket auf dem Server",
                          model="deepseek/deepseek-v4-flash", web_search="off")
        resp = asyncio.run(chat_endpoint(req))
    assert "Coding-Auftrag erkannt" in resp.reply  # → in der Weiche/Buch-Fallback
    assert "wird bearbeitet" in resp.reply


def test_normaler_chat_bleibt_beim_agenten():
    """Normale Frage → LLM-Weg, Hermes wird NICHT gerufen."""
    from app.services import llm_service
    with mock.patch.object(hg_instanz, "sende_auftrag", side_effect=AssertionError("Hermes darf nicht gerufen werden")), \
         mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(mem_instanz, "retrieve_relevant_memories", return_value=[]), \
         mock.patch.object(mem_instanz, "extract_and_store_memories", return_value=[]), \
         mock.patch.object(llm_service.llm_service, "chat",
                           return_value=("Die Hansestadt ist schön.", [])) as m_chat:
        req = ChatRequest(message="Wie hübsch ist Hamburg?",
                          model="deepseek/deepseek-v4-flash", web_search="off")
        resp = asyncio.run(chat_endpoint(req))
    assert "schön" in resp.reply
    m_chat.assert_called_once()
