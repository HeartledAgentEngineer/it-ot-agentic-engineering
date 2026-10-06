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
    # Die nächste Pause nach der Mindestlänge — nicht die letzte im Puffer:
    # sonst wächst der Happen immer weiter und der Text bliebe aus.
    assert 11.5 <= zweiter / RATE <= 13.5, 'Schnitt muss in der nächsten Pause liegen'


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


# ── Schritt 2: Aufnahme-Worker (Puffer, Takt, Abholen) ────────────────────────

def test_puffer_wartet_bis_genug_audio_da_ist():
    """Kurz nach dem Start gibt es noch keinen Happen — sonst zahlt man für Silben."""
    puffer = typefree.LivePuffer(RATE).ergaenzen([sprache(2.0)])
    assert puffer.naechster_happen() is None
    assert puffer.rest_sekunden() == pytest.approx(2.0, abs=0.05)


def test_puffer_schneidet_an_der_sprechpause():
    """Nach einer Pause ist ein Happen fertig — und er endet dort, nicht im Wort."""
    puffer = typefree.LivePuffer(RATE).ergaenzen([sprache(6.0), stille(1.0), sprache(1.0)])
    happen = puffer.naechster_happen()
    assert happen is not None
    # Der Schnitt liegt am Anfang der Pause (dort ist es schon leise) — nicht im Wort.
    assert 6.0 * RATE <= len(happen) <= 7.0 * RATE, 'Schnitt muss in der Pause liegen'
    assert puffer.rest_sekunden() == pytest.approx(2.0, abs=0.3)


def test_happen_lueckenlos_und_ohne_doppelung():
    """Die wichtigste Eigenschaft: Happen + Rest ergeben wieder genau das ganze Audio.

    Wäre hier ein Sample doppelt oder fehlte eines, würde der Text im Dokument
    doppelt auftauchen oder mitten im Wort abreißen.
    """
    bloecke = []
    for _ in range(6):
        bloecke.append(sprache(4.0))
        bloecke.append(stille(0.8))
    bloecke.append(sprache(2.0))
    puffer = typefree.LivePuffer(RATE).ergaenzen(bloecke)
    gesamt = puffer.daten()

    happen_liste = []
    while True:
        happen = puffer.naechster_happen()
        if happen is None:
            break
        happen_liste.append(happen)
        assert len(happen_liste) <= 20, 'der Puffer darf nicht endlos Happen liefern'

    assert len(happen_liste) >= 3, 'bei ~29 s Audio müssen mehrere Happen entstehen'
    zusammen = np.concatenate(happen_liste + [gesamt[puffer.geschnitten:]])
    assert len(zusammen) == len(gesamt)
    assert np.array_equal(zusammen, gesamt)


def test_takt_holt_neue_bloecke_nur_einmal():
    """Der Worker sieht dieselbe Blockliste mehrfach — doppelt darf nichts werden."""
    puffer = typefree.LivePuffer(RATE)
    bloecke = [sprache(1.0), stille(0.5)]
    gesehen, _ = typefree._live_takt(puffer, 0, bloecke)
    assert gesehen == 2 and len(puffer.bloecke) == 2
    gesehen, _ = typefree._live_takt(puffer, gesehen, bloecke)
    assert len(puffer.bloecke) == 2, 'derselbe Block darf nicht zweimal in den Puffer'
    gesehen, _ = typefree._live_takt(puffer, gesehen, bloecke + [sprache(1.0)])
    assert len(puffer.bloecke) == 3


def test_takt_ohne_audio_liefert_nichts():
    puffer = typefree.LivePuffer(RATE)
    gesehen, happen = typefree._live_takt(puffer, 0, [])
    assert gesehen == 0 and happen is None


def test_abholen_gibt_happen_und_leert_die_liste():
    """Der Verbraucher (Schritt 3) bekommt jeden Happen genau einmal."""
    with typefree.lock:
        typefree.live_happen.clear()
        typefree.live_happen.append(sprache(1.0))
    fertig = typefree.live_abholen()
    assert len(fertig) == 1
    assert typefree.live_abholen() == []


# ── Schritt 3: Happen transkribieren und roh einfügen ─────────────────────────

def test_happen_wird_transkribiert_und_eingefuegt():
    """Der Kern des Live-Modus: fertiger Happen → Text steht im Dokument."""
    eingefuegt = []
    text = typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('hallo welt', 'mai'), eingefuegt.append)
    assert text == 'hallo welt'
    assert eingefuegt == ['hallo welt']


def test_leerer_happen_loest_keinen_aufruf_aus():
    """Ein leerer Happen darf weder Kosten noch Tastendrücke verursachen."""
    gerufen = []
    assert typefree._live_stueck_verarbeiten(
        np.zeros(0, dtype=np.float32), lambda s: gerufen.append(1), print) is None
    assert gerufen == []


def test_happen_ohne_text_wird_nicht_eingefuegt():
    """Wenn das Modell nichts liefert, bleibt das Dokument unberührt."""
    eingefuegt = []
    assert typefree._live_stueck_verarbeiten(
        sprache(4), lambda s: ('', 'mai'), eingefuegt.append) is None
    assert eingefuegt == []


