"""Zusätzliche Grenzfall-Tests für die Fähigkeiten-Erkennung."""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.faehigkeiten import stoesst_an_grenze  # noqa: E402


@pytest.mark.parametrize(
    "text",
    [
        "Das digitale Zeitalter ist spannend.",
        "Das liegt darunter in der Schublade.",
    ],
)
def test_stoesst_an_grenze_ignoriert_marker_in_woertern(text):
    """Kurze Marker treffen nicht als Teil eines längeren Wortes."""
    assert stoesst_an_grenze(text) is False


@pytest.mark.parametrize("text", ["", None])
def test_stoesst_an_grenze_ignoriert_leere_eingaben(text):
    """Leere oder fehlende Eingaben sind keine Grenzüberschreitung."""
    assert stoesst_an_grenze(text) is False


@pytest.mark.parametrize("text", ["DATEI ANLEGEN", "FÜHRE AUS"])
def test_stoesst_an_grenze_ist_unabhaengig_von_gross_kleinschreibung(text):
    """Marker werden unabhängig von Groß- und Kleinschreibung erkannt."""
    assert stoesst_an_grenze(text) is True


@pytest.mark.parametrize("text", ["Bitte eine Datei anlegen.", "Führe aus."])
def test_stoesst_an_grenze_erkennt_grenzphrasen(text):
    """Mehrwort-Marker für Datei- und Terminalaktionen werden erkannt."""
    assert stoesst_an_grenze(text) is True
