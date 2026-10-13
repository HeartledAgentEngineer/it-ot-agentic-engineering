"""Zweitanfrage, wenn die Transkription hängt.

12.10.2026: „Type Free ist ganz, ganz langsam geworden." mai antwortete sonst in
1–2 s, an dem Tag im Median in 12,5 s, einzelne Anfragen hingen 56–181 s. Ohne
Zeitlimit wartete typeFREE bis zu 10 Minuten. Jetzt geht nach kurzer Wartezeit
— oder sofort nach 429/5xx — dieselbe Anfrage ein zweites Mal los; die erste
BRAUCHBARE Antwort gewinnt, und am Fristende werden alle Verbindungen
geschlossen. Nachgeschärft nach zwei Runden Codex-Ergebnisprüfung.

Die Reihenfolge der Antworten steuern Ereignisse, keine Timer: Eine Anfrage
wartet, bis die Antwort der anderen in der Ergebnis-Schlange liegt
(`MeldendeSchlange`). So hängt kein Test vom Tempo des Rechners ab.
"""
import http.server
import io
import json
import queue
import threading
import time
import types

import httpx
import pytest
from openai import OpenAI

import typefree


class StatusFehler(Exception):
    """Wie die Fehler des OpenAI-SDK: mit `status_code`."""

    def __init__(self, code):
        super().__init__(f'Status {code}')
        self.status_code = code


@pytest.fixture(autouse=True, scope='module')
def ssl_vorgebaut():
    """Wie `main()` beim Start: SSL-Kontext einmal vorbauen. Sonst zieht der erste Test,
    der eine Verbindung braucht, 0,8–1,4 s Aufbau von seiner Frist ab (Codex 13.10.2026).
    Den langsamen Aufbau selbst prüft ein eigener Test."""
    typefree.gemeinsamer_ssl_kontext()


@pytest.fixture
def eingetragen(monkeypatch):
    """Je Anfrage-Nummer ein Ereignis: „Antwort liegt in der Schlange"."""
    ereignisse = {1: threading.Event(), 2: threading.Event()}

    class MeldendeSchlange(queue.Queue):
        def put(self, eintrag, *args, **kwargs):
            super().put(eintrag, *args, **kwargs)
            ereignisse[eintrag[0]].set()

    monkeypatch.setattr(typefree, 'queue',
                        types.SimpleNamespace(Queue=MeldendeSchlange, Empty=queue.Empty))
    return ereignisse


class Client:
    """Nachgebauter Client. `warte[n]` ist ein Ereignis, auf das Anfrage n wartet;
    `verzoegerung[n]` eine feste Wartezeit. Freigabe am Testende über `alles_frei`."""

    def __init__(self, antworten=('erste', 'zweite'), fehler=None, warte=None,
                 verzoegerung=None):
        self.aufrufe = []
        self.dateien = []
        self.optionen = []
        self.ende = threading.Event()
        self._antworten = antworten
        self._fehler = fehler or {}
        self._warte = warte or {}
        self._verzoegerung = verzoegerung or {}
        self._sperre = threading.Lock()
        self.audio = types.SimpleNamespace(
            transcriptions=types.SimpleNamespace(create=self._create))

    def with_options(self, **kwargs):
        self.optionen.append(kwargs)
        return self

    def alles_frei(self):
        self.ende.set()
        for ereignis in self._warte.values():
            ereignis.set()

    def _create(self, **kwargs):
        with self._sperre:
            nummer = len(self.aufrufe) + 1
            self.aufrufe.append(kwargs)
            self.dateien.append((kwargs['file'].tell(), kwargs['file'].read()))
        if nummer in self._warte:
            self._warte[nummer].wait(10)
        if nummer in self._verzoegerung:
            self.ende.wait(self._verzoegerung[nummer])
        if nummer in self._fehler:
            raise self._fehler[nummer]
        return types.SimpleNamespace(text=self._antworten[nummer - 1])




@pytest.fixture(autouse=True)
def aufraeumen():
    yield
    for faden in threading.enumerate():
        if faden.name.startswith('stt-'):
            faden.join(10)


def _puffer(daten=b'RIFF-audio'):
    p = io.BytesIO(daten)
    p.name = 'audio.wav'
    p.read()                       # Dateizeiger am Ende, wie nach einem Fehlversuch
    return p


def _anfrage(client, daten=b'RIFF-audio', **kw):
    try:
        return typefree._stt_anfrage(client, 'm', _puffer(daten), 'v', **kw)
    finally:
        client.alles_frei()


# ── Grundfälle ───────────────────────────────────────────────────────────────

