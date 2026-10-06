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


# ── Ä-Sperre: wackelt Alt weg, darf die gehaltene Taste kein „ääää" tippen ────
ALT_AE = {'label': 'Alt + Ä', 'key': 'ä', 'mods': ['alt']}


def test_gehaltene_hotkey_taste_wird_waehrend_aufnahme_geschluckt():
    """Alt kurz los, Ä bleibt gedrückt: Windows wiederholt ein nacktes „ä"."""
    assert typefree.taste_schlucken('down', 'ä', ALT_AE, recording=True) is True


def test_loslassen_wird_nie_geschluckt():
    """Sonst sieht typeFREE das Loslassen nicht — die Aufnahme endete nie."""
    assert typefree.taste_schlucken('up', 'ä', ALT_AE, recording=True) is False


def test_ohne_aufnahme_wird_nichts_geschluckt():
    assert typefree.taste_schlucken('down', 'ä', ALT_AE, recording=False) is False


def test_andere_tasten_kommen_waehrend_aufnahme_durch():
    assert typefree.taste_schlucken('down', 'a', ALT_AE, recording=True) is False


def test_sperr_haken_laesst_bei_fehler_alles_durch():
    """Gibt der Haken nicht True zurück, sperrt `keyboard` die ganze Tastatur."""
    class Kaputt:
        event_type = 'down'
        @property
        def name(self):
            raise RuntimeError('unerwartet')
    assert typefree._sperr_haken(Kaputt()) is True


def test_sperr_haken_liefert_immer_bool(monkeypatch):
    class Ereignis:
        event_type = 'down'
        name = 'x'
    monkeypatch.setattr(typefree, 'active_hotkey', ALT_AE)
    monkeypatch.setattr(typefree, 'is_recording', True)
    assert typefree._sperr_haken(Ereignis()) is True
