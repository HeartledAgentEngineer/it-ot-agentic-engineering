"""Der Wächter darf keinen Fehlalarm auslösen, wenn schon gestoppt wurde.

Wettlaufsituation, gefunden bei der Fremdprüfung am 2026-07-29:
Lässt man die Taste in dem Moment los, in dem der Wächter das Mikrofon für tot
erklärt, laufen beide Wege durch. `stop_and_transcribe` besteht seine Prüfung
noch, transkribiert und fügt ein — und der Wächter schlägt trotzdem roten
Alarm. Der Text kommt an, und daneben steht eine Fehlermeldung.

Der Wächter muss die Aufnahme deshalb **im Lock** für sich beanspruchen.
"""
import pytest
import typefree


@pytest.fixture
def wachtstand(monkeypatch):
    """Wächter-Lauf ohne Mikrofon, ohne Netz, mit protokollierten Wirkungen."""
    protokoll = []
    monkeypatch.setattr(typefree, 'report_error',
                        lambda n: protokoll.append(f'ALARM: {n[:30]}'))
    monkeypatch.setattr(typefree, '_close_stream',
                        lambda: protokoll.append('close'))
    monkeypatch.setattr(typefree, '_reconnect_microphone',
                        lambda: protokoll.append('reconnect') or False)
    monkeypatch.setattr(typefree, 'stop_and_transcribe',
                        lambda: protokoll.append('senden'))
    monkeypatch.setattr(typefree, 'audio_frames', [])
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_session', 1)
    return protokoll


def test_totes_geraet_loest_alarm_aus(wachtstand, monkeypatch):
    """Der Normalfall muss weiter funktionieren."""
    monkeypatch.setattr(typefree, 'is_microphone_dead',
                        lambda *a, **k: True)
    typefree._watch_recording(1)
    assert any(e.startswith('ALARM') for e in wachtstand)
    assert typefree.is_recording is False


def test_kein_alarm_wenn_parallel_schon_gestoppt_wurde(wachtstand, monkeypatch):
    """Der eigentliche Fehler.

    `is_microphone_dead` setzt hier `is_recording` auf False — genau das, was
    ein paralleles `stop_and_transcribe` in derselben Millisekunde tut. Danach
    darf der Wächter KEINEN Alarm mehr auslösen, denn das Diktat ist bereits
    unterwegs.
    """
    def tot_und_parallel_gestoppt(*a, **k):
        typefree.is_recording = False      # der andere Thread war schneller
        return True

    monkeypatch.setattr(typefree, 'is_microphone_dead',
                        tot_und_parallel_gestoppt)
    typefree._watch_recording(1)
    assert not any(e.startswith('ALARM') for e in wachtstand), (
        'Fehlalarm neben einem erfolgreichen Diktat')
