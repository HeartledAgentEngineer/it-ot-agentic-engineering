"""Kontingente (Nutzungsgrenzen) von Claude Code und Codex lesen.

Codex wird aus lokalen Sitzungsdateien gelesen. `claude_messen` fragt den
Claude-Usage-Endpunkt ab und übergibt nur geprüfte Prozentwerte und
Rücksetzzeiten an `claude_schreiben`; `claude_lesen` bleibt Datei-Leser.

* Codex schreibt seine Kontingente in die eigenen Sitzungsdateien
  (`~/.codex/sessions/**/rollout-*.jsonl`, Ereignis `token_count`). Daraus
  werden ausschließlich Zahlen übernommen (Prozent, Rücksetzzeit, Zeitstempel);
  der Rest jeder Zeile wird im Speicher verworfen.
* `codex_messen` fragt Codex aktiv ab (ohne Tokenverbrauch) und übergibt nur geprüfte Prozentwerte und
  Rücksetzzeiten an `codex_schreiben` (`codex-kontingent.json`); `codex_lesen` nimmt den neueren Stand
  aus Sitzungsdateien und aktiver Messung.
* `claude_schreiben` legt nur Prozent und Rücksetzzeiten in
  `kontingent-claude.json` ab; `claude_lesen` liest und prüft sie.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CODEX_LIMIT_ID = "codex"
ANFANG_BYTES = 4096  # Dateianfang als Fingerabdruck: erkennt neu geschriebene Sitzungsdateien
CLAUDE_FENSTER = (("five_hour", "5h"), ("seven_day", "Woche"))
CODEX_FENSTER = ("5h", "Woche")
MESSUNG_ZUKUNFT = timedelta(minutes=1)  # Messzeit weiter in der Zukunft gilt nicht als „neuer“


@dataclass(frozen=True)
class Fenster:
    name: str                      # "5h" oder "Woche"
    prozent: float | None          # verbraucht, 0–100; None = unbekannt
    reset: datetime | None         # wann das Fenster zurückgesetzt wird
    zurueckgesetzt: bool = False   # Rücksetzzeit liegt in der Vergangenheit


@dataclass(frozen=True)
class Kontingent:
    master: str                    # "Claude" oder "Codex"
    fenster: tuple[Fenster, ...] = ()
    stand: datetime | None = None  # wann die Werte erhoben wurden
    fehler: str | None = None

    def fenster_nach_name(self, name: str) -> Fenster | None:
        return next((f for f in self.fenster if f.name == name), None)


# --- Hilfen ------------------------------------------------------------------

def _zahl(wert: Any) -> float | None:
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    try:
        zahl = float(wert)
    except (OverflowError, ValueError):
        return None
    return zahl if math.isfinite(zahl) else None


def _prozent(wert: Any) -> float | None:
    """Claude-Prozent zwischen 0 und 100; Zeitstempel verwenden weiter `_zahl`."""
    zahl = _zahl(wert)
    return zahl if zahl is not None and 0 <= zahl <= 100 else None


def _epoche(wert: Any) -> datetime | None:
    zahl = _zahl(wert)
    if zahl is None:
        return None
    try:
        return datetime.fromtimestamp(zahl, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _iso(wert: Any) -> datetime | None:
    if not isinstance(wert, str):
        return None
    try:
        zeit = datetime.fromisoformat(wert.replace("Z", "+00:00"))
    except ValueError:
        return None
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _fenster(name: str, roh: Any, prozent_feld: str, jetzt: datetime) -> Fenster:
    if not isinstance(roh, dict):
        return Fenster(name, None, None)
    # Gültig ist nur 0–100: negativ, über 100 oder nicht endlich heißt „unbekannt" – nie angenommene Freiheit.
    prozent = _prozent(roh.get(prozent_feld))
    reset = _epoche(roh.get("resets_at"))
    if reset is not None and reset <= jetzt:
        return Fenster(name, 0.0, reset, zurueckgesetzt=True)
    return Fenster(name, prozent, reset)


def daten_ordner() -> Path:
    """Datenordner festlegen.

    Liegt standardmäßig unter `%USERPROFILE%/.master-schalter/`. Bewusst **nicht** unter
    `%LOCALAPPDATA%`: Claude- und Codex-App sind MSIX-Pakete, ihre Kindprozesse werden von
    Windows in `AppData/Local/Packages/<App>/LocalCache/…` umgeleitet. Dort läse jeder
    Starter einen anderen Zustand (Autostart, Codex-Start, Claude-CLI). `MASTER_SCHALTER_DATEN`
    hat weiterhin Vorrang (Tests, Umlenkung).
    """
    eigen = os.environ.get("MASTER_SCHALTER_DATEN")
    if eigen:
        return Path(eigen)
    return Path.home() / ".master-schalter"


# --- Codex -------------------------------------------------------------------

def codex_ordner() -> Path:
    eigen = os.environ.get("MASTER_SCHALTER_CODEX_SESSIONS")
    return Path(eigen) if eigen else Path.home() / ".codex" / "sessions"


def _codex_eintrag(zeile: str) -> tuple[datetime, dict] | None:
    if '"rate_limits"' not in zeile:
        return None
    try:
        obj = json.loads(zeile)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    nutzlast = obj.get("payload")
    if not isinstance(nutzlast, dict) or nutzlast.get("type") != "token_count":
        return None
    grenzen = nutzlast.get("rate_limits")
    if not isinstance(grenzen, dict) or grenzen.get("limit_id") != CODEX_LIMIT_ID:
        return None
    if not isinstance(grenzen.get("primary"), dict):
        return None  # z. B. leere Einträge ohne Werte
    zeit = _iso(obj.get("timestamp"))
    if zeit is None:
        return None
    return zeit, {name: _nur_zahlen(grenzen.get(name)) for name in ("primary", "secondary")}


def _nur_zahlen(roh: Any) -> dict | None:
    """Aus einem Codex-Fenster nur Prozent (0–100) und Rücksetzzeit behalten, alles andere verwerfen."""
    if not isinstance(roh, dict):
        return None
    return {"used_percent": _prozent(roh.get("used_percent")), "resets_at": _zahl(roh.get("resets_at"))}


class CodexLeser:
    """Merkt sich je Sitzungsdatei Leseposition und neuesten Eintrag.

    Sitzungsdateien wachsen nur am Ende und können zweistellige MB groß sein. Beim
    ersten Mal wird eine Datei ganz gelesen, danach nur noch der angehängte Teil.
    Eine unvollständige letzte Zeile bleibt liegen, bis sie mit Zeilenumbruch endet.
    """

    def __init__(self) -> None:
        self.gelesen: dict[Path, int] = {}
        self._bester: dict[Path, tuple[datetime, dict]] = {}
        self._anfang: dict[Path, bytes] = {}

    def _anfang_unveraendert(self, datei: Path) -> bool:
        gemerkt = self._anfang.get(datei, b"")
        try:
            with datei.open("rb") as f:
                return f.read(len(gemerkt)) == gemerkt
        except OSError:
            return False

    def bester_eintrag(self, datei: Path) -> tuple[datetime, dict] | None:
        try:
            groesse = datei.stat().st_size
        except OSError:
            return self._bester.get(datei)
        start = self.gelesen.get(datei, 0)
        # Gekürzt oder neu geschrieben (auch wenn sie dabei wieder länger wurde): von vorn.
        if start and (groesse < start or not self._anfang_unveraendert(datei)):
            start = 0
            self.gelesen[datei] = 0
            self._bester.pop(datei, None)
            self._anfang.pop(datei, None)
        if groesse > start:
            try:
                with datei.open("rb") as f:
                    f.seek(start)
                    neu = f.read(groesse - start)
            except OSError:
                return self._bester.get(datei)
            if start == 0:
                self._anfang[datei] = neu[:ANFANG_BYTES]
            ende = neu.rfind(b"\n")
            if ende >= 0:
                bester = self._bester.get(datei)
                for zeile in neu[:ende].split(b"\n"):
                    if b'"rate_limits"' not in zeile:
                        continue
                    eintrag = _codex_eintrag(zeile.decode("utf-8", errors="replace"))
                    if eintrag and (bester is None or eintrag[0] >= bester[0]):
                        bester = eintrag
                if bester:
                    self._bester[datei] = bester
                self.gelesen[datei] = start + ende + 1
        return self._bester.get(datei)


_STANDARD_LESER = CodexLeser()


def _codex_sitzungen(ordner: Path | None, jetzt: datetime, leser: CodexLeser | None) -> Kontingent:
    """Neuester gültiger Codex-Eintrag über alle Sitzungsdateien.

    Die Dateien werden nach Änderungszeit absteigend gelesen. Ein Eintrag wird geschrieben,
    bevor die Datei geändert ist; seine Zeit liegt also nie nach der Änderungszeit der Datei.
    Sobald der beste Eintrag mindestens so neu ist wie die Änderungszeit der nächsten Datei,
    kann keine ältere Datei mehr einen neueren Eintrag enthalten — dort endet die Suche.
    """
    ordner = ordner or codex_ordner()
    leser = leser or _STANDARD_LESER
    if not ordner.is_dir():
        return Kontingent("Codex", fehler="keine Daten")
    try:
        dateien = sorted(((p.stat().st_mtime, p) for p in ordner.rglob("rollout-*.jsonl")), reverse=True)
    except OSError:
        return Kontingent("Codex", fehler="keine Daten")
    bester: tuple[datetime, dict] | None = None
    for mtime, datei in dateien:
        if bester and bester[0] >= datetime.fromtimestamp(mtime, timezone.utc):
            break
        eintrag = leser.bester_eintrag(datei)
        if eintrag and (bester is None or eintrag[0] > bester[0]):
            bester = eintrag
    if bester is None:
        return Kontingent("Codex", fehler="keine Daten")
    zeit, grenzen = bester
    return Kontingent("Codex", (
        _fenster("5h", grenzen["primary"], "used_percent", jetzt),
        _fenster("Woche", grenzen["secondary"], "used_percent", jetzt),
    ), stand=zeit)


def codex_datei() -> Path:
    return daten_ordner() / "codex-kontingent.json"


def _codex_filtern(fenster: Any) -> dict:
    """Nur Prozent (0–100) und Rücksetzzeit beider Fenster übernehmen; sonst leer (= ungültig)."""
    if not isinstance(fenster, dict):
        return {}
    sauber: dict = {}
    for name in CODEX_FENSTER:
        roh = fenster.get(name)
        if not isinstance(roh, dict):
            return {}
        prozent = _prozent(roh.get("used_percent"))
        if prozent is None:
            return {}
        reset_roh = roh.get("resets_at")
        if reset_roh is None:
            # Kein offenes Fenster: ohne Rücksetzzeit gilt nur 0 %; mit Verbrauch bleibt es ungültig.
            if prozent != 0:
                return {}
            sauber[name] = {"used_percent": 0.0, "resets_at": None}
            continue
        reset = _zahl(reset_roh)
        if reset is None or _epoche(reset) is None:
            return {}
        sauber[name] = {"used_percent": prozent, "resets_at": reset}
    return sauber


def codex_schreiben(fenster: Any, datei: Path | None = None, jetzt: datetime | None = None) -> bool:
    """Speichert die aktiv gemessenen Codex-Kontingente; ohne gültige Werte bleibt die alte Datei stehen."""
    sauber = _codex_filtern(fenster)
    if len(sauber) != len(CODEX_FENSTER):
        return False
    jetzt = jetzt or datetime.now(timezone.utc)
    inhalt = json.dumps({"version": 1, "gelesen_um": jetzt.isoformat(), "fenster": sauber}, ensure_ascii=False)
    _atomar_schreiben(datei or codex_datei(), inhalt)
    return True


def codex_messung_lesen(datei: Path | None = None, jetzt: datetime | None = None) -> Kontingent | None:
    """Aktive Codex-Messung aus der Messdatei; `None`, wenn sie fehlt oder nicht gültig ist."""
    datei = datei or codex_datei()
    jetzt = jetzt or datetime.now(timezone.utc)
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(roh, dict):
        return None
    stand = _iso(roh.get("gelesen_um"))
    sauber = _codex_filtern(roh.get("fenster"))
    if stand is None or len(sauber) != len(CODEX_FENSTER):
        return None
    return Kontingent("Codex", tuple(_fenster(name, sauber[name], "used_percent", jetzt)
                                     for name in CODEX_FENSTER), stand=stand)


def codex_lesen(ordner: Path | None = None, jetzt: datetime | None = None,
                leser: CodexLeser | None = None, messdatei: Path | None = None) -> Kontingent:
    """Der neuere Codex-Stand aus Sitzungsdateien und aktiver Messung.

    Die Sitzungsdateien sind nur frisch, solange Codex arbeitet; die aktive Messung (`codex_messen`)
    deckt auch die Ruhezeiten ab. Ohne gültige Messdatei bleibt es beim Stand aus den Sitzungsdateien.
    Eine Messung mit Zeit deutlich in der Zukunft wird nie bevorzugt.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    sitzungen = _codex_sitzungen(ordner, jetzt, leser)
    messung = codex_messung_lesen(messdatei, jetzt)
    if messung is None or messung.stand is None or messung.stand > jetzt + MESSUNG_ZUKUNFT:
        return sitzungen
    if sitzungen.fehler or sitzungen.stand is None or messung.stand > sitzungen.stand:
        return messung
    return sitzungen


