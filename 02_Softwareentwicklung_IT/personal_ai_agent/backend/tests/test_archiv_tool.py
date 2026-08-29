"""Tests für das Archiv-Tool (Wissensspeicher-Suche über Sprache).

Sichert: Eine Frage wie „was weißt du über EasyBank aus dem Archiv?"
durchsucht die Chat-Archive (statt der Dateisuche), Treffer-Notizen
tragen die Quelle (chatgpt/gemini/claude), Foto-Fragen lösen das
Archiv-Tool NICHT aus (False-Positive-Schutz).
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _archiv_tool  # noqa: E402


class _FakeArchiv:
    """Minimaler Archiv-Service-Stand-in (keine echte DB nötig)."""

    is_available = True

    def __init__(self, treffer):
        self._treffer = treffer
        self.letzte_frage = None
        self.aufrufe = 0

    def hybrid(self, frage, top_k=None):
        self.aufrufe += 1
        self.letzte_frage = frage
        return self._treffer


def _treffer_zu_easybank():
    """Zwei Chunks aus unterschiedlichen Quellen (ChatGPT + Gemini)."""
    return [
        {
            "text": "EasyBank hat die Überweisung am 12.03. abgelehnt, "
                    "weil das Limit überschritten war.",
            "source": "chatgpt",
            "beginn": "2026-03-12T10:00:00",
            "title": "EasyBank Probleme",
            "conversation_id": "c1",
        },
        {
            "text": "Die EasyBank-App braucht ein Update auf Version 4.2.",
            "source": "gemini",
            "beginn": "2026-04-02T09:30:00",
            "title": "EasyBank App",
            "conversation_id": "c2",
        },
    ]


def test_archiv_tool_erkennt_archiv_frage():
    """'aus dem Archiv' → Treffer-Hinweis mit Quellen (chatgpt/gemini)."""
    archiv = _FakeArchiv(_treffer_zu_easybank())
    ausgabe = _archiv_tool("Was weißt du über EasyBank aus dem Archiv?",
                           service=archiv)
    assert "Aus dem Archiv" in ausgabe
    assert "EasyBank" in ausgabe
    assert "[chatgpt" in ausgabe  # Quelle der Chunks sichtbar
    assert "[gemini" in ausgabe
    assert "--" not in ausgabe  # keine Dateinamen-Liste der Dateisuche


def test_archiv_tool_erkennt_erinnerungs_frage_mit_stichwort():
    """'erinnerst du dich an X' → Archiv-Suche mit extrahiertem Stichwort."""
    archiv = _FakeArchiv(_treffer_zu_easybank())
    ausgabe = _archiv_tool("Erinnerst du dich an EasyBank?", service=archiv)
    assert "Aus dem Archiv" in ausgabe
    assert archiv.aufrufe == 1
    assert archiv.letzte_frage == "easybank"  # Stichwort extrahiert


def test_archiv_tool_erkennt_wissens_frage_ohne_wort_archiv():
    """'was weißt du über X' (ohne das Wort Archiv) → Archiv-Suche."""
    archiv = _FakeArchiv(_treffer_zu_easybank())
    ausgabe = _archiv_tool("Was weißt du über EasyBank?", service=archiv)
    assert "Aus dem Archiv" in ausgabe
    assert archiv.letzte_frage == "easybank"


def test_archiv_tool_kein_false_positive_bei_foto_frage():
    """Foto-/Bild-Frage → "" (Dateisuche muss laufen, nicht das Archiv)."""
    archiv = _FakeArchiv(_treffer_zu_easybank())
    assert _archiv_tool("Was ist auf dem neuesten Foto?", service=archiv) == ""
    assert _archiv_tool("Was weißt du über das Bild von gestern?",
                        service=archiv) == ""
    assert _archiv_tool("Zeig mir den Screenshot von gestern",
                        service=archiv) == ""
    # Wichtig: Bei Foto-Fragen darf die Archiv-Suche GAR NICHT laufen.
    assert archiv.aufrufe == 0


def test_archiv_tool_kein_signal_leer():
    """Ohne Archiv-Signal → "" (kein False-Trigger, Verlauf/Datei bleibt)."""
    assert _archiv_tool("Wie hübsch ist Hamburg?",
                        service=_FakeArchiv([])) == ""


def test_archiv_tool_kein_treffer_hinweis():
    """Signal + keine Treffer → Hinweis statt Absturz."""
    ausgabe = _archiv_tool("Was weißt du über EasyBank?",
                           service=_FakeArchiv([]))
    assert "nichts gefunden" in ausgabe


def test_archiv_tool_archiv_nicht_verfuegbar_harter_bezug():
    """Archiv nicht erreichbar + expliziter Archiv-Bezug → ehrlicher
    Hinweis (damit NICHT die Dateisuche läuft)."""
    class _OhneArchiv(_FakeArchiv):
        is_available = False

    ausgabe = _archiv_tool("Was weißt du über EasyBank aus dem Archiv?",
                           service=_OhneArchiv([]))
    assert "nicht erreichbar" in ausgabe


def test_archiv_tool_archiv_nicht_verfuegbar_weiches_signal():
    """Archiv nicht erreichbar + weiches Signal → "" (Verlauf kann
    übernehmen, keine Archiv-Blockade)."""
    class _OhneArchiv(_FakeArchiv):
        is_available = False

    assert _archiv_tool("Erinnerst du dich an EasyBank?",
                        service=_OhneArchiv([])) == ""


def test_archiv_tool_hybrid_fehler_kein_crash():
    """Such-Fehler im Service → Hinweis statt Crash."""
    class _Kaputt:
        is_available = True

        def hybrid(self, frage, top_k=None):
            raise RuntimeError("DB weg")

    ausgabe = _archiv_tool("Was weißt du über EasyBank?", service=_Kaputt())
    assert "fehlgeschlagen" in ausgabe