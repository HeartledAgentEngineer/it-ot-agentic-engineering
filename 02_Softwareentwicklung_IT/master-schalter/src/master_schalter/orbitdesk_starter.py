"""Einheitlicher Starter für die Standalone-Windows-Executable (orbitdesk.exe).

Bedienung:
    orbitdesk.exe                   # Startet Leiste (Tray) und Übersicht (GUI)
    orbitdesk.exe --uebersicht      # Startet nur das Übersichtsfenster
    orbitdesk.exe --leiste          # Startet nur das Taskleistensymbol
    orbitdesk.exe status            # Führt 'masterwechsel status' aus
    orbitdesk.exe <befehl> ...      # Reicht alle Argumente an die Befehlszeile weiter
"""
from __future__ import annotations

import multiprocessing
import sys


def _gui_starter() -> None:
    from master_schalter import uebersicht
    uebersicht.main()


def _leiste_starter() -> None:
    from master_schalter import leiste
    leiste.main()


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    argumente = sys.argv[1:] if argv is None else list(argv)

    if not argumente:
        # Standard: Beide Komponenten starten (Leiste im Hintergrund-Thread/Prozess, GUI im Hauptthread)
        p_leiste = multiprocessing.Process(target=_leiste_starter, daemon=True)
        p_leiste.start()
        _gui_starter()
        return 0

    if argumente == ["--uebersicht"]:
        _gui_starter()
        return 0

    if argumente == ["--leiste"]:
        _leiste_starter()
        return 0

    # Alle anderen Argumente gehen an das CLI (masterwechsel)
    from master_schalter import cli
    return cli.main(argumente)


if __name__ == "__main__":
    sys.exit(main())