# --- Claude ------------------------------------------------------------------

def claude_datei() -> Path:
    return daten_ordner() / "kontingent-claude.json"


def _claude_filtern(rate_limits: Any) -> dict:
    """Nur Prozent und Rücksetzzeit der beiden Abo-Fenster übernehmen."""
    if not isinstance(rate_limits, dict):
        return {}
    sauber: dict = {}
    for schluessel, _ in CLAUDE_FENSTER:
        roh = rate_limits.get(schluessel)
        if not isinstance(roh, dict):
            return {}
        prozent = _prozent(roh.get("used_percentage"))
        reset_roh = roh.get("resets_at")
        if prozent is None:
            return {}
        if reset_roh is None:
            # Kein offenes Fenster: null nur bei 0 % (live 16.10.2026); mit Verbrauch bleibt es ungültig.
            if prozent != 0:
                return {}
            sauber[schluessel] = {"used_percentage": 0.0, "resets_at": None}
            continue
        reset = _zahl(reset_roh)
        if reset is None or _epoche(reset) is None:
            return {}
        sauber[schluessel] = {"used_percentage": prozent, "resets_at": reset}
    return sauber


def _atomar_schreiben(datei: Path, inhalt: str) -> None:
    datei.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=datei.name + ".", suffix=".tmp", dir=datei.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(inhalt)
        os.replace(tmp, datei)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def claude_schreiben(rate_limits: Any, datei: Path | None = None, jetzt: datetime | None = None) -> bool:
    """Speichert die Claude-Kontingente; ohne gültige Werte bleibt die alte Datei stehen."""
    sauber = _claude_filtern(rate_limits)
    if len(sauber) != len(CLAUDE_FENSTER):
        return False
    jetzt = jetzt or datetime.now(timezone.utc)
    inhalt = json.dumps({"gelesen_um": jetzt.isoformat(), "rate_limits": sauber}, ensure_ascii=False)
    _atomar_schreiben(datei or claude_datei(), inhalt)
    return True