def test_schnelle_antwort_braucht_keine_zweite_anfrage():
    client = Client()
    assert _anfrage(client, zweit_nach=30) == 'erste'
    assert len(client.aufrufe) == 1


def test_haengende_anfrage_wird_von_der_zweiten_ueberholt():
    client = Client(warte={1: threading.Event()})
    assert _anfrage(client, zweit_nach=0.01) == 'zweite'
    assert len(client.aufrufe) == 2


def test_beide_anfragen_schicken_das_ganze_audio():
    client = Client(warte={1: threading.Event()})
    _anfrage(client, zweit_nach=0.01)
    assert client.dateien == [(0, b'RIFF-audio'), (0, b'RIFF-audio')]
    assert client.aufrufe[0]['file'].name == 'audio.wav'


def test_hoechstens_zwei_anfragen(eingetragen):
    """Auch eine 503 der zweiten startet keine dritte."""
    client = Client(fehler={2: StatusFehler(503)}, warte={1: eingetragen[2]})
    assert _anfrage(client, zweit_nach=0.01) == 'erste'
    assert len(client.aufrufe) == 2


# ── Nur eine BRAUCHBARE Antwort gewinnt ──────────────────────────────────────

def test_leere_zweite_verdraengt_nicht_die_erste(eingetragen):
    """Sonst ginge im Live-Modus gesprochener Text als „Stille" verloren."""
    client = Client(antworten=('der echte Text', ''), warte={1: eingetragen[2]})
    assert _anfrage(client, zweit_nach=0.01) == 'der echte Text'


def test_auftragstext_gewinnt_nicht(eingetragen):
    client = Client(antworten=('der echte Text', 'Transkribiere diese Aufnahme'),
                    warte={1: eingetragen[2]})
    assert _anfrage(client, zweit_nach=0.01) == 'der echte Text'


def test_beide_leer_ist_stille(eingetragen):
    client = Client(antworten=('', ''), warte={1: eingetragen[2]})
    assert _anfrage(client, zweit_nach=0.01) == ''


def test_einzelne_leere_antwort_startet_keine_zweite():
    """Stille im Live-Happen soll nicht doppelt kosten."""
    client = Client(antworten=('',))
    assert _anfrage(client, zweit_nach=30) == ''
    assert len(client.aufrufe) == 1


def test_leer_und_die_andere_haengt_gibt_am_fristende_leer():
    client = Client(antworten=('', ''), warte={1: threading.Event()})
    assert _anfrage(client, zweit_nach=0.01, hoechstdauer=0.5) == ''


# ── 429/5xx: die Zweitanfrage ersetzt die SDK-Wiederholung ───────────────────

def test_drosselung_startet_die_zweite_sofort():
    client = Client(fehler={1: StatusFehler(429)})
    beginn = time.monotonic()
    assert _anfrage(client, zweit_nach=30) == 'zweite'
    assert time.monotonic() - beginn < 10          # nicht erst nach zweit_nach=30
    assert len(client.aufrufe) == 2


def test_serverfehler_startet_die_zweite_sofort():
    client = Client(fehler={1: StatusFehler(503)})
    assert _anfrage(client, zweit_nach=30) == 'zweite'


def test_aufruffehler_wird_nicht_wiederholt():
    """400 & Co. liegen an der Anfrage selbst — zweimal senden hilft nicht."""
    client = Client(fehler={1: StatusFehler(400)})
    with pytest.raises(StatusFehler):
        _anfrage(client, zweit_nach=30)
    assert len(client.aufrufe) == 1


def test_beide_scheitern_gibt_den_ersten_fehler():
    client = Client(fehler={1: StatusFehler(429), 2: StatusFehler(502)})
    with pytest.raises(StatusFehler, match='429'):
        _anfrage(client, zweit_nach=30)


def test_zweite_scheitert_erste_kommt_noch(eingetragen):
    client = Client(fehler={2: StatusFehler(429)}, warte={1: eingetragen[2]})
    assert _anfrage(client, zweit_nach=0.01) == 'erste'


# ── Fristen ──────────────────────────────────────────────────────────────────

def test_fehler_plus_haengende_anfrage_nennt_den_fehler():
    client = Client(fehler={1: StatusFehler(429)}, warte={2: threading.Event()})
    with pytest.raises(TimeoutError, match='429'):
        _anfrage(client, zweit_nach=30, hoechstdauer=1.0)


def test_haengen_beide_gibt_es_einen_zeitfehler():
    client = Client(warte={1: threading.Event(), 2: threading.Event()})
    beginn = time.monotonic()
    with pytest.raises(TimeoutError):
        _anfrage(client, zweit_nach=0.01, hoechstdauer=0.3)
    assert time.monotonic() - beginn < 5


