"""Absätze bei langen Diktaten (Scheibe 4, 20.10.2026).

Reine Funktionen in `absaetze.py` plus die Verdrahtung in `typefree`. Config nur
in `tmp_path`; nichts wird getippt, keine echte Zwischenablage (die Nähte
`zwischenablage_einfuegen` usw. sind in conftest gesperrt und werden hier selbst
ersetzt).

Die Absatz-Tests sind so gebaut, dass ein falsch erkanntes Satzende die Stelle
des Absatzes verschiebt: ein Satz, der nur als Ganzes „gehaltvoll" (>= 5 Wörter)
ist, zählt doppelt, wenn er fälschlich zerlegt wird.
"""
import re

import numpy as np
import pytest

import absaetze as ab
import typefree


def satz(n, wort='wort', ende='.'):
    """Ein Satz mit genau n Wörtern, z. B. 'Wort wort wort.'"""
    woerter = [wort] * n
    woerter[0] = wort.capitalize()
    return ' '.join(woerter) + ende


def text_aus(*saetze):
    return ' '.join(saetze)


def neu(text):
    return ab.absaetze(text)[0]


def anzahl(text):
    return ab.absaetze(text)[1]


def drei_gehaltvolle_dann_satz(s):
    """Drei gehaltvolle Sätze, dann `s` (der vierte), dann ein kurzer Satz.

    Bleibt `s` ein Satz, fällt der Absatz GENAU nach `s`. Wird `s` zerlegt,
    erreicht der Zähler vier schon früher und der Absatz steht mittendrin.
    """
    erwartet = text_aus(satz(5), satz(5), satz(5), s) + '\n\n' + satz(2)
    return neu(text_aus(satz(5), satz(5), satz(5), s, satz(2))), erwartet


# ── Unverändert ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('text', [
    '',
    'Hallo.',
    'Ein einziger, ganz langer Satz ' + 'mit sehr vielen Wörtern ' * 20 + 'der nie aufhört.',
    'Kurz. Auch kurz. Noch kürzer.',
    'Ohne Satzzeichen am Ende und ohne alles',
])
def test_kurze_texte_und_ein_satz_bleiben_unveraendert(text):
    assert ab.absaetze(text) == (text, 0)


# ── Schwelle 45 Wörter ───────────────────────────────────────────────────────

def test_absatz_nach_dem_satz_der_45_woerter_erreicht():
    # 15 Sätze à 3 Wörter = 45 (nicht gehaltvoll, ab 5): Absatz GENAU nach Satz 15.
    saetze = [satz(3) for _ in range(16)]
    ergebnis, n = ab.absaetze(text_aus(*saetze))
    assert n == 1
    erster, zweiter = ergebnis.split('\n\n')
    assert erster == text_aus(*saetze[:15])
    assert zweiter == saetze[15]


def test_kein_absatz_bei_44_woerter():
    # 14 Sätze à 3 + 1 Satz à 2 = 44, danach noch ein Satz: nicht erreicht.
    saetze = [satz(3) for _ in range(14)] + [satz(2), satz(3)]
    assert anzahl(text_aus(*saetze)) == 0


def test_zaehler_beginnt_nach_einem_absatz_neu():
    saetze = [satz(3) for _ in range(31)]
    ergebnis, n = ab.absaetze(text_aus(*saetze))
    assert n == 2
    assert [a.count('.') for a in ergebnis.split('\n\n')] == [15, 15, 1]


# ── Vier gehaltvolle Sätze ───────────────────────────────────────────────────

def test_vier_gehaltvolle_saetze_ergeben_einen_absatz():
    saetze = [satz(5), satz(6), satz(5), satz(7), satz(2)]
    ergebnis, n = ab.absaetze(text_aus(*saetze))
    assert n == 1
    assert ergebnis == text_aus(*saetze[:4]) + '\n\n' + saetze[4]


def test_vier_saetze_mit_vier_woertern_ergeben_keinen_absatz():
    saetze = [satz(4) for _ in range(5)]
    assert anzahl(text_aus(*saetze)) == 0


def test_drei_gehaltvolle_saetze_reichen_nicht():
    saetze = [satz(5), satz(5), satz(5), satz(2), satz(2)]
    assert anzahl(text_aus(*saetze)) == 0


