"""Halluzinationsfilter und Mindestdauer (Scheibe 1, 20.10.2026).

Whisper-artige Modelle erfinden bei Stille oder Rauschen Abspänne („Untertitel im
Auftrag des ZDF, 2021") und Höflichkeitsfloskeln („Danke."). Diese Prüfungen
sichern ab, dass solche Texte nie im Dokument landen und dass Mini-Tipper gar
nicht erst gesendet werden — alles ohne Mikrofon, Netz und echte Eingabe.
"""
import numpy as np
import pytest

import halluzination
import typefree

RATE = 16000


def sinus(sekunden, amplitude=0.1, rate=RATE):
    t = np.arange(int(sekunden * rate)) / rate
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def stille(sekunden, rate=RATE):
    return np.zeros(int(sekunden * rate), dtype=np.float32)


def sprache(sekunden):
    """Rauschen in Sprechlautstärke (wie in test_retry.py)."""
    rng = np.random.default_rng(3)
    return rng.normal(0, 0.2, int(sekunden * RATE)).astype(np.float32)


# ── Listen und Normalisierung ────────────────────────────────────────────────

def test_listen_sind_gefuellt_und_normalisiert():
    assert len(halluzination.ABSPANN) > 10
    assert len(halluzination.ZWEIFELHAFT) > 10
    for eintrag in halluzination.ABSPANN | halluzination.ZWEIFELHAFT:
        assert eintrag == halluzination.normalisieren(eintrag), eintrag


def test_normalisieren_klein_ohne_satzzeichen():
    assert halluzination.normalisieren('  Hallo,  Welt!! ') == 'hallo welt'
    assert halluzination.normalisieren('Amara.org-Community') == 'amara org community'
    assert halluzination.normalisieren('') == ''
    assert halluzination.normalisieren('...') == ''


def test_schluessel_entfernt_reine_zahlwoerter():
    assert halluzination.schluessel('ZDF, 2021') == 'zdf'
    assert halluzination.schluessel('Version 2 von 3b') == 'version von 3b'


def test_untertitel_mit_jahreszahl_ist_erfunden():
    assert halluzination.ist_erfunden('Untertitel im Auftrag des ZDF, 2021.', 5.0)
    assert halluzination.ist_erfunden('Untertitel im Auftrag des ZDF für funk, 2017', 5.0)


# ── ist_erfunden ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize('text', sorted(halluzination.ABSPANN))
def test_abspann_ist_immer_erfunden(text):
    assert halluzination.ist_erfunden(text, 5.0)
    assert halluzination.ist_erfunden(text.capitalize() + '.', 0.0)


def test_danke_nur_bei_stille_erfunden():
    assert halluzination.ist_erfunden('Danke.', 0.0)
    assert not halluzination.ist_erfunden('Danke.', 2.0)


def test_echter_satz_mit_danke_nie_erfunden():
    satz = 'Danke für die schnelle Antwort.'
    assert not halluzination.ist_erfunden(satz, 0.0)
    assert not halluzination.ist_erfunden(satz, 3.0)


def test_leerer_text_ist_nicht_erfunden():
    assert not halluzination.ist_erfunden('', 0.0)
    assert not halluzination.ist_erfunden('  ...  ', 0.0)


# ── abspann_entfernen ────────────────────────────────────────────────────────

def test_abspann_am_ende_wird_abgeschnitten():
    assert halluzination.abspann_entfernen(
        'Wir sehen uns morgen. Untertitel im Auftrag des ZDF, 2021.'
    ) == 'Wir sehen uns morgen.'


def test_abspann_aus_zwei_saetzen_am_ende():
    assert halluzination.abspann_entfernen(
        'Das war der Bericht. Vielen Dank fürs Zuschauen. Bitte abonnieren.'
    ) == 'Das war der Bericht.'


def test_wiederholter_abspann_wird_ganz_entfernt():
    assert halluzination.abspann_entfernen(
        'Bis morgen. Thanks for watching. Thanks for watching. Please subscribe.'
    ) == 'Bis morgen.'


def test_nur_abspann_ergibt_leeren_text():
    assert halluzination.abspann_entfernen('Untertitel der Amara.org-Community') == ''


def test_amara_org_bleibt_ein_satz():
    assert halluzination.abspann_entfernen(
        'Das klappt. Untertitel der Amara.org-Community'
    ) == 'Das klappt.'


def test_text_ohne_abspann_nur_gestrippt():
    assert halluzination.abspann_entfernen('  Ein ganz normaler Satz.  ') == 'Ein ganz normaler Satz.'
    assert halluzination.abspann_entfernen('') == ''


