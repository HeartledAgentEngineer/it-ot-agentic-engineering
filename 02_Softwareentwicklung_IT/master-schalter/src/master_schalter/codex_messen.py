"""Codex-Kontingent aktiv messen (`codex.exe app-server`, JSON-RPC über stdin/stdout).

Die Sitzungsdateien von Codex (`rollout-*.jsonl`) sind nur frisch, solange Codex arbeitet. Arbeitet
stattdessen Claude, ruht Codex, und die Messung wäre veraltet – die Automatik würde nie auslösen.
`messen()` fragt Codex deshalb selbst: `initialize` → Benachrichtigung `initialized` →
`account/rateLimits/read`. Das kostet keine Tokens.

Sicherheit:

* Start als Argumentliste ohne Shell, `stdin`/`stdout` als Pipe, `stderr` verworfen, unter Windows ohne
  Konsolenfenster. Umgebung ohne API-/Token-Schlüssel, Arbeitsverzeichnis ein leerer Ordner.
* Der Prozess samt allen Nachkommen wird **immer** beendet (Erfolg, Fehler, Frist, gescheiterter Fadenstart):
  unter Windows über ein Jobobjekt (greift auch, wenn der Elternprozess zuerst endet), sonst
  `taskkill /PID <eigene PID> /T /F` bzw. die eigene Prozessgruppe – nie über einen Programmnamen.
  Die Bereinigung ist hart zeitbegrenzt (`GNADENFRIST + BEREINIGUNG_SEKUNDEN + PIPE_SEKUNDEN`) und schließt
  `stdout` nie, solange der Lesefaden lebt (das würde blockieren); sie meldet dann lieber einen festen Fehler.
* Aus der Antwort werden nur Prozent und Rücksetzzeit der beiden Fenster übernommen, zugeordnet nach
  `windowDurationMins` (300 → „5h“, 10080 → „Woche“), nie nach Position. Kontofelder (Plan, Credits,
  Namen) werden weder gespeichert noch protokolliert noch ausgegeben.
* Fehler sind feste Texte mit einer Fehlerklasse – nie Text aus der Antwort oder aus einer Ausnahme.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

from . import __version__, codex_senden, modelle, signale

FRIST_SEKUNDEN = 20.0
MAX_ZEILEN = 200                 # mehr Zeilen bis zur Antwort gelten als ungültig
MAX_ZEILE_BYTES = 1024 * 1024
LIMIT_ID = "codex"
CREATE_SUSPENDED = 0x00000004    # Prozess angehalten starten, damit er dem Job zugewiesen werden kann
GNADENFRIST = 0.5                # nach geschlossenem stdin darf der Prozess freiwillig enden, dann wird er beendet
FENSTER_DAUER = {300.0: "5h", 10080.0: "Woche"}   # windowDurationMins → Fenstername

# Feste Fehlerklassen (Teil des Fehlertexts)
PROGRAMM = "Programm nicht gefunden"
START = "Prozess nicht gestartet"
ZEIT = "Zeitüberschreitung"
BEENDET = "Prozess vorzeitig beendet"
ANTWORT = "Antwort ungültig"
FEHLERANTWORT = "Fehlerantwort von Codex"
WERTE = "Werte ungültig"
BEREINIGUNG = "Bereinigung fehlgeschlagen"
SPEICHERN = "Speichern fehlgeschlagen"


class MessFehler(Exception):
    """Interner Abbruch mit fester Fehlerklasse (kein fremder Text)."""

    def __init__(self, klasse: str):
        super().__init__(klasse)
        self.klasse = klasse


def fehlertext(klasse: str) -> str:
    return f"Codex-Messung fehlgeschlagen ({klasse})"


def _befehl(programm: str) -> list[str]:
    """Argumentliste des Prozessstarts (eigene Funktion, damit Tests ein Attrappenprogramm einsetzen können)."""
    return [programm, "app-server"]


def _nachricht(**felder: Any) -> bytes:
    return json.dumps(felder, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def _lesen(strom, ziel: "queue.Queue[bytes | None]") -> None:
    """Hilfsfaden: Zeilen von stdout einsammeln; `None` markiert das Ende. Mengenbegrenzt."""
    anzahl = 0
    try:
        while True:
            zeile = strom.readline(MAX_ZEILE_BYTES + 1)
            if not zeile:
                break
            ziel.put(zeile)
            anzahl += 1
            if anzahl > MAX_ZEILEN or len(zeile) > MAX_ZEILE_BYTES:
                break
    except (OSError, ValueError):
        pass
    finally:
        ziel.put(None)


class _Gespraech:
    """Eine Zeile je Nachricht: senden und die Antwort mit passender Kennung abwarten."""

    def __init__(self, prozess: subprocess.Popen, zeilen: "queue.Queue[bytes | None]", ende: float):
        self.prozess = prozess
        self.zeilen = zeilen
        self.ende = ende
        self.gelesen = 0

    def senden(self, daten: bytes) -> None:
        try:
            self.prozess.stdin.write(daten)
            self.prozess.stdin.flush()
        except (OSError, ValueError):
            raise MessFehler(BEENDET) from None

    def antwort(self, kennung: int) -> dict:
        while True:
            rest = self.ende - time.monotonic()
            if rest <= 0:
                raise MessFehler(ZEIT)
            try:
                zeile = self.zeilen.get(timeout=rest)
            except queue.Empty:
                raise MessFehler(ZEIT) from None
            if zeile is None:
                raise MessFehler(BEENDET)
            self.gelesen += 1
            if self.gelesen > MAX_ZEILEN or len(zeile) > MAX_ZEILE_BYTES:
                raise MessFehler(ANTWORT)
            try:
                obj = json.loads(zeile)
            except ValueError:
                raise MessFehler(ANTWORT) from None
            if not isinstance(obj, dict):
                raise MessFehler(ANTWORT)
            if "method" in obj:
                continue   # Benachrichtigung oder Serveranfrage – keine Antwort auf unsere Frage
            antwort_id = obj.get("id")
            if type(antwort_id) is not int or antwort_id != kennung:
                continue
            if "error" in obj:
                raise MessFehler(FEHLERANTWORT)
            ergebnis = obj.get("result")
            if not isinstance(ergebnis, dict):
                raise MessFehler(ANTWORT)
            return ergebnis


def _fenster_aus(ergebnis: dict) -> dict[str, dict]:
    """Beide Fenster nach Dauer zuordnen; nur Prozent (0–100) und Rücksetzzeit übernehmen."""
    grenzen = ergebnis.get("rateLimits")
    if not isinstance(grenzen, dict):
        raise MessFehler(ANTWORT)
    kennung = grenzen.get("limitId")
    if kennung is not None and kennung != LIMIT_ID:
        nach_kennung = ergebnis.get("rateLimitsByLimitId")
        grenzen = nach_kennung.get(LIMIT_ID) if isinstance(nach_kennung, dict) else None
        if not isinstance(grenzen, dict):
            raise MessFehler(ANTWORT)
        if grenzen.get("limitId") not in (None, LIMIT_ID):
            raise MessFehler(ANTWORT)   # auch der Ausweichdatensatz muss selbst zu Codex gehören (fail-closed)
    gefunden: dict[str, dict] = {}
    for schluessel in ("primary", "secondary"):
        roh = grenzen.get(schluessel)
        if roh is None:
            continue
        if not isinstance(roh, dict):
            raise MessFehler(ANTWORT)
        dauer = signale._zahl(roh.get("windowDurationMins"))
        name = FENSTER_DAUER.get(dauer) if dauer is not None else None
        if name is None:
            continue   # unbekannte Dauer: ignorieren
        prozent = signale._prozent(roh.get("usedPercent"))
        if prozent is None:
            raise MessFehler(WERTE)
        reset_roh = roh.get("resetsAt")
        if reset_roh is None:
            if prozent != 0:
                raise MessFehler(WERTE)   # Verbrauch ohne Rücksetzzeit bleibt ungültig
            reset = None
        else:
            reset = signale._zahl(reset_roh)
            if reset is None or signale._epoche(reset) is None:
                raise MessFehler(WERTE)
        if name in gefunden:
            raise MessFehler(WERTE)   # zwei Fenster gleicher Dauer: nicht eindeutig
        gefunden[name] = {"used_percent": prozent, "resets_at": reset}
    if len(gefunden) != len(signale.CODEX_FENSTER):
        raise MessFehler(ANTWORT)
    return gefunden


class _Job:
    """Windows-Jobobjekt: beendet den ganzen Prozessbaum – auch wenn der Elternprozess schon fort ist.

    `taskkill /PID <Eltern> /T` findet Kinder nur über einen noch lebenden Elternprozess. Endet der
    Elternprozess zuerst (z. B. ein Startprogramm, das den eigentlichen Prozess erzeugt hat), bleiben
    die Kinder samt offener Pipe zurück. Im Jobobjekt gehören alle Nachkommen dazu; `KILL_ON_JOB_CLOSE`
    beendet sie außerdem, falls die Leiste selbst vorher stirbt. Der Prozess wird dafür angehalten
    gestartet, dem Job zugewiesen und erst dann fortgesetzt – so entkommt ihm kein Kind.
    Ohne Windows oder bei jedem Fehler gibt es keinen Job (`erzeugen()` liefert `None`); dann gilt der
    Rückfall `taskkill` bzw. die Prozessgruppe.
    """

    ZUGRIFF = 0x0001 | 0x0100 | 0x0800   # PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_SUSPEND_RESUME

    def __init__(self, kernel32, handle) -> None:
        self._k = kernel32
        self._handle = handle

    @classmethod
    def erzeugen(cls) -> "_Job | None":
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.CreateJobObjectW.restype = wintypes.HANDLE
            k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            k.SetInformationJobObject.restype = wintypes.BOOL
            k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            k.AssignProcessToJobObject.restype = wintypes.BOOL
            k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            k.TerminateJobObject.restype = wintypes.BOOL
            k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            k.OpenProcess.restype = wintypes.HANDLE
            k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            k.CloseHandle.restype = wintypes.BOOL
            k.CloseHandle.argtypes = [wintypes.HANDLE]

            class Basis(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class EAZ(ctypes.Structure):
                _fields_ = [("ReadOperationCount", ctypes.c_uint64), ("WriteOperationCount", ctypes.c_uint64),
                            ("OtherOperationCount", ctypes.c_uint64), ("ReadTransferCount", ctypes.c_uint64),
                            ("WriteTransferCount", ctypes.c_uint64), ("OtherTransferCount", ctypes.c_uint64)]

            class Erweitert(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", Basis), ("IoInfo", EAZ),
                            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            handle = k.CreateJobObjectW(None, None)
            if not handle:
                return None
            info = Erweitert()
            info.BasicLimitInformation.LimitFlags = 0x2000   # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
                k.CloseHandle(handle)
                return None
            return cls(k, handle)
        except Exception:  # noqa: BLE001 - ohne Job gilt der Rückfall
            return None

    def zuweisen_und_fortsetzen(self, pid: int) -> bool:
        """Den angehalten gestarteten Prozess dem Job zuweisen und fortsetzen. False: nicht fortgesetzt."""
        import ctypes
        from ctypes import wintypes

        prozess = self._k.OpenProcess(self.ZUGRIFF, False, pid)
        if not prozess:
            self.schliessen()          # nie zugewiesen: der Job beendet ihn nicht – Rückfall `taskkill /T /F`
            return False
        try:
            if not self._k.AssignProcessToJobObject(self._handle, prozess):
                self.schliessen()      # kein Job → Rückfall; der Prozess wird trotzdem fortgesetzt
            ntdll = ctypes.WinDLL("ntdll")
            ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
            ntdll.NtResumeProcess.restype = ctypes.c_long
            return ntdll.NtResumeProcess(prozess) >= 0
        finally:
            self._k.CloseHandle(prozess)

    @property
    def aktiv(self) -> bool:
        return self._handle is not None

    def beenden(self) -> None:
        if self._handle is not None:
            self._k.TerminateJobObject(self._handle, 1)

    def schliessen(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            self._k.CloseHandle(handle)


def _taskkill(pid: int, frist: float) -> None:
    try:
        subprocess.run(modelle._taskkill_argv(pid), capture_output=True, timeout=max(0.1, frist))
    except (OSError, subprocess.TimeoutExpired):
        pass  # ob der Baum endete, prüft die Nachkontrolle in `_beenden`


def _baum_beenden(prozess: subprocess.Popen, job: "_Job | None", frist: float) -> None:
    """Den ganzen Prozessbaum beenden – **immer**, auch wenn der direkte Prozess schon endete.

    Mit Job (Windows) werden alle Nachkommen beendet, unabhängig vom Elternprozess. Ohne Job: unter
    Windows `taskkill /PID <eigene PID> /T /F` (greift nur, solange der Elternprozess lebt), sonst die eigene
    Prozessgruppe (`start_new_session`, Gruppenkennung = PID; gilt auch nach dem Ende des Gruppenführers).
    """
    if job is not None and job.aktiv:
        job.beenden()
        return
    if os.name == "nt":
        if prozess.poll() is None:
            _taskkill(prozess.pid, frist)
        return
    try:
        os.killpg(prozess.pid, 9)
    except OSError:
        pass


def _freiwilliges_ende_abwarten(prozess: subprocess.Popen) -> None:
    """stdin schließen und kurz warten: ein Prozess, der bei EOF endet, braucht keinen Kill-Aufruf."""
    try:
        prozess.stdin.close()
    except (OSError, ValueError, AttributeError):
        pass
    ende = time.monotonic() + GNADENFRIST
    while prozess.poll() is None and time.monotonic() < ende:
        time.sleep(modelle.TAKT_SEKUNDEN)


def _beenden(prozess: subprocess.Popen, faden: "threading.Thread | None", job: "_Job | None", grenze: float) -> None:
    """Bereinigung mit harter Zeitgrenze: Baum beenden, Prozessende abwarten, Lesefaden einsammeln.

    Wartezeiten insgesamt höchstens `GNADENFRIST + BEREINIGUNG_SEKUNDEN + PIPE_SEKUNDEN` (und nie über
    `grenze`, einer monotonen Zeit). Der Lesefaden hält die Lesesperre von `stdout`; ein `close()` darauf
    würde bis zum Ende des Lesens blockieren. Solange der Faden lebt, wird `stdout` deshalb **nie** geschlossen:
    lieber ein Daemon-Faden samt Handle liegen lassen und einen festen Fehler melden als hängen.
    """
    try:
        _freiwilliges_ende_abwarten(prozess)
        kill_ende = min(time.monotonic() + modelle.BEREINIGUNG_SEKUNDEN, grenze)
        try:
            _baum_beenden(prozess, job, kill_ende - time.monotonic())
        except Exception:  # noqa: BLE001 - die Nachkontrolle entscheidet
            pass
        while prozess.poll() is None and time.monotonic() < kill_ende:
            time.sleep(modelle.TAKT_SEKUNDEN)
        lebt = prozess.poll() is None
        faden_lebt = False
        if faden is not None:
            faden.join(max(0.0, min(modelle.PIPE_SEKUNDEN, grenze - time.monotonic())))
            faden_lebt = faden.is_alive()
        if not faden_lebt:
            try:
                prozess.stdout.close()   # kein Leser mehr → nichts, was die Sperre hält
            except (OSError, ValueError, AttributeError):
                pass
        if lebt or faden_lebt:
            raise MessFehler(BEREINIGUNG)
    finally:
        if job is not None:
            job.schliessen()   # KILL_ON_JOB_CLOSE: letzte Sicherung gegen übrig gebliebene Nachkommen


def _abfragen(programm: str, frist: float) -> dict[str, dict]:
    """Prozess starten, Gespräch führen, Prozess immer beenden. Gibt die geprüften Fenster zurück."""
    beginn = time.monotonic()
    ende = beginn + frist
    job = _Job.erzeugen()
    try:
        umgebung = modelle._umgebung()
        arbeitsordner = modelle._leerer_ordner()
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | (CREATE_SUSPENDED if job is not None else 0)
        prozess = subprocess.Popen(
            _befehl(programm),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(arbeitsordner),
            env=umgebung,
            close_fds=True,
            start_new_session=(os.name != "nt"),
            creationflags=flags,
        )
    except (FileNotFoundError, PermissionError, NotADirectoryError):
        if job is not None:
            job.schliessen()
        raise MessFehler(PROGRAMM) from None
    except OSError:
        if job is not None:
            job.schliessen()
        raise MessFehler(START) from None
    except BaseException:
        if job is not None:
            job.schliessen()
        raise

    faden = None
    try:
        if job is not None and not job.zuweisen_und_fortsetzen(prozess.pid):
            raise MessFehler(START)
        zeilen: "queue.Queue[bytes | None]" = queue.Queue()
        lesefaden = threading.Thread(target=_lesen, args=(prozess.stdout, zeilen), daemon=True)
        lesefaden.start()
        faden = lesefaden     # erst nach gelungenem Start: ein nie gestarteter Faden wird nicht eingesammelt
        gespraech = _Gespraech(prozess, zeilen, ende)
        gespraech.senden(_nachricht(id=1, method="initialize",
                                    params={"clientInfo": {"name": "master-schalter", "version": __version__}}))
        gespraech.antwort(1)
        gespraech.senden(_nachricht(method="initialized"))
        gespraech.senden(_nachricht(id=2, method="account/rateLimits/read"))
        return _fenster_aus(gespraech.antwort(2))
    finally:
        # Immer – auch wenn der Fadenstart scheitert. Scheitert die Bereinigung, ist das der gravierendere Fehler.
        _beenden(prozess, faden, job, ende + GNADENFRIST + modelle.bereinigungsvorbehalt())


def messen(programm: str | None = None, frist: float = FRIST_SEKUNDEN,
           jetzt: datetime | None = None) -> signale.Kontingent:
    """Codex aktiv abfragen und das Ergebnis atomar nach `codex-kontingent.json` schreiben.

    Gibt das gemessene `Kontingent` zurück; jeder Fehler wird zu `Kontingent("Codex", fehler=<fester Text>)`
    – die Funktion wirft nie. Bei einem Fehler bleibt eine vorhandene Messdatei unverändert.

    Der Messfehler-Status in `messfehler.json` wird hier nachgeführt (Quelle „codex“): Fehler ⇒ Eintrag mit
    Fehlerklasse und festem Text, Erfolg ⇒ Eintrag weg. Das gilt für jeden Aufrufer; Schreibfehler der
    Statusdatei werden verschluckt.
    """
    kontingent, klasse = _messen(programm, frist, jetzt)
    if kontingent.fehler is not None:
        signale.messfehler_setzen("codex", klasse or "unbekannt", kontingent.fehler, jetzt=jetzt)
    else:
        signale.messfehler_loeschen("codex")
    return kontingent


def _messen(programm: str | None, frist: float, jetzt: datetime | None) -> tuple[signale.Kontingent, str | None]:
    """Die eigentliche Messung: (Kontingent, Fehlerklasse oder None). Wirft nie."""
    try:
        programm = programm or codex_senden.programm()
        if not programm:
            raise MessFehler(PROGRAMM)
        fenster = _abfragen(programm, frist)
        stand = jetzt or datetime.now(timezone.utc)
        try:
            gespeichert = signale.codex_schreiben(fenster, jetzt=stand)
        except Exception:  # noqa: BLE001 - nur die feste Fehlerklasse weitergeben
            raise MessFehler(SPEICHERN) from None
        if not gespeichert:
            raise MessFehler(WERTE)
        messung = signale.codex_messung_lesen(jetzt=stand)
        if messung is None:
            raise MessFehler(SPEICHERN)
        return messung, None
    except MessFehler as fehler:
        return signale.Kontingent("Codex", fehler=fehlertext(fehler.klasse)), fehler.klasse
    except Exception as fehler:  # noqa: BLE001 - nie fremder Text, nur der Klassenname
        klasse = type(fehler).__name__
        return signale.Kontingent("Codex", fehler=fehlertext(klasse)), klasse
