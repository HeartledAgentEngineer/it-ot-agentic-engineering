"""Konsistenz des Chat-Verlaufs (Fix 2026-09-25).

Sebastian-Befund: „Ich habe den Chat geschlossen, dann einen alten Chat
geöffnet oder einen neuen Chat geöffnet und dann aktualisiert gedrückt — und
dann kam wieder was ganz anderes. Jetzt kommen auch schon wieder Bilder, die
ich irgendwann schon mal hatte."

Diese Tests halten die drei Zusagen fest:
  (i)   gleiche Kennung → gleicher Verlauf (Round-Trip, zweimal geladen),
  (ii)  unbekannte Kennung → klarer Fehler, KEIN fremder Verlauf,
  (iii) zwei Chats (conv_main / conv_code) bleiben getrennt,
  (iv)  Reihenfolge stabil, keine Dublette nach erneutem Laden,
  (v)   ein Bildpfad bleibt an SEINER Nachricht (kein „letztes Bild").

Aufruf (Backend-Ordner):
    .venv/Scripts/python -m pytest tests/test_verlauf_konsistenz.py -q

WICHTIG: Die Verlaufsdatei wird in einen Temp-Ordner umgebogen — die echten
Daten (chroma_data/conversations.json) werden nie angefasst.
"""
import asyncio
import importlib
import json
import os
import sys
from unittest import mock

import pytest
from fastapi import HTTPException

from app.models import ChatRequest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


def _req(nachricht: str) -> ChatRequest:
    """Minimale ChatRequest für die Endpunkt-Tests.

    force_agent=True überspringt die Hermes-/Auftrags-Weiche: Der Test prüft
    den LLM-Weg, nicht die Delegation.
    """
    return ChatRequest(message=nachricht, model="deepseek/deepseek-v4-flash",
                       web_search="off", force_agent=True)


@pytest.fixture()
def chat_mod(tmp_path):
    """chat-Modul mit isoliertem, leerem Verlauf (keine echten Daten!)."""
    if "app.router.chat" in sys.modules:
        del sys.modules["app.router.chat"]
    mod = importlib.import_module("app.router.chat")
    mod.conversations.clear()
    mod.chat_verlauf.summarys.clear()
    mod._bild_cache.clear()
    # Persistenz NUR in den Temp-Ordner schreiben (Datenverlust-Schutz: die
    # echte conversations.json bleibt unberührt).
    mod.chat_verlauf._verlauf_datei = str(tmp_path / "conversations.json")
    mod.chat_verlauf._persist_dir = str(tmp_path)
    yield mod
    mod.conversations.clear()
    mod._bild_cache.clear()


def _msgs(mod, cid):
    return asyncio.run(mod.get_conversation(cid))["messages"]


# ── (i) gleiche Kennung → gleicher Verlauf ────────────────────────────────
def test_gleiche_id_gleicher_verlauf(chat_mod):
    """Zweimal laden mit derselben Kennung liefert exakt denselben Verlauf."""
    mod = chat_mod
    mod.conversations["conv_main"] = []
    mod.verlauf_nachricht_anhaengen("conv_main", "user", "Frage 1")
    mod._finish_exchange("conv_main", "Frage 1", "Antwort 1")

    erst = asyncio.run(mod.get_conversation("conv_main"))
    zweit = asyncio.run(mod.get_conversation("conv_main"))

    assert erst["id"] == zweit["id"] == "conv_main"
    assert erst["messages"] == zweit["messages"]
    assert [m["content"] for m in erst["messages"]] == ["Frage 1", "Antwort 1"]
    assert len(erst["messages"]) == 2  # keine Dublette durch das zweite Laden


# ── (ii) unbekannte Kennung → klarer Fehler, kein fremder Verlauf ─────────
def test_unbekannte_id_klarer_fehler_ohne_fremden_verlauf(chat_mod):
    """Eine alte/unbekannte Kennung (z. B. conv_8) liefert 404 — NICHT den
    Inhalt von conv_main. Die Fehlerantwort nennt nur Kennung/Zahl/Vorschau
    der vorhandenen Chats, niemals deren Nachrichten."""
    mod = chat_mod
    mod.conversations["conv_main"] = [
        {"role": "user", "content": "GEHEIMER INHALT", "zeit": "2026-09-25T10:00:00+02:00"},
    ]

    with pytest.raises(HTTPException) as fehler:
        asyncio.run(mod.get_conversation("conv_8_alt"))

    assert fehler.value.status_code == 404
    detail = fehler.value.detail
    assert detail["conversation_id"] == "conv_8_alt"
    assert "conv_8_alt" in detail["fehler"]

    roh = json.dumps(detail, ensure_ascii=False)
    # Kein fremder Verlauf in der Fehlerantwort:
    assert "GEHEIMER INHALT" not in roh
    # Aber das Angebot, den richtigen Chat zu öffnen:
    assert [c["id"] for c in detail["bekannte_chats"]] == ["conv_main"]
    assert detail["bekannte_chats"][0]["message_count"] == 1


