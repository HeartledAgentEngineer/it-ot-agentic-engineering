"""Tests: Der Daemon darf NIE ohne inhaltliche Ausgabe antworten.

Wunsch Sebastian (15.09.2026): Im Coding-Chat kamen nur Statusmeldungen
(„Hermes denkt nach", „Hermes hat geantwortet"), aber **keine inhaltliche
Antwort** — am Ende stand „Ergebnis —". Ursache: Antwort-Zeilen wurden nur
innerhalb des CLI-Kastens `╭─⚕ Hermes ╮` erkannt; kam der Kasten nicht an,
blieb das Ergebnis leer und wurde als „—" geschrieben.
"""
import os
import sys

import json

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import hermes_inbox_daemon as daemon  # noqa: E402


def test_rahmenszeile_erkannt():
    assert daemon._ist_rahmenszeile("╭──────────╮") is True
    assert daemon._ist_rahmenszeile("│  ┊  │") is True
    assert daemon._ist_rahmenszeile("Hallo Welt") is False
    assert daemon._ist_rahmenszeile("") is False


def test_fallback_ohne_zeilen_nennt_klaren_grund():
    """Keine Ausgabe → Klartext-Grund + Log-Hinweis (kein leerer Strich)."""
    text = daemon._roh_fallback([])
    assert "KEINE Ausgabe" in text
    assert "daemon.log" in text
    assert text.strip() not in ("", "—")


def test_fallback_liefert_echte_zeilen_und_ist_gekennzeichnet():
    """Rohausgabe wird geliefert, Rahmen/Noise fliegen raus."""
    zeilen = [
        "╭─⚕ Hermes ────────────╮",
        "Query: baue Knopf X ein",
        "Ich habe den Lebenslauf gelesen und die Stationen extrahiert.",
        "╰──────────────────────╯",
    ]
    text = daemon._roh_fallback(zeilen)
    assert "Ich habe den Lebenslauf gelesen" in text
    assert "Roh" in text, "Rohausgabe muss als solche gekennzeichnet sein"
    assert "╭" not in text and "Query:" not in text


def test_fallback_mit_bloecken_liefert_den_vollen_text_als_antwort():
    """Live-Test 25.09.2026: Der Chat zeigte nur „✅ Hermes hat geantwortet."

    Der echte Text stand ausschließlich in den Zwischenmeldungen (im Chat die
    „🧠 Gedanke"-Blasen); die ANTWORT war bloß der Hinweis „… oben in N Blöcken
    gestreamt." Die Antwort muss den vollständigen Text tragen — die Blöcke
    bleiben als mitlesbare Zwischenmeldungen bestehen.
    """
    zeilen = [
        "╭─⚕ Hermes ────────────╮",
        "Der Index enthält 82774 Nachrichten.",
        "Die Suche fand 735 Treffer zu Fabia.",
        "╰──────────────────────╯",
    ]
    bloecke = []
    text = daemon._roh_fallback(zeilen, block_writer=bloecke.append)
    # Die Antwort trägt den Inhalt selbst …
    assert "82774 Nachrichten" in text
    assert "735 Treffer" in text
    # … und ist nicht bloß ein Hinweis auf die Blöcke.
    assert "gestreamt" not in text
    # Die Zwischenmeldungen gibt es weiterhin.
    assert bloecke, "Zwischenmeldungen müssen erhalten bleiben"
    assert any("82774 Nachrichten" in b for b in bloecke)


def test_antwort_kasten_wird_weiterhin_erkannt():
    """Regression: der normale Weg (Antwort-Kasten) funktioniert unverändert."""
    a = daemon._CliAusgabe()
    assert a.zeile("╭─⚕ Hermes ────╮") == ("keine", "")
    art, text = a.zeile("Hier ist die Antwort.")
    assert art == "antwort"
    assert text == "Hier ist die Antwort."
    assert a.zeile("╰──────────────╯") == ("keine", "")


def test_gedanken_kasten_wird_nicht_zur_antwort():
    """Internes Reasoning darf nicht als Antwort durchschlagen."""
    a = daemon._CliAusgabe()
    a.zeile("┌─ Reasoning ──────────┐")
    art, _ = a.zeile("Let me think about this carefully")
    assert art in ("keine", "gedanke")
    assert art != "antwort"


def test_fallback_ohne_writer_liefert_alles_ungekuerzt():
    """Ohne block_writer kommt die KOMPLETTE Rohausgabe zurück (nicht gekürzt)."""
    zeilen = [f"Zeile {i}" for i in range(30)]

    text = daemon._roh_fallback(zeilen)

    assert "Zeile 0" in text and "Zeile 29" in text, "nichts darf verloren gehen"
    assert "gekürzt" not in text and "gekuerzt" not in text


