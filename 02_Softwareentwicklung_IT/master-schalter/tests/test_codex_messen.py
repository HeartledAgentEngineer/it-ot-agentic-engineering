"""Tests der aktiven Codex-Messung – nur mit Attrappenprogramm (kleines Python-Skript), nie mit echtem `codex.exe`."""
from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import automatik, codex_messen, signale

JETZT = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)
RESET_5H = int((JETZT + timedelta(hours=3)).timestamp())
RESET_WOCHE = int((JETZT + timedelta(days=4)).timestamp())
GEHEIM = "geheimer-kontoname@example.invalid"
FRIST_GROSSZUEGIG = 60.0     # Normalfall: die Attrappe antwortet/endet selbst; die Frist ist nicht Gegenstand

ATTRAPPE = r'''
import json, os, subprocess, sys, time

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
modus = cfg["modus"]


def senden(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def protokoll(zeile):
    with open(cfg["log"], "a", encoding="utf-8") as f:
        f.write(zeile.strip() + "\n")


with open(cfg["pid"], "w", encoding="utf-8") as f:
    f.write(str(os.getpid()))
if modus == "sofort_ende":
    sys.exit(0)
if modus == "taub":        # liest nie von stdin, läuft endlos (nur ein Kill beendet ihn)
    while True:
        with open(cfg["herzschlag"], "a", encoding="utf-8") as f:
            f.write("x")
        time.sleep(0.05)
while True:
    zeile = sys.stdin.readline()
    if not zeile:
        break
    protokoll(zeile)
    try:
        nachricht = json.loads(zeile)
    except ValueError:
        continue
    methode, kennung = nachricht.get("method"), nachricht.get("id")
    if methode == "initialize":
        if modus == "kaputt":
            sys.stdout.write("{das ist kein json\n")
            sys.stdout.flush()
            continue
        # Rauschen vor der Antwort: Benachrichtigung und Serveranfrage mit gleicher Kennung
        senden({"method": "mcpServer/startupStatus", "params": {"name": "x"}})
        senden({"id": 1, "method": "server/request", "params": {}})
        senden({"id": 99, "result": {"fremd": True}})
        senden({"id": kennung, "result": {"userAgent": "attrappe"}})
    elif methode == "account/rateLimits/read":
        if modus == "waise":   # startet einen Enkel, der stdout erbt, und endet sofort selbst
            enkel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            with open(cfg["enkel"], "w", encoding="utf-8") as f:
                f.write(str(enkel.pid))
            os._exit(0)
        if modus == "stumm":
            while True:
                with open(cfg["herzschlag"], "a", encoding="utf-8") as f:
                    f.write("x")
                time.sleep(0.05)
        if modus == "fehler":
            senden({"id": kennung, "error": {"code": -32000, "message": cfg["geheim"]}})
        else:
            senden({"id": kennung, "result": cfg["result"]})
'''


def _fenster(prozent, dauer, reset):
    return {"usedPercent": prozent, "windowDurationMins": dauer, "resetsAt": reset}


def _ergebnis(primary=None, secondary=None, **extra):
    """Antwort von `account/rateLimits/read` samt Kontofeldern, die nie gespeichert werden dürfen."""
    rate = {"limitId": "codex", "limitName": GEHEIM, "planType": "pro",
            "credits": {"hasCredits": True, "balance": "123.45"},
            "primary": primary if primary is not None else _fenster(24.5, 300, RESET_5H),
            "secondary": secondary if secondary is not None else _fenster(61.0, 10080, RESET_WOCHE),
            "rateLimitReachedType": None}
    rate.update(extra)
    return {"rateLimits": rate, "account": {"email": GEHEIM}}