def test_abspann_mitten_im_text_bleibt():
    text = 'Erst das. Bitte abonnieren. Dann geht es weiter mit dem Thema.'
    assert halluzination.abspann_entfernen(text) == text


def test_abspann_nach_zeilenumbruch():
    assert halluzination.abspann_entfernen(
        'Erster Absatz.\nUntertitel im Auftrag des ZDF, 2021'
    ) == 'Erster Absatz.'


# ── stimm_sekunden ───────────────────────────────────────────────────────────

def test_stimm_sekunden_stille_ist_null():
    assert halluzination.stimm_sekunden(stille(1.0)) == 0.0
    assert halluzination.stimm_sekunden(np.zeros(0, dtype=np.float32)) == 0.0


def test_stimm_sekunden_sinus_ist_eine_sekunde():
    assert halluzination.stimm_sekunden(sinus(1.0)) == pytest.approx(1.0, abs=0.03)


def test_stimm_sekunden_halb_sprache_halb_stille():
    daten = np.concatenate([sinus(0.5), stille(0.5)])
    assert halluzination.stimm_sekunden(daten) == pytest.approx(0.5, abs=0.03)


def test_stimm_sekunden_mikrofonform_n_mal_eins():
    daten = sinus(1.0).reshape(-1, 1)
    assert halluzination.stimm_sekunden(daten) == pytest.approx(1.0, abs=0.03)


def test_stimm_sekunden_leise_unter_schwelle_zaehlt_nicht():
    assert halluzination.stimm_sekunden(sinus(1.0, amplitude=0.005)) == 0.0


# ── Einhängen in typefree.py ─────────────────────────────────────────────────

@pytest.fixture
def stand(monkeypatch):
    """Ruhiggestellte Umgebung mit Aufzeichnung dessen, was passieren würde."""
    s = {'kopiert': [], 'hotkeys': [], 'gebucht': [], 'polish': [], 'transkribiert': []}
    monkeypatch.setattr(typefree.time, 'sleep', lambda sek: None)
    monkeypatch.setattr(typefree, 'pyperclip',
                        type('P', (), {'copy': staticmethod(s['kopiert'].append)}))
    monkeypatch.setattr(typefree, 'pyautogui',
                        type('G', (), {'hotkey': staticmethod(lambda *a: s['hotkeys'].append(a))}))
    monkeypatch.setattr(typefree, 'save_verbrauch', lambda *a, **k: None)
    monkeypatch.setattr(typefree, '_status_transcribing', lambda: None)
    monkeypatch.setattr(typefree, '_status_polishing', lambda: None)
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, 'report_error', lambda text: None)
    monkeypatch.setattr(typefree, '_close_stream', lambda: None)
    monkeypatch.setattr(typefree, '_ton_zurueck_melden', lambda sitzung: None)

    def polieren(text, *a, **k):
        s['polish'].append(text)
        return text

    def buchen(verbrauch, sekunden, monat, anbieter=None, diktat=True):
        s['gebucht'].append((sekunden, anbieter))
        return verbrauch

    monkeypatch.setattr(typefree, 'polish_text', polieren)
    monkeypatch.setattr(typefree, 'verbrauch_buchen', buchen)
    typefree.retry_verwerfen()
    yield s
    typefree.retry_verwerfen()


def transkribiert(monkeypatch, stand, text, anbieter='mai'):
    def fake(puffer, clients, **_):
        stand['transkribiert'].append(text)
        return text, anbieter
    monkeypatch.setattr(typefree, 'transcribe_audio', fake)


def test_zu_kurze_aufnahme_wird_nicht_gesendet(monkeypatch, stand):
    transkribiert(monkeypatch, stand, 'Hallo')
    monkeypatch.setattr(typefree, 'audio_frames', [sprache(0.2).reshape(-1, 1)])
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_live_lief', False)

    typefree.stop_and_transcribe()

    assert stand['transkribiert'] == [], 'zu kurz: keine Transkription'
    assert stand['gebucht'] == [], 'zu kurz: keine Buchung'
    assert stand['kopiert'] == [] and stand['hotkeys'] == []


def test_aufnahme_ab_mindestdauer_wird_verarbeitet(monkeypatch, stand):
    transkribiert(monkeypatch, stand, 'Hallo zusammen')
    monkeypatch.setattr(typefree, 'audio_frames', [sprache(1.0).reshape(-1, 1)])
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_live_lief', False)

    typefree.stop_and_transcribe()

    assert stand['transkribiert'] == ['Hallo zusammen']
    assert stand['kopiert'] == ['Hallo zusammen']
    assert len(stand['gebucht']) == 1


