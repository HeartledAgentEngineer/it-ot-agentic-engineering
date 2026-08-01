"""Nur eine typeFREE-Instanz darf laufen.

Am 29.07.2026 liefen zwei gleichzeitig: jedes Diktat kam doppelt an und
wurde doppelt bezahlt. Die geplante Aufgabenplanung würde das systematisch
erzeugen, weil sie regelmäßig prüft und neu startet.
"""
import typefree


def test_freie_sperre_laesst_starten():
    assert typefree.zweitstart_verhalten(
        schon_da=False, autostart=False) == 'weiter'


def test_freie_sperre_laesst_auch_den_autostart_durch():
    assert typefree.zweitstart_verhalten(
        schon_da=False, autostart=True) == 'weiter'


def test_belegte_sperre_meldet_sich_beim_handstart():
    """Von Hand gestartet willst du wissen, warum nichts passiert."""
    assert typefree.zweitstart_verhalten(
        schon_da=True, autostart=False) == 'melden_und_beenden'


def test_belegte_sperre_schweigt_beim_autostart():
    """Die Aufgabenplanung prüft alle paar Minuten — sonst stapeln sich Fenster."""
    assert typefree.zweitstart_verhalten(
        schon_da=True, autostart=True) == 'still_beenden'


def test_autostart_schalter_wird_erkannt():
    assert typefree.ist_autostart(['typefree.py', '--autostart']) is True
    assert typefree.ist_autostart(['typefree.py']) is False


def test_unbekannte_schalter_gelten_nicht_als_autostart():
    assert typefree.ist_autostart(['typefree.py', '--irgendwas']) is False