def test_kein_absatz_nach_dem_letzten_satz():
    # Die Schwelle (4 gehaltvolle Sätze) wird erst mit dem LETZTEN Satz erreicht.
    saetze = [satz(5) for _ in range(4)]
    assert ab.absaetze(text_aus(*saetze)) == (text_aus(*saetze), 0)
    # Mit einem weiteren Satz kommt der Absatz davor, nicht dahinter.
    mehr = saetze + [satz(5)]
    assert neu(text_aus(*mehr)).endswith('\n\n' + satz(5))


def test_kein_absatz_am_anfang():
    # Auch ein sehr langer erster Satz setzt keinen Absatz VOR sich.
    ergebnis = neu(text_aus(satz(60), satz(3)))
    assert not ergebnis.startswith('\n')
    assert ergebnis == satz(60) + '\n\n' + satz(3)


# ── Abkürzungen, Ziffern, Kleinbuchstabe ─────────────────────────────────────

@pytest.mark.parametrize('abk', [
    'z. B.', 'z.B.', 'Z. B.', 'd. h.', 'u. a.', 'u. ä.', 'o. ä.', 'usw.', 'USW.',
    'bzw.', 'ca.', 'etc.', 'vgl.', 'ggf.', 'evtl.', 'inkl.', 'bspw.', 'sog.',
    'Nr.', 'Dr.', 'Prof.', 'Hr.', 'Fr.', 'St.', 'Str.', 'S.', 'Abs.', 'Jh.',
    'Mio.', 'Mrd.', 'Tel.', 'ff.', 'u. U.', 'i. d. R.',
])
def test_abkuerzungen_sind_kein_satzende(abk):
    # Nach der Abkürzung folgt ein GROSSgeschriebenes Wort — nur die Abkürzung
    # verhindert hier das Satzende.
    ergebnis, erwartet = drei_gehaltvolle_dann_satz(
        f'Das ist ein Test {abk} Dann geht es weiter.')
    assert ergebnis == erwartet


def test_abkuerzungen_mitten_im_satz():
    ergebnis, erwartet = drei_gehaltvolle_dann_satz(
        'Das ist, d. h. im Grunde, Dr. Müller usw. Meier gemeint.')
    assert ergebnis == erwartet


def test_ziffer_vor_dem_punkt_ist_kein_satzende():
    ergebnis, erwartet = drei_gehaltvolle_dann_satz(
        'Wir treffen uns am 3. Oktober zu einem langen Essen.')
    assert ergebnis == erwartet
    ergebnis, erwartet = drei_gehaltvolle_dann_satz(
        'Wir nutzen jetzt die Version 2. Dann geht es richtig los.')
    assert ergebnis == erwartet


def test_kleinbuchstabe_danach_ist_kein_satzende():
    ergebnis, erwartet = drei_gehaltvolle_dann_satz(
        'Es ist wie es ist. und dann ging alles ganz schnell vorbei.')
    assert ergebnis == erwartet


def test_grossbuchstabe_danach_ist_ein_satzende():
    # Gegenprobe zu den Tests oben: ohne Sonderfall zerlegt der Zerleger.
    s = 'Es ist wie es ist. Und dann ging alles ganz schnell vorbei.'
    ergebnis, erwartet = drei_gehaltvolle_dann_satz(s)
    assert ergebnis != erwartet
    assert ergebnis.count('\n\n') == 1


# ── Satzzeichen ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('ende', ['?', '!', '…'])
def test_fragezeichen_ausrufezeichen_auslassung_sind_satzende(ende):
    saetze = [satz(5, ende=ende), satz(5, ende=ende), satz(5, ende=ende),
              satz(5, ende=ende), satz(2)]
    ergebnis, n = ab.absaetze(text_aus(*saetze))
    assert n == 1
    assert ergebnis == text_aus(*saetze[:4]) + '\n\n' + saetze[4]


def test_satzende_mit_schliessendem_anfuehrungszeichen():
    saetze = ['Er sagte: „Das ist ein ganz neuer Plan."', 'Sie sagte "Das stimmt wohl schon."',
              satz(5), satz(5), satz(2)]
    ergebnis, n = ab.absaetze(text_aus(*saetze))
    assert n == 1
    assert ergebnis == text_aus(*saetze[:4]) + '\n\n' + saetze[4]


