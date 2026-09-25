"""Prüft das Messwerkzeug: Wortfehlerquote und Happen-Schnitte.

Anlass: Am 25.09.2026 stand die Behauptung im Raum, lange Aufnahmen oder
schnelles Sprechen seien die Ursache der sinnlosen Wörter am Ende. Beides ließ
sich messen und widerlegen — dafür muss die Rechnung selbst stimmen.
"""
import numpy as np

import sprachmessung
import typefree


def test_identischer_text_hat_null_prozent():
    assert sprachmessung.wortfehlerquote('Der Commit ist da', 'Der Commit ist da') == 0.0


def test_gross_klein_und_satzzeichen_zaehlen_nicht():
    assert sprachmessung.wortfehlerquote(
        'der commit ist da!', 'Der Commit ist da.') == 0.0


def test_umlaute_werden_aufgeloest():
    assert sprachmessung.wortfehlerquote('Brötchen', 'Broetchen') == 0.0


def test_ein_falsches_wort_ergibt_einen_anteil():
    quote = sprachmessung.wortfehlerquote('Der Comet ist da', 'Der Commit ist da')
    assert 20.0 < quote < 30.0          # vier Wörter, eines falsch


def test_fehlender_text_ergibt_hundert_prozent():
    assert sprachmessung.wortfehlerquote('', 'Der Commit ist da') == 100.0


def test_leere_referenz_ergibt_null():
    assert sprachmessung.wortfehlerquote('irgendwas', '') == 0.0


def test_schnitt_landet_in_der_stille():
    """Der Happen-Schnitt darf nicht mitten ins Wort fallen."""
    rate = typefree.SAMPLE_RATE
    laut = np.random.RandomState(1).uniform(-0.5, 0.5, int(23 * rate)).astype('float32')
    stille = np.zeros(int(2 * rate), dtype='float32')
    danach = np.random.RandomState(2).uniform(-0.5, 0.5, int(35 * rate)).astype('float32')
    daten = np.concatenate([laut, stille, danach])

    stellen = sprachmessung.in_happen(daten, rate, grenze=25.0)

    assert len(stellen) == 3
    erste_grenze = stellen[0][1] / rate
    assert 23.0 <= erste_grenze <= 25.0      # liegt in der stillen Zone
    assert stellen[-1][1] == len(daten)      # der Rest wird immer genommen


def test_kurze_aufnahme_bleibt_ein_happen():
    rate = typefree.SAMPLE_RATE
    daten = np.zeros(int(5 * rate), dtype='float32')
    stellen = sprachmessung.in_happen(daten, rate, grenze=25.0)
    assert stellen == [(0, len(daten))]
