"""Der Umschalt-Modus: tippen zum Starten, nochmal tippen zum Beenden.

Warum es ihn gibt (gemessen 06.10.2026, Claude am PC + Notepad): Solange der
Hotkey gehalten wird, kommt Getipptes im Zielfenster nicht an — die Live-Happen
wurden geschnitten, aber nie eingefügt, und der Abschluss löschte dann Zeichen,
die es nie gab. Wer tippt statt hält, hat während des Sprechens keinen Finger
auf der Taste, und derselbe Einfüge-Weg funktioniert wie am Ende eines Diktats.
"""
import json

import typefree

HOTKEY = {'label': 'Alt + Ä', 'key': 'ä', 'mods': ['alt']}


def test_tippen_startet_und_stoppt():
    assert typefree.decide_hotkey_action(
        'down', 'ä', {'alt'}, HOTKEY, False, 'umschalten') == 'start'
    # Loslassen darf NICHT beenden — sonst wäre die Aufnahme nach dem ersten
    # Tippen sofort wieder vorbei.
    assert typefree.decide_hotkey_action(
        'up', 'ä', {'alt'}, HOTKEY, True, 'umschalten') is None
    assert typefree.decide_hotkey_action(
        'down', 'ä', {'alt'}, HOTKEY, True, 'umschalten') == 'stop'


def test_tippen_ohne_zusatztaste_startet_nicht():
    """Ein nacktes Ä im Text darf keine Aufnahme starten."""
    assert typefree.decide_hotkey_action(
        'down', 'ä', set(), HOTKEY, False, 'umschalten') is None


def test_halten_bleibt_unveraendert():
    """Die alte Betriebsart darf sich nicht mitverändern."""
    assert typefree.decide_hotkey_action(
        'down', 'ä', {'alt'}, HOTKEY, False) == 'start'
    assert typefree.decide_hotkey_action(
        'down', 'ä', {'alt'}, HOTKEY, True) is None
    assert typefree.decide_hotkey_action(
        'up', 'ä', set(), HOTKEY, True) == 'stop'


def test_live_laeuft_in_beiden_betriebsarten():
    """Test mit echtem Finger (06.10.2026 abends): Beim Halten kam Strg+V nicht
    an, direkt getippter Text (Unicode) dagegen schon — auch ohne Freigabe.
    Seit der Live-Modus direkt tippt, darf er auch beim Halten laufen."""
    assert typefree.live_erlaubt(True, 'umschalten') is True
    assert typefree.live_erlaubt(True, 'halten') is True
    assert typefree.live_erlaubt(False, 'umschalten') is False
    assert typefree.live_erlaubt(False, 'halten') is False


def _konfig(tmp_path, monkeypatch):
    pfad = tmp_path / 'config.json'
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(pfad))
    return pfad


def test_standard_ist_halten(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    assert typefree.load_hotkey_modus() == 'halten'


def test_modus_merkt_sich_die_wahl(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    typefree.save_hotkey_modus('umschalten')
    assert typefree.load_hotkey_modus() == 'umschalten'
    typefree.save_hotkey_modus('halten')
    assert typefree.load_hotkey_modus() == 'halten'


def test_unbekannter_modus_faellt_auf_halten_zurueck(tmp_path, monkeypatch):
    """Eine kaputte oder fremde Konfiguration darf nichts Unerwartetes starten."""
    pfad = _konfig(tmp_path, monkeypatch)
    pfad.write_text(json.dumps({'hotkey_modus': 'irgendwas'}), encoding='utf-8')
    assert typefree.load_hotkey_modus() == 'halten'


def test_modus_ueberschreibt_andere_einstellungen_nicht(tmp_path, monkeypatch):
    pfad = _konfig(tmp_path, monkeypatch)
    typefree.save_hotkey_config(3)
    typefree.save_live_config(True)
    typefree.save_hotkey_modus('umschalten')
    gespeichert = json.loads(pfad.read_text(encoding='utf-8'))
    assert gespeichert['hotkey_index'] == 3
    assert gespeichert['live'] is True
    assert gespeichert['hotkey_modus'] == 'umschalten'


def test_rueckruf_stellt_den_modus_um(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    monkeypatch.setattr(typefree, 'hotkey_modus', 'halten')
    typefree._select_hotkey_modus('umschalten')()
    assert typefree.hotkey_modus == 'umschalten'
    typefree._select_hotkey_modus('halten')()
    assert typefree.hotkey_modus == 'halten'
