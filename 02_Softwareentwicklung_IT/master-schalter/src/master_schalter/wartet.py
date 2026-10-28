"""„Wartet worauf“ je Thema: kurze technische Meldung, die der Master-Status anzeigt (`masterwechsel warte`).

Layout: `<datenordner>/wartet/<thema>.json` mit `{"text": <eine Zeile, höchstens 120 Zeichen>, "zeit": <ISO UTC>}`
und optional `"pid"` (Prozesskennung des Melders; schreibt `pruefkreis`, nicht `masterwechsel warte`).
Das Thema wird mit `paare.thema_pruefen` geprüft; der Dateiname entsteht nur daraus. Geschrieben wird atomar.
Eine Meldung mit `pid` gilt als **verwaist** (`verwaist`), wenn der Prozess beendet ist (`lebt`) oder erst nach
`zeit` gestartet wurde (pid wiederverwendet, nur Windows); das ist nur eine Anzeige – gelöscht wird nie automatisch.
Der Text soll eine technische Kurzangabe sein („Freigabe Vibe-Modus“, „Codex-Prüfung R2“) – keine Inhalte,
Namen oder Pfade. Erzwingen kann der Code das nicht; er begrenzt Form und Länge.

`alle_lesen` überspringt fehlende, zu große oder kaputte Dateien, statt zu raten.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import paare
from .signale import _atomar_schreiben, daten_ordner

MAX_ZEICHEN = 120
MAX_BYTES = 1024
MAX_PID = 2**31 - 1
START_TOLERANZ = timedelta(seconds=5)   # Prozessstart darf so weit nach `zeit` liegen (Uhr-/FILETIME-Rundung)
_LEERRAUM = re.compile(r"\s+")
_WINDOWS = sys.platform == "win32"
# Windows-Konstanten (winerror.h / winnt.h)
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87
_STILL_ACTIVE = 259


class WartetFehler(Exception):
    """Thema oder Text ist nicht zulässig."""


@dataclass(frozen=True)
class Meldung:
    thema: str
    text: str
    zeit: datetime
    pid: int | None = None   # Prozess des Melders (nur `pruefkreis`); alte Dateien ohne pid bleiben gültig


def ordner() -> Path:
    return daten_ordner() / "wartet"


def datei(thema: str) -> Path:
    try:
        return ordner() / f"{paare.thema_pruefen(thema)}.json"
    except paare.PaarFehler as fehler:
        raise WartetFehler(str(fehler)) from fehler


def text_bereinigen(text: str) -> str:
    """Eine Zeile: Steuerzeichen und Zeilenumbrüche werden zu Leerzeichen, höchstens `MAX_ZEICHEN` Zeichen."""
    if not isinstance(text, str):
        raise WartetFehler("Text fehlt")
    zeile = "".join(" " if not z.isprintable() else z for z in text)
    zeile = _LEERRAUM.sub(" ", zeile).strip()
    if not zeile:
        raise WartetFehler("Text ist leer")
    return zeile if len(zeile) <= MAX_ZEICHEN else zeile[: MAX_ZEICHEN - 1].rstrip() + "…"


def setzen(thema: str, text: str, jetzt: datetime | None = None) -> Meldung:
    pfad = datei(thema)
    meldung = Meldung(thema, text_bereinigen(text), jetzt or datetime.now(timezone.utc))
    _atomar_schreiben(pfad, json.dumps({"text": meldung.text, "zeit": meldung.zeit.isoformat()},
                                       ensure_ascii=False))
    return meldung


def loeschen(thema: str) -> bool:
    """Meldung des Themas entfernen; `False`, wenn keine da war (idempotent)."""
    try:
        datei(thema).unlink()
    except FileNotFoundError:
        return False
    return True


def _lesen(pfad: Path) -> Meldung | None:
    try:
        if pfad.stat().st_size > MAX_BYTES:
            return None
        roh = json.loads(pfad.read_text(encoding="utf-8"))
        paare.thema_pruefen(pfad.stem)
    except (OSError, ValueError, paare.PaarFehler):
        return None
    if not isinstance(roh, dict) or not isinstance(roh.get("text"), str) or not isinstance(roh.get("zeit"), str):
        return None
    try:
        zeit = datetime.fromisoformat(roh["zeit"])
        text = text_bereinigen(roh["text"])
    except (ValueError, WartetFehler):
        return None
    return Meldung(pfad.stem, text, zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc), _pid(roh.get("pid")))


def _pid(wert: object) -> int | None:
    """Eine brauchbare Prozesskennung (ganze Zahl, 1 bis 2^31-1) oder `None`; Text, negativ, Bool ⇒ keine pid."""
    if isinstance(wert, bool) or not isinstance(wert, int) or not 0 < wert <= MAX_PID:
        return None
    return wert


# --- verwaiste Meldungen: lebt der Prozess des Melders noch? ---------------------

class _WinApi:
    """Die wenigen kernel32-Aufrufe (ctypes); eigene Klasse, damit Tests die Antworten fälschen können."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes
        self._ctypes = ctypes
        self._wintypes = wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL
        k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        k.GetProcessTimes.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        self._k = k

    def oeffnen(self, pid: int):
        """`(Handle, 0)` bei Erfolg, sonst `(None, Fehlercode)`."""
        handle = self._k.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None, self._ctypes.get_last_error()
        return handle, 0

    def exitcode(self, handle) -> int | None:
        code = self._wintypes.DWORD()
        if not self._k.GetExitCodeProcess(handle, self._ctypes.byref(code)):
            return None
        return code.value

    def startzeit(self, handle) -> datetime | None:
        erzeugt, ende, kern, nutzer = (self._wintypes.FILETIME() for _ in range(4))
        ref = self._ctypes.byref
        if not self._k.GetProcessTimes(handle, ref(erzeugt), ref(ende), ref(kern), ref(nutzer)):
            return None
        hundert_ns = (erzeugt.dwHighDateTime << 32) | erzeugt.dwLowDateTime
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=hundert_ns // 10)

    def schliessen(self, handle) -> None:
        self._k.CloseHandle(handle)


