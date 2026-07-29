"""Prüft die 10-Minuten-Obergrenze gegen das Speicherleck."""
import numpy as np
import typefree

BLOCK = 1600   # 0,1 Sekunde bei 16 kHz


def _frames(sekunden):
    anzahl = int(sekunden * typefree.SAMPLE_RATE) // BLOCK
    return [np.zeros((BLOCK, 1), dtype='float32') for _ in range(anzahl)]


def test_leere_aufnahme_hat_dauer_null():
    assert typefree.recorded_seconds([]) == 0.0


def test_dauer_wird_korrekt_gerechnet():
    assert typefree.recorded_seconds(_frames(5)) == 5.0


def test_neun_minuten_neunundfuenfzig_laeuft_weiter():
    assert typefree.recording_limit_reached(_frames(599)) is False


def test_zehn_minuten_erreichen_die_grenze():
    assert typefree.recording_limit_reached(_frames(600)) is True
