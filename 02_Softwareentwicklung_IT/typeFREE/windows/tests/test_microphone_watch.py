"""Prüft die Mikrofon-Überwachung ohne echtes Mikrofon."""
import numpy as np
import typefree


def _block(wert=0.0, laenge=160):
    block = np.zeros((laenge, 1), dtype='float32')
    if wert:
        block[42, 0] = wert
    return block


def test_exakte_nullen_gelten_als_stumm():
    assert typefree.block_is_silent(_block()) is True


def test_leises_grundrauschen_gilt_als_signal():
    assert typefree.block_is_silent(_block(1e-7)) is False


def test_denkpause_von_acht_sekunden_ist_kein_fehler():
    """Pakete kommen weiter und enthalten Rauschen — kein Fehlalarm."""
    tot = typefree.is_microphone_dead(
        now=8.0, last_data_at=7.9, last_signal_at=7.9)
    assert tot is False


def test_abgeklemmtes_geraet_liefert_keine_pakete_mehr():
    tot = typefree.is_microphone_dead(
        now=8.0, last_data_at=4.5, last_signal_at=4.5)
    assert tot is True


def test_pakete_kommen_aber_nur_exakte_nullen():
    tot = typefree.is_microphone_dead(
        now=8.0, last_data_at=7.9, last_signal_at=4.0)
    assert tot is True


def test_knapp_unter_der_grenze_schlaegt_nicht_an():
    tot = typefree.is_microphone_dead(
        now=3.0, last_data_at=0.1, last_signal_at=0.1)
    assert tot is False
