"""„Ton aus während der Aufnahme": Logik, Merker-Datei, Schalter, Einhängepunkte.

Kein Test darf den echten Ton des PCs anfassen. Alles läuft gegen ein
Fake-Backend; `pycaw` wird nie geladen (die Fixture in `conftest.py` ersetzt
zusätzlich die echte Backend-Fabrik). Der Arbeitsfaden von `TonSperre` läuft
dagegen echt — gerade seine Reihenfolge ist das, was geprüft werden muss.
"""
import json
import subprocess
import sys
import threading
import time

import pytest
import ton_aus
import typefree


# ── Fake-Backend ──────────────────────────────────────────────────────────────
class FakeBackend:
    """Ein Lautsprecher-Ersatz, der jeden Aufruf mitschreibt."""

    def __init__(self, standard='lautsprecher', stumm=None, verzoegerung=0.0):
        self.standard = standard
        self.stumm = dict(stumm or {})
        self.verzoegerung = verzoegerung
        self.setzen = []             # (geraet, wert) in Aufrufreihenfolge
        self.faeden = set()          # in welchen Fäden wurde das Backend benutzt
        self.vorbereitet_im = None
        self.fehler_standard = None
        self.fehler_setzen = None
        self.fehler_geraete = set()   # nur diese Geräte scheitern beim Setzen

    def vorbereiten(self):
        self.vorbereitet_im = threading.get_ident()

    def standard_geraet(self):
        self.faeden.add(threading.get_ident())
        if self.fehler_standard:
            raise self.fehler_standard
        return self.standard

    def ist_stumm(self, geraet):
        self.faeden.add(threading.get_ident())
        return self.stumm.get(geraet, False)

    def stumm_setzen(self, geraet, wert):
        self.faeden.add(threading.get_ident())
        if self.verzoegerung:
            time.sleep(self.verzoegerung)
        if self.fehler_setzen:
            raise self.fehler_setzen
        if geraet in self.fehler_geraete:
            raise OSError('Gerät %s getrennt' % geraet)
        self.setzen.append((geraet, wert))
        self.stumm[geraet] = wert


@pytest.fixture
def aufbau(tmp_path):
    """(sperre, backend, merker_pfad) — der Arbeitsfaden startet erst beim ersten Befehl."""
    backend = FakeBackend()
    merker = tmp_path / 'ton_aus_aktiv.json'
    sperre = ton_aus.TonSperre(lambda: backend, str(merker))
    return sperre, backend, merker


def fertig(sperre):
    assert sperre.warten(5.0), 'Warteschlange wurde nicht leer'


# ── Grundverhalten ────────────────────────────────────────────────────────────
def test_aus_dann_zurueck_entstummt(aufbau):
    sperre, backend, _ = aufbau
    sperre.aus(1)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is True
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False
    assert backend.setzen == [('lautsprecher', True), ('lautsprecher', False)]


def test_schon_stummes_geraet_bleibt_unangetastet(aufbau):
    """War der Ton vorher aus, darf typeFREE ihn nachher nicht einschalten."""
    sperre, backend, merker = aufbau
    backend.stumm['lautsprecher'] = True
    sperre.aus(1)
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.setzen == []
    assert backend.stumm['lautsprecher'] is True
    assert not merker.exists()


def test_doppeltes_aus_schaltet_nur_einmal(aufbau):
    sperre, backend, _ = aufbau
    sperre.aus(1)
    sperre.aus(1)
    fertig(sperre)
    assert backend.setzen == [('lautsprecher', True)]


def test_zurueck_ohne_aus_tut_nichts(aufbau):
    sperre, backend, _ = aufbau
    sperre.zurueck(1)
    sperre.zurueck_alles()
    fertig(sperre)
    assert backend.setzen == []


def test_sofortiges_ende_laeuft_in_der_richtigen_reihenfolge(tmp_path):
    """aus und zurück liegen schon in der Schlange, bevor das Backend antwortet.

    Läuft `zurueck` vor `aus`, bliebe der Ton nach einem Kurz-Tipp stumm.
    """
    backend = FakeBackend(verzoegerung=0.05)
    sperre = ton_aus.TonSperre(lambda: backend, str(tmp_path / 'm.json'))
    sperre.aus(1)
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.setzen == [('lautsprecher', True), ('lautsprecher', False)]
    assert backend.stumm['lautsprecher'] is False


