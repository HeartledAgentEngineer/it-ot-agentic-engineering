"""Alltagsprotokoll S4 (03.11.2026): ``data_collection: deny`` in allen Nebenaufrufen.

Hermes, Runde 1: Gedächtnis-Auszug, Gesichts-Anlernen, Hermes-Weiche, Datei-Suchabsicht und
Glättung schickten nur ``allow_fallbacks`` (oder gar nichts) — OpenRouters Routing durfte dann
bei einem Anbieter landen, der Prompts speichert. Darin stehen Sebastians eigene Sätze.
Erfundene Texte, Attrappe statt Netz.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.llm_service import LLMService  # noqa: E402


@pytest.fixture
def dienst():
    aufrufe = []

    def create(**kw):
        aufrufe.append(kw)
        nachricht = SimpleNamespace(content="{}", tool_calls=None, annotations=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=nachricht)])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    s = LLMService()
    with mock.patch.object(s, "client", fake), \
            mock.patch.object(LLMService, "is_configured", new_callable=mock.PropertyMock,
                              return_value=True), \
            mock.patch.object(LLMService, "_lade_lernfaelle", return_value=[]):
        yield s, aufrufe


def _deny(aufruf):
    return (aufruf.get("extra_body") or {}).get("provider", {}).get("data_collection")


@pytest.mark.parametrize("aufruf", [
    lambda s: s.extract_memories("Ich arbeite als Testerin", "Schön."),
    lambda s: s.extrahiere_gesichts_anlernen("das ist Testperson Eins"),
    lambda s: s.braucht_hermes("Erkläre mir Wasser"),
    lambda s: s.extrahiere_datei_such_intent("das letzte Foto aus 2020"),
    lambda s: s.polish_text("äh also ich teste das", shield=None),
], ids=["gedaechtnis", "anlernen", "weiche", "dateisuche", "glaettung"])
def test_nebenaufruf_verbietet_datensammlung(dienst, aufruf):
    s, aufrufe = dienst
    aufruf(s)
    assert aufrufe, "kein Modellaufruf"
    for kw in aufrufe:
        assert _deny(kw) == "deny", kw.get("extra_body")
        # Die Ausweichlogik bleibt: andere ZDR-Anbieter dürfen einspringen.
        assert kw["extra_body"]["provider"].get("allow_fallbacks") is True
