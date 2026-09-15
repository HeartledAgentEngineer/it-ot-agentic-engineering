"""Tests: Der Daemon darf NIE ohne inhaltliche Ausgabe antworten.

Wunsch Sebastian (15.09.2026): Im Coding-Chat kamen nur Statusmeldungen
(„Hermes denkt nach", „Hermes hat geantwortet"), aber **keine inhaltliche
Antwort** — am Ende stand „Ergebnis —". Ursache: Antwort-Zeilen wurden nur
innerhalb des CLI-Kastens `╭─⚕ Hermes ╮` erkannt; kam der Kasten nicht an,
blieb das Ergebnis leer und wurde als „—" geschrieben.
"""
import os
import sys

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