# ── (ii b) dieselbe Zusage über echtes HTTP ──────────────────────────────
def test_404_ueber_echtes_http_kein_fremder_inhalt(chat_mod):
    """HTTP-Ebene (echter Router, echte JSON-Antwort): unbekannte Kennung
    liefert 404 mit klarer Meldung — und keinen fremden Nachrichteninhalt."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(chat_mod.router)
    client = TestClient(app)

    chat_mod.conversations["conv_main"] = [
        {"role": "user", "content": "GEHEIMER INHALT", "zeit": "2026-09-25T10:00:00+02:00"},
    ]

    antwort = client.get("/api/conversations/conv_8_alt")
    assert antwort.status_code == 404
    koerper = antwort.json()["detail"]
    assert koerper["conversation_id"] == "conv_8_alt"
    assert "existiert nicht" in koerper["fehler"]
    assert "GEHEIMER INHALT" not in antwort.text

    # Der richtige Chat bleibt über HTTP normal erreichbar (kein Nebeneffekt).
    ok = client.get("/api/conversations/conv_main")
    assert ok.status_code == 200
    assert ok.json()["id"] == "conv_main"
    assert [m["content"] for m in ok.json()["messages"]] == ["GEHEIMER INHALT"]


# ── (iii) zwei Chats bleiben getrennt ────────────────────────────────────
def test_zwei_chats_bleiben_getrennt(chat_mod):
    """conv_main und conv_code mischen sich nicht."""
    mod = chat_mod
    mod.conversations["conv_main"] = []
    mod.conversations["conv_code"] = []

    mod._finish_exchange("conv_main", "Hauptfrage", "Hauptantwort")
    mod._finish_exchange("conv_code", "Codefrage", "Codeantwort")

    haupt = _msgs(mod, "conv_main")
    code = _msgs(mod, "conv_code")

    assert [m["content"] for m in haupt] == ["Hauptfrage", "Hauptantwort"]
    assert [m["content"] for m in code] == ["Codefrage", "Codeantwort"]
    assert "Codefrage" not in [m["content"] for m in haupt]
    assert "Hauptfrage" not in [m["content"] for m in code]


# ── (iv) Reihenfolge stabil + keine Dublette nach erneutem Laden ─────────
def test_reihenfolge_und_keine_dublette(chat_mod):
    """Der Fall aus der Praxis: Die User-Nachricht wird beim Stream-Start
    sofort gesichert (mit offen-Markierung), danach kommt eine
    Hermes-Zwischenmeldung, danach der Abschluss. Früher wurde die Frage
    dabei ein ZWEITES Mal angehängt."""
    mod = chat_mod
    mod.conversations["conv_main"] = []

    mod.verlauf_nachricht_anhaengen("conv_main", "user", "Frage 1", offen=True)
    mod.verlauf_nachricht_anhaengen("conv_main", "assistant", "⚙️ Zwischenstand")
    mod._finish_exchange("conv_main", "Frage 1", "Antwort 1")

    erwartet = ["Frage 1", "⚙️ Zwischenstand", "Antwort 1"]
    assert [m["content"] for m in mod.conversations["conv_main"]] == erwartet
    # Die Markierung ist nach dem Abschluss abgeräumt (fertige Runde).
    assert "offen" not in mod.conversations["conv_main"][0]

    # Zwei „Reloads" (zwei Abrufe) ändern nichts an Inhalt oder Reihenfolge.
    a = _msgs(mod, "conv_main")
    b = _msgs(mod, "conv_main")
    assert [m["content"] for m in a] == erwartet
    assert [m["content"] for m in b] == erwartet
    assert [m["content"] for m in a] == [m["content"] for m in b]

    # Zeitstempel sind aufsteigend (append-only) — keine Lücken/Springe.
    zeiten = [m.get("zeit") for m in a]
    assert zeiten == sorted(zeiten)
    assert all(zeiten)


def test_finish_exchange_haengt_nicht_doppelt_an(chat_mod):
    """Idempotenz des Sofort-Sicherns: Die beim Stream-Start gesicherte Frage
    wird beim Abschluss NICHT erneut angehängt — auch nicht, wenn ein Zitat
    (Antwort-Funktion) an der Abschluss-Nachricht hängt."""
    mod = chat_mod
    mod.conversations["conv_main"] = []

    mod.verlauf_nachricht_anhaengen("conv_main", "user", "Frage 1", offen=True)
    mod._finish_exchange("conv_main", "Frage 1", "Antwort 1")
    assert [m["content"] for m in mod.conversations["conv_main"]] == \
        ["Frage 1", "Antwort 1"]

    # Mit Zitat-Anhang („↩ Antworten"): der gespeicherte Text ist der Anfang
    # der neuen Nachricht -> ebenfalls kein zweiter Eintrag.
    mod.conversations["conv_main"] = []
    mod.verlauf_nachricht_anhaengen("conv_main", "user", "Frage 2", offen=True)
    mod._finish_exchange(
        "conv_main", "Frage 2\n\n[Antwort des Nutzers auf diese frühere Nachricht:]",
        "Antwort 2",
    )
    assert [m.get("role") for m in mod.conversations["conv_main"]] == \
        ["user", "assistant"]
    fragen = [m for m in mod.conversations["conv_main"] if m["role"] == "user"]
    assert len(fragen) == 1


# ── (v) Bildpfad bleibt an seiner Nachricht ──────────────────────────────
def test_bildpfad_bleibt_an_seiner_nachricht(chat_mod):
    """Ein Bild hängt an der Nachricht, die es gezeigt hat. Eine spätere
    Antwort OHNE neues Bild trägt keinen Bildpfad."""
    mod = chat_mod
    mod.conversations["conv_main"] = []

    mod._finish_exchange(
        "conv_main", "Zeig das letzte Foto", "Hier:",
        bild_pfad="/storage/shared/DCIM/Camera/foto_1.jpg",
    )
    mod._finish_exchange("conv_main", "Und was ist drauf?", "Person X")

    msgs = mod.conversations["conv_main"]
    assert msgs[1]["bild_pfad"] == "/storage/shared/DCIM/Camera/foto_1.jpg"
    assert len(msgs) == 4
    assert "bild_pfad" not in msgs[3]   # neue Antwort: KEIN altes Bild

    # Und nach dem (erneuten) Laden steht der Pfad weiter an genau dieser
    # Nachricht — nicht an irgendeiner anderen.
    nach_reload = _msgs(mod, "conv_main")
    mit_bild = [i for i, m in enumerate(nach_reload) if m.get("bild_pfad")]
    assert mit_bild == [1]
    assert nach_reload[1]["content"] == "Hier:"


def test_bild_cache_haengt_kein_altes_bild_an_neue_antwort(chat_mod):
    """Der 10-Minuten-RAM-Cache (Option B) darf ein altes Bild NICHT als
    aktuelles Bild einer neuen Frage erscheinen lassen: keine Vorschau, kein
    gespeicherter Pfad an der neuen Nachricht."""
    mod = chat_mod
    mod.conversations["conv_main"] = []
    altes_bild = {"pfad": "/storage/shared/DCIM/Camera/alt.jpg",
                  "data_url": "data:image/jpeg;base64,AAA"}
    mod._bild_cache["conv_main"] = {
        "bilder": [altes_bild],
        "zeit": mod.time.time(),
        "nachricht_index": 0,
    }

    # Dateisuche liefert in dieser Runde NICHTS (reine Fortsetzungsfrage).
    with mock.patch.object(mod, "_archiv_tool", return_value=""), \
         mock.patch.object(mod, "_datei_tool", return_value=("", [])), \
         mock.patch.object(mod, "_verlauf_tool", return_value=""), \
         mock.patch.object(mod, "_gesicht_suche_tool", return_value=""), \
         mock.patch.object(mod.llm_service, "chat",
                           return_value=("Antwort ohne Bild", [])):
        req = _req("Und was war da drauf?")
        resp = asyncio.run(mod.chat(req))

    # Nichts wird ANGEZEIGT (bild_vorschau) und nichts GESPEICHERT (bild_pfad):
    assert resp.bild_vorschau is None
    assert resp.bild_pfad is None
    assert "bild_pfad" not in mod.conversations["conv_main"][-1]
    # Und die Antwort steht als normale Runde im Verlauf (nichts verschluckt).
    assert [m["content"] for m in mod.conversations["conv_main"]] == [
        "Und was war da drauf?", "Antwort ohne Bild",
    ]


def test_bild_cache_verwerfen(chat_mod):
    """Der Cache lässt sich ganz oder je Chat verwerfen (Verlassen/Start)."""
    mod = chat_mod
    mod._bild_cache["conv_main"] = {"bilder": [], "zeit": mod.time.time()}
    mod._bild_cache["conv_code"] = {"bilder": [], "zeit": mod.time.time()}

    assert mod._bild_cache_verwerfen("conv_main") == 1
    assert "conv_main" not in mod._bild_cache
    assert "conv_code" in mod._bild_cache        # andere Conversation bleibt

    assert mod._bild_cache_verwerfen() == 1      # Rest weg
    assert mod._bild_cache == {}

    # Über den Endpunkt (wie das Frontend ihn ruft):
    mod._bild_cache["conv_main"] = {"bilder": [], "zeit": mod.time.time()}
    antwort = asyncio.run(mod.bild_cache_verwerfen("conv_main"))
    assert antwort == {"verworfen": 1}
