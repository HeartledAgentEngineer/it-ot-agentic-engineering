"""P0 (12.10.2026): Termux-Werkzeuge lesen den API-Schlüssel selbst.

Vorher holten ``hermes-nacht-job.sh``, ``konversation_paket.sh`` und
``stream_an_frontend.sh`` den Schlüssel über ``/api/konfig`` — denselben
offenen Weg, über den ihn jede fremde Webseite abholen konnte. Die Route ist
entfernt; die Skripte lesen jetzt über ``termux/api-schluessel.sh``.

Offline: erfundene Einstellungsdateien unter ``tmp_path``, kein Netz.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
HELFER = PROJEKT / "termux" / "api-schluessel.sh"
SKRIPTE = (
    "termux/hermes-nacht-job.sh",
    "termux/konversation_paket.sh",
    "termux/stream_an_frontend.sh",
)


def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    return bash


def _helfer(datei: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_bash(), str(HELFER).replace("\\", "/"), str(datei).replace("\\", "/")],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


@pytest.mark.parametrize("skript", SKRIPTE)
def test_skript_nutzt_helfer_statt_konfig(skript):
    text = (PROJEKT / skript).read_text(encoding="utf-8")
    assert "api/konfig" not in text
    assert "termux/api-schluessel.sh" in text
    # backend/.env geht vor, dann die Datei im Projektordner
    assert text.index('"$PROJEKT/backend/.env"') < text.index('"$PROJEKT/.env"')


@pytest.mark.parametrize("skript", SKRIPTE)
def test_skript_gibt_schluessel_nie_aus(skript):
    text = (PROJEKT / skript).read_text(encoding="utf-8")
    for zeile in text.splitlines():
        if re.search(r"^\s*(log|echo|printf)\b", zeile):
            assert "$KEY" not in zeile and "$APIKEY" not in zeile, zeile


@pytest.mark.parametrize("skript", SKRIPTE + ("termux/api-schluessel.sh",))
def test_skript_syntax(skript):
    lauf = subprocess.run([_bash(), "-n", str(PROJEKT / skript).replace("\\", "/")],
                          capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert lauf.returncode == 0, lauf.stderr


@pytest.mark.parametrize("inhalt, erwartet", [
    ("API_KEY=abc123\n", "abc123"),
    ('export API_KEY="mit leer"\n', "mit leer"),
    ("API_KEY='einfach'\r\n", "einfach"),
    ("  API_KEY =  abc  \n", "abc"),
    # Wie das Backend (python-dotenv): der letzte Eintrag gilt,
    ("ANDERES=1\nAPI_KEY=erster\nAPI_KEY=zweiter\n", "zweiter"),
    # ein Kommentar nach Leerraum gehört nicht zum Wert, ein # ohne Leerraum schon.
    ("API_KEY=abc # Kommentar\n", "abc"),
    ('API_KEY="mit leer" # k\n', "mit leer"),
    ("API_KEY='x'#k\n", "x"),
    ("API_KEY=abc#def\n", "abc#def"),
])
def test_helfer_liest_wert(tmp_path, inhalt, erwartet):
    datei = tmp_path / "einstellungen"
    datei.write_bytes(inhalt.encode("utf-8"))
    lauf = _helfer(datei)
    assert lauf.returncode == 0
    assert lauf.stdout == erwartet + "\n"


@pytest.mark.parametrize("inhalt", [
    "API_KEY=abc123\n",
    'export API_KEY="mit leer"\n',
    "API_KEY='einfach'\r\n",
    "  API_KEY =  abc  \n",
    "ANDERES=1\nAPI_KEY=erster\nAPI_KEY=zweiter\n",
    "API_KEY=abc # Kommentar\n",
    'API_KEY="mit leer" # k\n',
    "API_KEY='x'#k\n",
    "API_KEY=abc#def\n",
    "API_KEY=erster\nAPI_KEY=\n",
    "API_KEY=\n",
    "# API_KEY=auskommentiert\n",
])
def test_helfer_liest_wie_das_backend(tmp_path, inhalt):
    """Gegenprobe mit dem Parser, den die Settings des Backends benutzen."""
    from dotenv import dotenv_values

    datei = tmp_path / "einstellungen"
    datei.write_bytes(inhalt.encode("utf-8"))
    backend = dotenv_values(datei).get("API_KEY") or ""
    lauf = _helfer(datei)
    assert lauf.stdout.rstrip("\n") == backend
    assert lauf.returncode == (0 if backend else 1)


@pytest.mark.parametrize("inhalt", [
    "API_KEY=\n",
    'API_KEY=""\n',
    "MEIN_API_KEY=nicht-gemeint\n",
    "ANDERES=1\n",
])
def test_helfer_ohne_wert_exit_1(tmp_path, inhalt):
    datei = tmp_path / "einstellungen"
    datei.write_text(inhalt, encoding="utf-8")
    lauf = _helfer(datei)
    assert lauf.returncode == 1
    assert lauf.stdout == ""


def test_helfer_fehlende_datei_exit_1(tmp_path):
    lauf = _helfer(tmp_path / "gibt-es-nicht")
    assert lauf.returncode == 1
    assert lauf.stdout == ""


def test_helfer_gibt_andere_schluessel_nicht_aus(tmp_path):
    datei = tmp_path / "einstellungen"
    datei.write_text("OPENROUTER_API_KEY=fremd-0815\nAPI_KEY=eigener\n"
                     "PCLOUD_TOKEN=fremd-4711\n", encoding="utf-8")
    lauf = _helfer(datei)
    assert lauf.stdout == "eigener\n"
    assert "fremd" not in lauf.stdout + lauf.stderr
