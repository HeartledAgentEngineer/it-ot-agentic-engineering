"""Tests: soll_hermes_delegieren (Task 3 — Weichen-Entscheidung)."""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.faehigkeiten import soll_hermes_delegieren  # noqa: E402


def test_delegiert_echten_coding_auftrag():
    assert soll_hermes_delegieren("Baue einen /health-Endpoint in der FastAPI-App") is True


def test_delegiert_trotz_grenzthema_ohne_coding_wort():
    # "Installiere ein Tool" ist kein klassisches Coding-Verb+Objekt der
    # ist_auftrag-Heuristik, aber ein Grenzthema → trotzdem an Hermes.
    assert soll_hermes_delegieren("Installiere mir bitte das Wetterpaket") is True


def test_delegiert_git_aktion():
    assert soll_hermes_delegieren("Mache einen Git commit und pushe") is True


def test_keine_delegation_bei_normaler_frage():
    assert soll_hermes_delegieren("Wie hübsch ist Hamburg?") is False


def test_keine_delegation_bei_upload():
    # Mit Dateien: Upload ist Verständnis, kein Hermes-Job.
    assert soll_hermes_delegieren("Analysiere das PDF und schreib mir eine Zusammenfassung", mit_dateien=True) is False
