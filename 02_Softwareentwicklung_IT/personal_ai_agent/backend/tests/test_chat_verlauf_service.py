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
    c = verlauf._get_or_create_conversation(None)
    assert c.startswith("conv_")
    c2 = verlauf._get_or_create_conversation(c)
    assert c2 == c  # existierende wiederverwendet


def test_finish_exchange_ohne_memory_fuegt_eintraege(verlauf):
    verlauf.conversations["c"] = []
    n = verlauf.finish_exchange("c", "Frage?", "Antwort")
    assert n == 0  # kein Extractor injiziert -> 0 Erinnerungen
    roles = [e["role"] for e in verlauf.conversations["c"]]
    assert roles == ["user", "assistant"]


def test_finish_exchange_mit_memory_extractor(verlauf):
    verlauf.conversations["c"] = []
    verlauf.setze_memory_extractor(lambda **kw: [1, 2])  # 2 Erinnerungen
    n = verlauf.finish_exchange("c", "q", "a")
    assert n == 2