# ── Sitzungsbindung (Überlappung zweier Aufnahmen) ────────────────────────────
def test_ueberlappung_laesst_den_ton_aus_bis_zur_letzten_sitzung(aufbau):
    """aus(A) → aus(B) → zurück(A) → zurück(B): erst das letzte stellt zurück."""
    sperre, backend, _ = aufbau
    sperre.aus(1)
    sperre.aus(2)
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is True, (
        'zurück der alten Sitzung hat den Ton unter der neuen Aufnahme eingeschaltet')
    sperre.zurueck(2)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False
    assert backend.setzen == [('lautsprecher', True), ('lautsprecher', False)]


def test_zurueck_alles_ignoriert_die_sitzung(aufbau):
    sperre, backend, _ = aufbau
    sperre.aus(5)
    sperre.zurueck_alles()
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False


# ── Fehler ────────────────────────────────────────────────────────────────────
def test_fehler_beim_geraet_finden_stuerzt_nicht_ab(aufbau):
    sperre, backend, merker = aufbau
    backend.fehler_standard = OSError('kein Gerät')
    sperre.aus(1)
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.setzen == []
    assert not merker.exists()


def test_fehler_beim_stummschalten_hinterlaesst_nichts_zurueckzustellen(aufbau):
    sperre, backend, merker = aufbau
    backend.fehler_setzen = OSError('COM kaputt')
    sperre.aus(1)
    fertig(sperre)
    backend.fehler_setzen = None
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.setzen == []
    assert not merker.exists()


def test_fehler_beim_zurueckstellen_behaelt_den_merker(aufbau):
    """Gelingt das Entstummen nicht, muss der nächste Start es nachholen können."""
    sperre, backend, merker = aufbau
    sperre.aus(1)
    fertig(sperre)
    backend.fehler_setzen = OSError('COM kaputt')
    sperre.zurueck(1)
    fertig(sperre)
    assert merker.exists()
    backend.fehler_setzen = None
    sperre.zurueck_alles()          # zweiter Versuch, z. B. beim Beenden
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False
    assert not merker.exists()


def test_kein_backend_ist_ein_no_op(tmp_path):
    sperre = ton_aus.TonSperre(lambda: None, str(tmp_path / 'm.json'))
    sperre.aus(1)
    sperre.zurueck(1)
    sperre.zurueck_alles()
    sperre.rueckstand_aufraeumen()
    assert sperre.warten(5.0)


def test_fabrik_die_wirft_ist_ein_no_op(tmp_path):
    def kaputt():
        raise ImportError('pycaw fehlt')

    sperre = ton_aus.TonSperre(kaputt, str(tmp_path / 'm.json'))
    sperre.aus(1)
    sperre.zurueck(1)
    assert sperre.warten(5.0)


# ── Gerätekennung und Faden ───────────────────────────────────────────────────
def test_zurueckgestellt_wird_das_gerät_das_stummgeschaltet_wurde(aufbau):
    """Wechselt das Standardgerät während der Aufnahme, bleibt das alte stumm-Opfer."""
    sperre, backend, _ = aufbau
    sperre.aus(1)
    fertig(sperre)
    backend.standard = 'kopfhoerer'
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False
    assert 'kopfhoerer' not in backend.stumm
    assert backend.setzen[-1] == ('lautsprecher', False)


def test_alle_backend_aufrufe_laufen_in_einem_eigenen_faden(aufbau):
    """COM wird in genau einem Faden benutzt — und nie im aufrufenden."""
    sperre, backend, _ = aufbau
    sperre.aus(1)
    sperre.zurueck(1)
    fertig(sperre)
    assert len(backend.faeden) == 1
    assert threading.get_ident() not in backend.faeden
    assert backend.vorbereitet_im in backend.faeden


def test_aufrufer_wartet_nicht_auf_das_backend(tmp_path):
    """Der Tastatur-Haken darf nicht auf COM warten."""
    backend = FakeBackend(verzoegerung=0.3)
    sperre = ton_aus.TonSperre(lambda: backend, str(tmp_path / 'm.json'))
    begonnen = time.monotonic()
    sperre.aus(1)
    assert time.monotonic() - begonnen < 0.1
    fertig(sperre)