def claude_lesen(datei: Path | None = None, jetzt: datetime | None = None) -> Kontingent:
    datei = datei or claude_datei()
    jetzt = jetzt or datetime.now(timezone.utc)
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Kontingent("Claude", fehler="keine Daten")
    except (OSError, ValueError):
        return Kontingent("Claude", fehler="keine Daten")
    if not isinstance(roh, dict) or not isinstance(roh.get("rate_limits"), dict):
        return Kontingent("Claude", fehler="keine Daten")
    grenzen = roh["rate_limits"]
    fenster = []
    for schluessel, name in CLAUDE_FENSTER:
        daten = grenzen.get(schluessel)
        if not isinstance(daten, dict):
            return Kontingent("Claude", fehler="keine Daten")
        prozent = _prozent(daten.get("used_percentage"))
        if prozent is None:
            return Kontingent("Claude", fehler="keine Daten")
        reset_roh = daten.get("resets_at")
        if reset_roh is None:
            if prozent != 0:
                return Kontingent("Claude", fehler="keine Daten")
            fenster.append(Fenster(name, 0.0, None))
            continue
        reset = _epoche(reset_roh)
        if reset is None:
            return Kontingent("Claude", fehler="keine Daten")
        if reset <= jetzt:
            fenster.append(Fenster(name, 0.0, reset, zurueckgesetzt=True))
        else:
            fenster.append(Fenster(name, prozent, reset))
    return Kontingent("Claude", tuple(
        fenster
    ), stand=_iso(roh.get("gelesen_um")))


def alle_lesen(jetzt: datetime | None = None) -> list[Kontingent]:
    return [claude_lesen(jetzt=jetzt), codex_lesen(jetzt=jetzt)]