def test_fallback_streamt_in_zeitbloecken(monkeypatch):
    """Mit block_writer kommt die Ausgabe in Blöcken (mitlesbar, Reihenfolge stimmt)."""
    monkeypatch.setattr(daemon, "ROH_BLOCK_PAUSE_S", 0)   # Test soll schnell sein
    zeilen = [f"Zeile {i}" for i in range(30)]
    bloecke = []

    schluss = daemon._roh_fallback(zeilen, block_writer=bloecke.append)

    # 30 Zeilen / 4 pro Block = 1 Kopfblock + 8 Inhaltsblöcke
    inhalt = [b for b in bloecke if b.startswith("Zeile")]
    assert len(inhalt) == 8, f"erwartet 8 Blöcke, war {len(inhalt)}"
    assert inhalt[0].splitlines()[0] == "Zeile 0", "Reihenfolge muss stimmen"
    assert inhalt[-1].splitlines()[-1] == "Zeile 29", "letzte Zeile muss dabei sein"
    assert all(len(b.splitlines()) <= daemon.ROH_BLOCK_ZEILEN for b in inhalt)
    # Die ANTWORT trägt den vollständigen Text selbst (25.09.2026) — vorher war
    # sie nur der Hinweis „… oben in N Blöcken gestreamt" und der Chat zeigte
    # „Hermes hat geantwortet" ohne inhaltliche Antwort.
    assert "Zeile 0" in schluss, "Antwort muss den Inhalt selbst tragen"
    assert "Zeile 29" in schluss, "Antwort muss vollständig sein"
    assert "gestreamt" not in schluss, "kein bloßer Hinweis auf die Blöcke"


def test_haeppchen_groesse_ist_klein():
    """Zwischenmeldungen kommen in kleinen Häppchen (mitlesbar, kein Block)."""
    assert daemon.FLUSH_MAX_ZEILEN <= 4
    assert daemon.FLUSH_S <= 1.0
    assert daemon.ROH_BLOCK_ZEILEN <= 6, "Rohausgabe-Blöcke müssen klein bleiben"


def test_stream_json_erkennt_antwort_und_abschluss():
    """Strukturierte Ausgabe (--format stream-json) wird richtig eingeordnet."""
    assert daemon._stream_json_zeile('{"type":"text","text":"HALLO"}') \
        == ("antwort", "HALLO")
    assert daemon._stream_json_zeile(
        '{"type":"result","text":"HALLO","tokens":{"input":1}}') == ("fertig", "HALLO")
    # Unbekannte Ereignisse (Werkzeug, Start) werden zur Zwischenmeldung.
    assert daemon._stream_json_zeile('{"type":"system","subtype":"init"}') \
        == ("gedanke", "")
    # Keine JSON-Zeile → die alte Erkennung übernimmt (None).
    assert daemon._stream_json_zeile("session_id: 20260925_222516") is None
    assert daemon._stream_json_zeile("{kaputt") is None
    assert daemon._stream_json_zeile("") is None


def test_stream_json_trennt_denktext_von_der_antwort():
    """Der Anlass (25.09.2026): Reasoning darf NICHT in der Antwort landen.

    Live sah Sebastian im Antwortfeld die Rohausgabe samt englischem Denken
    ("The user just sent ... I should respond briefly ...").
    Gemessen (25.09.2026): ``type=text`` sind ANTWORT-Bruchstuecke, ``type=result``
    ist die vollstaendige Antwort. Ein Denk-Ereignis eines anderen Typs wird zur
    Zwischenmeldung.
    """
    denk = json.dumps({"type": "thinking",
                       "text": "The user just sent a test. I should respond briefly."})
    antwort = json.dumps({"type": "result",
                          "text": "Test angekommen — Hermes läuft."})
    ausgabe = daemon._CliAusgabe()

    art_denk, _text_denk = daemon._art_und_text(denk, ausgabe)
    assert art_denk == "gedanke", "Denken muss Zwischenmeldung bleiben"

    art_ende, text_ende = daemon._art_und_text(antwort, ausgabe)
    assert art_ende == "ende"
    assert text_ende == "Test angekommen — Hermes läuft."
    assert "I should respond briefly" not in text_ende


def test_art_und_text_faellt_auf_die_alte_erkennung_zurueck():
    """Ohne JSON bleibt die Kasten-/Rohausgabe-Erkennung wirksam."""
    ausgabe = daemon._CliAusgabe()
    art, text = daemon._art_und_text("╭─⚕ Hermes ────────────╮", ausgabe)
    assert art in ("antwort", "gedanke", "rahmen", "keine")
    assert isinstance(text, str)
