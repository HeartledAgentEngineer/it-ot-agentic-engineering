"""Alle Frontend-Tests (``frontend/tests/*.js``) als Teil des Prüfbefehls.

Bisher liefen die Node-Tests nur von Hand. Ein Umbau an ``app.js`` konnte
Tests brechen, die Quelltextmuster lesen oder Funktionen wörtlich
ausschneiden (z. B. ``test_gedaechtnis_ui.js``, ``test_diff_darstellung.js``).
Der Prüfbefehl blieb dabei grün. Plan P0 (Sicherheit, 12.10.2026), Schritt P0.8.

Jeder Test läuft im Ordner ``frontend/`` mit dem Dateinamen als Argument, den
seine Aufrufzeile im Kopf nennt. Einige Tests leiten weitere Pfade aus dem
Verzeichnis des Arguments ab (``test_gedaechtnis_ui.js:28`` findet so
``index.html``).

Fehlt ``node``, werden die Tests übersprungen. Der Grund steht dann im
pytest-Bericht: „Frontend-Tests NICHT verifiziert“.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
TESTORDNER = FRONTEND / "tests"

# Welche Quelldatei ein Test als Argument bekommt. Alle übrigen bekommen app.js;
# Tests, die ihre Datei selbst finden, ignorieren das Argument.
ZUORDNUNG = {
    "test_erzaehlen.js": "erzaehlen.js",
    "test_anmelden.js": "anmelden.js",
    "test_gruppen_quiz.js": "gruppen_quiz.js",
    "test_wecken.js": "wecken.js",
    "test_sw_schluessel.js": "sw.js",
}
STANDARD = "app.js"

NODE = shutil.which("node")
TESTS = sorted(p.name for p in TESTORDNER.glob("test_*.js"))


def test_frontend_tests_gefunden():
    """Wächter: Der Ordner ist nicht leer und jede Zuordnung zeigt auf Vorhandenes."""
    assert len(TESTS) >= 27, f"nur {len(TESTS)} Frontend-Tests gefunden"
    for test, quelle in ZUORDNUNG.items():
        assert (TESTORDNER / test).is_file(), f"Zuordnung ohne Test: {test}"
        assert (FRONTEND / quelle).is_file(), f"Zuordnung ohne Quelldatei: {quelle}"


@pytest.mark.skipif(NODE is None, reason="Frontend-Tests NICHT verifiziert: node fehlt")
@pytest.mark.parametrize("name", TESTS)
def test_frontend_node(name):
    assert NODE is not None
    argument = ZUORDNUNG.get(name, STANDARD)
    lauf = subprocess.run(
        [NODE, f"tests/{name}", argument],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert lauf.returncode == 0, (
        f"{name} (Argument {argument}) rot, Exit {lauf.returncode}\n"
        f"{lauf.stdout[-2500:]}\n{lauf.stderr[-1500:]}"
    )