_api_cache: _WinApi | None = None


def _api() -> _WinApi:
    global _api_cache
    if _api_cache is None:
        _api_cache = _WinApi()
    return _api_cache


def lebt(pid: int) -> bool | None:
    """Läuft der Prozess? `True` = läuft, `False` = existiert nicht (mehr), `None` = unbekannt.

    Windows: `OpenProcess` scheitert mit `ERROR_INVALID_PARAMETER` (87) ⇒ `False`; mit `ERROR_ACCESS_DENIED` (5) oder
    einem anderen Fehler ⇒ `None`. Mit Handle entscheidet `GetExitCodeProcess`: `STILL_ACTIVE` (259) ⇒ `True`, sonst
    `False` (beendet, aber ein anderer Prozess hält noch ein Handle). Sonst `os.kill(pid, 0)`: kein Fehler ⇒ `True`,
    `ProcessLookupError` ⇒ `False`, `PermissionError` und alles andere ⇒ `None`. Wirft nie.
    """
    if isinstance(pid, bool) or not isinstance(pid, int) or not 0 < pid <= MAX_PID:
        return None
    try:
        if _WINDOWS:
            api = _api()
            handle, fehler = api.oeffnen(pid)
            if handle is None:
                return False if fehler == _ERROR_INVALID_PARAMETER else None
            try:
                code = api.exitcode(handle)
            finally:
                api.schliessen(handle)
            if code is None:
                return None
            return code == _STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:  # noqa: BLE001 - PermissionError, OverflowError und alles Unvorhergesehene: unbekannt
        return None


def startzeit(pid: int) -> datetime | None:
    """Startzeit des Prozesses (UTC) oder `None`, wenn unbekannt – nur unter Windows (`GetProcessTimes`). Wirft nie."""
    if not _WINDOWS or isinstance(pid, bool) or not isinstance(pid, int) or not 0 < pid <= MAX_PID:
        return None
    try:
        api = _api()
        handle, _fehler = api.oeffnen(pid)
        if handle is None:
            return None
        try:
            return api.startzeit(handle)
        finally:
            api.schliessen(handle)
    except Exception:  # noqa: BLE001
        return None


def verwaist(meldung: Meldung) -> bool:
    """Gehört die Meldung zu einem beendeten Prozess? Nur mit pid; unbekannter Zustand ⇒ `False` (normal anzeigen).

    Verwaist ist sie, wenn `lebt` `False` sagt, oder wenn der Prozess **nach** der Meldung gestartet wurde
    (Prozesskennung wiederverwendet). Unbekannte Startzeit zählt nur als „lebt“. Löscht nichts.
    """
    if meldung.pid is None:
        return False
    leben = lebt(meldung.pid)
    if leben is None:
        return False
    if leben is False:
        return True
    start = startzeit(meldung.pid)
    return start is not None and start > meldung.zeit + START_TOLERANZ


def alle_lesen() -> list[Meldung]:
    """Alle gültigen Meldungen, älteste zuerst; ungültige Dateien bleiben unberührt und ungezeigt."""
    try:
        pfade = sorted(ordner().glob("*.json"))
    except OSError:
        return []
    meldungen = [m for m in (_lesen(p) for p in pfade) if m is not None]
    return sorted(meldungen, key=lambda m: m.zeit)
