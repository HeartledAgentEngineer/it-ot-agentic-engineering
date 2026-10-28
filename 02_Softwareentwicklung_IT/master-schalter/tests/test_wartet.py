"""Tests für „Wartet worauf“ (`wartet.py`, `masterwechsel warte`, Anzeige in `kurz`)."""
from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import cli, kurz, wartet
from master_schalter.signale import Fenster, Kontingent

JETZT = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    return tmp_path / "daten"


def test_setzen_und_lesen(daten):
    wartet.setzen("master-schalter", "Freigabe Vibe-Modus", jetzt=JETZT)
    [m] = wartet.alle_lesen()
    assert (m.thema, m.text, m.zeit) == ("master-schalter", "Freigabe Vibe-Modus", JETZT)
    assert (daten / "wartet" / "master-schalter.json").is_file()


def test_text_wird_eine_zeile_und_begrenzt():
    assert wartet.text_bereinigen("  Codex-Prüfung\nR2\t läuft\x07 ") == "Codex-Prüfung R2 läuft"
    lang = wartet.text_bereinigen("x" * 300)
    assert len(lang) == wartet.MAX_ZEICHEN and lang.endswith("…")


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_leerer_text_ist_fehler(daten, text):
    with pytest.raises(wartet.WartetFehler):
        wartet.setzen("master-schalter", text)
    assert wartet.alle_lesen() == []


@pytest.mark.parametrize("thema", ["../x", "Groß", "a/b", ""])
def test_unzulaessiges_thema(daten, thema):
    with pytest.raises(wartet.WartetFehler):
        wartet.setzen(thema, "Text")


def test_loeschen_ist_idempotent(daten):
    wartet.setzen("t1", "Text")
    assert wartet.loeschen("t1") is True
    assert wartet.loeschen("t1") is False
    assert wartet.alle_lesen() == []


def test_kaputte_und_zu_grosse_dateien_werden_uebersprungen(daten):
    wartet.setzen("gut", "Text", jetzt=JETZT)
    (daten / "wartet" / "kaputt.json").write_text("{kein json", encoding="utf-8")
    (daten / "wartet" / "gross.json").write_text('{"text": "' + "x" * 2000 + '", "zeit": "2026-10-28T00:00:00+00:00"}',
                                                  encoding="utf-8")
    (daten / "wartet" / "ohnezeit.json").write_text('{"text": "x"}', encoding="utf-8")
    assert [m.thema for m in wartet.alle_lesen()] == ["gut"]
    assert (daten / "wartet" / "kaputt.json").is_file()      # nichts wird aufgeräumt oder geraten


def test_alle_lesen_ohne_ordner_ist_leer(daten):
    assert wartet.alle_lesen() == [] and not (daten / "wartet").exists()


def test_cli_warte_setzen_und_fertig(daten, capsys):
    assert cli.main(["warte", "master-schalter", "Freigabe", "Vibe-Modus"]) == 0
    assert "wartet auf „Freigabe Vibe-Modus“" in capsys.readouterr().out
    assert cli.main(["warte", "master-schalter", "--fertig"]) == 0
    assert "entfernt" in capsys.readouterr().out
    assert cli.main(["warte", "master-schalter", "--fertig"]) == 0
    assert "keine Wartemeldung" in capsys.readouterr().out


def test_cli_warte_fehler_ohne_nebenwirkung(daten, capsys):
    assert cli.main(["warte", "master-schalter"]) == 1
    assert "Text ist leer" in capsys.readouterr().err
    assert cli.main(["warte", "../x", "Text"]) == 1
    assert cli.main(["warte", "master-schalter", "Text", "--fertig"]) == 1
    assert "nimmt keinen Text" in capsys.readouterr().err
    assert wartet.alle_lesen() == []


def _k(name):
    return Kontingent(name, (Fenster("5h", 10.0, JETZT + timedelta(hours=2)),
                             Fenster("Woche", 20.0, JETZT + timedelta(days=3))), JETZT - timedelta(minutes=5))