def test_einfuegen_merkt_sich_den_text(monkeypatch):
    """Nach dem Einfügen ist bekannt, was im Dokument steht (für den Abschluss)."""
    getippt, kopiert, gedrueckt = [], [], []
    monkeypatch.setattr(typefree, 'unicode_tippen', getippt.append)
    monkeypatch.setattr(typefree.pyperclip, 'copy', kopiert.append)
    monkeypatch.setattr(typefree.pyautogui, 'hotkey',
                        lambda *tasten: gedrueckt.append(tasten))
    monkeypatch.setattr(typefree, '_fenster_titel', lambda: 'Editor')
    with typefree.lock:
        typefree.live_teile.clear()

    laenge = typefree._live_text_einfuegen('hallo welt')

    assert laenge == len('hallo welt ')
    assert getippt == ['hallo welt '], 'ein Happen endet mit Leerzeichen'
    # Direkt getippt statt Strg+V: Strg+V kommt bei gehaltenem Hotkey nicht an.
    assert kopiert == [] and gedrueckt == []
    teil = typefree.live_teile[0]
    assert teil['text'] == 'hallo welt '
    assert teil['roh'] == 'hallo welt', 'roh (ohne Trenner) wird geglättet'
    assert teil['fenster'] == 'Editor'
    assert teil['zeit'] > 0
    with typefree.lock:
        typefree.live_teile.clear()


def test_leerer_text_wird_nicht_eingefuegt(monkeypatch):
    """Kein Fenster bekommt eine leere Zwischenablage zu sehen."""
    kopiert = []
    monkeypatch.setattr(typefree.pyperclip, 'copy', kopiert.append)
    assert typefree._live_text_einfuegen('   ') == 0
    assert kopiert == []


# ── Schritt 4 (neu, 06.10.2026): jeder Block wird VOR dem Tippen geglättet ──
# Vorher löschte der Abschluss alles per Rücktaste und setzte die Gesamtglättung
# ein — Sebastian: „dass dann alles wieder gelöscht und ersetzt wird, gefällt
# mir nicht". Jetzt bleibt stehen, was einmal getippt ist.

def test_kontext_ist_das_ende_des_bisher_getippten():
    teile = [{'text': 'Erster Satz. '}, {'text': 'Zweiter Satz. '}]
    assert typefree.live_kontext(teile, grenze=14) == 'Zweiter Satz. '
    assert typefree.live_kontext(teile) == 'Erster Satz. Zweiter Satz. '
    assert typefree.live_kontext([]) == ''


def test_happen_wird_vor_dem_einfuegen_geglaettet():
    eingefuegt = []
    text = typefree._live_stueck_verarbeiten(
        sprache(4), lambda s: ('ähm hallo welt', 'mai'), eingefuegt.append,
        glaetten=lambda roh: 'Hallo Welt.')
    assert eingefuegt == ['Hallo Welt.']
    assert text == 'Hallo Welt.'


def test_scheitert_die_glaettung_kommt_der_rohtext():
    """Lieber roh als gar nicht — der Block darf nicht verloren gehen."""
    eingefuegt = []
    typefree._live_stueck_verarbeiten(
        sprache(4), lambda s: ('hallo welt', 'mai'), eingefuegt.append,
        glaetten=lambda roh: None)
    assert eingefuegt == ['hallo welt']


def _abschluss_vorbereiten(monkeypatch, teile, rest_text):
    getippt = []
    monkeypatch.setattr(typefree, '_live_warte_auf_schreiber', lambda: True)
    monkeypatch.setattr(typefree, '_live_transkribieren',
                        lambda stueck: (rest_text, 'mai'))
    monkeypatch.setattr(typefree, '_live_glaetten', lambda roh: roh.capitalize())
    monkeypatch.setattr(typefree, '_live_buchen', lambda s, a: None)
    monkeypatch.setattr(typefree, '_fenster_titel', lambda: 'Editor')
    monkeypatch.setattr(typefree, 'unicode_tippen', getippt.append)
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, 'live_geschnitten', 0.0)
    with typefree.lock:
        typefree.live_teile[:] = teile
    return getippt


def test_abschluss_tippt_nur_den_rest_und_ersetzt_nichts(monkeypatch):
    getippt = _abschluss_vorbereiten(
        monkeypatch, [{'text': 'Erster Satz. ', 'roh': 'Erster Satz.'}], 'und schluss')
    assert typefree._live_abschluss(sprache(2)) is True
    assert getippt == ['Und schluss ']     # geglättet angehängt, nichts gelöscht
    with typefree.lock:
        typefree.live_teile.clear()


def test_abschluss_ohne_getippten_text_meldet_false(monkeypatch):
    """Dann übernimmt die normale Verarbeitung — kein Diktat geht verloren."""
    _abschluss_vorbereiten(monkeypatch, [], '')
    assert typefree._live_abschluss(sprache(2)) is False


def test_glaettung_mit_kontext_wiederholt_den_kontext_nicht():
    from test_transkription import GlattungsAttrappe
    client = GlattungsAttrappe(antwort='Und dann gehen wir weiter.')
    ergebnis = typefree.polish_text('und dann ähm gehen wir weiter', client=client,
                                    kontext='Das ist der Anfang. ',
                                    modelle=('modell-a',))
    assert ergebnis == 'Und dann gehen wir weiter.'
    aufruf = client.aufrufe[0]
    assert aufruf['model'] == 'modell-a'
    nachricht = aufruf['messages'][-1]['content']
    assert 'Das ist der Anfang.' in nachricht
    assert 'NICHT wiederholen' in nachricht
    assert nachricht.rstrip().endswith('und dann ähm gehen wir weiter')


def test_happen_werden_gebucht():
    """Jeder Happen bezahlt seinen eigenen Aufruf beim liefernden Anbieter."""
    gebucht = []
    typefree._live_stueck_verarbeiten(
        sprache(4), lambda stueck: ('hallo welt', 'mai'), lambda t: None,
        lambda sekunden, anbieter: gebucht.append((round(sekunden, 1), anbieter)))
    assert gebucht == [(4.0, 'mai')]