# ── Merker-Datei ──────────────────────────────────────────────────────────────
def test_merker_wird_geschrieben_und_wieder_geloescht(aufbau):
    sperre, _, merker = aufbau
    sperre.aus(1)
    fertig(sperre)
    assert json.loads(merker.read_text(encoding='utf-8')) == {'geraete': ['lautsprecher']}
    sperre.zurueck(1)
    fertig(sperre)
    assert not merker.exists()


def test_rueckstand_vom_harten_abbruch_wird_beim_start_aufgeraeumt(aufbau):
    sperre, backend, merker = aufbau
    backend.stumm['altes_geraet'] = True
    merker.write_text(json.dumps({'geraet': 'altes_geraet'}), encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)
    assert backend.stumm['altes_geraet'] is False
    assert not merker.exists()


def test_merker_steht_vor_dem_stummschalten(tmp_path):
    """Der Merker muss schon liegen, wenn der Ton ausgeht — sonst rettet ihn kein Neustart."""
    merker = tmp_path / 'm.json'
    backend = FakeBackend()
    gesehen = []
    original = backend.stumm_setzen

    def setzen(geraet, wert):
        gesehen.append(merker.exists())
        original(geraet, wert)

    backend.stumm_setzen = setzen
    sperre = ton_aus.TonSperre(lambda: backend, str(merker))
    sperre.aus(1)
    fertig(sperre)
    assert gesehen == [True]


def test_ohne_schreibbaren_merker_wird_nicht_stummgeschaltet(tmp_path):
    """Kann der Merker nicht geschrieben werden, bliebe der Ton nach einem Absturz aus."""
    backend = FakeBackend()
    sperre = ton_aus.TonSperre(lambda: backend, str(tmp_path / 'fehlt' / 'm.json'))
    sperre.aus(1)
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.setzen == []


def test_fehlgeschlagenes_stummschalten_nimmt_das_geraet_aus_dem_merker(aufbau):
    sperre, backend, merker = aufbau
    backend.fehler_setzen = OSError('COM kaputt')
    sperre.aus(1)
    fertig(sperre)
    assert not merker.exists()


def test_offener_rueckstand_bleibt_bei_neuer_aufnahme_erhalten(aufbau):
    """Gerät A war beim Start getrennt; eine Aufnahme auf B darf A nicht vergessen."""
    sperre, backend, merker = aufbau
    backend.stumm['geraet_a'] = True
    backend.fehler_geraete = {'geraet_a'}
    merker.write_text(json.dumps({'geraete': ['geraet_a']}), encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)
    assert json.loads(merker.read_text(encoding='utf-8')) == {'geraete': ['geraet_a']}

    sperre.aus(1)                    # Standard ist 'lautsprecher' (Gerät B)
    fertig(sperre)
    assert sorted(json.loads(merker.read_text(encoding='utf-8'))['geraete']) == [
        'geraet_a', 'lautsprecher']
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False
    assert json.loads(merker.read_text(encoding='utf-8')) == {'geraete': ['geraet_a']}


def test_offenes_geraet_wird_bei_naechster_aufnahme_mitgenommen(aufbau):
    """Ist das offene Gerät A wieder da und Standard, gehört seine Stummschaltung uns."""
    sperre, backend, merker = aufbau
    backend.stumm['geraet_a'] = True
    backend.fehler_geraete = {'geraet_a'}
    merker.write_text(json.dumps({'geraete': ['geraet_a']}), encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)

    backend.fehler_geraete = set()   # A ist wieder angeschlossen und Standard
    backend.standard = 'geraet_a'
    sperre.aus(1)
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.stumm['geraet_a'] is False
    assert not merker.exists()