class Attrappe:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self.skript = tmp_path / "attrappe.py"
        self.skript.write_text(ATTRAPPE, encoding="utf-8")
        self.cfg = tmp_path / "attrappe.json"
        self.log = tmp_path / "attrappe.log"
        self.herzschlag = tmp_path / "herzschlag.txt"
        self.pid = tmp_path / "attrappe.pid"
        self.enkel = tmp_path / "enkel.pid"
        self.datei = tmp_path / "keine-echten-daten" / "codex-kontingent.json"
        monkeypatch.setattr(codex_messen, "_befehl", lambda programm: [sys.executable, str(self.skript), str(self.cfg)])

    def konfig(self, modus="ok", result=None, **extra):
        self.cfg.write_text(json.dumps({
            "modus": modus, "result": result if result is not None else _ergebnis(),
            "log": str(self.log), "herzschlag": str(self.herzschlag), "geheim": GEHEIM,
            "pid": str(self.pid), "enkel": str(self.enkel), **extra}), encoding="utf-8")

    def aufraeumen(self) -> None:
        """Übrig gebliebene Attrappenprozesse (nur die selbst aufgezeichneten PIDs) beenden."""
        for datei in (self.pid, self.enkel):
            try:
                os.kill(int(datei.read_text(encoding="utf-8")), signal.SIGTERM)
            except (OSError, ValueError):
                pass

    def empfangen(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(z) for z in self.log.read_text(encoding="utf-8").splitlines() if z.strip()]


@pytest.fixture(autouse=True)
def _grosszuegige_bereinigungsbudgets(monkeypatch):
    """Kill und Einsammeln des Lesefadens dauern unter Volllast länger als die Produktivwerte (5 s/3 s);
    Tests, die die Budgets selbst knapp setzen, überschreiben das."""
    monkeypatch.setattr(codex_messen.modelle, "BEREINIGUNG_SEKUNDEN", 30.0)
    monkeypatch.setattr(codex_messen.modelle, "PIPE_SEKUNDEN", 15.0)


@pytest.fixture
def attrappe(tmp_path, monkeypatch):
    a = Attrappe(tmp_path, monkeypatch)
    yield a
    a.aufraeumen()


