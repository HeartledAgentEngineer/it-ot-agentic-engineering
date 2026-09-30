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


def test_standard_ist_an():
    """Seit 01.10.2026 Standard an (Knopf weg); die Anfrage laesst das Feld leer."""
    from app.config import Settings
    assert Settings.model_fields["tool_use"].default is True
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


def _mit_werkzeugen(extra_body) -> bool:
    return any(t.get("type") == "function" for t in (extra_body or {}).get("tools") or [])


def _llm_mit_attrappe(create):
    from types import SimpleNamespace

    from app.services.llm_service import llm_service

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return llm_service, [
        mock.patch.object(llm_service, "client", fake_client),
        mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                          return_value=True),
    ]


def _stueck(text):
    from types import SimpleNamespace
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
        content=text, tool_calls=None, annotations=None, reasoning_details=None))])


def test_rueckfall_ohne_werkzeuge_wenn_werkzeug_weg_vor_dem_text_scheitert():
    """Werkzeuge sind Standard (01.10.2026): lehnt das Modell/der Anbieter die
    tools ab, kommt eine Antwort ohne Werkzeuge statt einer Fehlermeldung."""
    from app.services import werkzeuge

    aufrufe = []

    def create(**kw):
        aufrufe.append(kw)
        if _mit_werkzeugen(kw["extra_body"]):
            raise RuntimeError("400 tools not supported")
        return iter([_stueck("Antwort ohne Werkzeuge")])

    llm, patches = _llm_mit_attrappe(create)
    for p in patches:
        p.start()
    try:
        ereignisse = list(llm.chat_stream("Frage", no_retention=True, werkzeuge=True))
    finally:
        for p in reversed(patches):
            p.stop()
    assert len(aufrufe) == 2
    assert _mit_werkzeugen(aufrufe[0]["extra_body"]) and not _mit_werkzeugen(aufrufe[1]["extra_body"])
    assert any("ohne" in e.get("status", "") for e in ereignisse)
    assert "".join(e.get("delta", "") for e in ereignisse) == "Antwort ohne Werkzeuge"
    # Der Rueckfall bekommt den Werkzeug-Hinweis NICHT (Kopie statt Original geaendert).
    assert werkzeuge.SYSTEM_HINWEIS not in aufrufe[1]["messages"][0]["content"]
    assert aufrufe[1]["extra_body"]["provider"]["data_collection"] == "deny"


def test_kein_rueckfall_wenn_schon_text_kam():
    """Kam schon Text, wird nicht ein zweites Mal geantwortet - der Fehler bleibt."""
    import pytest

    aufrufe = []

    def create(**kw):
        aufrufe.append(kw)

        def strom():
            yield _stueck("Halbe Antw")
            raise RuntimeError("Verbindung weg")
        return strom()

    llm, patches = _llm_mit_attrappe(create)
    for p in patches:
        p.start()
    try:
        gesehen = []
        with pytest.raises(RuntimeError):
            for e in llm.chat_stream("Frage", werkzeuge=True):
                gesehen.append(e)
    finally:
        for p in reversed(patches):
            p.stop()
    assert len(aufrufe) == 1
    assert [e.get("delta") for e in gesehen if e.get("delta")] == ["Halbe Antw"]
