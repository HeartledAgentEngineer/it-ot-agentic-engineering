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

from app.services.hermes_local import (  # noqa: E402
    LocalHermesJob,
    _extrahiere_boxen,
    _arbeitet_noch,
)
import app.services.hermes_local as hl  # noqa: E402

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


# ----------------------------------------------------------------------
# Regression: vorzeitiger Abschluss (Live-Bug "Hermes haengt / wird zu frueh
# als fertig gewertet")

def test_arbeitet_noch_toolzeile_mit_prompt_ist_arbeit():
    """Werkzeug-Zeile sichtbar UND '❯' unten (Prompt steht waehrend der Arbeit
    permanent da): Das ist KEIN fertiger Zustand — der Agent arbeitet noch.
    Frueher gab die Funktion hier fälschlich False zurück, wodurch der Stream
    den Auftrag sofort beendete und den arbeitenden Agenten wegraeumte."""
    pane_arbeitend = (
        "╭─ Hermes ───────────────╮\n"
        "│  Zwischenantwort       │\n"
        "╰────────────────────────╯\n"
        "  ┊ 💻 preparing terminal…\n"
        "⚕ deepseek-x │ 3% │ ⏱ 51s ─ Auftrag\n"
        "⚕ ❯ /queue /bg /steer Ctrl+C\n"
    )
    assert _arbeitet_noch(pane_arbeitend) is True


def test_arbeitet_noch_laufzeit_timer():
    """Ein aktiver Fortschritts-Timer ('⏱ <n>s' mit n>0) bedeutet: Agent denkt
    gerade weiter, auch wenn gerade kein Tool-Schritt sichtbar ist."""
    pane_mit_timer = (
        "╭─ Hermes ───────────────╮\n"
        "│  Denkt gerade…         │\n"
        "╰────────────────────────╯\n"
        "⚕ modell │ 17.2K | 45% │ ⏱ 84s ─ Titel\n"
        "⚕ ❯ msg=interrupt\n"
    )
    assert _arbeitet_noch(pane_mit_timer) is True


def test_arbeitet_noch_fertige_pane_ist_falsch():
    """Nur eine abgeschlossene Antwort-Box + leerer Prompt, kein Timer und
    keine Tool-Zeile: Das ist ein fertiger Zustand (False)."""
    pane_fertig = (
        "╭─ Hermes ───────────────╮\n"
        "│  Das ist das Ergebnis. │\n"
        "╰────────────────────────╯\n"
        "❯ "
    )
    assert _arbeitet_noch(pane_fertig) is False


def _fertige_job_pane() -> str:
    """Pane einer abgeschlossenen Antwort (finale Box + Prompt)."""
    return (
        "╭─ Hermes ───────────────╮\n"
        "│  Ich habe den Fix gebaut. │\n"
        "╰────────────────────────╯\n"
        "❯ "
    )


def test_stream_auftrag_wartet_auf_stabiles_idle(monkeypatch, tmp_path):
    """stream_auftrag beendet NICHT schon beim bloßen Sichtbarwerden des '❯' +
    erster Box, sondern erst, wenn die Pane über ein Idle-Fenster stabil bleibt.
    Ergebnis = die finale Antwort-Box."""
    pane = _fertige_job_pane()
    job = LocalHermesJob("Test")
    with mock.patch.object(job, "_pane_text", return_value=pane), \
         mock.patch.object(job, "alle_antwort_boxen",
                           return_value=["Ich habe den Fix gebaut."]), \
         mock.patch.object(job, "lebt_noch", return_value=True):
        monkeypatch.setattr(hl, "ist_verfuegbar", lambda: True)
        monkeypatch.setattr(hl, "_ABSCHLUSS_IDLE_S", 1)
        monkeypatch.setattr(hl.hermes_registry, "starte",
                            lambda *a, **k: job)
        ereignisse = list(hl.stream_auftrag("id-x", "Test", timeout=60))
        job.beende()
    ergebnis = [e for e in ereignisse if e["art"] == "ergebnis"]
    assert ergebnis
    assert ergebnis[0]["text"] == "Ich habe den Fix gebaut."


def test_stream_auftrag_verhindert_sofort_abschluss(monkeypatch):
    """Zwischen zwei Denkschritten löst eine kurze 'Vorschaubox + Prompt'-
    Pane KEIN sofortiges 'fertig' aus: sie ist (a) nicht stabil und gilt mit
    Tool-/Timer-Bezug weiter als Arbeit. Statt eines sofortigen Ergebnis liefert
    der Stream hier einen 'fehler' (Timeout) statt des falschen Frühabschlusses."""
    # Arbeitend: Werkzeug sichtbar + Prompt permanent => _arbeitet_noch True.
    pane_arbeit = (
        "  ┊ 💻 preparing terminal…\n"
        "⚕ modell │ 3% │ ⏱ 51s ─ T\n"
        "⚕ ❯ /queue /bg\n"
    )
    job = LocalHermesJob("Test")
    with mock.patch.object(job, "_pane_text", return_value=pane_arbeit), \
         mock.patch.object(job, "lebt_noch", return_value=True):
        monkeypatch.setattr(hl, "ist_verfuegbar", lambda: True)
        monkeypatch.setattr(hl.hermes_registry, "starte",
                            lambda *a, **k: job)
        # Sehr kurzer Timeout, damit der Test schnell endet; der Punkt ist,
        # dass KEIN "ergebnis" geliefert wird, solange er arbeitet.
        ereignisse = list(hl.stream_auftrag("id-y", "Test", timeout=2))
        job.beende()
    arten = {e["art"] for e in ereignisse}
    assert "ergebnis" not in arten
    assert "fehler" in arten