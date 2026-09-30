"""Tests: Tool Use im Stream-Weg des Chats (Spec docs/spec-tool-use-v1.md, 30.09.2026).

Prueft den Schalter und die Verdrahtung in ``router/chat.py``:
- Schalter: Anfrage-Feld ``werkzeuge`` vor Konfiguration ``tool_use`` (Standard aus).
- Werkzeuge an: die Vorab-Weiche (Archiv/Datei/Verlauf/Gesicht/Fotos/Beziehungen)
  laeuft NICHT, ``llm_service.chat_stream`` bekommt ``werkzeuge=True``,
  Statuszeilen und angesehene Bilder kommen im Stream an.
- Werkzeuge aus: alter Weg unveraendert (Weiche laeuft, ``werkzeuge=False``).

Offline: das Modell ist eine Attrappe, Verlauf/Erinnerungen werden nicht geschrieben.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_tool_use_stream.py -q
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from unittest import mock



BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.models import ChatRequest  # noqa: E402

WEICHE = ("_archiv_tool", "_datei_tool", "_verlauf_tool", "_gesicht_suche_tool",
          "_fotos_uebersicht_tool", "_beziehungen_tool")


def _chat_modul():
    # Frisch holen: ein anderer Test laedt app.router.chat neu (sys.modules).
    return importlib.import_module("app.router.chat")


def _sse_lesen(antwort) -> list:
    async def sammeln():
        teile = []
        async for t in antwort.body_iterator:
            teile.append(t if isinstance(t, str) else t.decode("utf-8"))
        return "".join(teile)
    roh = asyncio.run(sammeln())
    return [json.loads(z[len("data: "):]) for z in roh.splitlines() if z.startswith("data: ")]


def _lauf(werkzeuge, weiche_erlaubt, modell_ereignisse):
    chat = _chat_modul()
    aufgerufen = {}

    def modell(**kw):
        aufgerufen.update(kw)
        yield from modell_ereignisse

    def verboten(*a, **k):
        raise AssertionError("Vorab-Weiche darf mit Werkzeugen nicht laufen")

    patches = [
        mock.patch.object(chat.llm_service, "chat_stream", side_effect=modell),
        mock.patch.object(chat.memory_service, "retrieve_relevant_memories", return_value=[]),
        mock.patch.object(chat.memory_service, "get_memory_count", return_value=0),
        mock.patch.object(chat, "_finish_exchange", return_value=0),
        mock.patch.object(chat, "_hole_kontext_summary", return_value=("", None)),
        mock.patch.object(chat, "_gesichter_merke", return_value=""),
    ]
    for name in WEICHE:
        if weiche_erlaubt:
            rueckgabe = ("", []) if name == "_datei_tool" else ""
            patches.append(mock.patch.object(chat, name, return_value=rueckgabe))
        else:
            patches.append(mock.patch.object(chat, name, side_effect=verboten))
    for p in patches:
        p.start()
    try:
        req = ChatRequest(message="Schau dir mein letztes Foto an und such Beispiele im Archiv",
                          force_agent=True, archiv=False, werkzeuge=werkzeuge)
        antwort = asyncio.run(chat.chat_stream(req))
        ereignisse = _sse_lesen(antwort)
        finish = chat._finish_exchange
        return ereignisse, aufgerufen, finish
    finally:
        for p in reversed(patches):
            p.stop()


def test_schalter_vorrang_anfrage_vor_konfiguration(monkeypatch):
    chat = _chat_modul()
    monkeypatch.setattr(settings, "tool_use", False)
    assert chat._werkzeuge_an(ChatRequest(message="x")) is False
    assert chat._werkzeuge_an(ChatRequest(message="x", werkzeuge=True)) is True
    monkeypatch.setattr(settings, "tool_use", True)
    assert chat._werkzeuge_an(ChatRequest(message="x")) is True
    assert chat._werkzeuge_an(ChatRequest(message="x", werkzeuge=False)) is False


def test_standard_ist_aus():
    from app.config import Settings
    assert Settings.model_fields["tool_use"].default is False
    assert ChatRequest(message="x").werkzeuge is None


def test_mit_werkzeugen_keine_weiche_und_status_im_stream():
    bild = {"data_url": "data:image/jpeg;base64,AAAA", "pfad": "/sdcard/DCIM/IMG_1.jpg"}
    ereignisse, aufgerufen, finish = _lauf(True, weiche_erlaubt=False, modell_ereignisse=[
        {"status": "🔧 durchsucht Handy-Dateien …"},
        {"werkzeug": {"name": "dateien_suchen", "ok": True}},
        {"bild": bild},
        {"delta": "Ich sehe eine Tabelle."},
    ])
    assert aufgerufen["werkzeuge"] is True
    status = [e["status"] for e in ereignisse if "status" in e]
    assert "🤔 Agent überlegt (mit Werkzeugen)…" in status
    assert "🔧 durchsucht Handy-Dateien …" in status
    assert "".join(e.get("delta", "") for e in ereignisse) == "Ich sehe eine Tabelle."
    assert not any("werkzeug" in e for e in ereignisse)  # Protokoll bleibt intern
    fertig = [e for e in ereignisse if e.get("done")][0]
    assert fertig["bild_pfad"] == "/sdcard/DCIM/IMG_1.jpg"
    assert fertig["bild_vorschau"] == bild["data_url"]
    # Der Verlauf merkt sich den Bildpfad wie bei der Dateisuche.
    assert finish.call_args.kwargs["bild_pfad"] == "/sdcard/DCIM/IMG_1.jpg"


def test_ohne_werkzeuge_alter_weg_unveraendert():
    ereignisse, aufgerufen, _ = _lauf(False, weiche_erlaubt=True,
                                      modell_ereignisse=[{"delta": "Antwort"}])
    assert aufgerufen["werkzeuge"] is False
    status = [e["status"] for e in ereignisse if "status" in e]
    assert status == ["🤔 Agent überlegt…"]


def test_llm_aufruf_mit_werkzeugen_behaelt_riegel_und_websuche():
    """Der echte Modellaufruf: Werkzeug-Schemata + Websuche in EINER tools-Liste,
    Datenschutz-Riegel bleibt, System-Prompt bekommt den Werkzeug-Hinweis."""
    from types import SimpleNamespace

    from app.services import werkzeuge
    from app.services.llm_service import llm_service

    aufrufe = []

    def create(**kw):
        aufrufe.append(kw)
        return iter([SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content="ok", tool_calls=None, annotations=None,
                                  reasoning_details=None))])])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with mock.patch.object(llm_service, "client", fake_client), \
         mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                           return_value=True):
        ereignisse = list(llm_service.chat_stream("Frage", web_search="auto",
                                                  no_retention=True, werkzeuge=True))
    assert [e.get("delta") for e in ereignisse] == ["ok"]
    extra = aufrufe[0]["extra_body"]
    namen = [t.get("function", {}).get("name") for t in extra["tools"]]
    assert set(werkzeuge.REGISTER) <= set(namen)
    assert any(t.get("type") == "openrouter:web_search" for t in extra["tools"])
    assert extra["provider"]["data_collection"] == "deny"
    assert "tool_choice" not in extra
    assert werkzeuge.SYSTEM_HINWEIS in aufrufe[0]["messages"][0]["content"]
    assert aufrufe[0]["stream"] is True
