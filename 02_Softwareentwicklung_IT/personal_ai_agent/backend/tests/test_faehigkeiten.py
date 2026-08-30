"""Tests für das Fähigkeiten-Manifest (Agent-Selbstbild).

Sichert: Der Agent kennt seine Fähigkeiten (kann/kann_nicht) und erkennt,
welche Anfragen an eine Grenze stoßen (Terminal/Datei/System → Hermes).
"""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.faehigkeiten import (  # noqa: E402
    FAEHIGKEITEN,
    GRENZE_MARKER,
    stoesst_an_grenze,
)


def test_manifest_struktur():
    """Das Manifest hat 'kann' und 'kann_nicht' als Listen."""
    assert isinstance(FAEHIGKEITEN["kann"], list)
    assert isinstance(FAEHIGKEITEN["kann_nicht"], list)
    assert "chat_verstaendnis" in FAEHIGKEITEN["kann"]
    assert "terminal" in FAEHIGKEITEN["kann_nicht"]


def test_grenz_marker_nicht_leer():
    assert len(GRENZE_MARKER) > 5


def test_stoesst_an_grenze_terminal():
    """Anfrage mit Terminal-/System-Bezug stößt an die Grenze."""
    assert stoesst_an_grenze("Installiere mir ein Tool auf dem Server") is True
    assert stoesst_an_grenze("Führe diesen Befehl im Terminal aus") is True


def test_stoesst_an_grenze_bei_datei():
    assert stoesst_an_grenze("Lege eine Datei an im Projekt") is True


def test_keine_grenze_bei_chat():
    """Normale Chat-Fragen stoßen NICHT an die Grenze."""
    assert stoesst_an_grenze("Wie hübsch ist Hamburg?") is False
    assert stoesst_an_grenze("Was ist in dem Dokument wichtig?") is False


def test_keine_falschen_treffer_durch_substrings():
    """Kurze Marker ('git','run') dürfen nicht in normalen Wörtern
    treffen (Critic-Befund HOCH): 'digital' enthält 'git', 'darunter' 'run'."""
    assert stoesst_an_grenze("Das digitale Zeitalter ist spannend") is False
    assert stoesst_an_grenze("Das liegt darunter in der Schublade") is False


def test_keine_grenze_bei_datei_lesen():
    """DATEI LESEN ist KEINE Grenze (Agent kann über Dateisuche/Archiv lesen).
    Regression: das nackte Marker-Wort 'datei' wurde entfernt, sonst landete
    'Lies meine Lebenslauf-Datei' fälschlich an Hermes ('musst du hochladen')."""
    assert stoesst_an_grenze(
        "Lies den Inhalt meiner Lebenslauf-Datei und fasse zusammen."
    ) is False
    assert stoesst_an_grenze("Was steht in meinem Lebenslauf?") is False
    assert stoesst_an_grenze("Zeig mir das letzte Bild") is False


def test_grenze_bei_datei_schreiben_bleibt():
    """DATEI SCHREIBEN bleibt eine Grenze (Agent kann nicht schreiben)."""
    assert stoesst_an_grenze("Schreibe Code in die Datei test.py") is True