def test_keine_zweitanfrage_nach_fristende(caplog):
    """Wartezeit für die Zweitanfrage liegt hinter dem Fristende — sie startet nie.
    Geprüft über das Protokoll, nicht über Aufrufzahlen (kein Wetten aufs Tempo)."""
    client = Client(warte={1: threading.Event()})
    with pytest.raises(TimeoutError):
        _anfrage(client, zweit_nach=1.0, hoechstdauer=0.3)
    assert 'zweite Anfrage' not in caplog.text


def test_langsamer_verbindungsaufbau_haelt_die_frist_und_startet_keine_anfrage(monkeypatch):
    """Der Aufbau läuft im Anfragefaden (Codex 13.10.2026): Hängt er, kehrt die Anfrage
    trotzdem zum Fristende zurück; wird er danach fertig, geht keine Anfrage mehr los und
    die Verbindung wird geschlossen."""
    echt = typefree.gemeinsamer_ssl_kontext
    aufbau_frei, aufgebaut, verbindungen = threading.Event(), threading.Event(), []
    echter_client = httpx.Client

    def langsam():
        aufbau_frei.wait(10)
        return echt()

    def merkender_client(**kw):
        verbindung = echter_client(**kw)
        verbindungen.append(verbindung)
        aufgebaut.set()
        return verbindung

    monkeypatch.setattr(typefree, 'gemeinsamer_ssl_kontext', langsam)
    monkeypatch.setattr(typefree.httpx, 'Client', merkender_client)
    client = Client()
    try:
        with pytest.raises(TimeoutError):
            _anfrage(client, zweit_nach=30, hoechstdauer=0.2)   # Aufbau hängt noch
    finally:
        aufbau_frei.set()
    assert aufgebaut.wait(5)
    for _ in range(500):                                      # Faden schließt selbst
        if verbindungen[0].is_closed:
            break
        time.sleep(0.01)
    assert verbindungen[0].is_closed
    assert client.aufrufe == []


def test_ssl_kontext_wird_nur_einmal_gebaut():
    assert typefree.gemeinsamer_ssl_kontext() is typefree.gemeinsamer_ssl_kontext()


@pytest.fixture
def spaete_auswertung(monkeypatch):
    """Ergebnis-Schlange, die Antwort 2 erst nach `nachlauf` Sekunden herausgibt — auch
    über ihr eigenes Zeitlimit hinaus. So wird Antwort 2 sicher NACH dem Fristende
    ausgewertet, ohne dass ein Test auf das Tempo des Rechners wettet."""
    einstellung = {'nachlauf': 0.0}

    class SpaeteSchlange(queue.Queue):
        def get(self, block=True, timeout=None):
            eintrag = super().get(timeout=10)       # wartet über das Zeitlimit hinaus
            if eintrag[0] == 2:
                time.sleep(einstellung['nachlauf'])
            return eintrag

    monkeypatch.setattr(typefree, 'queue',
                        types.SimpleNamespace(Queue=SpaeteSchlange, Empty=queue.Empty))
    return einstellung


def test_vor_fristende_eingetroffen_zaehlt_auch_wenn_spaet_ausgewertet(spaete_auswertung):
    """Antwort 2 kam rechtzeitig, wird aber erst nach dem Fristende ausgewertet."""
    spaete_auswertung['nachlauf'] = 2.5
    client = Client(fehler={1: StatusFehler(429)})
    assert _anfrage(client, zweit_nach=30, hoechstdauer=2.0) == 'zweite'


def test_nach_fristende_eingetroffen_zaehlt_nicht(spaete_auswertung):
    client = Client(fehler={1: StatusFehler(429)}, verzoegerung={2: 0.8})
    with pytest.raises(TimeoutError, match='429'):
        _anfrage(client, zweit_nach=30, hoechstdauer=0.3)


def test_buchung_haelt_die_antwort_nicht_auf():
    """Die Buchung läuft in eigenem Faden — eine hängende Buchung hält weder die
    Antwort noch das Schließen der Verbindungen am Fristende auf (Codex 13.10.2026)."""
    frei, gebucht = threading.Event(), []
    client = Client(fehler={1: StatusFehler(429)})
    try:
        beginn = time.monotonic()
        assert _anfrage(client, zweit_nach=30, hoechstdauer=30,
                        bei_zweitanfrage=lambda s: (frei.wait(10), gebucht.append(s))
                        ) == 'zweite'
        assert time.monotonic() - beginn < 5
        assert all(o['http_client'].is_closed for o in client.optionen)
    finally:
        frei.set()
    assert _gebucht(gebucht), 'Zweitanfrage wurde nicht gebucht'


