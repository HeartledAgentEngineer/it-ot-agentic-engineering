"""Feste Ersetzungen (Scheibe 3, 20.10.2026).

Reine Funktionen in `ersetzungen.py` plus die Verdrahtung in `typefree`. Dateien
nur in `tmp_path`; nichts wird getippt, keine echte Zwischenablage, kein echtes
`os.startfile` (die Nähte `zwischenablage_einfuegen`, `unicode_tippen` und
`datei_oeffnen` sind in conftest gesperrt und werden hier selbst ersetzt).
"""
import os

import numpy as np
import pytest

import ersetzungen as er
import typefree


def regeln_aus(text):
    regeln, kaputt = er.einlesen(text)
    assert kaputt == 0
    return regeln


def wende(text, regel_text):
    return er.anwenden(text, regeln_aus(regel_text))


# ── Wortgrenzen ───────────────────────────────────────────────────────────────

def test_kein_treffer_mitten_im_wort():
    assert wende('Der Kalender ist voll', 'ende => Schluss') == 'Der Kalender ist voll'


def test_treffer_vor_punkt_und_komma():
    assert wende('Das ist das ende.', 'ende => Schluss') == 'Das ist das Schluss.'
    assert wende('Am ende, dann', 'ende => Schluss') == 'Am Schluss, dann'


def test_treffer_am_textanfang_und_textende():
    assert wende('ende gut, alles ende', 'ende => X') == 'X gut, alles X'


def test_regel_mit_satzzeichen_am_rand():
    assert wende('Ich mag c++ sehr', 'c++ => C Plus Plus') == 'Ich mag C Plus Plus sehr'
    assert wende('Ich mag c++', 'c++ => CPP') == 'Ich mag CPP'


# ── Mehrwort, Groß/klein ─────────────────────────────────────────────────────

@pytest.mark.parametrize('gesagt', ['n acht n', 'N-acht-N', 'n  acht   n', 'N Acht-n',
                                    'n \t acht - n'])
def test_mehrwort_mit_leerzeichen_und_bindestrich(gesagt):
    assert wende(f'Ich nutze {gesagt} täglich', 'n acht n => n8n') == 'Ich nutze n8n täglich'


def test_gross_klein_egal():
    assert wende('KLOD kode', 'klod kode => Claude Code') == 'Claude Code'
    assert wende('Klod Kode', 'klod kode => Claude Code') == 'Claude Code'


def test_bindestrich_in_regel_trifft_auch_leerzeichen():
    assert wende('e mail und e-mail', 'e-mail => Mail') == 'Mail und Mail'


# ── Vorrang, keine Kette ──────────────────────────────────────────────────────

def test_laengere_regel_hat_vorrang():
    regeln = 'claude => Claude\nclaude code => Claude Code'
    assert wende('mit claude code arbeiten', regeln) == 'mit Claude Code arbeiten'
    # Reihenfolge in der Datei ist egal
    regeln = 'claude code => Claude Code\nclaude => Claude'
    assert wende('mit claude code und claude', regeln) == 'mit Claude Code und Claude'


def test_keine_kette():
    assert wende('a und b', 'a => b\nb => c') == 'b und c'
    assert wende('a', 'a => b\nb => c') == 'b'


def test_keine_ueberlappung_ein_durchgang():
    assert wende('ab ab', 'ab => ab ab') == 'ab ab ab ab'


# ── wörtlicher Ersatz ────────────────────────────────────────────────────────

def test_ersatz_wird_woertlich_eingesetzt():
    assert wende('pfad', r'pfad => C:\neu\1\g<0>') == r'C:\neu\1\g<0>'


# ── Dateiformat ───────────────────────────────────────────────────────────────

def test_kommentare_leerzeilen_und_kaputte_zeilen():
    text = ('# Kommentar\n'
            '\n'
            '   # eingerückter Kommentar\n'
            'a => b\n'
            'ohne pfeil\n'
            ' => nur rechts\n'
            '   \n'
            'c => d  \n')
    regeln, kaputt = er.einlesen(text)
    assert regeln == [('a', 'b'), ('c', 'd')]
    assert kaputt == 2


def test_leerraum_um_beide_seiten_wird_entfernt():
    regeln, _ = er.einlesen('   klod   kode   =>    Claude Code   \n')
    assert er.anwenden('klod kode', regeln) == 'Claude Code'
    assert regeln[0][1] == 'Claude Code'


