"""Prüft die Entscheidung „starten / stoppen / nichts tun" ohne echte Tastatur."""
import typefree

STRG_SHIFT_AE = {'label': 'Strg + Shift + Ä', 'key': 'ä', 'mods': ['ctrl', 'shift']}
F5            = {'label': 'F5',               'key': 'f5', 'mods': []}


def test_druecken_mit_allen_modifiern_startet():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'ä', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=False)
    assert ergebnis == 'start'


def test_loslassen_beendet_auch_wenn_strg_schon_los_ist():
    """Der eigentliche Fehler: Strg wurde vor Ä losgelassen."""
    ergebnis = typefree.decide_hotkey_action(
        'up', 'ä', set(), STRG_SHIFT_AE, recording=True)
    assert ergebnis == 'stop'


def test_druecken_ohne_modifier_startet_nicht():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'ä', set(), STRG_SHIFT_AE, recording=False)
    assert ergebnis is None


def test_gehaltene_taste_startet_nicht_zweimal():
    """Windows schickt bei gehaltener Taste laufend neue KEY_DOWN-Ereignisse."""
    ergebnis = typefree.decide_hotkey_action(
        'down', 'ä', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=True)
    assert ergebnis is None


def test_loslassen_ohne_laufende_aufnahme_tut_nichts():
    ergebnis = typefree.decide_hotkey_action(
        'up', 'ä', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=False)
    assert ergebnis is None


def test_fremde_taste_wird_ignoriert():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'x', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=False)
    assert ergebnis is None


def test_hotkey_ohne_modifier_startet_direkt():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'f5', set(), F5, recording=False)
    assert ergebnis == 'start'