def test_satzende_mit_schliessender_klammer():
    saetze = ['Das war (wie schon gesagt) ein guter Plan (glaube ich.)', satz(5), satz(5),
              satz(5), satz(2)]
    ergebnis, n = ab.absaetze(text_aus(*saetze))
    assert n == 1
    assert ergebnis == text_aus(*saetze[:4]) + '\n\n' + saetze[4]


def test_naechster_satz_darf_mit_anfuehrungszeichen_beginnen():
    saetze = [satz(5), satz(5), satz(5), satz(5), '„Neuer Satz" kommt nun.']
    assert neu(text_aus(*saetze)).endswith('\n\n„Neuer Satz" kommt nun.')


# ── Vorhandene Absätze ───────────────────────────────────────────────────────

def test_vorhandene_absaetze_bleiben_exakt_erhalten():
    text = 'Erster Teil.\n\nZweiter Teil.\r\n\r\nDritter Teil.\n \n\t\nVierter Teil.'
    assert ab.absaetze(text) == (text, 0)


def test_zaehlen_beginnt_nach_jedem_vorhandenen_trenner_neu():
    # 2 × 3 gehaltvolle Sätze, getrennt durch einen echten Absatz: insgesamt 6,
    # aber nie 4 am Stück — also KEIN neuer Absatz.
    abschnitt = text_aus(satz(5), satz(5), satz(5))
    text = abschnitt + '\r\n\r\n' + abschnitt
    assert ab.absaetze(text) == (text, 0)


def test_neue_absaetze_neben_vorhandenen():
    abschnitt = text_aus(satz(5), satz(5), satz(5), satz(5), satz(2))
    text = abschnitt + '\r\n\r\n' + abschnitt
    ergebnis, n = ab.absaetze(text)
    assert n == 2
    teile = ergebnis.split('\r\n\r\n')
    assert len(teile) == 2
    for t in teile:
        assert t == text_aus(*[satz(5)] * 4) + '\n\n' + satz(2)


def test_mehrfach_leerzeichen_an_der_absatzstelle_werden_zu_einem_absatz():
    text = satz(5) + '  ' + satz(5) + ' \t ' + satz(5) + '   ' + satz(5) + '    ' + satz(2)
    ergebnis, n = ab.absaetze(text)
    assert n == 1
    assert ergebnis.endswith(satz(5) + '\n\n' + satz(2))
    assert '\n\n ' not in ergebnis and ' \n\n' not in ergebnis


def test_einfacher_zeilenumbruch_an_der_absatzstelle_wird_zu_absatz():
    text = satz(5) + ' ' + satz(5) + ' ' + satz(5) + ' ' + satz(5) + '\n' + satz(2)
    ergebnis, n = ab.absaetze(text)
    assert n == 1
    assert ergebnis.endswith(satz(5) + '\n\n' + satz(2))


# ── Eigenschaft: nur Leerraum ändert sich ────────────────────────────────────

def _flach(text):
    return re.sub(r'\s+', ' ', text)


TEXTE = [
    text_aus(*[satz(3) for _ in range(40)]),
    text_aus(*[satz(7, ende=e) for e in '.!?….!?….']),
    'Das gilt z. B. für Dr. Meier usw. Er kam am 3. Oktober. ' * 8,
    '„Hallo." (Ja.) Nein! Wirklich? ' * 12,
    'a. b. c. d. e. f. g.\n\nh. i.\r\n\r\nj. k. l. m.',
    'Ein längerer Satz mit Komma, Gedankenstrich – und Klammern (wie hier). ' * 10,
    '   Führender und folgender Leerraum.   Zweiter Satz hier.   ',
]


@pytest.mark.parametrize('text', TEXTE)
def test_nur_leerraum_wird_geaendert(text):
    ergebnis, _ = ab.absaetze(text)
    assert _flach(ergebnis) == _flach(text)
    assert re.sub(r'\s', '', ergebnis) == re.sub(r'\s', '', text)


