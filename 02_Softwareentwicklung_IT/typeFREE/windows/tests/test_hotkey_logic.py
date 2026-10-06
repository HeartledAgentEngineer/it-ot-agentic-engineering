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


# ── Zusatztasten-Freigabe: bei gehaltenem Alt wird Strg+V zu Strg+Alt+V ───────
# Gemessen in Notepad (06.10.2026): Strg+V bei gehaltenem Alt fügt nichts ein,
# 3× Rücktaste bei gehaltenem Alt leerte das Dokument (Alt+Rücktaste = Rückgängig).
def test_freigegebener_modifier_wird_waehrend_aufnahme_geschluckt():
    """Wackelt Alt nach der Freigabe, darf es nicht wieder „gedrückt" werden."""
    assert typefree.taste_schlucken('down', 'alt', ALT_AE, recording=True,
                                    modifier='alt', mods_frei=True) is True


def test_modifier_ohne_freigabe_kommt_durch():
    """Modus „Alles auf einmal": keine Freigabe, also auch keine Sperre."""
    assert typefree.taste_schlucken('down', 'alt', ALT_AE, recording=True,
                                    modifier='alt', mods_frei=False) is False


def test_eigenes_strg_v_wird_nicht_geschluckt():
    """typeFREE tippt selbst Strg+V — das darf die Sperre nicht treffen."""
    strg_ae = {'label': 'Strg + Ä', 'key': 'ä', 'mods': ['ctrl']}
    assert typefree.taste_schlucken('down', 'ctrl', strg_ae, recording=True,
                                    modifier='ctrl', mods_frei=True,
                                    eigene_eingabe=True) is False


def test_modifier_loslassen_kommt_immer_durch():
    assert typefree.taste_schlucken('up', 'alt', ALT_AE, recording=True,
                                    modifier='alt', mods_frei=True) is False


def test_modifier_nach_aufnahme_kommt_durch():
    assert typefree.taste_schlucken('down', 'alt', ALT_AE, recording=False,
                                    modifier='alt', mods_frei=True) is False


def test_eigene_eingabe_zeitfenster():
    assert typefree.eigene_eingabe_aktiv(jetzt=10.0, bis=10.2) is True
    assert typefree.eigene_eingabe_aktiv(jetzt=10.3, bis=10.2) is False


# ── Messpunkte: welche Zusatztasten meldet Windows gerade als gedrückt? ──────
def test_tastenzustand_text_nennt_gedrueckte_tasten():
    gedrueckt = {0x12}                                   # nur Alt
    text = typefree.tastenzustand_text(lambda vk: vk in gedrueckt)
    assert text == 'Alt=unten Strg=oben Shift=oben'


def test_tastenzustand_text_uebersteht_fehler():
    def kaputt(vk):
        raise OSError('kein Zugriff')
    assert typefree.tastenzustand_text(kaputt) == 'Tastenzustand unbekannt'


# ── Umschalt-Modus: das zweite Tippen muss trotz Ä-Sperre stoppen ────────────
# 06.10.2026 abends: Die Sperre schluckte das zweite Tippen, bevor
# `on_key_event` es sah — die Aufnahme ließ sich nicht mehr beenden.
def test_zweites_tippen_stoppt_im_umschalt_modus():
    assert typefree.umschalt_stopp('down', 'ä', ALT_AE, recording=True,
                                   modus='umschalten', hotkey_unten=False) is True


def test_wiederholung_des_ersten_tippens_stoppt_nicht():
    """Taste vom Start noch gedrückt → Windows wiederholt, das ist kein Tipp."""
    assert typefree.umschalt_stopp('down', 'ä', ALT_AE, recording=True,
                                   modus='umschalten', hotkey_unten=True) is False


def test_halten_modus_stoppt_nicht_beim_druecken():
    assert typefree.umschalt_stopp('down', 'ä', ALT_AE, recording=True,
                                   modus='halten', hotkey_unten=False) is False


def test_ohne_aufnahme_kein_stopp():
    assert typefree.umschalt_stopp('down', 'ä', ALT_AE, recording=False,
                                   modus='umschalten', hotkey_unten=False) is False


def test_andere_taste_stoppt_nicht():
    assert typefree.umschalt_stopp('down', 'a', ALT_AE, recording=True,
                                   modus='umschalten', hotkey_unten=False) is False


def test_loslassen_stoppt_nicht():
    assert typefree.umschalt_stopp('up', 'ä', ALT_AE, recording=True,
                                   modus='umschalten', hotkey_unten=False) is False