def test_erfundener_abspann_wird_verworfen_aber_gebucht(monkeypatch, stand):
    transkribiert(monkeypatch, stand, 'Untertitel im Auftrag des ZDF, 2021.')
    typefree._verarbeite_audio(sprache(3.0))

    assert stand['kopiert'] == [] and stand['hotkeys'] == [], 'nichts eingefügt'
    assert stand['polish'] == [], 'nicht geglättet'
    assert len(stand['gebucht']) == 1, 'die Transkription lief und kostet'
    assert stand['gebucht'][0][1] == 'mai'
    assert not typefree.retry_bereit()


def test_danke_auf_stillem_audio_wird_verworfen(monkeypatch, stand):
    transkribiert(monkeypatch, stand, 'Danke.')
    typefree._verarbeite_audio(stille(2.0))

    assert stand['kopiert'] == [] and stand['hotkeys'] == []
    assert len(stand['gebucht']) == 1


def test_danke_auf_sprache_wird_eingefuegt(monkeypatch, stand):
    transkribiert(monkeypatch, stand, 'Danke.')
    typefree._verarbeite_audio(sprache(2.0))

    assert stand['kopiert'] == ['Danke.']
    assert stand['hotkeys'] == [('ctrl', 'v')]
    assert len(stand['gebucht']) == 1


def test_abspann_am_ende_wird_vor_dem_einfuegen_abgeschnitten(monkeypatch, stand):
    transkribiert(monkeypatch, stand, 'Wir sehen uns morgen. Untertitel im Auftrag des ZDF, 2021.')
    typefree._verarbeite_audio(sprache(3.0))

    assert stand['polish'] == ['Wir sehen uns morgen.']
    assert stand['kopiert'] == ['Wir sehen uns morgen.']


def test_leerer_text_wird_verworfen_statt_leer_eingefuegt(monkeypatch, stand):
    transkribiert(monkeypatch, stand, '')
    typefree._verarbeite_audio(sprache(2.0))

    assert stand['kopiert'] == [] and stand['hotkeys'] == []
    assert len(stand['gebucht']) == 1


@pytest.fixture
def live_frisch():
    def zuruecksetzen():
        with typefree.lock:
            typefree.live_teile.clear()
            typefree.live_ausstehend = ''
            typefree.live_verworfen = 0
            typefree.live_fehler = False
    zuruecksetzen()
    yield
    zuruecksetzen()


def test_live_erfundener_happen_wird_verworfen_aber_gebucht(live_frisch):
    eingefuegt, gebucht = [], []
    ergebnis = typefree._live_stueck_verarbeiten(
        sprache(3), lambda s: ('Vielen Dank fürs Zuschauen.', 'mai'),
        lambda kern, fuge: eingefuegt.append(kern),
        buchen=lambda sek, anbieter: gebucht.append((sek, anbieter)))

    assert ergebnis is None
    assert eingefuegt == []
    assert len(gebucht) == 1 and gebucht[0][1] == 'mai'
    assert gebucht[0][0] == pytest.approx(3.0)


def test_live_normaler_satz_wird_wie_bisher_eingefuegt(live_frisch):
    eingefuegt, gebucht = [], []
    ergebnis = typefree._live_stueck_verarbeiten(
        sprache(3), lambda s: ('Das ist ein normaler Satz.', 'mai'),
        lambda kern, fuge: eingefuegt.append(kern),
        buchen=lambda sek, anbieter: gebucht.append((sek, anbieter)))

    assert ergebnis is not None
    assert eingefuegt == [ergebnis]
    assert len(gebucht) == 1


def test_live_abspann_am_happenende_wird_abgeschnitten(live_frisch):
    eingefuegt = []
    typefree._live_stueck_verarbeiten(
        sprache(3), lambda s: ('Bis gleich. Thanks for watching.', 'mai'),
        lambda kern, fuge: eingefuegt.append(kern))
    assert len(eingefuegt) == 1
    assert 'watching' not in eingefuegt[0]
    assert eingefuegt[0].startswith('Bis gleich')


def test_live_danke_auf_stille_verworfen(live_frisch):
    eingefuegt, gebucht = [], []
    ergebnis = typefree._live_stueck_verarbeiten(
        stille(3), lambda s: ('Danke.', 'mai'),
        lambda kern, fuge: eingefuegt.append(kern),
        buchen=lambda sek, anbieter: gebucht.append(anbieter))
    assert ergebnis is None and eingefuegt == [] and gebucht == ['mai']


def test_live_happen_ohne_text_bucht_weiterhin_nicht(live_frisch):
    gebucht = []
    assert typefree._live_stueck_verarbeiten(
        sprache(3), lambda s: ('', 'mai'), lambda k, f: None,
        buchen=lambda sek, anbieter: gebucht.append(anbieter)) is None
    assert gebucht == []


