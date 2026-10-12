"""Tests: Fließtext ist der Standard, Tabellen nur auf Wunsch (12.10.2026).

Befund Sebastian: Personen kamen im Chat manchmal als Tabelle; gewünscht ist
vorlesbarer Fließtext, Tabellen nur auf Anfrage. Ursache: ``system_prompt.md``
empfahl allgemein „Listen, Tabellen, Zwischenüberschriften“, und Werkzeuge
lieferten „Feld: Wert“-Zeilen, deren Form das Modell übernahm.

(a) liest ``system_prompt.md`` direkt; (b) baut den Gesamtprompt aus
erfundenen Dateien in ``tmp_path`` — die echte ``system_prompt.local.md``
wird nie gelesen.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_fliesstext_regel.py -q
"""
import os
import sys
from unittest import mock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

PROMPT_PFAD = os.path.join(BACKEND, "system_prompt.md")


def _prompt() -> str:
    with open(PROMPT_PFAD, encoding="utf-8") as f:
        return f.read()


def test_prompt_macht_fliesstext_zum_standard():
    inhalt = _prompt()
    assert "Standard ist Fließtext" in inhalt
    assert "vorlesen" in inhalt
    assert "Keine Textwände" in inhalt           # die Längenregel bleibt


def test_prompt_behandelt_werkzeugergebnisse_als_rohdaten():
    inhalt = _prompt()
    assert "Werkzeugergebnisse sind Rohdaten" in inhalt
    assert "„Feld: Wert“" in inhalt
    assert "mache daraus Sätze" in inhalt


def test_prompt_erlaubt_tabellen_nur_auf_wunsch():
    inhalt = _prompt()
    assert "nur auf ausdrücklichen Wunsch" in inhalt
    for wunsch in ("„als Tabelle“", "„als Liste“", "„Übersicht“", "„Stichpunkte“"):
        assert wunsch in inhalt, wunsch
    # Die alte, allgemeine Empfehlung ist weg.
    assert "Gut lesbar gliedern — Listen, Tabellen" not in inhalt


def test_prompt_behaelt_die_archiv_fluss_regel():
    inhalt = _prompt()
    assert "Wenn du aus dem Archiv erzählst" in inhalt
    assert "keine Strichliste" in inhalt


def test_gesamtprompt_mit_lokaler_ergaenzung_behaelt_die_regel(tmp_path):
    """Die persönliche Ergänzung wird HINTER die Basisregeln gehängt — die
    Fließtext-Regel steht also immer im Gesamtprompt, und zwar vorn."""
    from app.services.llm_service import llm_service

    basis = tmp_path / "system_prompt.md"
    basis.write_text(_prompt(), encoding="utf-8")
    lokal = tmp_path / "system_prompt.local.md"
    lokal.write_text("ERFUNDENE LOKALE ERGÄNZUNG: Der Nutzer heißt Beispiel.", encoding="utf-8")
    with mock.patch("app.services.llm_service.settings.system_prompt_file", str(basis)), \
         mock.patch("app.services.llm_service.settings.system_prompt_local_file", str(lokal)):
        prompt = llm_service.load_system_prompt()
    assert "Standard ist Fließtext" in prompt
    assert "ERFUNDENE LOKALE ERGÄNZUNG" in prompt
    assert prompt.index("Standard ist Fließtext") < prompt.index("ERFUNDENE LOKALE ERGÄNZUNG")