def test_kurz_zeigt_meldungen_aelteste_zuerst_und_veraltet():
    neu = wartet.Meldung("b", "Codex-Prüfung R2", JETZT - timedelta(minutes=5))
    alt = wartet.Meldung("a", "Freigabe Vibe-Modus", JETZT - timedelta(hours=30))
    text = kurz.zeilen([_k("Claude"), _k("Codex")], [], [], schwelle=95, automatik_global=True, jetzt=JETZT,
                       zone=timezone.utc, wartet_auf=(neu, alt))
    warte = [z for z in text if z.startswith("Wartet worauf:")]
    assert warte == ["Wartet worauf: a: Freigabe Vibe-Modus (seit 27.10. 06:00) (veraltet?)",
                     "Wartet worauf: b: Codex-Prüfung R2 (seit 11:55)"]


def test_kurz_ohne_meldung():
    text = kurz.zeilen([_k("Claude"), _k("Codex")], [], [], schwelle=95, automatik_global=True, jetzt=JETZT,
                       zone=timezone.utc)
    assert text[-1] == kurz.WARTET == "Wartet worauf: nichts gemeldet"


def test_sammeln_liest_wartemeldungen(daten, monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    wartet.setzen("master-schalter", "Freigabe Vibe-Modus")
    assert any(z.startswith("Wartet worauf: master-schalter: Freigabe Vibe-Modus") for z in kurz.sammeln())


# --- verwaiste Meldung per pid erkennen (pruefkreis schreibt "pid") ------------------------------------------------

def _schreibe(daten, thema, text="Prüfung R1 läuft (pruefkreis, x)", zeit=JETZT, **zusatz):
    """Meldungsdatei wie `pruefkreis.wartet_melden` (mit pid) – `setzen` schreibt nie eine pid."""
    ordner = daten / "wartet"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{thema}.json").write_text(json.dumps({"text": text, "zeit": zeit.isoformat(), **zusatz}),
                                          encoding="utf-8")


def _beendete_kind_pid():
    """Pid eines Kindprozesses, der beendet ist und dessen Handle auch im Elternprozess freigegeben wurde."""
    kind = subprocess.Popen([sys.executable, "-c", "pass"])
    pid = kind.pid
    kind.wait(timeout=60)
    del kind
    gc.collect()
    return pid


def test_setzen_schreibt_keine_pid(daten):
    wartet.setzen("master-schalter", "Freigabe Vibe-Modus", jetzt=JETZT)
    roh = json.loads((daten / "wartet" / "master-schalter.json").read_text(encoding="utf-8"))
    assert sorted(roh) == ["text", "zeit"]
    assert wartet.alle_lesen()[0].pid is None


def test_pid_wird_gelesen_alte_dateien_ohne_pid_bleiben_gueltig(daten):
    _schreibe(daten, "mit", pid=4242)
    _schreibe(daten, "ohne")
    meldungen = {m.thema: m.pid for m in wartet.alle_lesen()}
    assert meldungen == {"mit": 4242, "ohne": None}


@pytest.mark.parametrize("pid", ["abc", "123", -5, 0, True, False, 1.5, 2**40, None, [1], {"a": 1}])
def test_kaputte_pid_macht_die_meldung_nicht_ungueltig_sondern_pidlos(daten, pid):
    _schreibe(daten, "kaputt", pid=pid)
    [m] = wartet.alle_lesen()
    assert m.thema == "kaputt" and m.text.startswith("Prüfung R1") and m.pid is None


class _FalscheWinApi:
    """Gefälschte kernel32-Antworten: `oeffnen` ⇒ (Handle|None, Fehlercode), `exitcode` ⇒ Code|None."""

    def __init__(self, handle=None, fehler=0, exitcode=None, start=None):
        self.handle, self.fehler, self._exitcode, self._start = handle, fehler, exitcode, start
        self.geschlossen = []

    def oeffnen(self, pid):
        return self.handle, self.fehler

    def exitcode(self, handle):
        return self._exitcode

    def startzeit(self, handle):
        return self._start

    def schliessen(self, handle):
        self.geschlossen.append(handle)