def test_schreibfehler_laesst_den_alten_merker_heil(aufbau, monkeypatch):
    """Ein abgebrochenes Schreiben darf den Nachweis für Gerät A nicht zerstören."""
    sperre, backend, merker = aufbau
    backend.stumm['geraet_a'] = True
    backend.fehler_geraete = {'geraet_a'}
    merker.write_text(json.dumps({'geraete': ['geraet_a']}), encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)

    def kaputt(*args, **kwargs):
        raise OSError('Platte voll')

    monkeypatch.setattr(ton_aus.json, 'dump', kaputt)
    sperre.aus(1)                    # Gerät B — Merker lässt sich nicht schreiben
    fertig(sperre)
    monkeypatch.undo()
    assert backend.stumm.get('lautsprecher', False) is False   # B nicht stumm
    assert json.loads(merker.read_text(encoding='utf-8')) == {'geraete': ['geraet_a']}


def test_gescheitertes_zurueck_blockiert_kein_anderes_geraet(aufbau):
    """A wird während des Diktats getrennt; die nächste Aufnahme auf B muss B stummschalten."""
    sperre, backend, merker = aufbau
    backend.standard = 'geraet_a'
    sperre.aus(1)
    fertig(sperre)
    backend.fehler_geraete = {'geraet_a'}
    sperre.zurueck(1)
    fertig(sperre)

    backend.standard = 'lautsprecher'
    sperre.aus(2)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is True
    sperre.zurueck(2)
    fertig(sperre)
    assert backend.stumm['lautsprecher'] is False
    assert json.loads(merker.read_text(encoding='utf-8')) == {'geraete': ['geraet_a']}

    backend.fehler_geraete = set()   # A wieder da: Beenden holt es nach
    sperre.zurueck_alles()
    fertig(sperre)
    assert backend.stumm['geraet_a'] is False
    assert not merker.exists()


def test_offenes_geraet_inzwischen_laut_wird_normal_stummgeschaltet(aufbau):
    """A wurde von Hand wieder eingeschaltet: Rückstand erledigt, A muss trotzdem stumm."""
    sperre, backend, merker = aufbau
    backend.stumm['geraet_a'] = True
    backend.fehler_geraete = {'geraet_a'}
    merker.write_text(json.dumps({'geraete': ['geraet_a']}), encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)

    backend.fehler_geraete = set()
    backend.stumm['geraet_a'] = False    # von Hand wieder laut
    backend.standard = 'geraet_a'
    sperre.aus(1)
    fertig(sperre)
    assert backend.stumm['geraet_a'] is True
    sperre.zurueck(1)
    fertig(sperre)
    assert backend.stumm['geraet_a'] is False
    assert not merker.exists()


def test_rueckstand_im_alten_format_wird_gelesen(aufbau):
    sperre, backend, merker = aufbau
    backend.stumm['altes_geraet'] = True
    merker.write_text(json.dumps({'geraet': 'altes_geraet'}), encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)
    assert backend.stumm['altes_geraet'] is False
    assert not merker.exists()


def test_kaputter_merker_wird_entfernt_ohne_absturz(aufbau):
    sperre, backend, merker = aufbau
    merker.write_text('{kein JSON', encoding='utf-8')
    sperre.rueckstand_aufraeumen()
    fertig(sperre)
    assert backend.setzen == []
    assert not merker.exists()


def test_ohne_rueckstand_passiert_nichts(aufbau):
    sperre, backend, _ = aufbau
    sperre.rueckstand_aufraeumen()
    fertig(sperre)
    assert backend.setzen == []


# ── Import ohne Nebenwirkung ──────────────────────────────────────────────────
def test_import_laedt_weder_pycaw_noch_comtypes():
    """Das Modul muss in jeder Umgebung importierbar sein — pycaw nur faul."""
    code = ('import sys; sys.path.insert(0, %r); import ton_aus; '
            'assert "pycaw" not in sys.modules; '
            'assert "comtypes" not in sys.modules' % ton_aus.__file__.rsplit('\\', 1)[0])
    ergebnis = subprocess.run([sys.executable, '-c', code],
                              capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr


# ── Schalter in der config.json ───────────────────────────────────────────────
def _konfig(tmp_path, monkeypatch):
    pfad = tmp_path / 'config.json'
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(pfad))
    return pfad