def test_rechte_seite_darf_leer_sein():
    regeln, kaputt = er.einlesen('äh =>\nähm => \n')
    assert kaputt == 0 and [r for _, r in regeln] == ['', '']


def test_rechte_seite_darf_pfeil_enthalten():
    regeln, kaputt = er.einlesen('pfeil => a => b\n')
    assert kaputt == 0 and regeln == [('pfeil', 'a => b')]


def test_bom_wird_toleriert(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_bytes('\ufeffa => b\n'.encode('utf-8'))
    assert er.Ersetzungen(str(datei)).regeln() == [('a', 'b')]


def test_leere_regelliste_laesst_text_unveraendert():
    assert er.anwenden('Hallo  Welt', []) == 'Hallo  Welt'
    assert er.anwenden('', regeln_aus('a => b')) == ''


# ── Umlaute / ß ──────────────────────────────────────────────────────────────

def test_umlaute_und_eszett_sind_wortzeichen():
    regeln = 'grüße => Gruß'
    assert wende('viele Grüße', regeln) == 'viele Gruß'
    assert wende('wir Grüßen', regeln) == 'wir Grüßen'
    assert wende('Größe', 'größe => Groesse') == 'Groesse'
    assert wende('Übergröße', 'größe => X') == 'Übergröße'


def test_umlaut_regel_mit_grossbuchstaben_im_text():
    assert wende('ÜBER Alles', 'über => ueber') == 'ueber Alles'


# ── Löschen ──────────────────────────────────────────────────────────────────

def test_loesch_regel_zieht_leerzeichen_zusammen():
    assert wende('Das äh ist gut', 'äh =>') == 'Das ist gut'


def test_loesch_regel_am_anfang_und_ende():
    assert wende('äh das ist gut', 'äh =>') == 'das ist gut'
    assert wende('das ist gut äh', 'äh =>') == 'das ist gut '


def test_loesch_regel_laesst_fremde_doppelte_leerzeichen_stehen():
    assert wende('a  b äh c', 'äh =>') == 'a  b c'
    assert wende('a  b c', 'äh =>') == 'a  b c'


def test_loesch_regel_mehrere_nacheinander():
    assert wende('so äh ähm also', 'äh =>\nähm =>') == 'so also'


# ── Doppelte Regeln ──────────────────────────────────────────────────────────

def test_spaetere_doppelregel_gewinnt():
    assert wende('foo', 'foo => eins\nFOO => zwei') == 'zwei'


def test_doppelregel_nach_normalisierung_leerraum_und_bindestrich():
    assert wende('a b', 'a b => eins\na-b => zwei') == 'zwei'


# ── muster ────────────────────────────────────────────────────────────────────

def test_muster_ohne_regeln_ist_none():
    assert er.muster([]) is None


def test_muster_ist_ein_kompilierter_ausdruck():
    import re
    assert isinstance(er.muster(regeln_aus('a => b\nc => d')), re.Pattern)


# ── Lader ────────────────────────────────────────────────────────────────────

def setze_mtime(pfad, sekunden):
    os.utime(pfad, (sekunden, sekunden))


def test_fehlende_datei_gibt_leere_liste(tmp_path):
    e = er.Ersetzungen(str(tmp_path / 'gibt_es_nicht.txt'))
    assert e.regeln() == []
    assert e.anwenden('hallo') == ('hallo', 0)


def test_lader_liest_bei_aenderung_neu(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_text('a => b\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_000)
    e = er.Ersetzungen(str(datei))
    assert e.regeln() == [('a', 'b')]

    # gleiche Größe, gleiche mtime → Cache (die Datei wird nicht neu gelesen)
    datei.write_text('a => c\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_000)
    assert e.regeln() == [('a', 'b')]

    # andere mtime → neu gelesen
    setze_mtime(datei, 1_000_000_100)
    assert e.regeln() == [('a', 'c')]


def test_lader_liest_bei_aenderung_der_groesse_neu(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_text('a => b\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_000)
    e = er.Ersetzungen(str(datei))
    assert e.regeln() == [('a', 'b')]
    datei.write_text('a => b\nc => d\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_000)
    assert e.regeln() == [('a', 'b'), ('c', 'd')]


def test_lader_wirkt_auf_anwenden(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_text('klod => Claude\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_000)
    e = er.Ersetzungen(str(datei))
    assert e.anwenden('mit klod und klod') == ('mit Claude und Claude', 2)
    datei.write_text('klod => Opus\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_200)
    assert e.anwenden('mit klod') == ('mit Opus', 1)


def test_lader_datei_verschwindet_gibt_leere_liste(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_text('a => b\n', encoding='utf-8')
    e = er.Ersetzungen(str(datei))
    assert e.regeln() == [('a', 'b')]
    datei.unlink()
    assert e.regeln() == []


def test_lesefehler_behaelt_letzte_gueltige_regeln_und_loggt_einmal(tmp_path, caplog):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_text('a => b\n', encoding='utf-8')
    setze_mtime(datei, 1_000_000_000)
    e = er.Ersetzungen(str(datei))
    assert e.regeln() == [('a', 'b')]

    datei.write_bytes(b'a => \xff\xfe\xfa kaputt\n')      # kein gültiges UTF-8
    setze_mtime(datei, 1_000_000_100)
    with caplog.at_level('WARNING', logger='typefree'):
        assert e.regeln() == [('a', 'b')]
        assert e.regeln() == [('a', 'b')]
        assert e.regeln() == [('a', 'b')]
    meldungen = [r for r in caplog.records if 'rsetzungen' in r.getMessage()]
    assert len(meldungen) == 1
    assert 'kaputt' not in meldungen[0].getMessage()


def test_lesefehler_beim_ersten_laden_gibt_leere_liste(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_bytes(b'\xff\xfe\xfa')
    assert er.Ersetzungen(str(datei)).regeln() == []


def test_lader_zaehlt_kaputte_zeilen(tmp_path):
    datei = tmp_path / 'ersetzungen.txt'
    datei.write_text('a => b\nkaputt\n', encoding='utf-8')
    e = er.Ersetzungen(str(datei))
    assert e.regeln() == [('a', 'b')]
    assert e.kaputt == 1


# ── Vorlage ──────────────────────────────────────────────────────────────────

def test_vorlage_ist_gueltig_und_hat_nur_auskommentierte_beispiele():
    regeln, kaputt = er.einlesen(er.VORLAGE)
    assert regeln == [] and kaputt == 0
    for beispiel in ('# n acht n => n8n', '# klod kode => Claude Code',
                     '# typ frei => typeFREE'):
        assert beispiel in er.VORLAGE


def test_vorlage_beispiele_funktionieren_ohne_kommentarzeichen():
    entkommentiert = '\n'.join(
        z[2:] for z in er.VORLAGE.splitlines() if z.startswith('# ') and '=>' in z)
    regeln = regeln_aus(entkommentiert)
    assert er.anwenden('ich nutze N-Acht-N und klod kode', regeln) == \
        'ich nutze n8n und Claude Code'


def test_anlegen_falls_fehlt_schreibt_vorlage(tmp_path):
    pfad = tmp_path / 'ersetzungen.txt'
    er.anlegen_falls_fehlt(str(pfad))
    assert pfad.read_text(encoding='utf-8') == er.VORLAGE


def test_anlegen_falls_fehlt_ueberschreibt_nie(tmp_path):
    pfad = tmp_path / 'ersetzungen.txt'
    pfad.write_text('meine => Regeln\n', encoding='utf-8')
    er.anlegen_falls_fehlt(str(pfad))
    assert pfad.read_text(encoding='utf-8') == 'meine => Regeln\n'


# ── Einhängen in typefree ────────────────────────────────────────────────────

class Ablauf:
    pass


@pytest.fixture
def ablauf(monkeypatch, tmp_path):
    s = Ablauf()
    s.eingefuegt, s.fehler, s.blocks, s.geoeffnet = [], [], [], []
    s.datei = tmp_path / 'ersetzungen.txt'
    s.datei.write_text('klod kode => Claude Code\näh =>\n', encoding='utf-8')
    setze_mtime(s.datei, 1_000_000_000)
    monkeypatch.setattr(typefree, '_ersetzungen', er.Ersetzungen(str(s.datei)))

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


def test_ersetzen_wendet_regeln_an(ablauf):
    assert typefree.ersetzen('ich nutze Klod Kode') == 'ich nutze Claude Code'


def test_ersetzen_loggt_nur_die_anzahl(ablauf, caplog):
    with caplog.at_level('INFO', logger='typefree'):
        typefree.ersetzen('klod kode und klod kode')
    zeilen = [r.getMessage() for r in caplog.records if 'Treffer' in r.getMessage()]
    assert zeilen == ['Ersetzungen: 2 Treffer']


def test_ersetzen_ohne_treffer_loggt_nichts(ablauf, caplog):
    with caplog.at_level('INFO', logger='typefree'):
        assert typefree.ersetzen('nichts dabei') == 'nichts dabei'
    assert not [r for r in caplog.records if 'Treffer' in r.getMessage()]


def test_ersetzen_bei_fehler_text_unveraendert(ablauf, monkeypatch, caplog):
    class Kaputt:
        def anwenden(self, text):
            raise RuntimeError('geheimer diktattext')

    monkeypatch.setattr(typefree, '_ersetzungen', Kaputt())
    with caplog.at_level('DEBUG', logger='typefree'):
        assert typefree.ersetzen('klod kode') == 'klod kode'
    protokoll = caplog.text + ''.join(str(r.exc_info) for r in caplog.records)
    assert 'geheimer diktattext' not in protokoll
    assert 'RuntimeError' in caplog.text


def test_ersetzungen_pfad_liegt_neben_der_config():
    assert os.path.dirname(typefree.ersetzungen_pfad()) == os.path.dirname(typefree.CONFIG_PATH)
    assert os.path.basename(typefree.ersetzungen_pfad()) == 'ersetzungen.txt'


def test_diktat_bekommt_ersetzten_text_eingefuegt(monkeypatch, ablauf):
    diktat(monkeypatch, 'Ich nutze klod kode jeden Tag')
    typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == ['Ich nutze Claude Code jeden Tag']
    assert ablauf.fehler == []


def test_letztes_diktat_enthaelt_den_ersetzten_text(monkeypatch, ablauf):
    diktat(monkeypatch, 'mit klod kode')
    typefree._verarbeite_audio(sprache(2.0))
    assert typefree.letztes_diktat == 'mit Claude Code'


def test_ersetzung_wirkt_auf_den_geglaetteten_text(monkeypatch, ablauf):
    diktat(monkeypatch, 'roh')
    monkeypatch.setattr(typefree, 'polish_text', lambda text: 'Geglättet klod kode.')
    typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == ['Geglättet Claude Code.']


def test_fehler_in_ersetzungen_fuegt_originaltext_ein(monkeypatch, ablauf):
    class Kaputt:
        def anwenden(self, text):
            raise RuntimeError('boom')

    monkeypatch.setattr(typefree, '_ersetzungen', Kaputt())
    diktat(monkeypatch, 'mit klod kode')
    typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == ['mit klod kode']
    assert ablauf.fehler == []


def test_halluzinations_verwerfpfad_ruft_ersetzen_nicht(monkeypatch, ablauf):
    gerufen = []
    monkeypatch.setattr(typefree, 'ersetzen', lambda t: gerufen.append(t) or t)
    diktat(monkeypatch, 'Untertitel der Amara.org-Community')
    typefree._verarbeite_audio(np.zeros(typefree.SAMPLE_RATE * 2, dtype=np.float32))
    assert ablauf.eingefuegt == []
    assert gerufen == []


@pytest.fixture
def live(monkeypatch, ablauf):
    def zuruecksetzen():
        with typefree.lock:
            typefree.live_teile.clear()
            typefree.live_ausstehend = ''
            typefree.live_verworfen = 0
    zuruecksetzen()
    yield
    zuruecksetzen()


def test_live_block_ganz_geloescht_wird_gebucht_und_als_verworfen_gezaehlt(live, ablauf):
    """Codex R1: Ein von einer Lösch-Regel geleerter Block kostet trotzdem und
    zählt als verworfen — sonst sendete der Abschluss die Aufnahme erneut."""
    eingefuegt, gebucht = [], []
    ergebnis = typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('äh.', 'mai'),
        lambda kern, fuge: eingefuegt.append(kern),
        buchen=lambda sek, anbieter: gebucht.append(anbieter))
    assert ergebnis is None and eingefuegt == []
    assert gebucht == ['mai']
    assert typefree.live_verworfen == 1


def test_live_nur_satzzeichen_ohne_ersetzung_bleibt_wie_bisher(live, ablauf):
    gebucht = []
    typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('…', 'mai'), lambda k, f: None,
        buchen=lambda sek, anbieter: gebucht.append(anbieter))
    assert gebucht == [] and typefree.live_verworfen == 0


def test_live_block_wird_ersetzt_getippt(live, ablauf):
    eingefuegt = []
    text = typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('ich nutze klod kode.', 'mai'),
        lambda kern, fuge: eingefuegt.append((kern, fuge)))
    assert eingefuegt == [('ich nutze Claude Code', '')]
    assert text == 'ich nutze Claude Code'


def test_live_roh_text_fuer_geht_weiter_bleibt_unveraendert(live, ablauf, monkeypatch):
    """Die Fortsetzungsprüfung sieht den ROHEN Text, nicht den ersetzten."""
    gesehen = []
    echt = typefree.geht_weiter
    monkeypatch.setattr(typefree, 'geht_weiter',
                        lambda t: gesehen.append(t) or echt(t))
    with typefree.lock:
        typefree.live_teile.append({'text': 'vorher', 'roh': 'vorher',
                                    'fenster': '', 'zeit': 0.0})
    typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('klod kode läuft', 'mai'),
        lambda kern, fuge: None)
    assert gesehen == ['klod kode läuft']


def test_live_fehler_in_ersetzungen_tippt_original(live, ablauf, monkeypatch):
    class Kaputt:
        def anwenden(self, text):
            raise RuntimeError('boom')

    monkeypatch.setattr(typefree, '_ersetzungen', Kaputt())
    eingefuegt = []
    typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('klod kode', 'mai'),
        lambda kern, fuge: eingefuegt.append(kern))
    assert eingefuegt == ['klod kode']


# ── Tray-Eintrag ─────────────────────────────────────────────────────────────

def test_tray_legt_datei_an_und_oeffnet_ueber_die_naht(monkeypatch, tmp_path):
    ziel = tmp_path / 'ersetzungen.txt'
    geoeffnet, fehler = [], []
    monkeypatch.setattr(typefree, 'ersetzungen_pfad', lambda: str(ziel))
    monkeypatch.setattr(typefree, 'datei_oeffnen', geoeffnet.append)
    monkeypatch.setattr(typefree, 'report_error', fehler.append)
    typefree._on_ersetzungen_bearbeiten(None, None)
    assert ziel.read_text(encoding='utf-8') == er.VORLAGE
    assert geoeffnet == [str(ziel)]
    assert fehler == []


def test_tray_ueberschreibt_vorhandene_datei_nicht(monkeypatch, tmp_path):
    ziel = tmp_path / 'ersetzungen.txt'
    ziel.write_text('a => b\n', encoding='utf-8')
    geoeffnet = []
    monkeypatch.setattr(typefree, 'ersetzungen_pfad', lambda: str(ziel))
    monkeypatch.setattr(typefree, 'datei_oeffnen', geoeffnet.append)
    typefree._on_ersetzungen_bearbeiten(None, None)
    assert ziel.read_text(encoding='utf-8') == 'a => b\n'
    assert geoeffnet == [str(ziel)]


def test_tray_fehler_beim_oeffnen_geht_an_report_error(monkeypatch, tmp_path):
    ziel = tmp_path / 'ersetzungen.txt'
    fehler = []

    def platzt(pfad):
        raise OSError('kein Editor')

    monkeypatch.setattr(typefree, 'ersetzungen_pfad', lambda: str(ziel))
    monkeypatch.setattr(typefree, 'datei_oeffnen', platzt)
    monkeypatch.setattr(typefree, 'report_error', fehler.append)
    typefree._on_ersetzungen_bearbeiten(None, None)
    assert len(fehler) == 1 and 'kein Editor' in fehler[0]


def test_datei_oeffnen_ist_in_tests_gesperrt():
    with pytest.raises(AssertionError):
        typefree.datei_oeffnen('irgendwas.txt')


def test_diktat_das_nach_ersetzungen_leer_ist_wird_nicht_eingefuegt_aber_gebucht(
        monkeypatch, ablauf):
    """Löscht eine Regel alles (nur „äh"), wird nichts Leeres eingefügt; die
    Anfrage lief und wird gebucht, die Aufnahme verworfen."""
    gebucht = []
    monkeypatch.setattr(typefree, '_diktat_buchen', lambda d, a: gebucht.append(a))
    diktat(monkeypatch, 'äh')
    typefree._verarbeite_audio(sprache(2.0))
    assert ablauf.eingefuegt == []
    assert gebucht == ['mai']
    assert ablauf.fehler == []
    assert not typefree.retry_bereit()
