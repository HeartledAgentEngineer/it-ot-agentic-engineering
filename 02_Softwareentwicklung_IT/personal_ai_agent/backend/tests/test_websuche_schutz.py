"""Tests: keine Websuche bei persönlichen Fragen (Plan websuche-persoenlich, Fassung 4).

Offline, nur erfundene Namen. Prüft die Regel (``websuche_schutz``), den
gemeinsamen Namens-Helfer (``werkzeuge.bekannte_namen``), die Verdrahtung in
``/chat`` und ``/stream``, den Systemhinweis und den DSML-Filter der Schleife.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_websuche_schutz.py -q
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.models import ChatRequest  # noqa: E402
from app.services import websuche_schutz as ws  # noqa: E402
from app.services import werkzeug_schleife as schleife  # noqa: E402
from app.services import werkzeuge  # noqa: E402

NAMEN = ["Ida Testmann", "Bodo Beispiel"]


def modus(nachricht, verlauf=(), m="auto", namen=NAMEN):
    return ws.wirksamer_modus(m, nachricht, list(verlauf), namen)


# --- Regel -----------------------------------------------------------------

@pytest.mark.parametrize("m", ["auto", "manual"])
@pytest.mark.parametrize("frage,grund", [
    ("Zeig mal eine Diashow mit Bildern vom Urlaub", "bild"),
    ("Hast du Fotos vom Sommerfest?", "bild"),
    ("Was weißt du über Opa?", "familie"),
    ("Wann hat meine Schwester Geburtstag?", "familie"),
    ("Was macht eigentlich Ida gerade?", "person"),
    ("Erzähl mir von bodo beispiel", "person"),
])
def test_persoenliche_frage_schaltet_websuche_aus(m, frage, grund):
    assert modus(frage, m=m) == ("off", grund)


def test_neutrale_frage_behaelt_modus():
    assert modus("Wie wird das Wetter morgen in Hamburg?") == ("auto", "")
    assert modus("Wie wird das Wetter morgen in Hamburg?", m="manual") == ("manual", "")


def test_aus_bleibt_aus_und_unbekannter_modus_unberuehrt():
    assert modus("Zeig Fotos von Opa", m="off") == ("off", "")


def test_name_nur_als_ganzes_wort():
    assert modus("Ich habe eine Idee für morgen") == ("auto", "")
    assert modus("Ida kommt morgen") == ("off", "person")


def test_kaputte_oder_leere_namensliste_wirft_nicht():
    assert modus("Was macht Ida?", namen=[]) == ("auto", "")
    assert modus("Was macht Ida?", namen=None) == ("auto", "")
    assert modus("Was macht Ida?", namen=[None, "", 42]) == ("auto", "")


def test_ausdruecklicher_suchauftrag_behaelt_modus():
    assert modus("Such im Internet nach Opa Testmann") == ("auto", "")
    assert modus("Google mal Bodo Beispiel") == ("auto", "")
    # Auch wenn vorher eine Bildfrage im Verlauf steht.
    assert modus("Such im Internet nach Ida Testmann",
                 verlauf=["Zeig Fotos von Ida"]) == ("auto", "")


@pytest.mark.parametrize("frage", [
    "Zeig Fotos von Oma, aber suche nicht im Internet",
    "Verzichte auf die Websuche; zeig Fotos von Oma",
    "Websuche an, zeig Fotos von Oma",          # kein Suchverb -> kein Auftrag
    "Such ohne Internet nach Bildern von Opa",
    "Lass das Googeln, zeig Bilder von Opa",
])
def test_verneinung_oder_fehlender_auftrag_sperrt(frage):
    assert modus(frage)[0] == "off"


def test_folgefrage_bleibt_gesperrt_solange_im_verlauf():
    verlauf = ["Zeig Fotos von Oma", "zeig mehr davon", "noch mehr", "und weiter", "weiter"]
    assert modus("zeig mehr davon", verlauf=verlauf) == ("off", "verlauf")
    assert modus("zeig mehr davon", verlauf=["Wie spät ist es?", "danke"]) == ("auto", "")


def test_zusammenfassung_zaehlt_mit():
    texte = ws.nutzertexte([{"role": "user", "content": "danke"},
                            {"role": "assistant", "content": "Gern"}],
                           "Sebastian wollte Fotos von Oma sehen.")
    assert texte == ["danke", "Sebastian wollte Fotos von Oma sehen."]
    assert modus("zeig mehr davon", verlauf=texte) == ("off", "verlauf")


def test_log_nennt_nur_den_grund(caplog):
    with caplog.at_level(logging.INFO, logger="app.services.websuche_schutz"):
        modus("Was macht Ida Testmann? Zeig Fotos")
    text = caplog.text
    assert "Grund: bild" in text
    assert "Ida" not in text and "Fotos" not in text


# --- gemeinsamer Namens-Helfer ---------------------------------------------

def test_bekannte_namen_aus_dem_quiz():
    with mock.patch("app.services.gruppen_quiz.personen",
                    return_value={"ok": True, "personen": [{"name": "Ida Testmann"}, {"name": ""}]}):
        assert werkzeuge.bekannte_namen() == ["Ida Testmann"]


def test_bekannte_namen_rueckfall_auf_alten_katalog():
    with mock.patch("app.services.gruppen_quiz.personen", return_value={"ok": True, "personen": []}), \
         mock.patch("app.services.gesichter_service.liste_personen",
                    return_value=[{"name": "Bodo Beispiel"}]):
        assert werkzeuge.bekannte_namen() == ["Bodo Beispiel"]


def test_bekannte_namen_wirft_nie():
    with mock.patch("app.services.gruppen_quiz.personen", side_effect=OSError("kaputt")):
        assert werkzeuge.bekannte_namen() == []


def test_personen_liste_nutzt_denselben_helfer():
    with mock.patch.object(werkzeuge, "_bekannte_personen",
                           return_value=("alt", [{"name": "Bodo Beispiel"}])):
        assert "Bodo Beispiel" in werkzeuge._personen_liste({}).text


def test_systemhinweis_enthaelt_websuche_regel():
    assert "Suche nie im Internet nach Personen" in werkzeuge.SYSTEM_HINWEIS


# --- Verdrahtung -----------------------------------------------------------

def _chat_modul():
    return importlib.import_module("app.router.chat")


def _sse_lesen(antwort) -> list:
    async def sammeln():
        teile = []
        async for t in antwort.body_iterator:
            teile.append(t if isinstance(t, str) else t.decode("utf-8"))
        return "".join(teile)
    roh = asyncio.run(sammeln())
    return [json.loads(z[len("data: "):]) for z in roh.splitlines() if z.startswith("data: ")]


def _stream(nachricht, web, summary="", verlauf=()):
    chat = _chat_modul()
    aufgerufen = {}

    def modell(**kw):
        aufgerufen.update(kw)
        yield {"delta": "ok"}

    patches = [
        mock.patch.object(chat.llm_service, "chat_stream", side_effect=modell),
        mock.patch.object(chat.memory_service, "retrieve_relevant_memories", return_value=[]),
        mock.patch.object(chat.memory_service, "get_memory_count", return_value=0),
        mock.patch.object(chat, "_finish_exchange", return_value=0),
        mock.patch.object(chat, "_hole_kontext_summary", return_value=(summary, None)),
        mock.patch.object(chat, "_gesichter_merke", return_value=""),
        mock.patch.object(werkzeuge, "bekannte_namen", return_value=list(NAMEN)),
    ]
    # Eigener Verlauf: nie den vorhandenen Standard-Verlauf am Rechner mitlesen.
    patches.append(mock.patch.dict(chat.conversations, {"conv_websuche_test": list(verlauf)}))
    patches.append(mock.patch.object(chat, "_get_or_create_conversation",
                                     return_value="conv_websuche_test"))
    for p in patches:
        p.start()
    try:
        req = ChatRequest(message=nachricht, force_agent=True, archiv=False, werkzeuge=True,
                          web_search=web,
                          conversation_id="conv_websuche_test")
        ereignisse = _sse_lesen(asyncio.run(chat.chat_stream(req)))
        return ereignisse, aufgerufen
    finally:
        for p in reversed(patches):
            p.stop()


def test_stream_bildfrage_kommt_mit_websuche_aus_an():
    ereignisse, kw = _stream("Zeig eine Diashow mit Bildern von Opa", "auto")
    assert kw["web_search"] == "off"
    assert any("🔒" in e.get("status", "") for e in ereignisse)


def test_stream_neutrale_frage_behaelt_websuche_ohne_statuszeile():
    ereignisse, kw = _stream("Wie wird das Wetter morgen in Hamburg?", "manual")
    assert kw["web_search"] == "manual"
    assert not any("🔒" in e.get("status", "") for e in ereignisse)


def test_stream_ohne_websuche_keine_statuszeile():
    ereignisse, kw = _stream("Zeig Fotos von Opa", "off")
    assert kw["web_search"] == "off"
    assert not any("🔒" in e.get("status", "") for e in ereignisse)


def test_stream_zusammenfassung_sperrt_folgefrage():
    _, kw = _stream("zeig mehr davon", "auto", summary="Es ging um Fotos von Oma.")
    assert kw["web_search"] == "off"


def test_chat_weg_bildfrage_kommt_mit_websuche_aus_an():
    chat = _chat_modul()
    with mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(chat.memory_service, "retrieve_relevant_memories", return_value=[]), \
         mock.patch.object(chat.memory_service, "extract_and_store_memories", return_value=[]), \
         mock.patch.dict(chat.conversations, {"conv_websuche_test": []}),          mock.patch.object(chat, "_get_or_create_conversation", return_value="conv_websuche_test"),          mock.patch.object(chat, "_hole_kontext_summary", return_value=("", None)), \
         mock.patch.object(chat, "_archiv_tool", return_value=""), \
         mock.patch.object(chat, "_datei_tool", return_value=("", [])), \
         mock.patch.object(werkzeuge, "bekannte_namen", return_value=list(NAMEN)), \
         mock.patch.object(chat.llm_service, "chat", return_value=("Antwort", [])) as m_chat:
        req = ChatRequest(message="Was macht Ida Testmann?", web_search="auto",
                          model="deepseek/deepseek-v4-flash")
        asyncio.run(chat.chat(req))
    assert m_chat.call_args.kwargs["web_search"] == "off"


def test_chat_weg_zusammenfassung_sperrt_folgefrage():
    chat = _chat_modul()
    with mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(chat.memory_service, "retrieve_relevant_memories", return_value=[]), \
         mock.patch.object(chat.memory_service, "extract_and_store_memories", return_value=[]), \
         mock.patch.dict(chat.conversations, {"conv_websuche_test": []}),          mock.patch.object(chat, "_get_or_create_conversation", return_value="conv_websuche_test"),          mock.patch.object(chat, "_hole_kontext_summary", return_value=("Fotos von Oma", None)), \
         mock.patch.object(chat, "_archiv_tool", return_value=""), \
         mock.patch.object(chat, "_datei_tool", return_value=("", [])), \
         mock.patch.object(werkzeuge, "bekannte_namen", return_value=[]), \
         mock.patch.object(chat.llm_service, "chat", return_value=("Antwort", [])) as m_chat:
        req = ChatRequest(message="zeig mehr davon", web_search="manual",
                          model="deepseek/deepseek-v4-flash")
        asyncio.run(chat.chat(req))
    assert m_chat.call_args.kwargs["web_search"] == "off"


# --- DSML-Filter -----------------------------------------------------------

def _text(t):
    return {"choices": [{"delta": {"content": t}}]}


def _laufe(*stuecke):
    def modell(messages, tool_choice):
        return iter([_text(s) for s in stuecke])
    return list(schleife.laufe(modell, [{"role": "user", "content": "Frage"}]))


def _deltas(ereignisse):
    return "".join(e.get("delta", "") for e in ereignisse)


def test_dsml_im_ersten_stueck_loest_rueckfall_aus():
    with pytest.raises(schleife.DsmlAlsText):
        _laufe("<｜DSML｜function_calls>fotos_mit_person")


def test_dsml_ueber_drei_stuecke_geteilt():
    with pytest.raises(schleife.DsmlAlsText):
        _laufe("<｜", "DS", "ML｜function_calls>")


def test_dsml_ascii_schreibweise():
    with pytest.raises(schleife.DsmlAlsText):
        _laufe("<|DSML|invoke>")


def test_dsml_nach_normalem_text_gibt_statuszeile():
    ereignisse = _laufe("Ich schaue nach. ", "<｜DSML｜", "function_calls>geheim")
    assert _deltas(ereignisse) == "Ich schaue nach. "
    assert any(e.get("status") == schleife.DSML_STATUS for e in ereignisse)
    assert "DSML" not in json.dumps(ereignisse, ensure_ascii=False)


def test_spitze_klammer_ohne_marke_bleibt_vollstaendig():
    ereignisse = _laufe("a <", "b und 3 <", "4 sowie <｜x")
    assert _deltas(ereignisse) == "a <b und 3 <4 sowie <｜x"
    assert not any("status" in e for e in ereignisse)


def test_llm_rueckfall_nur_ohne_vorherigen_text():
    """Ganze Kette: DSML ohne Text -> chat_stream antwortet ohne Werkzeuge."""
    from types import SimpleNamespace

    from app.services.llm_service import llm_service

    def stueck(t):
        return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content=t, tool_calls=None, annotations=None, reasoning_details=None))])

    aufrufe = []

    def create(**kw):
        aufrufe.append(kw)
        if len(aufrufe) == 1:
            return iter([stueck("<｜DSML｜function_calls>")])
        return iter([stueck("Antwort ohne Werkzeuge")])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with mock.patch.object(llm_service, "client", fake), \
         mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                           return_value=True):
        ereignisse = list(llm_service.chat_stream("Frage", no_retention=True, werkzeuge=True))
    assert len(aufrufe) == 2
    assert _deltas(ereignisse) == "Antwort ohne Werkzeuge"


def test_chat_weg_neutrale_frage_behaelt_websuche():
    """Gegenprobe: Der Verlauf ist abgeschottet, die Sperre greift nicht pauschal."""
    chat = _chat_modul()
    with mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(chat.memory_service, "retrieve_relevant_memories", return_value=[]), \
         mock.patch.object(chat.memory_service, "extract_and_store_memories", return_value=[]), \
         mock.patch.dict(chat.conversations, {"conv_websuche_test": []}), \
         mock.patch.object(chat, "_get_or_create_conversation", return_value="conv_websuche_test"), \
         mock.patch.object(chat, "_hole_kontext_summary", return_value=("", None)), \
         mock.patch.object(chat, "_archiv_tool", return_value=""), \
         mock.patch.object(chat, "_datei_tool", return_value=("", [])), \
         mock.patch.object(werkzeuge, "bekannte_namen", return_value=list(NAMEN)), \
         mock.patch.object(chat.llm_service, "chat", return_value=("Antwort", [])) as m_chat:
        req = ChatRequest(message="Wie wird das Wetter morgen in Hamburg?", web_search="manual",
                          model="deepseek/deepseek-v4-flash")
        asyncio.run(chat.chat(req))
    assert m_chat.call_args.kwargs["web_search"] == "manual"


# --- Codex-Ergebnisprüfung R1 ----------------------------------------------

@pytest.mark.parametrize("frage", [
    "Ida Testmann nutzt Google Drive",
    "Hat Opa ein Google-Konto?",
    "Zeig Fotos aus Google Fotos",
])
def test_blosse_google_erwaehnung_ist_kein_auftrag(frage):
    assert modus(frage)[0] == "off"


@pytest.mark.parametrize("frage", ["Google mal Bodo Beispiel", "googel nach Opa Testmann",
                                   "Kannst du Ida Testmann googeln?"])
def test_google_als_verb_bleibt_auftrag(frage):
    assert modus(frage) == ("auto", "")


@pytest.mark.parametrize("web", ["auto", "manual"])
def test_nach_eigenem_werkzeug_keine_websuche_mehr(web):
    """'Welche Personen kennst du?' passiert die Eingangssperre; liefert danach
    personen_liste Namen, darf die nächste Runde die Websuche nicht mehr haben."""
    from types import SimpleNamespace

    from app.services.llm_service import llm_service

    def stueck(content=None, tool_calls=None):
        return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content=content, tool_calls=tool_calls, annotations=None, reasoning_details=None))])

    aufruf = SimpleNamespace(index=0, id="a1", function=SimpleNamespace(
        name="personen_liste", arguments="{}"))
    aufrufe = []

    def create(**kw):
        aufrufe.append(kw["extra_body"])
        if len(aufrufe) == 1:
            return iter([stueck(tool_calls=[aufruf])])
        return iter([stueck("Du kennst Ida.")])

    def hat_web(extra):
        return "plugins" in extra or any(
            t.get("type") == "openrouter:web_search" for t in extra.get("tools") or [])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with mock.patch.object(llm_service, "client", fake), \
         mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                           return_value=True), \
         mock.patch.object(werkzeuge, "ausfuehren",
                           return_value=werkzeuge.Ergebnis("2 bekannte Personen: Ida Testmann")):
        list(llm_service.chat_stream("Welche Personen kennst du?", web_search=web,
                                     no_retention=True, werkzeuge=True))
    assert len(aufrufe) == 2
    assert hat_web(aufrufe[0])          # erste Runde: Eingangssperre ließ die Frage durch
    assert not hat_web(aufrufe[1])      # nach dem Werkzeugergebnis: aus