def test_anzahl_entspricht_den_eingefuegten_absaetzen():
    text = text_aus(*[satz(3) for _ in range(46)])
    ergebnis, n = ab.absaetze(text)
    assert n == ergebnis.count('\n\n') == 3


# ── Einhängen in typefree ────────────────────────────────────────────────────

class Ablauf:
    pass


LANG = text_aus(satz(5), satz(5), satz(5), satz(5), satz(2))
LANG_MIT_ABSATZ = text_aus(*[satz(5)] * 4) + '\n\n' + satz(2)


@pytest.fixture
def ablauf(monkeypatch):
    s = Ablauf()
    s.eingefuegt, s.fehler = [], []

    class Ergebnis:
        geschrieben = True
        snapshot = None
        nummer = 1

    def einfuegen(text):
        s.eingefuegt.append(text)
        return Ergebnis()

    monkeypatch.setattr(typefree, 'zwischenablage_einfuegen', einfuegen)
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck', lambda *a: True)
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck_an', False)
    monkeypatch.setattr(typefree.pyautogui, 'hotkey', lambda *a: None)
    monkeypatch.setattr(typefree.time, 'sleep', lambda s_: None)
    monkeypatch.setattr(typefree, 'letztes_diktat', None)
    monkeypatch.setattr(typefree, 'absaetze_an', False)
    monkeypatch.setattr(typefree, 'save_verbrauch', lambda *a, **k: None)
    monkeypatch.setattr(typefree, 'verbrauch_buchen', lambda v, *a, **k: v)
    monkeypatch.setattr(typefree, '_status_transcribing', lambda: None)
    monkeypatch.setattr(typefree, '_status_polishing', lambda: None)
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, 'report_error', s.fehler.append)
    monkeypatch.setattr(typefree, 'polish_text', lambda text: text)
    typefree.retry_verwerfen()
    yield s
    typefree.retry_verwerfen()


def sprache(sekunden):
    rng = np.random.default_rng(3)
    return rng.normal(0, 0.2, int(sekunden * typefree.SAMPLE_RATE)).astype(np.float32)


def diktat(monkeypatch, text):
    monkeypatch.setattr(typefree, 'transcribe_audio',
                        lambda puffer, clients, **_: (text, 'mai'))


def test_schalter_aus_fuegt_unveraendert_ein(monkeypatch, ablauf):
    diktat(monkeypatch, LANG)
    typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == [LANG]
    assert typefree.letztes_diktat == LANG


def test_schalter_an_fuegt_mit_absaetzen_ein_und_merkt_sie(monkeypatch, ablauf):
    monkeypatch.setattr(typefree, 'absaetze_an', True)
    diktat(monkeypatch, LANG)
    typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == [LANG_MIT_ABSATZ]
    assert typefree.letztes_diktat == LANG_MIT_ABSATZ
    assert ablauf.fehler == []


def test_absaetze_kommen_nach_den_ersetzungen(monkeypatch, ablauf):
    """Die Absatzzählung sieht den Text nach den festen Ersetzungen."""
    gesehen = []
    echt = ab.absaetze
    monkeypatch.setattr(typefree, 'absaetze_an', True)
    monkeypatch.setattr(typefree, 'ersetzen', lambda t: t.replace('ZZZ', 'wort'))
    monkeypatch.setattr(ab, 'absaetze', lambda t: gesehen.append(t) or echt(t))
    diktat(monkeypatch, LANG.replace('wort', 'ZZZ'))
    typefree._verarbeite_audio(sprache(2.0))
    assert gesehen == [LANG]


def test_logzeile_nennt_nur_die_anzahl(monkeypatch, ablauf, caplog):
    monkeypatch.setattr(typefree, 'absaetze_an', True)
    diktat(monkeypatch, LANG)
    with caplog.at_level('INFO', logger='typefree'):
        typefree._verarbeite_audio(sprache(2.0))
    zeilen = [r.getMessage() for r in caplog.records if r.getMessage().startswith('Absätze')]
    assert zeilen == ['Absätze: 1 eingefügt']


