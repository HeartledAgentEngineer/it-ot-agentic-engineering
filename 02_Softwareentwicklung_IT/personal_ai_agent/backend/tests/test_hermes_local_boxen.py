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


# ----------------------------------------------------------------------
# Regression: End-Output bei LEERER Pane muss zurückgegeben werden.
# Der Agent antwortet, leert danach aber die TUI/Pane statt den '❯' stehen
# zu lassen -> vorher blieb der Auftrag ewig auf "laeuft" (Ergebnis kam nie an).

def test_abschluss_bereit_leere_pane_mit_endoutput():
    """Leere Pane + bereits gepuffertes End-Output => abschluss-bereit."""
    job = LocalHermesJob("Test")
    job.letzte_antwort = "Das ist das Ergebnis."
    assert hl._abschluss_bereit(job, "") is True
    assert hl._abschluss_bereit(job, "\n\n   \n") is True
    job.beende()


def test_abschluss_bereit_leere_pane_OHNE_endoutput():
    """Leere Pane ohne gepuffertes End-Output ist KEIN Abschluss-Signal."""
    job = LocalHermesJob("Test")
    assert hl._abschluss_bereit(job, "") is False
    job.beende()


def test_abschluss_bereit_prompt_da():
    """Klassischer '❯'-Prompt zählt weiterhin als Abschluss-Signal."""
    job = LocalHermesJob("Test")
    assert hl._abschluss_bereit(job, "irgendwas\n❯ ") is True
    job.beende()


def test_sicheres_ergebnis_nutzt_endoutput_puffer():
    """_sicheres_ergebnis liefert das gepufferte End-Output vor der Pane."""
    job = LocalHermesJob("Test")
    job.letzte_antwort = "Gepuffertes Ergebnis"
    with mock.patch.object(job, "alle_antwort_boxen",
                           return_value=["Aus Pane (sollte nicht gewaehlt)"]):
        assert hl._sicheres_ergebnis(job) == "Gepuffertes Ergebnis"
    job.beende()


def test_sicheres_ergebnis_faellt_zurueck_auf_pane():
    """Ohne Puffer: letzte Antwort-Box aus der Pane."""
    job = LocalHermesJob("Test")
    with mock.patch.object(job, "alle_antwort_boxen",
                           return_value=["Erste", "Letzte"]):
        assert hl._sicheres_ergebnis(job) == "Letzte"
    job.beende()


def test_sicheres_ergebnis_platzhalter_wenn_nichts_da():
    """Weder Puffer noch Pane-Box => Platzhalter, nie leer."""
    job = LocalHermesJob("Test")
    with mock.patch.object(job, "alle_antwort_boxen", return_value=[]):
        assert hl._sicheres_ergebnis(job) == "—"
    job.beende()


def test_stream_auftrag_endoutput_bei_leerer_pane(monkeypatch):
    """Reproduziert den Live-Bug: Hermes antwortet, dann wird die Pane leer.
    Die Antwort-Box wurde gepuffert; als die Pane leer bleibt, wird das
    End-Output als "ergebnis" geliefert, NICHT als "fehler"/Timeout."""
    job = LocalHermesJob("Test")
    # Zuerst eine Box puffern, DANN liefert die Pane nichts mehr.
    pane_mit_box = (
        "╭─ Hermes ───────────────╮\n"
        "│  ok                    │\n"
        "╰────────────────────────╯\n"
    )
    states = [
        pane_mit_box,   # Box wird geparst + gepuffert
        "",             # Pane leer geworden => soll abschliessen
        "",
        "",
        "",
    ]
    with mock.patch.object(job, "_pane_text",
                           side_effect=lambda: states.pop(0) if states else ""), \
         mock.patch.object(job, "lebt_noch", return_value=True):
        monkeypatch.setattr(hl, "ist_verfuegbar", lambda: True)
        monkeypatch.setattr(hl, "_ABSCHLUSS_IDLE_S", 1)
        monkeypatch.setattr(hl.hermes_registry, "starte",
                            lambda *a, **k: job)
        ereignisse = list(hl.stream_auftrag("id-z", "Test", timeout=10))
        job.beende()
    ergebnis = [e for e in ereignisse if e["art"] == "ergebnis"]
    assert ergebnis, f"kein ergebnis unter Ereignissen: {ereignisse}"
    assert ergebnis[0]["text"] == "ok"


# ----------------------------------------------------------------------
# Regression: Rueckfrage des Agenten (kein Abschluss) vs finale Antwort.
# Der Nutzer will auf eine Frage per /eingabe antworten koennen - daher darf
# eine offene Frage den Auftrag NICHT als "fertig" abschliessen.

