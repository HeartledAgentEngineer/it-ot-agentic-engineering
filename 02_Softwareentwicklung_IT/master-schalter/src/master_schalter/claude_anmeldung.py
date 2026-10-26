"""Unterstützte interaktive Anmeldung über die installierte Claude-Code-CLI."""
from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping

from . import modelle

LOGIN_ARGUMENTE = ("auth", "login", "--claudeai")
LOGIN_FEHLT = "Claude-Code-CLI wurde nicht gefunden"
LOGIN_NUR_WINDOWS = "Interaktive Claude-Anmeldung wird nur unter Windows unterstützt"


class Anmeldefehler(Exception):
    """Fester, sicherer Fehler für den Loginstart ohne Prozessausgabe."""


def login_befehl() -> list[str]:
    programm = modelle.claude_programm()
    if not programm:
        raise Anmeldefehler(LOGIN_FEHLT)
    return [*programm, *LOGIN_ARGUMENTE]


def login_umgebung(quelle: Mapping[str, str] | None = None) -> dict[str, str]:
    """Vererbt die Umgebung, wobei leer/fehlendes CLAUDE_CONFIG_DIR den Standard meint."""
    umgebung = dict(os.environ if quelle is None else quelle)
    if not umgebung.get("CLAUDE_CONFIG_DIR"):
        umgebung.pop("CLAUDE_CONFIG_DIR", None)
    return umgebung


def login_starten(umgebung: Mapping[str, str] | None = None):
    """Öffnet den offiziellen interaktiven Login in einer eigenen sichtbaren Windows-Konsole."""
    if os.name != "nt":
        raise Anmeldefehler(LOGIN_NUR_WINDOWS)
    return subprocess.Popen(
        login_befehl(), env=login_umgebung(umgebung),
        creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def prozessbaum_beenden(prozess) -> None:
    """Beendet nach Timeout ausschließlich den Baum der selbst gestarteten CLI."""
    if os.name != "nt":
        raise Anmeldefehler(LOGIN_NUR_WINDOWS)
    try:
        subprocess.run(
            ["taskkill", "/PID", str(prozess.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=5,
        )
    finally:
        prozess.wait(timeout=5)