def test_ohne_absaetze_keine_logzeile(monkeypatch, ablauf, caplog):
    monkeypatch.setattr(typefree, 'absaetze_an', True)
    diktat(monkeypatch, 'Nur ein kurzer Satz.')
    with caplog.at_level('INFO', logger='typefree'):
        typefree._verarbeite_audio(sprache(2.0))
    assert not [r for r in caplog.records if r.getMessage().startswith('Absätze')]
    assert ablauf.eingefuegt == ['Nur ein kurzer Satz.']


def test_fehler_in_absaetze_fuegt_original_ein_und_loggt_nur_den_typ(
        monkeypatch, ablauf, caplog):
    def kaputt(text):
        raise RuntimeError('geheimer diktattext')

    monkeypatch.setattr(typefree, 'absaetze_an', True)
    monkeypatch.setattr(ab, 'absaetze', kaputt)
    diktat(monkeypatch, LANG)
    with caplog.at_level('DEBUG', logger='typefree'):
        typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == [LANG]
    assert typefree.letztes_diktat == LANG
    assert ablauf.fehler == []
    protokoll = caplog.text + ''.join(str(r.exc_info) for r in caplog.records)
    assert 'geheimer diktattext' not in protokoll
    assert 'RuntimeError' in caplog.text


def test_halluzinations_verwerfpfad_ruft_absaetze_nicht(monkeypatch, ablauf):
    gerufen = []
    monkeypatch.setattr(typefree, 'absaetze_an', True)
    monkeypatch.setattr(ab, 'absaetze', lambda t: gerufen.append(t) or (t, 0))
    diktat(monkeypatch, 'Untertitel der Amara.org-Community')
    typefree._verarbeite_audio(np.zeros(typefree.SAMPLE_RATE * 2, dtype=np.float32))
    assert ablauf.eingefuegt == []
    assert gerufen == []


def _live_zuruecksetzen():
    with typefree.lock:
        typefree.live_teile.clear()
        typefree.live_ausstehend = ''
        typefree.live_verworfen = 0


def test_live_ruft_absaetze_nicht(monkeypatch, ablauf):
    gerufen = []
    monkeypatch.setattr(typefree, 'absaetze_an', True)
    monkeypatch.setattr(ab, 'absaetze', lambda t: gerufen.append(t) or (t, 0))
    eingefuegt = []
    _live_zuruecksetzen()
    try:
        typefree._live_stueck_verarbeiten(
            sprache(4), lambda stueck: (LANG, 'mai'),
            lambda kern, fuge: eingefuegt.append(kern))
    finally:
        _live_zuruecksetzen()
    assert gerufen == []
    assert eingefuegt and '\n\n' not in eingefuegt[0]


# ── Schalter in der config.json ──────────────────────────────────────────────

def _konfig(tmp_path, monkeypatch):
    pfad = tmp_path / 'config.json'
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(pfad))
    return pfad


def test_schalter_ist_standardmaessig_aus(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    assert typefree.load_absaetze_config() is False


def test_schalter_merkt_sich_die_wahl(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    typefree.save_absaetze_config(True)
    assert typefree.load_absaetze_config() is True
    typefree.save_absaetze_config(False)
    assert typefree.load_absaetze_config() is False


def test_schalter_ueberschreibt_andere_einstellungen_nicht(tmp_path, monkeypatch):
    pfad = _konfig(tmp_path, monkeypatch)
    typefree.save_ton_aus_config(False)
    typefree.save_absaetze_config(True)
    assert typefree.load_ton_aus_config() is False
    assert '"absaetze": true' in pfad.read_text(encoding='utf-8')
    typefree.save_ton_aus_config(True)
    assert typefree.load_absaetze_config() is True


def test_kaputte_config_ist_aus(tmp_path, monkeypatch):
    pfad = _konfig(tmp_path, monkeypatch)
    pfad.write_text('{kaputt', encoding='utf-8')
    assert typefree.load_absaetze_config() is False


def test_tray_haekchen_schaltet_und_speichert(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    monkeypatch.setattr(typefree, 'absaetze_an', False)
    typefree._schalte_absaetze(None, None)
    assert typefree.absaetze_an is True
    assert typefree.load_absaetze_config() is True
    typefree._schalte_absaetze(None, None)
    assert typefree.absaetze_an is False
    assert typefree.load_absaetze_config() is False