# ── Live-Abschluss: verworfen ist nicht gescheitert (Codex-Ergebnisprüfung R1) ──

def _abschluss_ruhig(monkeypatch, rest_text, rest_platzt=False, schreiber_fertig=True):
    """Abschluss ohne Schreiber, Tippen und Buchhaltung; der Rest liefert `rest_text`."""
    def transkribieren(stueck):
        if rest_platzt:
            raise RuntimeError('Netz weg')
        return rest_text, 'mai'
    gebucht = []
    monkeypatch.setattr(typefree, '_live_warte_auf_schreiber', lambda: schreiber_fertig)
    monkeypatch.setattr(typefree, '_live_transkribieren', transkribieren)
    monkeypatch.setattr(typefree, '_live_glaetten', lambda roh: roh)
    monkeypatch.setattr(typefree, '_live_buchen', lambda s, a: gebucht.append(a))
    monkeypatch.setattr(typefree, '_tippen_animiert', lambda t: None)
    monkeypatch.setattr(typefree, '_fenster_titel', lambda: 'Editor')
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, 'live_geschnitten', 0.0)
    return gebucht


def test_live_alles_verworfen_sendet_die_aufnahme_nicht_erneut(monkeypatch, live_frisch):
    """Nur Erfundenes gehört: Abschluss meldet True — die normale Verarbeitung
    (zweiter, bezahlter Aufruf über die ganze Aufnahme) läuft NICHT."""
    gebucht = _abschluss_ruhig(monkeypatch, 'Untertitel im Auftrag des ZDF, 2021.')
    assert typefree._live_abschluss(stille(2)) is True
    assert gebucht == ['mai']          # der verworfene Rest ist gebucht, einmal


def test_stop_ruft_nach_verworfenem_live_keine_normale_verarbeitung(monkeypatch, live_frisch):
    _abschluss_ruhig(monkeypatch, 'Thanks for watching.')
    normal = []
    monkeypatch.setattr(typefree, '_verarbeite_audio', lambda *a, **k: normal.append(a))
    monkeypatch.setattr(typefree, '_close_stream', lambda: None)
    monkeypatch.setattr(typefree, '_ton_zurueck_melden', lambda sitzung: None)
    monkeypatch.setattr(typefree, '_status_transcribing', lambda: None)
    monkeypatch.setattr(typefree, '_live_lief', True)
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, 'audio_frames', [sprache(2).reshape(-1, 1)])
    typefree.stop_and_transcribe()
    assert normal == []


def test_live_verworfen_und_gescheitert_uebernimmt_die_normale_verarbeitung(
        monkeypatch, live_frisch):
    """War auch ein Fehler dabei, kann echte Sprache verloren sein: dann False,
    damit die normale Verarbeitung die ganze Aufnahme nachholt."""
    _abschluss_ruhig(monkeypatch, '', rest_platzt=True)
    with typefree.lock:
        typefree.live_verworfen = 1
    assert typefree._live_abschluss(sprache(2)) is False


def test_live_ohne_verworfenes_und_ohne_text_bleibt_false(monkeypatch, live_frisch):
    _abschluss_ruhig(monkeypatch, '')
    assert typefree._live_abschluss(sprache(2)) is False


def test_neue_aufnahme_setzt_verworfen_und_fehler_zurueck(monkeypatch, live_frisch):
    with typefree.lock:
        typefree.live_verworfen = 3
        typefree.live_fehler = True
    monkeypatch.setattr(typefree, '_open_stream', lambda: None)
    monkeypatch.setattr(typefree, '_status_recording', lambda: None)
    monkeypatch.setattr(typefree, '_ton_aus_melden', lambda sitzung: None)
    monkeypatch.setattr(typefree, '_watch_recording', lambda session: None)
    monkeypatch.setattr(typefree, 'live_modus', False)
    monkeypatch.setattr(typefree, 'is_recording', False)
    typefree.start_recording()
    try:
        assert typefree.live_verworfen == 0
        assert typefree.live_fehler is False
    finally:
        with typefree.lock:
            typefree.is_recording = False


def test_live_verworfen_aber_schreiber_haengt_uebernimmt_die_normale_verarbeitung(
        monkeypatch, live_frisch):
    """Codex R2: Läuft die Wartefrist ab, kann ein hängender Happen noch
    scheitern — dann nicht „alles verworfen" melden, sondern nachholen."""
    _abschluss_ruhig(monkeypatch, 'Thanks for watching.', schreiber_fertig=False)
    assert typefree._live_abschluss(stille(2)) is False


