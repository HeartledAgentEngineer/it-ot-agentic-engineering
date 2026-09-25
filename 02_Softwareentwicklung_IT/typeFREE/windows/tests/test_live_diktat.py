"""Live-Diktat: Happen-Schnitt während der Aufnahme.

Prüft die reinen Funktionen aus `typefree.py` — kein Mikrofon, keine API. Der
Schnitt muss an Sprechpausen liegen (dort endet ein Satz), nach der Höchstdauer
trotzdem kommen, und kleine Reste nicht verschicken.
"""
import numpy as np
import pytest

import typefree


def sprache(sekunden, rate=16000, pegel=0.3):
    """Rauschen in Sprechlautstärke — ein echter Pegel, keine digitale Null."""
    rng = np.random.default_rng(1)
    return (rng.normal(0, pegel, int(sekunden * rate))).astype(np.float32)


def stille(sekunden, rate=16000):
    """Eine Sprechpause: praktisch nichts (Grundrauschen)."""
    rng = np.random.default_rng(2)
    return (rng.normal(0, 0.002, int(sekunden * rate))).astype(np.float32)


RATE = 16000


def test_ohne_genug_audio_gibt_es_keinen_happen():
    """Unter der Mindestlänge wird nichts verschickt — sonst zahlt man für Silben."""
    assert typefree.live_schnitt(sprache(1.5), RATE, 0.0) is None


def test_sprechpause_wird_als_schnitt_erkannt():
    """Sprechen → Pause → der Schnitt liegt in der Pause, nicht im Wort."""
    daten = np.concatenate([sprache(5), stille(1.0), sprache(1)])
    schnitt = typefree.live_schnitt(daten, RATE, 0.0)
    assert schnitt is not None
    sekunde = schnitt / RATE
    assert 5.0 <= sekunde <= 6.0, f'Schnitt bei {sekunde:.2f} s liegt nicht in der Pause'


def test_ohne_pause_wartet_der_live_modus():
    """Bei durchgehendem Sprechen unter der Höchstdauer passiert nichts."""
    assert typefree.live_schnitt(sprache(8), RATE, 0.0) is None


def test_nach_hoechstdauer_wird_trotzdem_geschnitten():
    """Sonst wächst ein Happen unbegrenzt — Notbremse an der leisesten Stelle."""
    schnitt = typefree.live_schnitt(sprache(12), RATE, 0.0)
    assert schnitt is not None
    assert 8.5 <= schnitt / RATE <= 10.0


def test_zweiter_happen_zaehlt_ab_der_schnittstelle():
    """Der echte Live-Ablauf: Audio wächst weiter, der nächste Happen beginnt
    dort, wo der vorige geschnitten wurde — und es darf nichts doppelt ankommen."""
    anfang = np.concatenate([sprache(5), stille(1.0), sprache(6)])
    erster = typefree.live_schnitt(anfang, RATE, 0.0)
    assert erster is not None
    assert 5.0 <= erster / RATE <= 6.0, 'Schnitt muss in der ersten Pause liegen'

    daten = np.concatenate([anfang, stille(1.0), sprache(5), stille(1.0)])
    zweiter = typefree.live_schnitt(daten, RATE, erster / RATE)
    assert zweiter is not None
    assert zweiter > erster
    assert zweiter / RATE >= 17.0, 'Schnitt muss in der neuen Pause liegen'


def test_in_happen_zerlegt_vollstaendig():
    """Die Zerlegung darf nichts verlieren — jeder Sample steckt in genau einem Happen."""
    daten = np.concatenate([sprache(4), stille(1.0), sprache(9), stille(1.0), sprache(3)])
    stellen = typefree.in_happen(daten, RATE, 6.0)
    assert stellen[0][0] == 0
    assert stellen[-1][1] == len(daten)
    for (_, ende), (anfang, _) in zip(stellen, stellen[1:]):
        assert ende == anfang


def test_stillste_stelle_bleibt_im_fenster():
    """Der Schnitt liegt höchstens `suchweite` vor dem Ziel."""
    daten = sprache(20)
    ziel = 12.0
    assert 10.5 * RATE <= typefree.stillste_stelle(daten, RATE, ziel) <= ziel * RATE


@pytest.mark.parametrize('sekunden', [0.0, 0.05])
def test_zu_kurzer_block_bleibt_bei_null(sekunden):
    """Kein Absturz bei leeren oder fast leeren Puffern."""
    leer = sprache(sekunden)
    assert typefree.live_schnitt(leer, RATE, 0.0) is None
