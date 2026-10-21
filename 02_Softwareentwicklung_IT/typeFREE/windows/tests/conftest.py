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


@pytest.fixture(autouse=True)
def kein_echter_ton(monkeypatch):
    """Kein Test darf den echten Ton des PCs stummschalten.

    Die echte Backend-Fabrik (pycaw/WASAPI) wird durch eine ersetzt, die
    „kein Backend" meldet. Tests der Sperre geben ihr eigenes Fake-Backend mit.
    """
    import ton_aus

    monkeypatch.setattr(ton_aus, 'windows_backend', lambda: None)


@pytest.fixture(autouse=True)
def keine_echte_zwischenablage(monkeypatch):
    """Kein Test darf die echte Windows-Zwischenablage anfassen.

    Eine echte Probe würde Sebastians kopierten Inhalt überschreiben. Gesperrt
    sind alle drei Nähte in `typefree` UND die Fabrik der echten Win32-Schicht
    in `zwischenablage` (so erreicht auch ein Test, der die Naht vergisst, die
    Zwischenablage nicht). Ein Test, der den Ablauf prüfen will, ersetzt die
    Nähte selbst (monkeypatch gewinnt); die Zwischenablage-Logik selbst läuft
    gegen eine Fake-API (`test_zwischenablage.py`).
    """
    import typefree
    import zwischenablage

    def verboten(*args, **kwargs):
        raise AssertionError('Test wollte die echte Zwischenablage anfassen — '
                             'vorher abfangen')

    for name in ('zwischenablage_einfuegen', 'zwischenablage_zurueck',
                 'zwischenablage_kopieren'):
        monkeypatch.setattr(typefree, name, verboten)
    monkeypatch.setattr(zwischenablage, 'standard_api', verboten)


@pytest.fixture(autouse=True)
def keine_echten_ersetzungen(monkeypatch, tmp_path):
    """Kein Test liest Sebastians echte `ersetzungen.txt` oder startet einen Editor.

    Der Lader zeigt auf eine nicht vorhandene Datei in `tmp_path` (= keine Regeln),
    `datei_oeffnen` (sonst `os.startfile`) ist gesperrt. Ein Test, der Regeln oder
    das Öffnen prüfen will, ersetzt beides selbst (monkeypatch gewinnt).
    """
    import ersetzungen
    import typefree

    def verboten(*args, **kwargs):
        raise AssertionError('Test wollte echt eine Datei öffnen — vorher abfangen')

    monkeypatch.setattr(typefree, '_ersetzungen',
                        ersetzungen.Ersetzungen(str(tmp_path / 'keine_ersetzungen.txt')))
    monkeypatch.setattr(typefree, 'datei_oeffnen', verboten)