# ── Schreiber-Fertigsignal ohne Lücke (Codex-Ergebnisprüfung R3) ──────────────

@pytest.fixture
def warteschlange_frisch():
    def zuruecksetzen():
        with typefree.lock:
            typefree.live_happen.clear()
            typefree.live_in_arbeit = 0
    zuruecksetzen()
    yield
    zuruecksetzen()


def test_abholen_zaehlt_im_selben_abschnitt_als_in_arbeit(warteschlange_frisch):
    with typefree.lock:
        typefree.live_happen[:] = [sprache(1), sprache(1)]
    assert len(typefree.live_abholen(in_arbeit=True)) == 2
    assert typefree.live_in_arbeit == 2
    # Die Liste ist leer, aber zwei Happen sind noch in Arbeit: nicht fertig.
    assert typefree._live_warte_auf_schreiber(hoechstens=0.2) is False


def test_abholen_ohne_in_arbeit_zaehlt_nicht(warteschlange_frisch):
    with typefree.lock:
        typefree.live_happen[:] = [sprache(1)]
    typefree.live_abholen()
    assert typefree.live_in_arbeit == 0


def test_schreiber_bleibt_zwischen_zwei_happen_in_arbeit(monkeypatch, warteschlange_frisch):
    """Vorher meldete der Schreiber zwischen zwei abgeholten Happen kurz „frei" —
    der Abschluss konnte dann voreilig „alles verworfen" entscheiden."""
    gesehen = []

    def verarbeiten(stueck, *a, **k):
        with typefree.lock:
            gesehen.append(typefree.live_in_arbeit)

    monkeypatch.setattr(typefree, '_live_stueck_verarbeiten', verarbeiten)
    monkeypatch.setattr(typefree.time, 'sleep', lambda s: None)
    monkeypatch.setattr(typefree, 'is_recording', False)
    with typefree.lock:
        typefree.live_happen[:] = [sprache(1), sprache(1)]
    typefree._live_schreiber(session=-1)
    assert gesehen == [2, 1]           # nie 0, solange noch ein Happen offen ist
    assert typefree.live_in_arbeit == 0
    assert typefree._live_warte_auf_schreiber(hoechstens=0.2) is True


def test_schreiber_zaehlt_auch_nach_fehler_herunter(monkeypatch, warteschlange_frisch, live_frisch):
    def platzt(*a, **k):
        raise RuntimeError('Netz weg')

    monkeypatch.setattr(typefree, '_live_stueck_verarbeiten', platzt)
    monkeypatch.setattr(typefree.time, 'sleep', lambda s: None)
    monkeypatch.setattr(typefree, 'is_recording', False)
    with typefree.lock:
        typefree.live_happen[:] = [sprache(1)]
    typefree._live_schreiber(session=-1)
    assert typefree.live_in_arbeit == 0
    assert typefree.live_fehler is True


# ── Letzter Schnitt nach dem Ende bleibt im Rest (Codex-Ergebnisprüfung R4) ────

def test_schnitt_nach_dem_ende_wird_nicht_mehr_abgelegt(monkeypatch, warteschlange_frisch):
    """Endet die Aufnahme, während `_live_takt` noch schneidet, darf der Happen
    nicht mehr in die Warteschlange — der Schreiber ist vielleicht schon fertig.
    `live_geschnitten` bleibt stehen, damit der Abschluss den Teil als Rest nimmt."""
    def takt_waehrend_stop(puffer, gesehen, bloecke):
        typefree.is_recording = False          # Stop kommt genau jetzt dazwischen
        return gesehen, sprache(2)

    monkeypatch.setattr(typefree, '_live_takt', takt_waehrend_stop)
    monkeypatch.setattr(typefree.time, 'sleep', lambda s: None)
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, 'live_geschnitten', 4.0)
    typefree._live_worker(typefree._session)
    assert typefree.live_happen == []
    assert typefree.live_geschnitten == 4.0


def test_schnitt_waehrend_der_aufnahme_wird_abgelegt(monkeypatch, warteschlange_frisch):
    aufrufe = []

    def takt(puffer, gesehen, bloecke):
        aufrufe.append(1)
        if len(aufrufe) == 2:
            typefree.is_recording = False      # zweite Runde: Aufnahme vorbei
            return gesehen, None
        return gesehen, sprache(2)

    monkeypatch.setattr(typefree, '_live_takt', takt)
    monkeypatch.setattr(typefree.time, 'sleep', lambda s: None)
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, 'live_geschnitten', 0.0)
    typefree._live_worker(typefree._session)
    assert len(typefree.live_happen) == 1