def _windows_mit(monkeypatch, api):
    monkeypatch.setattr(wartet, "_WINDOWS", True)
    monkeypatch.setattr(wartet, "_api", lambda: api)


@pytest.mark.parametrize("handle, fehler, exitcode, erwartet", [
    (None, 87, None, False),        # ERROR_INVALID_PARAMETER: Prozess existiert nicht
    (None, 5, None, None),          # ERROR_ACCESS_DENIED: unbekannt
    (None, 1, None, None),          # jeder andere Fehler: unbekannt
    (None, 0, None, None),
    (777, 0, 259, True),            # STILL_ACTIVE
    (777, 0, 0, False),             # beendet, Handle noch offen
    (777, 0, 1, False),
    (777, 0, 258, False),
    (777, 0, None, None),           # GetExitCodeProcess selbst scheitert
])
def test_lebt_windows_fehlerwege_einzeln(monkeypatch, handle, fehler, exitcode, erwartet):
    api = _FalscheWinApi(handle, fehler, exitcode)
    _windows_mit(monkeypatch, api)
    assert wartet.lebt(4242) is erwartet
    assert api.geschlossen == ([handle] if handle is not None else [])     # Handle wird immer geschlossen


def test_lebt_windows_api_wirft_ist_unbekannt(monkeypatch):
    monkeypatch.setattr(wartet, "_WINDOWS", True)

    def kaputt():
        raise OSError("synthetisch")

    monkeypatch.setattr(wartet, "_api", kaputt)
    assert wartet.lebt(4242) is None


@pytest.mark.parametrize("fehler, erwartet", [
    (None, True),
    (ProcessLookupError(), False),
    (PermissionError(), None),
    (OSError("anderer Fehler"), None),
])
def test_lebt_posix_fehlerwege_einzeln(monkeypatch, fehler, erwartet):
    aufrufe = []

    def kill(pid, signal):
        aufrufe.append((pid, signal))
        if fehler is not None:
            raise fehler

    monkeypatch.setattr(wartet, "_WINDOWS", False)
    monkeypatch.setattr(wartet.os, "kill", kill)
    assert wartet.lebt(4242) is erwartet
    assert aufrufe == [(4242, 0)]


@pytest.mark.parametrize("pid", [0, -1, 2**31, "12", None, True, 1.5])
def test_lebt_mit_unbrauchbarer_pid_ist_unbekannt_und_fasst_nichts_an(monkeypatch, pid):
    monkeypatch.setattr(wartet.os, "kill", lambda *a: pytest.fail("os.kill darf nicht laufen"))
    monkeypatch.setattr(wartet, "_api", lambda: pytest.fail("kernel32 darf nicht laufen"))
    assert wartet.lebt(pid) is None


def test_lebt_echter_lauf_eigene_pid_lebt():
    assert wartet.lebt(os.getpid()) is True


def test_lebt_echter_lauf_beendeter_kindprozess_ist_tot():
    kind = subprocess.Popen([sys.executable, "-c", "pass"])
    kind.wait(timeout=60)
    assert wartet.lebt(kind.pid) is False          # beendet, Handle des Elternprozesses (Windows) noch offen
    pid = kind.pid
    del kind
    gc.collect()
    assert wartet.lebt(pid) is False               # Handle freigegeben: Prozess existiert nicht mehr


@pytest.mark.skipif(sys.platform != "win32", reason="GetProcessTimes gibt es nur unter Windows")
def test_startzeit_echter_lauf_eigener_prozess_liegt_in_der_vergangenheit():
    start = wartet.startzeit(os.getpid())
    assert start is not None and start.tzinfo is not None
    assert datetime(2020, 1, 1, tzinfo=timezone.utc) < start <= datetime.now(timezone.utc)


def test_startzeit_unbekannt_ausserhalb_windows_und_bei_fehlern(monkeypatch):
    monkeypatch.setattr(wartet, "_WINDOWS", False)
    assert wartet.startzeit(os.getpid()) is None
    _windows_mit(monkeypatch, _FalscheWinApi(None, 87))
    assert wartet.startzeit(4242) is None
    _windows_mit(monkeypatch, _FalscheWinApi(777, 0, start=None))
    assert wartet.startzeit(4242) is None


