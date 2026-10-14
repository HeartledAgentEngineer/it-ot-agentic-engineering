"""Tests: Websuche mit Namensverbot (Plan websuche-namensverbot, Fassung 7, 14.10.2026).

Offline, nur erfundene Namen. Prüft die Namensprüfung (``websuche_schutz``), die
Namensquellen (``werkzeuge.bekannte_namen_streng``), den kontextfreien Suchaufruf
(``web_suche``), die Verdrahtung in ``llm_service`` und ``/chat``/``/stream``, den
Systemhinweis und den DSML-Filter der Schleife.

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
from types import SimpleNamespace
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.models import ChatRequest  # noqa: E402
from app.services import web_suche  # noqa: E402
from app.services import websuche_schutz as ws  # noqa: E402
from app.services import werkzeug_schleife as schleife  # noqa: E402
from app.services import werkzeuge  # noqa: E402

BESTAND = ["Ida Beispiel", "Bo Testmann", "Sebastian Beispiel", "Jörg Müller", "Oskar"]
KONTAKTE = ["Erika Fremdmann", "Pizza Express", "Arbeit"]


def bestand():
    return ws.bestand_bauen(BESTAND, KONTAKTE)


def treffer(text, nachricht=""):
    b = bestand()
    return ws.enthaelt_namen(text, b, ws.freigaben(nachricht, b))


# --- Namensprüfung ---------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Ida Beispiel Wohnort", "Was macht Ida", "bo testmann Firma", "Bo heute",
    "Idas Firma", "Testmanns Arbeitgeber", "Ida's Hund", "Oskar Hamburg",
    "Mueller Bauunternehmen",            # Umschrift: bekannt ist „Müller“
])
def test_bekannte_namen_sperren(text):
    assert treffer(text) is True


@pytest.mark.parametrize("text", [
    "Wetter morgen Hamburg", "Wie lange brauche ich zu Oma und Opa nach Lübeck",
    "Öffnungszeiten Baumarkt Eimsbüttel", "Ich habe eine Idee", "Erika Mustermann Professorin",
    "Pizza Lieferdienst Altona",        # Kontakt „Pizza Express“ zählt nur als volle Folge
    "Arbeit finden Hamburg",            # Einzelwort-Kontakt zählt nicht
])
def test_allgemeines_orte_und_fremde_namen_gehen_durch(text):
    assert treffer(text) is False


def test_kontakt_zaehlt_als_volle_folge_vorname_allein_nicht():
    assert treffer("Erika Fremdmann Adresse") is True
    assert treffer("Erika Fremdmanns Adresse") is True
    assert treffer("Erika Adresse") is False          # Grenze: Vorname aus Kontakt


def test_umschrift_in_beide_richtungen_andere_varianten_nicht():
    b = ws.bestand_bauen(["Kai Mueller"])
    assert ws.enthaelt_namen("Müller", b) is True
    assert treffer("Jörg") is True and treffer("Joerg") is True
    assert treffer("Myller") is False                 # Grenze: andere Umschrift


def test_kurze_teile_ab_zwei_zeichen_einzelne_buchstaben_nicht():
    b = ws.bestand_bauen(["Bo T Testmann"])
    assert ws.enthaelt_namen("Bo", b) is True
    assert ws.enthaelt_namen("T", b) is False


def test_liste_none_sperrt_und_leere_liste_nicht():
    assert ws.enthaelt_namen("Wetter morgen", None) is True
    assert ws.enthaelt_namen("Ida Beispiel", ws.bestand_bauen([])) is False


def test_kaputte_eintraege_werfen_nicht():
    b = ws.bestand_bauen([None, "", 42, "Ida"], [None, 7])
    assert ws.enthaelt_namen("Ida", b) is True


def test_log_nennt_keinen_text(caplog):
    with caplog.at_level(logging.INFO, logger="app.services.websuche_schutz"):
        treffer("Ida Beispiel Wohnort")
    assert "abgelehnt" in caplog.text
    assert "Ida" not in caplog.text and "Wohnort" not in caplog.text


# --- Freigaben (nur aus Sebastians eigener Nachricht) ----------------------

def test_fremder_voller_name_mit_bekanntem_vornamen_nur_mit_eigenem_auftrag():
    assert treffer("Sebastian Fremdmann Professor") is True
    assert treffer("Sebastian Fremdmann Professor",
                   "Such im Internet nach Sebastian Fremdmann") is False
    assert treffer("Sebastian Fremdmann", "Google mal Sebastian Fremdmann") is False


def test_vom_modell_erfundener_auftrag_gibt_keine_freigabe():
    # Nutzer fragt nach dem bekannten Sebastian; das Modell formuliert selbst einen Auftrag.
    assert treffer("Such im Internet nach Sebastian Fremdmann",
                   "Was macht Sebastian Beispiel?") is True


def test_ida_geburtstag_mit_eigenem_auftrag_ist_gewollt():
    assert treffer("Ida Geburtstag") is True
    assert treffer("Ida Geburtstag", "Such im Internet nach Ida Geburtstag") is False


@pytest.mark.parametrize("nachricht,text", [
    ("Such im Internet nach Ida Beispiel Fremdmann", "Ida Beispiel Fremdmann"),   # voller Name
    ("Such im Internet nach Klara Testmann", "Klara Testmann"),                   # Nachname
    ("Such im Internet nach Ida Bo", "Ida Bo"),                                   # nur Bekannte
    ("Such nicht im Internet nach Sebastian Fremdmann", "Sebastian Fremdmann"),   # Sperrwort
    ("Sebastian Fremdmann nutzt Google Drive", "Sebastian Fremdmann"),            # kein Auftrag
])
def test_ungueltige_freigaben(nachricht, text):
    assert treffer(text, nachricht) is True


def test_suchauftrag_erkennung():
    assert ws.ist_suchauftrag("Such im Internet nach dem Wetter")
    assert ws.ist_suchauftrag("Kannst du das googeln?")
    assert not ws.ist_suchauftrag("Opa spricht über Google Drive")
    assert not ws.ist_suchauftrag("Lass das Googeln")


# --- Namensquellen ---------------------------------------------------------

@pytest.fixture()
def quellen(tmp_path, monkeypatch):
    """Alle Namensquellen in tmp_path - nie die echten Dateien."""
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    monkeypatch.setattr("app.services.gesichter_service.KATALOG_DATEI",
                        tmp_path / "gesichter_katalog.json")
    werkzeuge._NAMEN_CACHE.clear()
    yield tmp_path
    werkzeuge._NAMEN_CACHE.clear()


def _datei(ordner, name, inhalt):
    (ordner / name).write_text(
        inhalt if isinstance(inhalt, str) else json.dumps(inhalt), encoding="utf-8")


def _kontaktdatei(ordner, inhalt):
    _datei(ordner, "whatsapp_zuordnung.json", inhalt)


def test_streng_liest_alle_quellen(quellen):
    _datei(quellen, "personen_bestaetigt.json", {"bestaetigt": {"P1": "Ida Beispiel"}})
    _datei(quellen, "personen_vorgaben.json",
           {"gleich": [], "zugeordnet": [{"bild_id": "1", "name": "Rolf Zuordner"}]})
    _datei(quellen, "personen_profile.json", {"profile": {"Gerda Profil": {"notizen": []}}})
    _datei(quellen, "gesichter_katalog.json", {"personen": [{"name": "Bo Testmann"}]})
    _kontaktdatei(quellen, {"chats": [
        {"telefonbuch_namen": ["Erika Fremdmann"], "whatsapp_name": "Udo Testmann",
         "teilnehmer": [{"name": "Lea Muster"}, {"name": None}]}]})
    b = werkzeuge.bekannte_namen_streng()
    for name in ("Ida", "Zuordner", "Gerda", "Bo", "Erika Fremdmann", "Udo Testmann",
                 "Lea Muster"):
        assert ws.enthaelt_namen(name, b), name


def test_streng_ohne_dateien_ist_leer_aber_lesbar(quellen):
    b = werkzeuge.bekannte_namen_streng()
    assert b is not None and b.anzahl() == {"teile": 0, "volle": 0}


def test_streng_leere_aber_gueltige_dateien_sind_kein_fehler(quellen):
    _datei(quellen, "personen_bestaetigt.json", {"bestaetigt": {}})
    _datei(quellen, "personen_vorgaben.json", {"gleich": [], "verschieden": []})
    _datei(quellen, "personen_profile.json", {"profile": {}})
    _datei(quellen, "gesichter_katalog.json", {"personen": []})
    _kontaktdatei(quellen, {"chats": []})
    assert werkzeuge.bekannte_namen_streng() is not None


@pytest.mark.parametrize("name,inhalt", [
    # Codex-Ergebnisprüfung R2/1: das Quiz sortiert beschädigte Einträge still aus.
    ("personen_bestaetigt.json", "{kaputt"),
    ("personen_bestaetigt.json", {"bestaetigt": ["Ida Beispiel"]}),
    ("personen_bestaetigt.json", {"bestaetigt": {"P1": 42}}),
    ("personen_bestaetigt.json", {"andere": {}}),
    ("personen_vorgaben.json", {"zugeordnet": {"name": "Ida"}}),
    ("personen_vorgaben.json", {"zugeordnet": ["Ida"]}),
    ("personen_vorgaben.json", {"zugeordnet": [{"name": 7}]}),
    ("personen_vorgaben.json", ["kein Objekt"]),
    ("personen_profile.json", {"profile": ["Ida"]}),
    ("personen_profile.json", "{kaputt"),
    # R1/1 und R2/2: alter Katalog kaputt, falsche Form oder beschädigte Einträge.
    ("gesichter_katalog.json", "{kaputt"),
    ("gesichter_katalog.json", '"nur Text"'),
    ("gesichter_katalog.json", {"andere": 1}),
    ("gesichter_katalog.json", {"personen": ["Ida Beispiel"]}),
    ("gesichter_katalog.json", [{"name": ["Ida"]}]),
])
def test_streng_beschaedigte_personenquelle_ergibt_none(quellen, name, inhalt):
    _datei(quellen, name, inhalt)
    assert werkzeuge.bekannte_namen_streng() is None


@pytest.mark.parametrize("chat", [
    {"telefonbuch_namen": "Erika Fremdmann"},          # Text statt Liste (R1/2)
    {"telefonbuch_namen": [42]},
    {"whatsapp_name": ["Udo Testmann"]},
    {"teilnehmer": {"name": "Lea Muster"}},            # Objekt statt Liste
    {"teilnehmer": ["Lea Muster"]},
    {"teilnehmer": [{"name": 7}]},
    "kein Objekt",
])
def test_streng_beschaedigte_kontaktfelder_ergeben_none(quellen, chat):
    _kontaktdatei(quellen, {"chats": [chat]})
    assert werkzeuge.bekannte_namen_streng() is None


@pytest.mark.parametrize("inhalt", ["{kaputt", {"chats": "x"}, ["x"]])
def test_streng_kaputte_kontaktdatei_ergibt_none(quellen, inhalt):
    _kontaktdatei(quellen, inhalt)
    assert werkzeuge.bekannte_namen_streng() is None


def test_streng_wurf_ergibt_none(quellen):
    with mock.patch.object(werkzeuge, "_personen_namen_streng", side_effect=OSError("weg")):
        assert werkzeuge.bekannte_namen_streng() is None


def test_bekannte_namen_bleibt_fuer_andere_verwender(quellen):
    with mock.patch("app.services.gruppen_quiz.personen",
                    return_value={"ok": True, "personen": [{"name": "Ida Beispiel"}]}):
        assert werkzeuge.bekannte_namen() == ["Ida Beispiel"]


def test_systemhinweis_enthaelt_namensverbot():
    assert "nie nach Personennamen" in werkzeuge.SYSTEM_HINWEIS


# --- Suchaufruf (kontextfrei) ----------------------------------------------

def _fake_llm(aufrufe, text="Morgen 14 Grad.", quellen=None):
    from app.services.llm_service import llm_service

    def create(**kw):
        aufrufe.append(kw)
        nachricht = SimpleNamespace(content=text, annotations=quellen or [
            {"type": "url_citation", "url_citation": {"url": "https://wetter.example",
                                                      "title": "Wetter"}}])
        return SimpleNamespace(choices=[SimpleNamespace(message=nachricht)])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return [mock.patch.object(llm_service, "client", fake),
            mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                              return_value=True),
            mock.patch.object(werkzeuge, "bekannte_namen_streng", return_value=bestand())]


def _mit(patches):
    class _Kontext:
        def __enter__(self):
            for p in patches:
                p.start()

        def __exit__(self, *a):
            for p in reversed(patches):
                p.stop()
    return _Kontext()


def test_suche_ohne_namen_ist_kontextfrei():
    aufrufe = []
    with _mit(_fake_llm(aufrufe)):
        r = web_suche.suchen("Wetter morgen Hamburg")
    assert r.ok and r.quellen[0]["url"] == "https://wetter.example"
    assert len(aufrufe) == 1
    kw = aufrufe[0]
    assert kw["messages"] == [{"role": "user", "content": "Wetter morgen Hamburg"}]
    assert kw["extra_body"]["plugins"][0]["id"] == "web"
    assert kw["extra_body"]["provider"]["data_collection"] == "deny"


def test_suche_mit_namen_geht_nicht_ins_netz():
    aufrufe = []
    with _mit(_fake_llm(aufrufe)):
        r = web_suche.suchen("Ida Beispiel Wohnort")
    assert r.abgelehnt and not r.ok and aufrufe == []
    assert "Personennamen" in r.text


def test_suche_bei_unlesbarer_liste_geht_nicht_ins_netz():
    aufrufe = []
    patches = _fake_llm(aufrufe)
    patches[-1] = mock.patch.object(werkzeuge, "bekannte_namen_streng", return_value=None)
    with _mit(patches):
        r = web_suche.suchen("Wetter morgen")
    assert r.abgelehnt and aufrufe == []


# --- Werkzeug-Weg in llm_service --------------------------------------------

def _stueck(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
        content=content, tool_calls=tool_calls, annotations=None, reasoning_details=None))])


def _werkzeug_lauf(web, anfrage, nutzer="Frage"):
    """Runde 1: Modell ruft web_suche(anfrage); Runde 2: Antwort."""
    from app.services.llm_service import llm_service

    haupt, such = [], []
    aufruf = SimpleNamespace(index=0, id="a1", function=SimpleNamespace(
        name="web_suche", arguments=json.dumps({"anfrage": anfrage})))

    def create(**kw):
        if kw.get("stream"):
            haupt.append(kw)
            if len(haupt) == 1:
                return iter([_stueck(tool_calls=[aufruf])])
            return iter([_stueck("fertig")])
        such.append(kw)
        nachricht = SimpleNamespace(content="Treffer", annotations=[
            {"type": "url_citation", "url_citation": {"url": "https://x.example", "title": "X"}}])
        return SimpleNamespace(choices=[SimpleNamespace(message=nachricht)])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with mock.patch.object(llm_service, "client", fake), \
         mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                           return_value=True), \
         mock.patch.object(werkzeuge, "bekannte_namen_streng", return_value=bestand()):
        ereignisse = list(llm_service.chat_stream(nutzer, web_search=web, no_retention=True,
                                                  werkzeuge=True, nutzer_nachricht=nutzer))
    return ereignisse, haupt, such


def _namen(extra):
    return [t.get("function", {}).get("name") for t in extra.get("tools") or []]


def _hat_serversuche(extra):
    return "plugins" in extra or any(
        t.get("type") == "openrouter:web_search" for t in extra.get("tools") or [])


@pytest.mark.parametrize("web", ["off", "manual", "auto"])
def test_hauptaufruf_sucht_nie_selbst(web):
    _, haupt, _ = _werkzeug_lauf(web, "Wetter morgen")
    assert haupt and not any(_hat_serversuche(k["extra_body"]) for k in haupt)


def test_auto_bietet_web_suche_an_und_sucht_ohne_namen():
    ereignisse, haupt, such = _werkzeug_lauf("auto", "Wetter morgen Hamburg")
    assert "web_suche" in _namen(haupt[0]["extra_body"])
    assert len(such) == 1
    assert such[0]["messages"] == [{"role": "user", "content": "Wetter morgen Hamburg"}]
    assert any(e.get("sources") for e in ereignisse)


@pytest.mark.parametrize("web", ["off", "manual"])
def test_off_und_manual_bieten_web_suche_nicht_an_und_suchen_nicht(web):
    ereignisse, haupt, such = _werkzeug_lauf(web, "Wetter morgen")
    assert "web_suche" not in _namen(haupt[0]["extra_body"])
    assert such == []      # auch ein erfundener Aufruf sucht nicht


def test_auto_mit_namen_sucht_nicht_und_zeigt_status():
    ereignisse, _, such = _werkzeug_lauf("auto", "Ida Beispiel Wohnort")
    assert such == []
    assert any(e.get("status") == web_suche.STATUS_ABGELEHNT for e in ereignisse)


def test_auto_freigabe_nur_aus_der_nutzernachricht():
    _, _, such = _werkzeug_lauf("auto", "Sebastian Fremdmann Professor",
                                nutzer="Such im Internet nach Sebastian Fremdmann")
    assert len(such) == 1
    _, _, such = _werkzeug_lauf("auto", "Such im Internet nach Sebastian Fremdmann",
                                nutzer="Was macht Sebastian Beispiel?")
    assert such == []


def test_auto_nach_persoenlichem_werkzeug_bleibt_suche_moeglich_aber_ohne_namen():
    """Nach personen_liste darf das Modell suchen - nur eben nicht mit Namen."""
    from app.services.llm_service import llm_service

    haupt, such = [], []
    runden = [
        [_stueck(tool_calls=[SimpleNamespace(index=0, id="p1", function=SimpleNamespace(
            name="personen_liste", arguments="{}"))])],
        [_stueck(tool_calls=[SimpleNamespace(index=0, id="w1", function=SimpleNamespace(
            name="web_suche", arguments=json.dumps({"anfrage": "Ida Beispiel Firma"})))])],
        [_stueck("fertig")],
    ]

    def create(**kw):
        if kw.get("stream"):
            haupt.append(kw)
            return iter(runden.pop(0))
        such.append(kw)
        raise AssertionError("darf nicht suchen")

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with mock.patch.object(llm_service, "client", fake), \
         mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                           return_value=True), \
         mock.patch.object(werkzeuge, "bekannte_namen_streng", return_value=bestand()), \
         mock.patch.object(werkzeuge, "ausfuehren",
                           return_value=werkzeuge.Ergebnis("Ida Beispiel, Bo Testmann")):
        list(llm_service.chat_stream("Welche Personen kennst du?", web_search="auto",
                                     no_retention=True, werkzeuge=True,
                                     nutzer_nachricht="Welche Personen kennst du?"))
    assert len(haupt) == 3 and such == []
    assert "web_suche" in _namen(haupt[1]["extra_body"])


def test_register_platzhalter_sucht_nie():
    r = werkzeuge.ausfuehren("web_suche", {"anfrage": "Wetter"})
    assert r.ok is False and "aus" in r.text


# --- Verdrahtung /stream und /chat -----------------------------------------

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


def _treffer(text="Morgen sonnig", quellen=None, abgelehnt=False):
    return web_suche.Suchergebnis(not abgelehnt, text, quellen or [], abgelehnt)


def _stream(nachricht, web, suche):
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
        mock.patch.object(chat, "_hole_kontext_summary", return_value=("", None)),
        mock.patch.object(chat, "_gesichter_merke", return_value=""),
        mock.patch.dict(chat.conversations, {"conv_websuche_test": []}),
        mock.patch.object(chat, "_get_or_create_conversation", return_value="conv_websuche_test"),
        mock.patch.object(web_suche, "suchen", side_effect=suche),
    ]
    for p in patches:
        p.start()
    try:
        req = ChatRequest(message=nachricht, force_agent=True, archiv=False, werkzeuge=True,
                          web_search=web, conversation_id="conv_websuche_test")
        return _sse_lesen(asyncio.run(chat.chat_stream(req))), aufgerufen
    finally:
        for p in reversed(patches):
            p.stop()


def test_stream_manual_sucht_vorab_mit_dem_eigenen_satz():
    gesucht = []

    def suche(anfrage, nachricht=""):
        gesucht.append((anfrage, nachricht))
        return _treffer(quellen=[{"url": "https://w.example", "title": "W"}])

    ereignisse, kw = _stream("Wie wird das Wetter morgen in Hamburg?", "manual", suche)
    assert gesucht == [("Wie wird das Wetter morgen in Hamburg?",
                        "Wie wird das Wetter morgen in Hamburg?")]
    assert "[Websuche zu deiner Frage]" in kw["user_message"]
    assert kw["nutzer_nachricht"] == "Wie wird das Wetter morgen in Hamburg?"
    assert any(e.get("sources") for e in ereignisse)


def test_stream_manual_mit_namen_status_und_keine_notiz():
    ereignisse, kw = _stream("Was macht Ida Beispiel?", "manual",
                             lambda a, n="": _treffer(abgelehnt=True))
    assert any("🔒" in e.get("status", "") for e in ereignisse)
    assert "[Websuche" not in kw["user_message"]


@pytest.mark.parametrize("web", ["auto", "off"])
def test_stream_auto_und_off_suchen_nicht_vorab(web):
    def suche(*a, **k):
        raise AssertionError("keine Vorab-Suche")
    _, kw = _stream("Wetter morgen?", web, suche)
    assert kw["web_search"] == web


def _chat_weg(nachricht, web, suche):
    chat = _chat_modul()
    with mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(chat.memory_service, "retrieve_relevant_memories", return_value=[]), \
         mock.patch.object(chat.memory_service, "extract_and_store_memories", return_value=[]), \
         mock.patch.dict(chat.conversations, {"conv_websuche_test": []}), \
         mock.patch.object(chat, "_get_or_create_conversation", return_value="conv_websuche_test"), \
         mock.patch.object(chat, "_hole_kontext_summary", return_value=("", None)), \
         mock.patch.object(chat, "_archiv_tool", return_value=""), \
         mock.patch.object(chat, "_datei_tool", return_value=("", [])), \
         mock.patch.object(web_suche, "suchen", side_effect=suche), \
         mock.patch.object(chat.llm_service, "chat", return_value=("Antwort", [])) as m_chat:
        req = ChatRequest(message=nachricht, web_search=web, model="deepseek/deepseek-v4-flash")
        antwort = asyncio.run(chat.chat(req))
    return m_chat.call_args.kwargs, antwort


def test_chat_weg_manual_sucht_vorab_und_liefert_quellen():
    kw, antwort = _chat_weg("Wie lange brauche ich zu Oma nach Lübeck?", "manual",
                            lambda a, n="": _treffer(quellen=[{"url": "https://r.example",
                                                                 "title": "R"}]))
    assert "[Websuche zu deiner Frage]" in kw["user_message"]
    assert antwort.sources[0].url == "https://r.example"


def test_chat_weg_auto_sucht_nicht():
    def suche(*a, **k):
        raise AssertionError("keine Suche")
    kw, _ = _chat_weg("Wetter morgen?", "auto", suche)
    assert "[Websuche" not in kw["user_message"]


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
    from app.services.llm_service import llm_service

    aufrufe = []

    def create(**kw):
        aufrufe.append(kw)
        if len(aufrufe) == 1:
            return iter([_stueck("<｜DSML｜function_calls>")])
        return iter([_stueck("Antwort ohne Werkzeuge")])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with mock.patch.object(llm_service, "client", fake), \
         mock.patch.object(type(llm_service), "is_configured", new_callable=mock.PropertyMock,
                           return_value=True):
        ereignisse = list(llm_service.chat_stream("Frage", no_retention=True, werkzeuge=True))
    assert len(aufrufe) == 2
    assert _deltas(ereignisse) == "Antwort ohne Werkzeuge"
    assert not _hat_serversuche(aufrufe[1]["extra_body"])