def test_jede_anfrage_eigene_verbindung_ohne_stille_wiederholung():
    client = Client(warte={1: threading.Event()})
    _anfrage(client, zweit_nach=0.2, hoechstdauer=30)
    erste, zweite = client.optionen
    assert erste['max_retries'] == zweite['max_retries'] == 0
    assert isinstance(erste['http_client'], httpx.Client)
    assert erste['http_client'] is not zweite['http_client']
    assert 25 < erste['timeout'] <= 30                  # Restzeit nach dem Aufbau
    assert zweite['timeout'] <= 30 - 0.2                # nur die Restzeit


def test_verbindungen_sind_danach_geschlossen():
    client = Client(warte={1: threading.Event()})
    _anfrage(client, zweit_nach=0.01)
    assert all(o['http_client'].is_closed for o in client.optionen)


# ── Echter OpenAI-Client gegen einen lokalen Server (kein Netz) ──────────────

class _Server:
    """Lokaler HTTP-Server: Anfrage 1 hängt, Anfrage 2 antwortet (oder hängt auch)."""

    def __init__(self, zweite_antwortet):
        self.anfragen = 0
        zaehler_sperre = threading.Lock()
        aussen = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
                with zaehler_sperre:
                    aussen.anfragen += 1
                    nummer = aussen.anfragen
                if nummer == 2 and zweite_antwortet:
                    koerper = json.dumps({'text': 'vom Server'}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(koerper)))
                    self.end_headers()
                    self.wfile.write(koerper)
                    return
                time.sleep(20)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = OpenAI(base_url=f'http://127.0.0.1:{self.server.server_port}/v1',
                             api_key='test')

    def stopp(self):
        self.server.shutdown()
        self.server.server_close()


def _faeden_enden(frist):
    ende = time.monotonic() + frist
    while time.monotonic() < ende:
        if not [f for f in threading.enumerate() if f.name.startswith('stt-')]:
            return True
        time.sleep(0.05)
    return False


def test_echter_client_zweite_gewinnt_und_die_erste_bricht_ab():
    server = _Server(zweite_antwortet=True)
    try:
        text = typefree._stt_anfrage(server.client, 'm', _puffer(), 'v',
                                     zweit_nach=0.2, hoechstdauer=10)
        assert text == 'vom Server'
        assert server.anfragen == 2
        assert _faeden_enden(5), 'die unterlegene Anfrage läuft weiter'
    finally:
        server.stopp()


def test_echter_client_harte_gesamtfrist():
    """Beide hängen: Zeitfehler am Fristende, danach enden beide Fäden selbst."""
    server = _Server(zweite_antwortet=False)
    try:
        beginn = time.monotonic()
        with pytest.raises(TimeoutError):
            typefree._stt_anfrage(server.client, 'm', _puffer(), 'v',
                                  zweit_nach=0.2, hoechstdauer=1.0)
        assert time.monotonic() - beginn < 3
        assert _faeden_enden(5), 'eine Anfrage lebt über die Frist hinaus'
    finally:
        server.stopp()


# ── Kosten: gebucht wird nur, was die App ausdrücklich bucht ─────────────────

def _gebucht(liste, anzahl=1):
    """Die Buchung läuft in eigenem Faden — bis zu 5 s auf sie warten."""
    ende = time.monotonic() + 5
    while len(liste) < anzahl and time.monotonic() < ende:
        time.sleep(0.01)
    return liste

def test_zweitanfrage_meldet_sich_zum_buchen():
    gebucht = []
    client = Client(warte={1: threading.Event()})
    audio = b'x' * (typefree.SAMPLE_RATE * 2 * 3)       # 3 s PCM-16
    _anfrage(client, daten=audio, zweit_nach=0.01, bei_zweitanfrage=gebucht.append)
    assert _gebucht(gebucht) == [pytest.approx(3.0)]


