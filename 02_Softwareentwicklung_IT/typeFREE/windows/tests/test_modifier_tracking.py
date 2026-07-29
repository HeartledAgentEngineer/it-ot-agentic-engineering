"""Modifier müssen unabhängig von der Windows-Anzeigesprache erkannt werden.

Auf deutschem Windows meldet die `keyboard`-Bibliothek `STRG` und `UMSCHALT`
statt `ctrl` und `shift`. Wer nur auf die englischen Namen prüft, bekommt eine
leere Modifier-Menge — und jede Strg-Kombination bleibt wirkungslos.
Scancodes sind dagegen Hardware-Nummern und in jeder Sprache gleich.
"""
import keyboard
import pytest
import typefree

STRG_SHIFT_AE = {'label': 'Strg + Shift + Ä', 'key': 'ä', 'mods': ['ctrl', 'shift']}

SC_STRG         = 29
SC_SHIFT_LINKS  = 42
SC_SHIFT_RECHTS = 54
SC_AE           = 40


class Ereignis:
    """Nachbau eines Ereignisses der keyboard-Bibliothek."""

    def __init__(self, name, scan_code, event_type=keyboard.KEY_DOWN):
        self.name = name
        self.scan_code = scan_code
        self.event_type = event_type


@pytest.fixture(autouse=True)
def aufnahme_protokoll(monkeypatch):
    """Fängt start_recording ab, damit kein Mikrofon geöffnet wird."""
    gestartet = []
    monkeypatch.setattr(typefree, 'start_recording',
                        lambda: gestartet.append('start'))
    monkeypatch.setattr(typefree, 'active_hotkey', STRG_SHIFT_AE)
    monkeypatch.setattr(typefree, 'is_recording', False)
    typefree._mods_down.clear()
    yield gestartet
    typefree._mods_down.clear()


def test_deutsche_modifier_namen_starten_die_aufnahme(aufnahme_protokoll):
    """Deutsches Windows: STRG und UMSCHALT statt ctrl und shift."""
    typefree.on_key_event(Ereignis('STRG', SC_STRG))
    typefree.on_key_event(Ereignis('UMSCHALT', SC_SHIFT_LINKS))
    typefree.on_key_event(Ereignis('Ä', SC_AE))
    assert aufnahme_protokoll == ['start']


def test_englische_modifier_namen_funktionieren_weiter(aufnahme_protokoll):
    """Ein englisches Windows darf durch den Fix nicht kaputtgehen."""
    typefree.on_key_event(Ereignis('ctrl', SC_STRG))
    typefree.on_key_event(Ereignis('shift', SC_SHIFT_LINKS))
    typefree.on_key_event(Ereignis('ä', SC_AE))
    assert aufnahme_protokoll == ['start']


def test_rechtes_shift_zaehlt_genauso(aufnahme_protokoll):
    typefree.on_key_event(Ereignis('STRG-RECHTS', SC_STRG))
    typefree.on_key_event(Ereignis('UMSCHALT RECHTS', SC_SHIFT_RECHTS))
    typefree.on_key_event(Ereignis('Ä', SC_AE))
    assert aufnahme_protokoll == ['start']


def test_losgelassener_modifier_wird_wieder_ausgetragen(aufnahme_protokoll):
    typefree.on_key_event(Ereignis('STRG', SC_STRG))
    typefree.on_key_event(Ereignis('UMSCHALT', SC_SHIFT_LINKS))
    typefree.on_key_event(Ereignis('UMSCHALT', SC_SHIFT_LINKS, keyboard.KEY_UP))
    typefree.on_key_event(Ereignis('Ä', SC_AE))
    assert aufnahme_protokoll == []


def test_hotkey_ohne_modifier_startet_nicht(aufnahme_protokoll):
    typefree.on_key_event(Ereignis('Ä', SC_AE))
    assert aufnahme_protokoll == []


def test_modifier_landen_nicht_als_haupttaste_in_der_entscheidung(aufnahme_protokoll):
    """Ein Modifier darf die Entscheidungsfunktion gar nicht erreichen."""
    typefree.on_key_event(Ereignis('STRG', SC_STRG))
    assert typefree._mods_down == {'ctrl'}