def _meldung(pid, zeit=JETZT):
    return wartet.Meldung("master-schalter", "Prüfung R1 läuft", zeit, pid)


def test_verwaist_ohne_pid_ist_nie_verwaist_und_fragt_den_prozess_nicht(monkeypatch):
    monkeypatch.setattr(wartet, "lebt", lambda pid: pytest.fail("ohne pid keine Prozessabfrage"))
    assert wartet.verwaist(_meldung(None)) is False


@pytest.mark.parametrize("leben, start, erwartet", [
    (False, None, True),                                       # Prozess beendet
    (None, JETZT + timedelta(hours=1), False),                 # unbekannt ⇒ normal anzeigen
    (True, None, False),                                       # Startzeit unbekannt ⇒ nur „lebt“ werten
    (True, JETZT - timedelta(minutes=1), False),               # Prozess älter als die Meldung: der Melder selbst
    (True, JETZT + timedelta(seconds=3), False),               # innerhalb der Toleranz
    (True, JETZT + timedelta(minutes=10), True),               # pid wiederverwendet: Start nach `zeit`
])
def test_verwaist_entscheidung(monkeypatch, leben, start, erwartet):
    monkeypatch.setattr(wartet, "lebt", lambda pid: leben)
    monkeypatch.setattr(wartet, "startzeit", lambda pid: start)
    assert wartet.verwaist(_meldung(4242)) is erwartet


def test_anzeige_pid_lebt_ist_normale_zeile(daten):
    _schreibe(daten, "master-schalter", pid=os.getpid(), zeit=datetime.now(timezone.utc))
    zeile = [z for z in kurz.sammeln() if z.startswith("Wartet worauf:")]
    assert len(zeile) == 1 and "verwaist" not in zeile[0]


def test_anzeige_pid_tot_ist_verwaist_in_status_und_uebersicht(daten, monkeypatch, tmp_path):
    from master_schalter import paare, uebersicht_modell
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen("master-schalter", "00000000-0000-4000-8000-0000000000a1",
                 paare.laufend_bilden("master-schalter"), aktiv=True)
    _schreibe(daten, "master-schalter", pid=_beendete_kind_pid(), zeit=datetime.now(timezone.utc))

    erwartet = "(verwaist – Prozess beendet; `warte master-schalter --fertig` räumt auf)"
    status = [z for z in kurz.sammeln() if z.startswith("Wartet worauf:")]
    assert len(status) == 1 and status[0].endswith(erwartet)
    snap = uebersicht_modell.aufnehmen(datetime.now(timezone.utc), timezone.utc)
    assert len(snap.wartet) == 1 and snap.wartet[0].endswith(erwartet)
    assert (daten / "wartet" / "master-schalter.json").is_file()       # nur Anzeige, nichts wird gelöscht


def test_anzeige_wiederverwendete_pid_ist_verwaist(monkeypatch):
    """Die pid lebt, gehört aber zu einem Prozess, der nach der Meldung gestartet wurde."""
    monkeypatch.setattr(wartet, "lebt", lambda pid: True)
    monkeypatch.setattr(wartet, "startzeit", lambda pid: JETZT + timedelta(minutes=30))
    zeile = kurz._wartet_zeile(_meldung(4242, JETZT - timedelta(minutes=5)), JETZT + timedelta(hours=1), timezone.utc)
    assert zeile.endswith("(verwaist – Prozess beendet; `warte master-schalter --fertig` räumt auf)")


def test_anzeige_ohne_pid_wie_bisher(daten):
    wartet.setzen("master-schalter", "Freigabe Vibe-Modus")
    [zeile] = [z for z in kurz.sammeln() if z.startswith("Wartet worauf:")]
    assert zeile.startswith("Wartet worauf: master-schalter: Freigabe Vibe-Modus (seit ")
    assert "verwaist" not in zeile
