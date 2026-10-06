"""Der Tray-Schalter für die Ausgabe: alles auf einmal oder live satzweise.

Entscheidung 1 im Plan: Live ist **nicht** Standard. Der Schalter wirkt sofort
und die Wahl bleibt in der `config.json` stehen — auch ein Neustart darf sie
nicht verlieren, und der Hotkey daneben darf nicht überschrieben werden.
"""
import json

import typefree


def _konfig(tmp_path, monkeypatch):
    pfad = tmp_path / 'config.json'
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(pfad))
    return pfad


def test_standard_ist_aus(tmp_path, monkeypatch):
    """Ohne gespeicherte Wahl läuft alles wie bisher — auf einmal."""
    _konfig(tmp_path, monkeypatch)
    assert typefree.load_live_config() is False


def test_schalter_merkt_sich_die_wahl(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    typefree.save_live_config(True)
    assert typefree.load_live_config() is True
    typefree.save_live_config(False)
    assert typefree.load_live_config() is False


def test_schalter_ueberschreibt_andere_einstellungen_nicht(tmp_path, monkeypatch):
    """Der Hotkey darf nicht verloren gehen, wenn man die Ausgabe umstellt."""
    pfad = _konfig(tmp_path, monkeypatch)
    typefree.save_hotkey_config(3)
    typefree.save_live_config(True)
    gespeichert = json.loads(pfad.read_text(encoding='utf-8'))
    assert gespeichert['hotkey_index'] == 3
    assert gespeichert['live'] is True


def test_rueckruf_stellt_den_modus_um(tmp_path, monkeypatch):
    """Der Tray-Eintrag wirkt sofort, nicht erst nach einem Neustart."""
    _konfig(tmp_path, monkeypatch)
    monkeypatch.setattr(typefree, 'live_modus', False)
    typefree._select_live(True)()
    assert typefree.live_modus is True
    typefree._select_live(False)()
    assert typefree.live_modus is False


def test_kaputte_konfiguration_bedeutet_aus(tmp_path, monkeypatch):
    """Eine unlesbare config.json darf die Anlage nicht in den Live-Modus zwingen."""
    pfad = _konfig(tmp_path, monkeypatch)
    pfad.write_text('{kein JSON', encoding='utf-8')
    assert typefree.load_live_config() is False
