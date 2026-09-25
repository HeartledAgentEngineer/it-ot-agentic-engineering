"""Erneuter Versuch: fehlgeschlagene Aufnahme behalten und wiederholen.

Sebastians Anforderung (25.09.2026): „Ich möchte nicht mehrere Minuten labern und
dann ist alles weg." Die Aufnahme bleibt deshalb im Arbeitsspeicher, und das
Tray-Menü bietet sie erneut an. Diese Prüfungen sichern genau das ab — ohne
Mikrofon und ohne Netz.
"""
import numpy as np
import pytest

import typefree


@pytest.fixture(autouse=True)
def sauber():
    """Jeder Test startet ohne behaltene Aufnahme."""
    typefree.retry_verwerfen()
    yield
    typefree.retry_verwerfen()


@pytest.fixture
def still(monkeypatch):
    """Tray, Zwischenablage und Buchhaltung ruhigstellen."""
    monkeypatch.setattr(typefree, 'pyperclip', type('P', (), {'copy': staticmethod(lambda t: None)}))
    monkeypatch.setattr(typefree, 'pyautogui', type('G', (), {'hotkey': staticmethod(lambda *a: None)}))
    monkeypatch.setattr(typefree, 'save_verbrauch', lambda *a, **k: None)
    monkeypatch.setattr(typefree, '_status_transcribing', lambda: None)
    monkeypatch.setattr(typefree, '_status_polishing', lambda: None)
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, 'report_error', lambda text: None)
    monkeypatch.setattr(typefree, 'polish_text', lambda text: text)


def sprache(sekunden):
    rng = np.random.default_rng(3)
    return rng.normal(0, 0.2, int(sekunden * typefree.SAMPLE_RATE)).astype(np.float32)


def test_ohne_fehlschlag_gibt_es_nichts_zu_wiederholen():
    assert not typefree.retry_bereit()
    assert typefree.retry_text() == 'Letztes Diktat erneut versuchen'


def test_gemerkte_aufnahme_ist_bereit_und_nennt_ihre_laenge():
    typefree.aufnahme_merken(sprache(12), '429 gedrosselt')
    assert typefree.retry_bereit()
    assert '12 s' in typefree.retry_text()
    assert typefree.letzte_aufnahme['sekunden'] == pytest.approx(12.0, abs=0.1)
    assert typefree.letzte_aufnahme['fehler'] == '429 gedrosselt'


def test_fehlschlag_behaelt_die_aufnahme(monkeypatch, still):
    """Der Kern der Anforderung: nach einem Fehlschlag ist das Audio nicht weg."""
    def platzt(*a, **k):
        raise RuntimeError('Kein Anbieter konnte transkribieren — 429')

    monkeypatch.setattr(typefree, 'transcribe_audio', platzt)
    typefree._verarbeite_audio(sprache(20))

    assert typefree.retry_bereit(), 'Aufnahme muss für den zweiten Versuch bereitliegen'
    assert typefree.letzte_aufnahme['sekunden'] == pytest.approx(20.0, abs=0.1)


def test_erfolg_verwirft_die_aufnahme(monkeypatch, still):
    """Was angekommen ist, muss nicht wiederholt werden."""
    monkeypatch.setattr(typefree, 'transcribe_audio',
                        lambda puffer, clients: ('Text aus dem zweiten Versuch', 'mai'))
    typefree.aufnahme_merken(sprache(5), 'alter Fehlschlag')
    typefree._verarbeite_audio(sprache(8), erneut=True)

    assert not typefree.retry_bereit(), 'nach dem Erfolg darf nichts liegenbleiben'


def test_erneuter_versuch_bucht_die_kosten_erneut(monkeypatch, still):
    """Auch der zweite Versuch kostet Geld — er wird wie ein Diktat gebucht."""
    gebucht = {}

    def merke(verbrauch, sekunden, monat, anbieter=None):
        gebucht['sekunden'], gebucht['anbieter'] = sekunden, anbieter
        return verbrauch

    monkeypatch.setattr(typefree, 'transcribe_audio',
                        lambda puffer, clients: ('Text', 'mai'))
    monkeypatch.setattr(typefree, 'verbrauch_buchen', merke)
    typefree._verarbeite_audio(sprache(6), erneut=True)

    assert gebucht['anbieter'] == 'mai'
    assert gebucht['sekunden'] == pytest.approx(6.0, abs=0.1)
