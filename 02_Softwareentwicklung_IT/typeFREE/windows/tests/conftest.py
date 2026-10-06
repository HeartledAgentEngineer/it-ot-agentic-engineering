"""Legt den Ordner `windows/` in den Suchpfad, damit `import typefree` klappt."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def kein_echtes_tippen(monkeypatch):
    """Kein Test darf in Sebastians Vordergrundfenster tippen.

    Am 06.10.2026 tippte ein Test zweimal echt „hallo welt " ins aktive Fenster,
    weil `unicode_tippen` neu war und nicht abgefangen wurde. Ein Test, der das
    Tippen prüfen will, ersetzt die Funktion selbst (monkeypatch gewinnt).
    """
    import typefree

    def verboten(*args, **kwargs):
        raise AssertionError('Test wollte echt tippen — vorher abfangen')

    monkeypatch.setattr(typefree, 'unicode_tippen', verboten)
    for name in ('hotkey', 'press', 'keyDown', 'keyUp', 'write', 'typewrite'):
        monkeypatch.setattr(typefree.pyautogui, name, verboten)