def test_schalter_ist_standardmaessig_an(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    assert typefree.load_ton_aus_config() is True


def test_schalter_merkt_sich_die_wahl(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    typefree.save_ton_aus_config(False)
    assert typefree.load_ton_aus_config() is False
    typefree.save_ton_aus_config(True)
    assert typefree.load_ton_aus_config() is True


def test_schalter_ueberschreibt_andere_einstellungen_nicht(tmp_path, monkeypatch):
    pfad = _konfig(tmp_path, monkeypatch)
    typefree.save_hotkey_config(3)
    typefree.save_ton_aus_config(False)
    gespeichert = json.loads(pfad.read_text(encoding='utf-8'))
    assert gespeichert['hotkey_index'] == 3
    assert gespeichert['ton_aus'] is False


def test_kaputte_konfiguration_bedeutet_an(tmp_path, monkeypatch):
    pfad = _konfig(tmp_path, monkeypatch)
    pfad.write_text('{kein JSON', encoding='utf-8')
    assert typefree.load_ton_aus_config() is True


def test_tray_rueckruf_stellt_um_und_speichert(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    monkeypatch.setattr(typefree, 'ton_aus_an', True)
    typefree._schalte_ton_aus()
    assert typefree.ton_aus_an is False
    assert typefree.load_ton_aus_config() is False
    typefree._schalte_ton_aus()
    assert typefree.ton_aus_an is True
    assert typefree.load_ton_aus_config() is True


def test_merker_liegt_neben_der_config(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    assert typefree.ton_merker_pfad() == str(tmp_path / 'ton_aus_aktiv.json')


# ── Einhängepunkte in typefree.py ─────────────────────────────────────────────
class FakeTon:
    """Schreibt mit, was typefree der Sperre meldet — und in welcher Reihenfolge."""

    def __init__(self, protokoll=None):
        self.protokoll = protokoll if protokoll is not None else []

    def aus(self, sitzung):
        self.protokoll.append(('aus', sitzung))

    def zurueck(self, sitzung):
        self.protokoll.append(('zurueck', sitzung))

    def zurueck_alles(self):
        self.protokoll.append(('zurueck_alles',))

    def warten(self, hoechstens=2.0):
        self.protokoll.append(('warten', hoechstens))
        return True

    def rueckstand_aufraeumen(self):
        self.protokoll.append(('rueckstand',))


@pytest.fixture
def aufnahme_stand(monkeypatch):
    """start_recording ohne Mikrofon, ohne Fenster, ohne Wächter-Faden."""
    protokoll = []
    ton = FakeTon(protokoll)
    monkeypatch.setattr(typefree, 'ton', ton)
    monkeypatch.setattr(typefree, 'ton_aus_an', True)
    monkeypatch.setattr(typefree, 'live_modus', False)
    monkeypatch.setattr(typefree, '_open_stream',
                        lambda: protokoll.append('open'))
    monkeypatch.setattr(typefree, '_close_stream',
                        lambda: protokoll.append('close'))
    monkeypatch.setattr(typefree, '_status_recording', lambda: None)
    monkeypatch.setattr(typefree, '_status_transcribing', lambda: None)
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, '_watch_recording', lambda session: None)
    monkeypatch.setattr(typefree, 'report_error', lambda n: protokoll.append('ALARM'))
    monkeypatch.setattr(typefree, 'is_recording', False)
    monkeypatch.setattr(typefree, '_session', 6)
    monkeypatch.setattr(typefree, 'audio_frames', [])
    return protokoll


def test_start_meldet_aus_mit_der_sitzungsnummer(aufnahme_stand):
    typefree.start_recording()
    assert ('aus', 7) in aufnahme_stand
    assert aufnahme_stand.index('open') < aufnahme_stand.index(('aus', 7))


def test_start_ohne_schalter_meldet_nichts(aufnahme_stand, monkeypatch):
    monkeypatch.setattr(typefree, 'ton_aus_an', False)
    typefree.start_recording()
    assert not any(e[0] == 'aus' for e in aufnahme_stand if isinstance(e, tuple))


def test_start_ohne_mikrofon_schaltet_den_ton_nicht_aus(aufnahme_stand, monkeypatch):
    def kaputt():
        raise OSError('kein Mikrofon')

    monkeypatch.setattr(typefree, '_open_stream', kaputt)
    typefree.start_recording()
    assert not any(e[0] == 'aus' for e in aufnahme_stand if isinstance(e, tuple))


def test_start_ohne_sperre_laeuft_normal(aufnahme_stand, monkeypatch):
    """Vor main() oder ohne Backend gibt es keine Sperre — das Diktat läuft trotzdem."""
    monkeypatch.setattr(typefree, 'ton', None)
    typefree.start_recording()
    assert typefree.is_recording is True


def test_stop_meldet_zurueck_direkt_nach_dem_mikrofon(aufnahme_stand, monkeypatch):
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_session', 7)
    typefree.stop_and_transcribe()
    assert aufnahme_stand == ['close', ('zurueck', 7)]


def test_stop_stellt_auch_bei_ausgeschaltetem_schalter_zurueck(aufnahme_stand,
                                                              monkeypatch):
    """Der Schalter verhindert nur neues Stummschalten, nie das Zurückstellen."""
    monkeypatch.setattr(typefree, 'ton_aus_an', False)
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_session', 7)
    typefree.stop_and_transcribe()
    assert ('zurueck', 7) in aufnahme_stand


def test_stop_ohne_aufnahme_meldet_nichts(aufnahme_stand):
    typefree.stop_and_transcribe()
    assert aufnahme_stand == []


def test_waechter_toter_pfad_stellt_den_ton_zurueck(monkeypatch):
    protokoll = []
    monkeypatch.setattr(typefree, 'ton', FakeTon(protokoll))
    monkeypatch.setattr(typefree, 'report_error', lambda n: protokoll.append('ALARM'))
    monkeypatch.setattr(typefree, '_close_stream', lambda: protokoll.append('close'))
    monkeypatch.setattr(typefree, '_reconnect_microphone', lambda: False)
    monkeypatch.setattr(typefree, 'is_microphone_dead', lambda *a, **k: True)
    monkeypatch.setattr(typefree, 'audio_frames', [])
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_session', 4)
    typefree._watch_recording(4)
    assert protokoll[0] == 'close'
    assert ('zurueck', 4) in protokoll


def test_neu_verbinden_beruehrt_den_ton_nicht(monkeypatch):
    protokoll = []
    monkeypatch.setattr(typefree, 'ton', FakeTon(protokoll))
    monkeypatch.setattr(typefree, '_close_stream', lambda: None)
    monkeypatch.setattr(typefree, '_open_stream', lambda: None)
    typefree._reconnect_microphone()
    assert protokoll == []


def test_beenden_stellt_alles_zurueck_und_wartet(monkeypatch):
    protokoll = []
    monkeypatch.setattr(typefree, 'ton', FakeTon(protokoll))
    monkeypatch.setattr(typefree, '_close_stream', lambda: None)

    class Icon:
        def stop(self):
            protokoll.append('icon_stop')

    typefree._on_quit(Icon(), None)
    assert protokoll[0] == ('zurueck_alles',)
    assert protokoll[1][0] == 'warten'
    assert 'icon_stop' in protokoll


def test_beenden_ohne_sperre_stuerzt_nicht_ab(monkeypatch):
    monkeypatch.setattr(typefree, 'ton', None)
    monkeypatch.setattr(typefree, '_close_stream', lambda: None)

    class Icon:
        def stop(self):
            pass

    typefree._on_quit(Icon(), None)


def test_einrichten_legt_sperre_an_raeumt_auf_und_meldet_atexit(monkeypatch, tmp_path):
    protokoll = []
    erzeugt = []

    def baue(fabrik, merker):
        erzeugt.append((fabrik, merker))
        return FakeTon(protokoll)

    registriert = []
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    monkeypatch.setattr(typefree, 'ton', None)
    monkeypatch.setattr(typefree.ton_aus, 'TonSperre', baue)
    monkeypatch.setattr(typefree.atexit, 'register',
                        lambda f, *a, **k: registriert.append(f))
    typefree.ton_einrichten()
    assert typefree.ton is not None
    assert erzeugt[0][0] is typefree.ton_aus.windows_backend
    assert erzeugt[0][1] == str(tmp_path / 'ton_aus_aktiv.json')
    assert ('rueckstand',) in protokoll
    assert len(registriert) == 1
    registriert[0]()
    assert ('zurueck_alles',) in protokoll