def test_nicht_abgeschickte_zweitanfrage_wird_nicht_gebucht(monkeypatch):
    """Die Zweitanfrage ist angestoßen, ihr Aufbau aber erst fertig, nachdem die erste
    gewonnen hat — sie geht nicht hinaus und kostet nichts (Codex 13.10.2026)."""
    echt = typefree.gemeinsamer_ssl_kontext
    aufbau_frei, zweiter_baut, verbindungen = threading.Event(), threading.Event(), []
    echter_client = httpx.Client

    def zweiter_haengt():
        if threading.current_thread().name == 'stt-2':   # am Faden erkannt, nicht an
            zweiter_baut.set()                # der Reihenfolge; erst jetzt antwortet 1
            aufbau_frei.wait(10)
        return echt()

    def merkender_client(**kw):
        verbindungen.append(echter_client(**kw))
        return verbindungen[-1]

    monkeypatch.setattr(typefree, 'gemeinsamer_ssl_kontext', zweiter_haengt)
    monkeypatch.setattr(typefree.httpx, 'Client', merkender_client)
    gebucht = []
    client = Client(warte={1: zweiter_baut})
    try:
        assert _anfrage(client, zweit_nach=0.05, hoechstdauer=30,
                        bei_zweitanfrage=gebucht.append) == 'erste'
    finally:
        aufbau_frei.set()
    for _ in range(500):                      # zweiter Faden schließt selbst
        if len(verbindungen) == 2 and verbindungen[1].is_closed:
            break
        time.sleep(0.01)
    assert len(verbindungen) == 2 and verbindungen[1].is_closed
    time.sleep(0.05)
    assert gebucht == [] and len(client.aufrufe) == 1


def test_ohne_zweitanfrage_wird_nichts_extra_gebucht():
    gebucht = []
    _anfrage(Client(), zweit_nach=30, bei_zweitanfrage=gebucht.append)
    assert gebucht == []


def test_buchung_der_zweitanfrage_zaehlt_kein_diktat():
    stand = typefree.verbrauch_buchen({}, 60, '2026-10', 'mai')
    stand = typefree.verbrauch_buchen(stand, 60, '2026-10', 'mai', diktat=False)
    assert stand['monat_diktate'] == 1
    assert stand['monat_sekunden'] == 60
    assert stand['monat_zweitanfragen'] == 1
    assert stand['monat_betrag'] == pytest.approx(2 * typefree.kosten_fuer(60, 'mai'))


KETTE = (('mai', 'microsoft/mai-transcribe-2', 'https://x', 'stt'),)


def test_kette_bucht_beim_richtigen_anbieter(monkeypatch):
    gebucht = []
    monkeypatch.setattr(typefree, 'zweitanfrage_nach', lambda s: 0.01)
    client = Client(warte={1: threading.Event()})
    try:
        text, anbieter = typefree._kette_durchlaufen(
            _puffer(), {'mai': client}, KETTE,
            zweitanfrage_buchen=lambda s, n: gebucht.append(n))
    finally:
        client.alles_frei()
    assert (text, anbieter, _gebucht(gebucht)) == ('zweite', 'mai', ['mai'])


def test_werkzeuge_ohne_buchung_ruehren_die_verbrauchsdatei_nicht_an(monkeypatch):
    """sprachmessung.py ruft die Kette ohne geladenen Verbrauchsstand auf —
    eine Buchung schriebe {} über die echte Datei (Codex, Runde 2)."""
    monkeypatch.setattr(typefree, 'zweitanfrage_nach', lambda s: 0.01)
    monkeypatch.setattr(typefree, 'save_verbrauch',
                        lambda v: pytest.fail('Verbrauchsdatei angefasst'))
    clients = [Client(warte={1: threading.Event()}) for _ in range(2)]
    try:
        typefree._kette_durchlaufen(_puffer(), {'mai': clients[0]}, KETTE)
        typefree.transcribe_audio(_puffer(), {'mai': clients[1]}, kette=KETTE)
        assert all(len(c.aufrufe) == 2 for c in clients)   # Zweitanfrage lief jeweils
    finally:
        for c in clients:
            c.alles_frei()


def test_buchung_wartet_nicht_auf_die_mikrofon_sperre(monkeypatch):
    """Der Audio-Callback hält `lock` — die Buchung nutzt eine eigene Sperre."""
    monkeypatch.setattr(typefree, 'save_verbrauch', lambda v: None)
    monkeypatch.setattr(typefree, 'verbrauch', {})
    fertig = threading.Event()
    with typefree.lock:
        faden = threading.Thread(
            target=lambda: (typefree._zweitanfrage_buchen(5, 'mai'), fertig.set()))
        faden.start()
        assert fertig.wait(5), 'Buchung blockiert an der Mikrofon-Sperre'
    faden.join()


def test_wartezeit_waechst_mit_dem_audio():
    assert typefree.zweitanfrage_nach(0) == typefree.STT_ZWEIT_NACH
    assert typefree.zweitanfrage_nach(140) > typefree.zweitanfrage_nach(20)
    assert typefree.zweitanfrage_nach(140) < 10      # bleibt deutlich unter den Hängern
