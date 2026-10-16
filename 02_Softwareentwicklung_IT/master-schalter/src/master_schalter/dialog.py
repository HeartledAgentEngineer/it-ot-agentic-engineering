"""Bestätigungsdialoge der Taskleiste (nativ, fail-closed).

Ein einfacher Ja/Nein-Dialog über die Windows-API (`MessageBoxW`). Standardknopf ist **Nein**
(`MB_DEFBUTTON2`) – ein versehentliches Enter bricht ab. Nur ein echtes Ja gibt `True` zurück.
In Tests wird `frage` **nie** aufgerufen; die Leiste bekommt die Funktion injiziert (Stub).
"""
from __future__ import annotations

import ctypes

MB_YESNO = 0x00000004
MB_ICONQUESTION = 0x00000020
MB_TOPMOST = 0x00040000
MB_DEFBUTTON2 = 0x00000100
IDYES = 6


def frage(titel: str, text: str) -> bool:
    """Ja/Nein-Dialog; nur ein echtes Ja (`IDYES`) ergibt `True` (fail-closed)."""
    ergebnis = ctypes.windll.user32.MessageBoxW(
        None, text, titel, MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_DEFBUTTON2)
    return ergebnis == IDYES