def _lebt(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    return code.value == 259                              # STILL_ACTIVE


def _warte_tot(pid: int, frist: float = 60.0) -> bool:
    ende = time.monotonic() + frist
    while time.monotonic() < ende:
        if not _lebt(pid):
            return True
        time.sleep(0.05)
    return False


def _messen(**kw):
    return codex_messen.messen(programm="ignoriert.exe", frist=kw.pop("frist", FRIST_GROSSZUEGIG),
                               jetzt=kw.pop("jetzt", JETZT), **kw)


class _FristNachBereit:
    """Zählt den Startaufwand der Attrappe nicht gegen die Frist.

    Tests, deren Gegenstand das Ende einer Messung *nach* dem Start der Attrappe ist (Frist, Bereinigung), laufen mit
    großer Frist. Sobald die Attrappe "bereit" meldet (`bereit()`), wird die Frist des laufenden Gesprächs auf
    `rest` Sekunden verkürzt und der wartende Leser geweckt – danach läuft der echte Frist-Pfad (`ZEIT`) ab.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, bereit, rest: float = 1.0, obergrenze: float = 180.0):
        self.gespraeche: list = []
        self.verkuerzt = False
        self._bereit, self._rest, self._obergrenze = bereit, rest, obergrenze
        echt = codex_messen._Gespraech.__init__

        def init(selbst, *a, **k):
            echt(selbst, *a, **k)
            self.gespraeche.append(selbst)

        monkeypatch.setattr(codex_messen._Gespraech, "__init__", init)
        self._faden = threading.Thread(target=self._lauf, daemon=True)

    def start(self) -> None:
        self._faden.start()

    def _lauf(self) -> None:
        ende = time.monotonic() + self._obergrenze
        while time.monotonic() < ende:
            if self.gespraeche and self._bereit():
                gespraech = self.gespraeche[0]
                gespraech.ende = time.monotonic() + self._rest
                gespraech.zeilen.put(b'{"method":"wecken"}\n')   # Benachrichtigung: Leser rechnet die Frist neu
                self.verkuerzt = True
                return
            time.sleep(0.05)


# --- Erfolg ---------------------------------------------------------------------------------

def test_gueltige_antwort_ordnet_beide_fenster_zu_und_schreibt_die_datei(attrappe):
    attrappe.konfig()

    k = _messen()

    assert k.fehler is None and k.master == "Codex" and k.stand == JETZT
    assert k.fenster_nach_name("5h").prozent == 24.5
    assert k.fenster_nach_name("Woche").prozent == 61.0
    assert k.fenster_nach_name("5h").reset == datetime.fromtimestamp(RESET_5H, timezone.utc)
    assert k.fenster_nach_name("Woche").reset == datetime.fromtimestamp(RESET_WOCHE, timezone.utc)
    gelesen = signale.codex_messung_lesen(attrappe.datei, jetzt=JETZT)
    assert gelesen is not None and gelesen.fenster == k.fenster and gelesen.stand == JETZT


def test_protokoll_initialize_initialized_dann_ratelimits(attrappe):
    attrappe.konfig()

    _messen()

    nachrichten = attrappe.empfangen()
    assert [n.get("method") for n in nachrichten] == ["initialize", "initialized", "account/rateLimits/read"]
    assert nachrichten[0]["id"] == 1 and nachrichten[0]["params"]["clientInfo"]["name"] == "master-schalter"
    assert "version" in nachrichten[0]["params"]["clientInfo"]
    assert "id" not in nachrichten[1]            # Benachrichtigung ohne Kennung
    assert nachrichten[2]["id"] == 2


def test_fenster_werden_nach_dauer_zugeordnet_auch_bei_vertauschter_reihenfolge(attrappe):
    attrappe.konfig(result=_ergebnis(primary=_fenster(70.0, 10080, RESET_WOCHE),
                                     secondary=_fenster(5.0, 300, RESET_5H)))

    k = _messen()

    assert k.fehler is None
    assert k.fenster_nach_name("5h").prozent == 5.0
    assert k.fenster_nach_name("5h").reset == datetime.fromtimestamp(RESET_5H, timezone.utc)
    assert k.fenster_nach_name("Woche").prozent == 70.0


def test_datei_und_ausgabe_enthalten_keine_kontofelder(attrappe, capsys):
    attrappe.konfig()

    k = _messen()

    assert k.fehler is None, k.fehler
    text = attrappe.datei.read_text(encoding="utf-8")
    for fremd in (GEHEIM, "pro", "credits", "123.45", "planType", "email", "limitName"):
        assert fremd not in text
    daten = json.loads(text)
    assert set(daten) == {"version", "gelesen_um", "fenster"}
    assert set(daten["fenster"]) == {"5h", "Woche"}
    assert all(set(w) == {"used_percent", "resets_at"} for w in daten["fenster"].values())
    ausgabe = capsys.readouterr()
    assert GEHEIM not in ausgabe.out + ausgabe.err


def test_prozess_wird_nach_erfolg_beendet(attrappe, monkeypatch):
    attrappe.konfig()
    gestartet = []
    echt = subprocess.Popen

    def popen(argv, **k):
        p = echt(argv, **k)
        if argv[0] == sys.executable:      # nur die Attrappe, nicht `taskkill` der Bereinigung
            gestartet.append(p)
        return p

    monkeypatch.setattr(codex_messen.subprocess, "Popen", popen)

    k = _messen()

    assert k.fehler is None, k.fehler
    assert len(gestartet) == 1 and gestartet[0].poll() is not None


def test_reset_null_nur_bei_null_prozent(attrappe):
    attrappe.konfig(result=_ergebnis(primary=_fenster(0.0, 300, None)))
    k = _messen()
    assert k.fehler is None
    assert k.fenster_nach_name("5h").prozent == 0.0 and k.fenster_nach_name("5h").reset is None

    attrappe.konfig(result=_ergebnis(primary=_fenster(12.0, 300, None)))
    assert _messen().fehler == codex_messen.fehlertext(codex_messen.WERTE)


def test_andere_limit_kennung_wird_ueber_die_kennungsliste_gefunden(attrappe):
    ergebnis = _ergebnis(limitId="premium")
    ergebnis["rateLimitsByLimitId"] = {"codex": _ergebnis()["rateLimits"]}
    attrappe.konfig(result=ergebnis)
    assert _messen().fenster_nach_name("5h").prozent == 24.5

    attrappe.konfig(result=_ergebnis(limitId="premium"))
    assert _messen().fehler == codex_messen.fehlertext(codex_messen.ANTWORT)


# --- Fehler ---------------------------------------------------------------------------------

def _alt_schreiben(attrappe):
    assert signale.codex_schreiben({"5h": {"used_percent": 3.0, "resets_at": RESET_5H},
                                    "Woche": {"used_percent": 4.0, "resets_at": RESET_WOCHE}},
                                   attrappe.datei, jetzt=JETZT - timedelta(hours=1))
    return attrappe.datei.read_bytes()


def test_fehlerantwort_gibt_festen_text_und_laesst_die_datei_stehen(attrappe):
    attrappe.konfig(modus="fehler")
    alt = _alt_schreiben(attrappe)

    k = _messen()

    assert k.fehler == "Codex-Messung fehlgeschlagen (Fehlerantwort von Codex)"
    assert GEHEIM not in k.fehler and k.fenster == ()
    assert attrappe.datei.read_bytes() == alt


def test_kaputtes_json_ist_ein_fehler(attrappe):
    attrappe.konfig(modus="kaputt")
    alt = _alt_schreiben(attrappe)

    k = _messen()

    assert k.fehler == "Codex-Messung fehlgeschlagen (Antwort ungültig)"
    assert attrappe.datei.read_bytes() == alt


def test_keine_antwort_endet_an_der_frist_und_beendet_den_prozess(attrappe, monkeypatch):
    """Frist ist Gegenstand: `messen()` endet nicht vor der Frist und kehrt innerhalb Frist + Gnadenfrist +
    Vorbehalt (+ großzügiger Lastzuschlag) zurück. Der Start der Attrappe zählt nicht in die Zusicherungen:
    Prozess tot, Herzschlag steht – und, falls sie schon lief, ihre PID ist tot."""
    attrappe.konfig(modus="stumm")
    alt = _alt_schreiben(attrappe)
    gestartet = []
    echt = subprocess.Popen

    def popen(argv, **k):
        p = echt(argv, **k)
        gestartet.append(p)
        return p

    monkeypatch.setattr(codex_messen.subprocess, "Popen", popen)
    frist = 2.0

    beginn = time.monotonic()
    k = _messen(frist=frist)
    dauer = time.monotonic() - beginn

    assert k.fehler == "Codex-Messung fehlgeschlagen (Zeitüberschreitung)"
    assert dauer >= frist - 0.1                                   # nie vor der Frist
    assert dauer < frist + codex_messen.GNADENFRIST + codex_messen.modelle.bereinigungsvorbehalt() + 60
    assert attrappe.datei.read_bytes() == alt
    assert len(gestartet) == 1 and gestartet[0].poll() is not None
    if attrappe.pid.exists():
        assert _warte_tot(_pid(attrappe))
    if attrappe.herzschlag.exists():                 # Herzschlag des Attrappenprozesses darf nicht mehr wachsen
        time.sleep(0.4)
        erste = attrappe.herzschlag.stat().st_size
        time.sleep(0.4)
        assert attrappe.herzschlag.stat().st_size == erste


def test_stumme_attrappe_nach_bereit_endet_an_der_frist_und_wird_beendet(attrappe, monkeypatch):
    """Wie oben, aber erst nach "bereit" (Anfrage `account/rateLimits/read` angekommen) wird die Frist verkürzt:
    der Prozess lief sicher, seine PID und sein Herzschlag sind prüfbar."""
    attrappe.konfig(modus="stumm")
    alt = _alt_schreiben(attrappe)
    bereit = _FristNachBereit(monkeypatch, lambda: any(
        n.get("method") == "account/rateLimits/read" for n in attrappe.empfangen()))
    bereit.start()

    k = _messen()

    assert bereit.verkuerzt
    assert k.fehler == "Codex-Messung fehlgeschlagen (Zeitüberschreitung)"
    assert attrappe.datei.read_bytes() == alt
    assert _warte_tot(_pid(attrappe))
    time.sleep(0.4)
    erste = attrappe.herzschlag.stat().st_size
    time.sleep(0.4)
    assert attrappe.herzschlag.stat().st_size == erste


def test_prozess_der_sofort_endet_ist_ein_fehler(attrappe):
    attrappe.konfig(modus="sofort_ende")

    k = _messen()

    assert k.fehler == "Codex-Messung fehlgeschlagen (Prozess vorzeitig beendet)"


@pytest.mark.parametrize("wert", [100.5, -0.1, 250, "50", True, None, float("nan")])
def test_prozent_ausserhalb_oder_ungueltig_ist_ein_fehler(attrappe, wert):
    attrappe.konfig(result=_ergebnis(primary=_fenster(wert, 300, RESET_5H)))
    alt = _alt_schreiben(attrappe)

    k = _messen()

    assert k.fehler == codex_messen.fehlertext(codex_messen.WERTE)
    assert attrappe.datei.read_bytes() == alt


def test_unbekannte_dauer_wird_ignoriert_und_fehlendes_fenster_ist_ein_fehler(attrappe):
    attrappe.konfig(result=_ergebnis(primary=_fenster(999.0, 43200, RESET_5H)))   # unbekannte Dauer: nicht beachtet

    k = _messen()

    assert k.fehler == codex_messen.fehlertext(codex_messen.ANTWORT)   # „5h“ fehlt – nichts wird geraten
    assert not attrappe.datei.exists()


def test_zwei_fenster_gleicher_dauer_sind_nicht_eindeutig(attrappe):
    attrappe.konfig(result=_ergebnis(secondary=_fenster(10.0, 300, RESET_5H)))

    assert _messen().fehler == codex_messen.fehlertext(codex_messen.WERTE)


@pytest.mark.parametrize("ergebnis", [{}, {"rateLimits": []}, {"rateLimits": {"primary": "x", "secondary": {}}}])
def test_unvollstaendige_antwort_ist_ein_fehler(attrappe, ergebnis):
    attrappe.konfig(result=ergebnis)

    assert _messen().fehler == codex_messen.fehlertext(codex_messen.ANTWORT)


def test_programm_nicht_gefunden_ist_ein_fester_fehler(tmp_path):
    k = codex_messen.messen(programm=str(tmp_path / "gibt-es-nicht.exe"), frist=2.0, jetzt=JETZT)

    assert k.fehler == "Codex-Messung fehlgeschlagen (Programm nicht gefunden)"
    assert str(tmp_path) not in k.fehler


def test_ohne_programm_aus_umgebung_ist_es_ein_fehler_kein_echter_start(monkeypatch):
    monkeypatch.setattr(codex_messen.codex_senden, "programm", lambda: None)

    assert codex_messen.messen(jetzt=JETZT).fehler == codex_messen.fehlertext(codex_messen.PROGRAMM)


def test_unerwartete_ausnahme_zeigt_nur_den_klassennamen(monkeypatch):
    def kaputt(programm, frist):
        raise RuntimeError(GEHEIM)

    monkeypatch.setattr(codex_messen, "_abfragen", kaputt)

    k = codex_messen.messen(programm="x.exe", jetzt=JETZT)

    assert k.fehler == "Codex-Messung fehlgeschlagen (RuntimeError)"
    assert GEHEIM not in k.fehler


def test_speicherfehler_wird_zum_festen_fehler(attrappe, monkeypatch):
    attrappe.konfig()

    def kaputt(*a, **k):
        raise OSError(GEHEIM)

    monkeypatch.setattr(signale, "_atomar_schreiben", kaputt)

    k = _messen()

    assert k.fehler == codex_messen.fehlertext(codex_messen.SPEICHERN) and GEHEIM not in k.fehler


# --- Prozessstart -------------------------------------------------------------------------------

def test_start_ohne_shell_mit_pipes_ohne_konsolenfenster(monkeypatch):
    aufrufe = []

    def popen(argv, **kwargs):
        aufrufe.append((argv, kwargs))
        raise FileNotFoundError("egal")

    monkeypatch.setattr(codex_messen.subprocess, "Popen", popen)

    codex_messen.messen(programm="C:/x/codex.exe", frist=1.0, jetzt=JETZT)

    argv, kw = aufrufe[0]
    assert argv == ["C:/x/codex.exe", "app-server"] and isinstance(argv, list)
    assert not kw.get("shell")
    assert kw["stdin"] == subprocess.PIPE and kw["stdout"] == subprocess.PIPE
    assert kw["stderr"] == subprocess.DEVNULL
    if sys.platform == "win32":
        assert kw["creationflags"] & subprocess.CREATE_NO_WINDOW
    assert not any(n.upper().startswith(("OPENAI_", "ANTHROPIC_")) for n in kw["env"])


# --- signale: neuerer Stand, Schreiben, Lesen ---------------------------------------------------------

def _rollout(ordner: Path, zeit: str, prozent: float) -> None:
    datei = ordner / "2026" / "10" / "26" / "rollout-a.jsonl"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(json.dumps({"timestamp": zeit, "type": "event_msg", "payload": {
        "type": "token_count", "rate_limits": {
            "limit_id": "codex",
            "primary": {"used_percent": prozent, "window_minutes": 300, "resets_at": RESET_5H},
            "secondary": {"used_percent": 9.0, "window_minutes": 10080, "resets_at": RESET_WOCHE}}}}) + "\n",
                     encoding="utf-8")


def _messung(datei: Path, jetzt: datetime, fuenf=50.0) -> None:
    assert signale.codex_schreiben({"5h": {"used_percent": fuenf, "resets_at": RESET_5H},
                                    "Woche": {"used_percent": 20.0, "resets_at": RESET_WOCHE}}, datei, jetzt=jetzt)


def test_codex_lesen_nimmt_die_neuere_messung(tmp_path):
    _rollout(tmp_path / "s", "2026-10-26T13:00:00Z", 11.0)
    messdatei = tmp_path / "m.json"
    _messung(messdatei, JETZT - timedelta(minutes=1))

    k = signale.codex_lesen(tmp_path / "s", jetzt=JETZT, leser=signale.CodexLeser(), messdatei=messdatei)

    assert k.stand == JETZT - timedelta(minutes=1) and k.fenster_nach_name("5h").prozent == 50.0


def test_codex_lesen_nimmt_die_neuere_sitzung(tmp_path):
    _rollout(tmp_path / "s", "2026-10-26T13:59:00Z", 11.0)
    messdatei = tmp_path / "m.json"
    _messung(messdatei, JETZT - timedelta(minutes=30))

    k = signale.codex_lesen(tmp_path / "s", jetzt=JETZT, leser=signale.CodexLeser(), messdatei=messdatei)

    assert k.stand == datetime(2026, 10, 26, 13, 59, tzinfo=timezone.utc) and k.fenster_nach_name("5h").prozent == 11.0


def test_codex_lesen_ohne_sitzungen_nutzt_die_messung(tmp_path):
    messdatei = tmp_path / "m.json"
    _messung(messdatei, JETZT)

    k = signale.codex_lesen(tmp_path / "gibt-es-nicht", jetzt=JETZT, messdatei=messdatei)

    assert k.fehler is None and k.stand == JETZT


def test_codex_lesen_ohne_messdatei_bleibt_unveraendert(tmp_path):
    _rollout(tmp_path / "s", "2026-10-26T13:00:00Z", 11.0)

    k = signale.codex_lesen(tmp_path / "s", jetzt=JETZT, leser=signale.CodexLeser(), messdatei=tmp_path / "fehlt.json")

    assert k.stand == datetime(2026, 10, 26, 13, 0, tzinfo=timezone.utc) and k.fenster_nach_name("5h").prozent == 11.0
    assert signale.codex_lesen(tmp_path / "leer", jetzt=JETZT, messdatei=tmp_path / "fehlt.json").fehler == "keine Daten"


@pytest.mark.parametrize("inhalt", ["{", "[]", '{"gelesen_um": "gestern", "fenster": {}}',
                                    '{"gelesen_um": "2026-10-26T13:59:00+00:00", "fenster": {"5h": {"used_percent": 101, "resets_at": 1}}}'])
def test_kaputte_messdatei_wird_ignoriert(tmp_path, inhalt):
    messdatei = tmp_path / "m.json"
    messdatei.write_text(inhalt, encoding="utf-8")

    assert signale.codex_messung_lesen(messdatei, JETZT) is None
    assert signale.codex_lesen(tmp_path / "leer", jetzt=JETZT, messdatei=messdatei).fehler == "keine Daten"


def test_messung_aus_der_zukunft_wird_nie_bevorzugt(tmp_path):
    _rollout(tmp_path / "s", "2026-10-26T13:00:00Z", 11.0)
    messdatei = tmp_path / "m.json"
    _messung(messdatei, JETZT + timedelta(hours=5))

    k = signale.codex_lesen(tmp_path / "s", jetzt=JETZT, leser=signale.CodexLeser(), messdatei=messdatei)

    assert k.fenster_nach_name("5h").prozent == 11.0


def test_abgelaufenes_messfenster_gilt_als_zurueckgesetzt(tmp_path):
    messdatei = tmp_path / "m.json"
    _messung(messdatei, JETZT - timedelta(hours=4))   # RESET_5H liegt 3 h nach JETZT; hier „jetzt“ ist später

    k = signale.codex_messung_lesen(messdatei, jetzt=JETZT + timedelta(hours=4))

    assert k.fenster_nach_name("5h").zurueckgesetzt and k.fenster_nach_name("5h").prozent == 0.0


def test_codex_schreiben_ungueltig_laesst_alte_datei_stehen(tmp_path):
    messdatei = tmp_path / "m.json"
    _messung(messdatei, JETZT)
    alt = messdatei.read_bytes()

    assert not signale.codex_schreiben({"5h": {"used_percent": 120, "resets_at": RESET_5H},
                                        "Woche": {"used_percent": 1, "resets_at": RESET_WOCHE}}, messdatei, JETZT)
    assert not signale.codex_schreiben({"5h": {"used_percent": 1, "resets_at": RESET_5H}}, messdatei, JETZT)
    assert messdatei.read_bytes() == alt
    assert list(tmp_path.glob("*.tmp")) == []


# --- Automatik-Zusammenspiel ------------------------------------------------------------------------

def test_mit_frischer_aktiver_messung_ist_codex_frei(tmp_path):
    jetzt = datetime.now(timezone.utc)
    messdatei = signale.codex_datei()
    assert signale.codex_schreiben({"5h": {"used_percent": 20.0, "resets_at": (jetzt + timedelta(hours=2)).timestamp()},
                                    "Woche": {"used_percent": 30.0, "resets_at": (jetzt + timedelta(days=3)).timestamp()}},
                                   messdatei, jetzt=jetzt - timedelta(minutes=1))

    codex = signale.codex_lesen(tmp_path / "keine-sitzungen", jetzt=jetzt)

    assert automatik._codex_frei(codex, 80, jetzt)


def test_mit_alter_aktiver_messung_ist_codex_nicht_frei(tmp_path):
    jetzt = datetime.now(timezone.utc)
    assert signale.codex_schreiben({"5h": {"used_percent": 20.0, "resets_at": (jetzt + timedelta(hours=2)).timestamp()},
                                    "Woche": {"used_percent": 30.0, "resets_at": (jetzt + timedelta(days=3)).timestamp()}},
                                   jetzt=jetzt - timedelta(minutes=11))

    codex = signale.codex_lesen(tmp_path / "keine-sitzungen", jetzt=jetzt)

    assert not automatik._codex_frei(codex, 80, jetzt)


# --- Bereinigung: harte Zeitgrenze, Elternprozess endet zuerst, Fadenstart scheitert ------------------

def _pid(attrappe: Attrappe, datei: Path | None = None) -> int:
    datei = datei or attrappe.pid
    ende = time.monotonic() + 60
    while time.monotonic() < ende:
        try:
            return int(datei.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.05)
    raise AssertionError("PID-Datei der Attrappe fehlt")


def test_bereinigung_haengt_nie_auch_wenn_der_kill_nicht_wirkt(attrappe, monkeypatch):
    """Kill wirkt nicht, der Lesefaden steckt im `read()`: stdout darf nicht geschlossen werden (das blockierte
    unbegrenzt). Erwartet: fester Bereinigungsfehler innerhalb Frist + Gnadenfrist + Bereinigungsbudget."""
    attrappe.konfig(modus="taub")
    monkeypatch.setattr(codex_messen, "_baum_beenden", lambda *a: None)
    monkeypatch.setattr(codex_messen.modelle, "BEREINIGUNG_SEKUNDEN", 0.3)
    monkeypatch.setattr(codex_messen.modelle, "PIPE_SEKUNDEN", 0.3)
    gestartet = []
    echt = subprocess.Popen

    def popen(argv, **k):
        p = echt(argv, **k)
        gestartet.append(p)
        return p

    monkeypatch.setattr(codex_messen.subprocess, "Popen", popen)
    ergebnis = {}

    def lauf():
        ergebnis["k"] = _messen(frist=1.0)

    faden = threading.Thread(target=lauf, daemon=True)
    beginn = time.monotonic()
    faden.start()
    faden.join(120)

    assert not faden.is_alive(), "messen() hängt in der Bereinigung"
    assert ergebnis["k"].fehler == codex_messen.fehlertext(codex_messen.BEREINIGUNG)
    assert time.monotonic() - beginn < 1.0 + codex_messen.GNADENFRIST + 0.6 + 60      # nur "hängt nicht", großzügig
    assert not gestartet[0].stdout.closed      # Lesefaden lebt noch: nie ein close() darauf


def test_elternprozess_endet_zuerst_der_enkel_wird_trotzdem_beendet(attrappe, monkeypatch):
    """`taskkill /T` findet Kinder nur über den lebenden Elternprozess; das Jobobjekt beendet den ganzen Baum."""
    if os.name != "nt":
        pytest.skip("Jobobjekt (Windows)")
    attrappe.konfig(modus="waise")
    bereit = _FristNachBereit(monkeypatch, lambda: attrappe.enkel.exists())      # Enkel läuft, Elternprozess endet
    bereit.start()

    k = _messen()

    assert bereit.verkuerzt
    enkel = _pid(attrappe, attrappe.enkel)
    assert k.fehler == codex_messen.fehlertext(codex_messen.ZEIT)     # keine Antwort – nicht „Bereinigung“
    assert _warte_tot(enkel), "Enkelprozess des eigenen Baums lebt noch"


def test_ohne_job_beendet_taskkill_den_prozess(attrappe, monkeypatch):
    monkeypatch.setattr(codex_messen._Job, "erzeugen", classmethod(lambda cls: None))
    attrappe.konfig(modus="taub")
    bereit = _FristNachBereit(monkeypatch, lambda: attrappe.pid.exists())
    bereit.start()

    k = _messen()

    assert bereit.verkuerzt
    assert k.fehler == codex_messen.fehlertext(codex_messen.ZEIT)
    assert _warte_tot(_pid(attrappe))


def test_scheitert_der_fadenstart_wird_der_prozess_trotzdem_beendet(attrappe, monkeypatch):
    attrappe.konfig(modus="taub")

    class KaputterFaden:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError(GEHEIM)

    monkeypatch.setattr(codex_messen.threading, "Thread", KaputterFaden)
    gestartet = []
    echt = subprocess.Popen

    def popen(argv, **k):
        p = echt(argv, **k)
        gestartet.append(p)
        return p

    monkeypatch.setattr(codex_messen.subprocess, "Popen", popen)

    k = _messen()

    assert k.fehler == "Codex-Messung fehlgeschlagen (RuntimeError)" and GEHEIM not in k.fehler
    assert len(gestartet) == 1 and gestartet[0].poll() is not None      # der gestartete Prozess wurde beendet


@pytest.mark.skipif(os.name != "nt", reason="Jobobjekt gibt es nur unter Windows")
def test_scheitert_openprocess_wird_der_angehaltene_prozess_trotzdem_beendet(attrappe, monkeypatch):
    attrappe.konfig(modus="taub")
    echt_erzeugen = codex_messen._Job.erzeugen

    class OhneOpenProcess:
        def __init__(self, k):
            self._k = k

        def OpenProcess(self, *a):
            return 0

        def __getattr__(self, name):
            return getattr(self._k, name)

    def erzeugen(cls):
        job = echt_erzeugen()
        if job is not None:
            job._k = OhneOpenProcess(job._k)
        return job

    monkeypatch.setattr(codex_messen._Job, "erzeugen", classmethod(erzeugen))
    gestartet = []
    echt = subprocess.Popen

    def popen(argv, **k):
        p = echt(argv, **k)
        gestartet.append(p)
        return p

    monkeypatch.setattr(codex_messen.subprocess, "Popen", popen)

    k = _messen()

    assert k.fehler == codex_messen.fehlertext(codex_messen.START)
    assert gestartet and _warte_tot(gestartet[0].pid)              # nie fortgesetzt – trotzdem beendet
    assert any("taskkill" in str(p.args).lower() for p in gestartet[1:])   # über den Rückfall, nicht den Job


def test_ausweichdatensatz_mit_fremder_limit_kennung_gilt_nie_als_codex(attrappe):
    fremd = _ergebnis()["rateLimits"]
    fremd["limitId"] = "premium"
    ergebnis = _ergebnis(limitId="premium")
    ergebnis["rateLimitsByLimitId"] = {"codex": fremd}
    attrappe.konfig(result=ergebnis)

    k = _messen()

    assert k.fehler == codex_messen.fehlertext(codex_messen.ANTWORT)
    assert not attrappe.datei.exists()
