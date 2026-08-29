"""Tests: Boxen-/Gedanken-Parsing des lokalen Hermes-Jobs (Track C).

Reproduziert den LIVE-Fehler „Fehler im lokalen Hermes-Job: Name T is not
defined": `neue_gedanken()` referenzierte beim Schliessen einer Antwort-Box
eine nie definierte Variable `t` (NameError) — sobald die erste Hermes-Box
fertig war, brach der Auftrag ab, bevor das Ergebnis geliefert wurde.

Hier wird das Parsing ohne tmux geprueft (`_pane_text()` gemockt).
"""
import os
import sys
from contextlib import contextmanager
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.hermes_local import LocalHermesJob, _extrahiere_boxen  # noqa: E402

_PANE_MIT_BOX = (
    "╭─ Hermes ──────────────────────────────────────────────╮\n"
    "│  Ich schaue mir die Datei an.                        │\n"
    "│  Dann baue ich den Fix.                              │\n"
    "╰───────────────────────────────────────────────────────╯\n"
    "❯ "
)

_PANE_MIT_TOOL = (
    "💻 /tmp/prj $ python -m pytest tests/ -q\n"
    "❯ "
)


@contextmanager
def _job_mit_pane(pane_text):
    """Job ohne echten tmux-Start; `_pane_text` liefert den Test-Inhalt."""
    job = LocalHermesJob("Test-Auftrag")
    with mock.patch.object(job, "_pane_text", return_value=pane_text):
        yield job
    job.beende()


def test_neue_gedanken_box_ohne_nameerror():
    """Fertige Antwort-Box darf keinen NameError werfen (Regression „Name T")."""
    with _job_mit_pane(_PANE_MIT_BOX) as job:
        gedanken = job.neue_gedanken()
    assert gedanken == ["Ich schaue mir die Datei an.\nDann baue ich den Fix."]


def test_neue_gedanken_tool_zeile():
    """Werkzeug-Zeile wird als 🔧-Gedanke geliefert."""
    with _job_mit_pane(_PANE_MIT_TOOL) as job:
        gedanken = job.neue_gedanken()
    assert gedanken == ["🔧 python -m pytest tests/ -q"]


def test_neue_gedanken_box_und_tool_gemischt():
    """Box + Tool-Zeile in einer Pane: beides wird geliefert, zweiter Poll leer."""
    pane = _PANE_MIT_TOOL + _PANE_MIT_BOX
    with _job_mit_pane(pane) as job:
        erste = job.neue_gedanken()
        zweite = job.neue_gedanken()   # Dedup: nichts Neues
    assert erste == [
        "🔧 python -m pytest tests/ -q",
        "Ich schaue mir die Datei an.\nDann baue ich den Fix.",
    ]
    assert zweite == []


def test_extrahiere_boxen_mehrere_boxen():
    """_extrahiere_boxen liefert alle Antwort-Boxen (Raum-getrennt verketten)."""
    pane = _PANE_MIT_BOX + "noch was\n" + _PANE_MIT_BOX
    boxen = _extrahiere_boxen(pane)
    assert len(boxen) == 2
    assert all("Ich schaue mir die Datei an." in b for b in boxen)


def test_neue_gedanken_leere_pane():
    """Leere Pane → keine Gedanken, kein Fehler."""
    with _job_mit_pane("") as job:
        assert job.neue_gedanken() == []