def test_ist_offene_frage_true():
    """Frage am Ende (letzte Zeile mit '?') => True."""
    assert hl._ist_offene_frage("Musst du die Datei hochladen?") is True
    assert hl._ist_offene_frage("Soll ich das committen?\nBitte antworte.") is False  # endet nicht mit '?'
    assert hl._ist_offene_frage("Zuerst ein Schritt.\nSoll ich pushen?") is True


def test_ist_offene_frage_false_fuer_finale_antwort():
    """Sachliche Antwort ohne abschliessende Frage => False."""
    assert hl._ist_offene_frage("Der Fix ist fertig, alles gruen.") is False
    assert hl._ist_offene_frage("") is False


def test_ist_offene_frage_code_quote_keine_frage():
    """Ueberwiegend Code erklaert die Frage weg (sachliches Endergebnis)."""
    code_text = (
        "def f():\n"
        "    return 1\n"
        "Mehr Code\n"
        "Soll ich pushen?\n"
    )
    assert hl._ist_offene_frage(code_text) is False


def test_stream_auftrag_rueckfrage_laesst_session_offen(monkeypatch):
    """Rueckfrage ('?') => 'frage'-Event, KEIN 'ergebnis', Loops weiter.
    Erst wenn spaeter eine finale (nicht-fragende) Antwort erscheint, kommt
    'ergebnis' und der Auftrag wird abgeschlossen."""
    job = LocalHermesJob("Test")
    # Deterministischer Verlauf, 1 Pane-Text pro Loop-Iteration:
    # Phase A: leere Pane + gepufferte Frage -> frage-Ereignis.
    # Phase B: weiter leere Pane, Frage bleibt (Dedup, kein Abschluss).
    # Phase C: leere Pane + gepuffertes END-OUTPUT -> ergebnis.
    job.letzte_antwort = "Soll ich hochladen?"
    zaehler = {"i": 0}
    pane_verlauf = ["", "", "", ""]       # beidesmal leer/stabil

    def pane_text():
        return pane_verlauf[0]

    def neue_gedanken():
        # Nur einmal ein neues (nicht-fragendes) kuenstliches Signal abgeben,
        # das den Stabilitaetszaehler ruecksetzt — danach Stille.
        zaehler["i"] += 1
        if zaehler["i"] == 6:
            job.letzte_antwort = "Fertig, alles ok."
        return []

    with mock.patch.object(job, "_pane_text", pane_text), \
         mock.patch.object(job, "neue_gedanken", neue_gedanken), \
         mock.patch.object(job, "lebt_noch", return_value=True):
        monkeypatch.setattr(hl, "ist_verfuegbar", lambda: True)
        monkeypatch.setattr(hl, "_ABSCHLUSS_IDLE_S", 1)
        monkeypatch.setattr(hl.hermes_registry, "starte",
                            lambda *a, **k: job)
        ereignisse = list(hl.stream_auftrag("id-f", "Test", timeout=15))
        job.beende()
    arten = [e["art"] for e in ereignisse]
    assert "frage" in arten, f"Rueckfrage nicht gemeldet: {ereignisse}"
    assert "ergebnis" in arten, f"finale Antwort fehlt: {ereignisse}"
    ergebnis = [e for e in ereignisse if e["art"] == "ergebnis"][0]
    assert ergebnis["text"] == "Fertig, alles ok."


def test_stream_auftrag_timeout_liefert_gepuffertes_endoutput(monkeypatch):
    """Timeout mit bereits gepuffertem End-Output: das Ergebnis wird als
    'ergebnis' geliefert (nicht als 'fehler'). Reproduziert den Live-Befund:
    der Agent lieferte eine Zusammenfassung, aber die Pane blieb nicht long
    genug leer/stabil -> früher lief der Auftrag in einen 'fehler'-Timeout und
    das Ergebnis ging verloren."""
    job = LocalHermesJob("Test")
    job.letzte_antwort = "Hier die Zusammenfassung der Lebenslauf-Version."
    # Pane bleibt kurz-stabil aber niemals leer genug -> Abschluss-Pfad greift
    # nie, wir erreichen den Timeout mit gepuffertem End-Output.
    with mock.patch.object(job, "_pane_text", return_value="❯ "), \
         mock.patch.object(job, "lebt_noch", return_value=True):
        monkeypatch.setattr(hl, "ist_verfuegbar", lambda: True)
        monkeypatch.setattr(hl, "_ABSCHLUSS_IDLE_S", 9999)  # Idle nie erreicht
        monkeypatch.setattr(hl.hermes_registry, "starte",
                            lambda *a, **k: job)
        ereignisse = list(hl.stream_auftrag("id-t", "Test", timeout=2))
        job.beende()
    ergebnis = [e for e in ereignisse if e["art"] == "ergebnis"]
    assert ergebnis, f"kein ergebnis trotz gepuffertem End-Output: {ereignisse}"
    assert ergebnis[0]["text"] == "Hier die Zusammenfassung der Lebenslauf-Version."
    assert not any(e["art"] == "fehler" for e in ereignisse)