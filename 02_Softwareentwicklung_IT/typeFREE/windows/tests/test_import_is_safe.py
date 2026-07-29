"""Der Import von typefree darf nichts starten und nichts öffnen."""
import typefree


def test_import_baut_kein_tray_icon():
    assert typefree.tray_icon is None


def test_import_liest_keine_konfiguration():
    assert typefree.active_hotkey is None


def test_import_oeffnet_kein_mikrofon():
    assert typefree._stream is None
