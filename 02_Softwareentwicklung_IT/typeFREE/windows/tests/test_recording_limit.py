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


# ── Aussteuerung ──────────────────────────────────────────────────────────────
# Sinnlose Wörter im Betriebslog („Brother 1", „Buster Brauch") stehen immer am
# ENDE einer Aufnahme. Der Pegel steht deshalb im Log; unter dieser Schwelle
# wird gewarnt. Referenzmessung 25.09.2026: fehlerfreies deutsche Referenzaudio
# hatte RMS 0,088 bis 0,095 — die Schwelle liegt bewusst deutlich darunter.

def test_leise_aufnahme_wird_erkannt():
    leise = np.full((1600, 1), 0.01, dtype='float32')
    spitze, rms = typefree.aussteuerung(leise)
    assert abs(spitze - 0.01) < 1e-6
    assert rms < typefree.AUSSTEUERUNG_MIN_RMS


def test_lautes_referenzaudio_loest_keine_warnung_aus():
    laut = np.random.RandomState(0).uniform(-0.6, 0.6, (16000, 1)).astype('float32')
    spitze, rms = typefree.aussteuerung(laut)
    assert spitze <= 0.6 and rms > typefree.AUSSTEUERUNG_MIN_RMS


def test_stille_aufnahme_hat_rms_null():
    spitze, rms = typefree.aussteuerung(np.zeros((1600, 1), dtype='float32'))
    assert spitze == 0.0 and rms == 0.0


def test_schwelle_liegt_unter_dem_gemessenen_referenzpegel():
    """Die Warnung darf bei normaler Aussteuerung nicht anspringen."""
    assert typefree.AUSSTEUERUNG_MIN_RMS < 0.062    # leise Referenz, fehlerfrei
