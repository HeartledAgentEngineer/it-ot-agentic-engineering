"""Tests: Daemon-Antwort (Track C) ueberlebt das Neuladen der App.

Befund 2026-09-25 (Live-Test Sebastian): Fragt er im Chat eine Aufgabe, die an
den lokalen Hermes geht (Track C = Inbox-Kanal/Daemon), sieht er live Gedanken
und Antwort — nach dem Neuoeffnen der App ist beides weg. Ursache: Die echte
Antwort kommt spaeter aus ~/hermes_inbox/antworten.jsonl und wurde NIE in den
GESPEICHERTEN Verlauf geschrieben.

Fix: Der Poll-Endpunkt GET /api/auftraege/{id}/chat uebernimmt die fertige
Daemon-Antwort GENAU EINMAL in den verknuepften Verlauf (Merker im
Auftragseintrag -> kein Duplikat bei mehrfachem Poll).
"""
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import chat_verlauf  # noqa: E402
from app.services.auftrag_service import auftrag_service  # noqa: E402
from app.services.hermes_local import lese_daemon_antwort  # noqa: E402
from app.router.auftraege import auftrag_chat_ausgabe  # noqa: E402

# WICHTIG: app.router.chat ruft beim Import chat_verlauf.init(...) auf und laedt
# dabei den echten Verlauf von der Platte — das wuerde die Test-Gespraeche
# ueberschreiben. Deshalb hier einmal VOR den Fixtures importieren; der
# spaetere Lazy-Import (auftrag_service._in_verlauf_anhaengen) ist dann ein No-op.
from app.router import chat as _router_chat  # noqa: E402,F401

ANTWORT = "Klar: Ich habe den Knopf eingebaut und den Test ausgefuehrt."


@pytest.fixture()
def umgebung(tmp_path, monkeypatch):
    """Eigenes Auftragsbuch + eigener Verlauf + eigene Inbox (kein echtes HOME)."""
    buch = tmp_path / "auftraege.json"
    inbox = tmp_path / "hermes_inbox"
    inbox.mkdir()
    monkeypatch.setattr(auftrag_service, "_pfad", buch)
    monkeypatch.setenv("HERMES_INBOX_DIR", str(inbox))
    chat_verlauf.conversations.clear()
    chat_verlauf.summarys.clear()
    chat_verlauf.setze_memory_extractor(None)
    chat_verlauf.init(
        verlauf_datei=str(tmp_path / "conversations.json"),
        persist_dir=str(tmp_path / "persist"),
    )
    chat_verlauf.conversations["conv_code"] = []
    yield {"buch": buch, "inbox": inbox, "tmp": tmp_path}
    chat_verlauf.conversations.clear()


def _buch_schreiben(buch, eintraege):
    buch.write_text(json.dumps(eintraege, ensure_ascii=False), encoding="utf-8")


def _antwort_schreiben(inbox, auftrag_id, text):
    with (inbox / "antworten.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(
            {"auftrag_id": auftrag_id, "text": text}, ensure_ascii=False) + "\n")


def _auftrag(aid, **rest):
    basis = {
        "id": aid, "auftrag": "Baue Knopf X ein", "status": "fertig",
        "ergebnis": None, "status_meldungen": [], "rueckfragen": [],
    }
    basis.update(rest)
    return basis


def _verlauf_texte(cid="conv_code"):
    return [e.get("content") for e in chat_verlauf.conversations.get(cid, [])]


# ---------------------------------------------------------------------------
# 1) Antwort wird angehaengt
# ---------------------------------------------------------------------------
def test_antwort_wird_in_verlauf_angehaengt(umgebung):
    aid = "aaaaaaaa-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid, conversation_id="conv_code")])
    _antwort_schreiben(umgebung["inbox"], aid, ANTWORT)
    # Die Runde steht bisher nur als Platzhalter im Verlauf.
    chat_verlauf.conversations["conv_code"] = [
        {"role": "user", "content": "Baue Knopf X ein", "zeit": "t"},
        {"role": "assistant", "content": "➡️ Weitergeleitet an: Hermes (Handy)",
         "zeit": "t"},
    ]

    daten = auftrag_chat_ausgabe(aid)

    assert _verlauf_texte()[-1] == ANTWORT
    assert "uebernommen" in daten["verlauf_persistenz"]


# ---------------------------------------------------------------------------
# 2) Zweimaliges Abfragen erzeugt KEIN Duplikat
# ---------------------------------------------------------------------------
def test_zweimaliges_abfragen_kein_duplikat(umgebung):
    aid = "bbbbbbbb-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid, conversation_id="conv_code")])
    _antwort_schreiben(umgebung["inbox"], aid, ANTWORT)

    auftrag_chat_ausgabe(aid)
    zweite = auftrag_chat_ausgabe(aid)

    assert _verlauf_texte().count(ANTWORT) == 1
    assert "kein Duplikat" in zweite["verlauf_persistenz"]
    # Merker steht im Buch (Reload-/Neustart-fest).
    buch = json.loads(umgebung["buch"].read_text(encoding="utf-8"))
    assert buch[0]["antwort_verlauf_merker"]["geschrieben"] is True


# ---------------------------------------------------------------------------
# 3) Auftrag ohne Gespraechsverknuepfung verursacht keinen Fehler
# ---------------------------------------------------------------------------
def test_auftrag_ohne_gespraech_kein_fehler(umgebung):
    aid = "cccccccc-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid)])  # ohne conversation_id
    _antwort_schreiben(umgebung["inbox"], aid, ANTWORT)

    daten = auftrag_chat_ausgabe(aid)  # darf NICHT werfen

    assert chat_verlauf.conversations["conv_code"] == []
    assert "Kein Gespraech" in daten["verlauf_persistenz"]


