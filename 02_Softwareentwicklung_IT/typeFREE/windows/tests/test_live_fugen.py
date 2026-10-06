"""Blockgrenzen im Live-Modus: kein Punkt mitten im Satz.

06.10.2026: Die Block-Glättung hielt jeden Block für einen fertigen Satz —
„…am Ende schlecht erkannt." | „worden oder schlecht übersetzt…". Jetzt wird
das Satzzeichen am Blockende zurückgehalten. Ob der Satz weitergeht, verrät
der ROHE neue Block: mai schreibt Fortsetzungen klein, neue Sätze groß.
Gemessen an 6 echten Grenzfällen: diese Regel 6/6, das Lite-Modell per
Markierung 4/6, mit Zusatzhinweis 2/6.
"""
import typefree


def test_satzzeichen_am_ende_wird_abgetrennt():
    assert typefree.block_aufteilen('Das ist gut.') == ('Das ist gut', '.')
    assert typefree.block_aufteilen('Geht das? ') == ('Geht das', '?')
    assert typefree.block_aufteilen('und dann') == ('und dann', '')
    assert typefree.block_aufteilen('Na...') == ('Na', '...')


def test_kleiner_anfang_heisst_fortsetzung():
    assert typefree.geht_weiter('worden oder schlecht übersetzt') is True
    assert typefree.geht_weiter('ähm, schon deutlich schneller') is True
    assert typefree.geht_weiter('Mal gucken, was ich sehen kann') is False
    assert typefree.geht_weiter('„Zitat" am Anfang') is False
    assert typefree.geht_weiter('') is False


def test_erster_block_bekommt_keine_fuge():
    assert typefree.fuge_bestimmen(False, '.', erster_block=True) == ''


def test_fortsetzung_bekommt_nur_ein_leerzeichen():
    """Der Kern des Ganzen: der zurückgehaltene Punkt fällt weg."""
    assert typefree.fuge_bestimmen(True, '.', erster_block=False) == ' '


def test_neuer_satz_bekommt_das_zurueckgehaltene_zeichen():
    assert typefree.fuge_bestimmen(False, '.', erster_block=False) == '. '
    assert typefree.fuge_bestimmen(False, '?', erster_block=False) == '? '


def test_ohne_zurueckgehaltenes_zeichen_nur_leerzeichen():
    """mai hatte keinen Punkt gesetzt — dann erfinden wir keinen."""
    assert typefree.fuge_bestimmen(False, '', erster_block=False) == ' '


def test_fortsetzung_wird_klein_angeglichen():
    """Die Glättung schreibt den Blockanfang manchmal groß — mai wusste es besser."""
    assert typefree.anfang_angleichen('ähm schon schneller', 'Schon schneller.',
                                      weiter=True) == 'schon schneller.'


def test_nomen_am_anfang_bleibt_gross():
    assert typefree.anfang_angleichen('Variante läuft', 'Variante läuft.',
                                      weiter=True) == 'Variante läuft.'


def test_neuer_satz_beginnt_gross():
    assert typefree.anfang_angleichen('mal gucken', 'mal gucken.',
                                      weiter=False) == 'Mal gucken.'
