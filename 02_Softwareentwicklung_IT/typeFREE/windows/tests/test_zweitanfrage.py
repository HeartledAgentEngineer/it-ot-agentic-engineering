"""Zweitanfrage, wenn die Transkription hängt.

12.10.2026: „Type Free ist ganz, ganz langsam geworden." mai antwortete sonst in
1–2 s, an dem Tag im Median in 12,5 s, einzelne Anfragen hingen 56–181 s. Ohne
Zeitlimit wartete typeFREE bis zu 10 Minuten. Jetzt geht nach kurzer Wartezeit
dieselbe Anfrage ein zweites Mal los; die erste Antwort gewinnt.
"""
import io
import threading
import types

import pytest

import typefree


class HaengenderClient:
    """Erste Anfrage hängt, bis der Test sie freigibt; jede weitere antwortet sofort."""

    def __init__(self, antworten=('erste', 'zweite'), fehler=None):
        self.aufrufe = []
        self.dateien = []
        self.optionen = []
        self.freigabe = threading.Event()
        self._antworten = antworten
        self._fehler = fehler or {}
        self.audio = types.SimpleNamespace(
            transcriptions=types.SimpleNamespace(create=self._create))

    def with_options(self, **kwargs):
        self.optionen.append(kwargs)
        return self

    def _create(self, **kwargs):
        nummer = len(self.aufrufe) + 1
        self.aufrufe.append(kwargs)
        self.dateien.append((kwargs['file'].tell(), kwargs['file'].read()))
        if nummer == 1:
            self.freigabe.wait(5)
        if nummer in self._fehler:
            raise self._fehler[nummer]
        return types.SimpleNamespace(text=self._antworten[nummer - 1])


def _puffer():
    p = io.BytesIO(b'RIFF-audio')
    p.name = 'audio.wav'
    p.read()                       # Dateizeiger am Ende, wie nach einem Fehlversuch
    return p


def test_schnelle_antwort_braucht_keine_zweite_anfrage():
    client = HaengenderClient()
    client.freigabe.set()
    text = typefree._stt_anfrage(client, 'm', _puffer(), 'v', zweit_nach=2)
    assert text == 'erste'
    assert len(client.aufrufe) == 1


def test_haengende_anfrage_wird_von_der_zweiten_ueberholt():
    client = HaengenderClient()
    try:
        text = typefree._stt_anfrage(client, 'm', _puffer(), 'v', zweit_nach=0.05)
    finally:
        client.freigabe.set()
    assert text == 'zweite'
    assert len(client.aufrufe) == 2


def test_beide_anfragen_schicken_das_ganze_audio():
    client = HaengenderClient()
    try:
        typefree._stt_anfrage(client, 'm', _puffer(), 'v', zweit_nach=0.05)
    finally:
        client.freigabe.set()
    assert client.dateien == [(0, b'RIFF-audio'), (0, b'RIFF-audio')]
    assert client.aufrufe[0]['file'].name == 'audio.wav'


def test_zeitlimit_und_keine_stillen_wiederholungen():
    """Ohne Limit wartete das SDK bis zu 10 min und wiederholte selbst."""
    client = HaengenderClient()
    client.freigabe.set()
    typefree._stt_anfrage(client, 'm', _puffer(), 'v', hoechstdauer=30)
    assert client.optionen == [{'timeout': 30, 'max_retries': 0}]


def test_haengen_beide_gibt_es_einen_zeitfehler():
    client = HaengenderClient()

    def immer_haengen(**kwargs):
        client.freigabe.wait(5)
        return types.SimpleNamespace(text='zu spät')

    client.audio.transcriptions.create = immer_haengen
    try:
        with pytest.raises(TimeoutError):
            typefree._stt_anfrage(client, 'm', _puffer(), 'v',
                                  zweit_nach=0.05, hoechstdauer=0.2)
    finally:
        client.freigabe.set()


def test_fehler_der_ersten_wartet_auf_die_zweite():
    client = HaengenderClient(fehler={1: RuntimeError('502')})
    client.freigabe.set()
    # Erste scheitert sofort, bevor eine zweite lief → Fehler geht an die Kette.
    with pytest.raises(RuntimeError, match='502'):
        typefree._stt_anfrage(client, 'm', _puffer(), 'v', zweit_nach=2)


def test_zweite_scheitert_erste_kommt_noch():
    client = HaengenderClient(fehler={2: RuntimeError('429')})
    threading.Timer(0.2, client.freigabe.set).start()
    text = typefree._stt_anfrage(client, 'm', _puffer(), 'v', zweit_nach=0.05)
    assert text == 'erste'


def test_wartezeit_waechst_mit_dem_audio():
    assert typefree.zweitanfrage_nach(0) == typefree.STT_ZWEIT_NACH
    assert typefree.zweitanfrage_nach(140) > typefree.zweitanfrage_nach(20)
    assert typefree.zweitanfrage_nach(140) < 10      # bleibt deutlich unter den Hängern