# ---------------------------------------------------------------------------
# 4) Leere Antwort ergibt Klartext statt einer leeren Nachricht
# ---------------------------------------------------------------------------
def test_leere_antwort_ergibt_klartext(umgebung):
    aid = "dddddddd-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid, conversation_id="conv_code")])
    _antwort_schreiben(umgebung["inbox"], aid, "")   # Eintrag vorhanden, Text leer

    auftrag_chat_ausgabe(aid)

    letzte = _verlauf_texte()[-1]
    assert letzte and letzte.strip(), "es darf KEINE leere Nachricht entstehen"
    assert "ohne Text geantwortet" in letzte


# ---------------------------------------------------------------------------
# 5) Reihenfolge: erst die Frage, dann die Antwort
# ---------------------------------------------------------------------------
def test_reihenfolge_frage_dann_antwort(umgebung):
    aid = "eeeeeeee-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid, conversation_id="conv_code")])
    _antwort_schreiben(umgebung["inbox"], aid, ANTWORT)
    chat_verlauf.conversations["conv_code"] = [
        {"role": "user", "content": "Baue Knopf X ein", "zeit": "t"},
    ]

    auftrag_chat_ausgabe(aid)
    # Noch ein zweiter Auftrag im SELBEN Gespraech — Reihenfolge muss stimmen.
    aid2 = "eeeeeeee-5555-6666-7777-444444444444"
    _buch_schreiben(umgebung["buch"], [
        _auftrag(aid, conversation_id="conv_code"),
        _auftrag(aid2, conversation_id="conv_code"),
    ])
    _antwort_schreiben(umgebung["inbox"], aid2, "Zweite Antwort.")
    auftrag_chat_ausgabe(aid2)

    rollen = [(e["role"], e["content"])
              for e in chat_verlauf.conversations["conv_code"]]
    assert rollen[0] == ("user", "Baue Knopf X ein")
    assert rollen[1] == ("assistant", ANTWORT)
    assert rollen[2] == ("assistant", "Zweite Antwort.")


# ---------------------------------------------------------------------------
# 6) Ohne Daemon-Antwort bleibt der Platzhalter (nichts wird erfunden)
# ---------------------------------------------------------------------------
def test_ohne_daemon_antwort_bleibt_platzhalter(umgebung):
    aid = "ffffffff-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid, conversation_id="conv_code",
                                                 status="laeuft")])
    platzhalter = "➡️ Weitergeleitet an: Hermes (Handy)"
    chat_verlauf.conversations["conv_code"] = [
        {"role": "user", "content": "Baue Knopf X ein", "zeit": "t"},
        {"role": "assistant", "content": platzhalter, "zeit": "t"},
    ]

    daten = auftrag_chat_ausgabe(aid)  # keine antworten.jsonl vorhanden

    assert _verlauf_texte() == ["Baue Knopf X ein", platzhalter]
    assert "Noch keine Daemon-Antwort" in daten["verlauf_persistenz"]


# ---------------------------------------------------------------------------
# 7) Abgebrochener/fehlgeschlagener Auftrag: klare Meldung, kein Absturz
# ---------------------------------------------------------------------------
def test_abgebrochener_auftrag_klare_meldung(umgebung):
    aid = "99999999-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(
        aid, conversation_id="conv_code", status="fehler",
        ergebnis="Abgebrochen – Aufgabe wird vom LLM beantwortet.")])

    daten = auftrag_chat_ausgabe(aid)

    assert "abgebrochen" in daten["verlauf_persistenz"].lower()
    # Nichts wurde erfunden.
    assert chat_verlauf.conversations["conv_code"] == []


# ---------------------------------------------------------------------------
# 8) Fehlende Antwortdatei: kein Fehler
# ---------------------------------------------------------------------------
def test_fehlende_antwortdatei_ist_harmlos(umgebung):
    aid = "12341234-1111-2222-3333-444444444444"
    _buch_schreiben(umgebung["buch"], [_auftrag(aid, conversation_id="conv_code")])
    assert not (umgebung["inbox"] / "antworten.jsonl").exists()

    daten = auftrag_chat_ausgabe(aid)
    assert "Noch keine Daemon-Antwort" in daten["verlauf_persistenz"]


# ---------------------------------------------------------------------------
# 9) Leser: None (kein Eintrag) vs. "" (leerer Text) — wichtig fuer die
#    Unterscheidung "nichts erfinden" / "klare Meldung".
# ---------------------------------------------------------------------------
def test_leser_unterscheidet_kein_eintrag_und_leer(umgebung):
    aid = "aaaa1111-1111-2222-3333-444444444444"
    inbox = umgebung["inbox"]

    assert lese_daemon_antwort(aid) is None           # Datei fehlt

    _antwort_schreiben(inbox, aid, "")
    assert lese_daemon_antwort(aid) == ""             # Eintrag, aber leer

    _antwort_schreiben(inbox, aid, ANTWORT)
    _antwort_schreiben(inbox, aid, "Neueste Fassung")
    assert lese_daemon_antwort(aid) == "Neueste Fassung"   # letzte gewinnt


def test_leser_ueberspringt_kaputte_zeilen(umgebung):
    aid = "bbbb1111-1111-2222-3333-444444444444"
    pfad = umgebung["inbox"] / "antworten.jsonl"
    pfad.write_text(
        "{das ist kein json}\n"
        + json.dumps({"auftrag_id": aid, "text": ANTWORT}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    assert lese_daemon_antwort(aid) == ANTWORT
    assert lese_daemon_antwort("unbekannte-id") is None
