"""Tests: Live-Gedanken-Strecke (`sse.strom_auftrag_live`) gegen eine GEKAPPTE
Meldungsliste.

Regression (Sebastian 2026-09-15: „es hat irgendwann aufgehoert und ich konnte
erst weiter was sehen, wenn ich wieder aktualisiert habe"):
Das Auftragsbuch kappt `status_meldungen` auf die letzten N Eintraege. Der
frueher ABSOLUTE Zaehler (`gesehen = n`, dann `meldungen[n:]`) lief danach
dauerhaft leer: der Stream verstummte mitten im Lauf, waehrend der Agent
weiterarbeitete — neue Gedanken waren erst nach einem Reload sichtbar.

Der Fix findet den Anschluss ueber den UEBERLAPP der zuletzt gesendeten
Eintraege. Diese Tests halten beides fest: die Kappung darf den Strom nicht
abwuergen, und es darf nichts doppelt gesendet werden.
"""
import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import app.services.sse as sse  # noqa: E402


class _StubAuftrag:
    """Vertritt auftrag_service: liefert die Zustandsfolge nacheinander."""

    def __init__(self, states):
        self._states = states
        self._i = 0

    def einzeln(self, auftrag_id):  # noqa: D401 - Test-Signatur wie das Original
        i = min(self._i, len(self._states) - 1)
        self._i += 1
        return self._states[i]


def _zustandsfolge(gesamt: int, cap: int):
    """Wachsende Meldungsliste, ab `cap` auf die letzten `cap` gekappt — genau
    wie `auftrag_service.statusmeldung_hinzufuegen` es tut. Zuletzt: fertig."""
    states = []
    for n in range(1, gesamt + 1):
        liste = [f"m{k}" for k in range(max(1, n - cap + 1), n + 1)]
        states.append({"status": "laeuft", "status_meldungen": liste})
    states.append({"status": "fertig",
                   "status_meldungen": states[-1]["status_meldungen"],
                   "ergebnis": "FERTIG"})
    return states


def _ereignisse(states, monkeypatch):
    monkeypatch.setattr(sse, "auftrag_service", _StubAuftrag(states))
    monkeypatch.setattr(sse.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sse.memory_service, "get_memory_count", lambda: 0)
    raus = []
    for block in sse.strom_auftrag_live("aid-1", "conv_main", "▶️ startet"):
        if not block.startswith("data: "):
            continue
        raus.append(json.loads(block[len("data: "):]))
    return raus


def _gedanken(ereignisse):
    return [e["text"] for e in ereignisse if e.get("art") == "gedanke"]


def test_alle_gedanken_kommen_trotz_kappung(monkeypatch):
    """30 Gedanken bei Kappung auf 20: KEINER darf verloren gehen."""
    ereignisse = _ereignisse(_zustandsfolge(gesamt=30, cap=20), monkeypatch)
    gedanken = _gedanken(ereignisse)
    erwartet = [f"m{k}" for k in range(1, 31)]
    assert gedanken == erwartet


def test_keine_doppelten_gedanken(monkeypatch):
    """Der Ueberlapp-Abgleich darf Wiederholungen nicht doppelt senden."""
    ereignisse = _ereignisse(_zustandsfolge(gesamt=60, cap=20), monkeypatch)
    gedanken = _gedanken(ereignisse)
    assert gedanken == [f"m{k}" for k in range(1, 61)]


def test_kleine_kappung_ebenfalls_vollstaendig(monkeypatch):
    """Auch bei Kappung auf 5 (30 Meldungen) kommt alles an — der Fix haengt
    nicht an einer konkreten Kappungsgroesse."""
    ereignisse = _ereignisse(_zustandsfolge(gesamt=30, cap=5), monkeypatch)
    assert _gedanken(ereignisse) == [f"m{k}" for k in range(1, 31)]


def test_strecke_endet_mit_done_und_ergebnis(monkeypatch):
    ereignisse = _ereignisse(_zustandsfolge(gesamt=25, cap=20), monkeypatch)
    letzte = ereignisse[-1]
    assert letzte.get("done") is True
    assert letzte.get("auftrag_strecke") is True
    assert "FERTIG" in " ".join(
        e.get("delta", "") for e in ereignisse if "delta" in e
    )
