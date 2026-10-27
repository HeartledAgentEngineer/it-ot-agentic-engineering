"""Dynamische Modellkataloge der installierten Werkzeuge (Claude Code, Codex).

Liest und aktualisiert die regulären Modellangebote der installierten Werkzeuge in einem
lokalen Metadatencache (`modelle.json` im Datenordner). Gespeichert werden ausschließlich
Modellkennung und Anzeigename sowie ein einfacher Fehlerstatus – keine rohen Antworten,
keine Sitzungskennungen, keine Kontodaten. Die Abfrage läuft als eigener Kindprozess mit
festen Fristen und festen Ausgabegrenzen; es findet keine Inferenz statt, es wird keine
Anmeldung verändert und nichts an ein fremdes System gesendet.

Grenzen (bindend):
* Frist je Abfrage 30 s; die Bereinigung darf zusätzlich höchstens einen Vorbehalt
  (`bereinigungsvorbehalt()`: Kill-Wartezeit plus ein Einsammellauf) verbrauchen.
  Die gesamte Hintergrundaktualisierung 65 s umfasst Abfragen UND Bereinigung beider
  Anbieter – im Hängefall wird die Bereinigung budgetbewusst verkürzt, nie überzogen.
* Feste Obergrenzen für Bytes, Zeilen und Modellanzahl; eine Überschreitung ist ein Fehler
  – keine abgeschnittene Erfolgsliste.
* Bei Fehlern bleibt das letzte gute Ergebnis mit sichtbarem Zeit- und Fehlerstatus stehen;
  es gibt keinen Auto-Modellwechsel und keine geratene Ersatzliste.
* Unter Windows wird ausschließlich der selbst gestartete und noch eigene Prozessbaum über
  `taskkill /PID <eigene PID> /T /F` beendet – nie über einen Programmnamen gesucht.
  Eine fehlgeschlagene Bereinigung ist ein sichtbarer Fehler, kein Erfolgskatalog;
  ihre Wartezeiten laufen im selben Budget wie die Abfrage.
* Nur ein Abgleich je Anbieter gleichzeitig (Single-Flight); die kurze Cache-Schreibsperre
  wird erst nach der Abfrage genommen und mergt verlustfrei mit frisch gelesenem Bestand.

Herkunft der Kataloge: Codex meldet `models` (slug/display_name/visibility) über den
reinen App-CLI-Metadatenaufruf `codex … debug models`; Claude Code über die lokale
Control-Initialisierung ohne Anmeldung (nur `value`/`displayName` der passenden eigenen
`control_response`). Beides ist ein Werkzeugkatalog, keine Garantie einer freien Quote
oder Kontoberechtigung.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import codex_senden, signale, zustand
from .signale import _atomar_schreiben, daten_ordner

VERSION = 1
PROVIDER = ("claude", "codex")

FRIST_ABFRAGE = 30.0          # je CLI-Abfrage; die Bereinigung kommt budgetiert hinzu
FRIST_GESAMT = 65.0           # gesamte Hintergrundaktualisierung inklusive Bereinigung
TTL_STUNDEN = 24              # danach gilt ein Katalog als veraltet
SCHREIB_FRIST = 5.0           # kurze globale Sperre nur fürs Merge/Schreiben

MAX_BYTES = 1024 * 1024       # feste Obergrenzen je Ausgabestrom
MAX_ZEILEN = 5000
MAX_MODELLE = 200
MAX_FELD = 200                # je Kennung/Anzeigename

TAKT_SEKUNDEN = 0.05
BEREINIGUNG_SEKUNDEN = 5.0    # Warten auf das Ende des beendeten Baums
PIPE_SEKUNDEN = 3.0           # zeitbegrenztes Einsammeln der eigenen Datenströme

KEINE_DATEN = "keine Daten"
PROGRAMM_FEHLT = "Programm nicht gefunden"
ZEITUEBERSCHREITUNG = "Zeitüberschreitung"
AUSGABELIMIT = "Ausgabelimit überschritten"
ANTWORT_UNGUELTIG = "Antwort ungültig"
KEINE_MODELLE = "keine Modelle gemeldet"
ABFRAGE_FEHLGESCHLAGEN = "Abfrage fehlgeschlagen"
BEREINIGUNG_FEHLGESCHLAGEN = "Bereinigung fehlgeschlagen"
SPEICHERN_FEHLGESCHLAGEN = "Speichern fehlgeschlagen"
KATEGORIEN = (KEINE_DATEN, PROGRAMM_FEHLT, ZEITUEBERSCHREITUNG, AUSGABELIMIT, ANTWORT_UNGUELTIG,
              KEINE_MODELLE, ABFRAGE_FEHLGESCHLAGEN, BEREINIGUNG_FEHLGESCHLAGEN, SPEICHERN_FEHLGESCHLAGEN)


class KatalogFehler(Exception):
    """Unbekannter Modellprovider oder unzulässige Nutzung."""


class AbfrageFehler(Exception):
    """Sichere, einfache Fehlerkategorie einer Katalogabfrage – niemals Rohdaten des Werkzeugs."""

    kategorie = ABFRAGE_FEHLGESCHLAGEN

    def __init__(self, meldung: str = ""):
        super().__init__(meldung or self.kategorie)


class ProgrammFehlt(AbfrageFehler):
    kategorie = PROGRAMM_FEHLT


class ZeitFehler(AbfrageFehler):
    kategorie = ZEITUEBERSCHREITUNG


class GrenzFehler(AbfrageFehler):
    kategorie = AUSGABELIMIT


class AntwortFehler(AbfrageFehler):
    kategorie = ANTWORT_UNGUELTIG


class KeineModelleFehler(AbfrageFehler):
    kategorie = KEINE_MODELLE


class BereinigungsFehler(AbfrageFehler):
    kategorie = BEREINIGUNG_FEHLGESCHLAGEN


@dataclass(frozen=True)
class Modell:
    id: str
    name: str


@dataclass(frozen=True)
class Katalog:
    provider: str
    modelle: tuple[Modell, ...] = ()
    zeit: datetime | None = None    # wann der Katalog ermittelt wurde
    fehler: str | None = None       # einfache Fehlerkategorie des letzten Abgleichs
    veraltet: bool = False          # älter als die TTL oder ohne verwertbaren Zeitstempel


@dataclass(frozen=True)
class Ausgang:
    rc: int
    stdout: bytes = b""
    stderr: bytes = b""


@dataclass(frozen=True)
class Aufruf:
    """Fertig gebauter Kindprozessaufruf: Argumentliste, Umgebung, stdin-Eingabe, Anfragekennung."""

    liste: tuple[str, ...]
    umgebung: dict[str, str]
    eingabe: bytes
    kennung: str | None = None


Transport = Callable[[list[str], dict[str, str], bytes, float], Ausgang]


def datei() -> Path:
    return daten_ordner() / "modelle.json"


# --- Prüfen der Modellfelder --------------------------------------------------

def _feld(wert: object) -> str | None:
    """Sauberer Text (getrimmt, ohne Kontrollzeichen, begrenzt) oder None."""
    if not isinstance(wert, str):
        return None
    text = wert.strip()
    if not text or len(text) > MAX_FELD:
        return None
    if any(ord(zeichen) < 32 or ord(zeichen) == 127 for zeichen in text):
        return None
    return text


def _pruefe_modelle(rohe: list, id_feld: str, name_feld: str, *, nur_sichtbar: bool = False) -> tuple[Modell, ...]:
    """Einträge prüfen und deduplizieren (erste Kennung gewinnt).

    Einzelne kaputte Einträge (falscher Typ, Kontrollzeichen, Überlänge, leer) werden
    übersprungen – sie sind keine wählbaren Modelle. Die Liste wird nie durch geratene
    Einträge ersetzt oder aufgefüllt; ein fehlender Anzeigename fällt auf die eigene
    Kennung zurück. `nur_sichtbar` übernimmt (Codex) nur `visibility == "list"`.
    """
    gesehen: set[str] = set()
    modelle: list[Modell] = []
    for eintrag in rohe:
        if not isinstance(eintrag, dict):
            continue
        if nur_sichtbar and eintrag.get("visibility") != "list":
            continue
        ident = _feld(eintrag.get(id_feld))
        if ident is None or ident in gesehen:
            continue
        gesehen.add(ident)
        modelle.append(Modell(ident, _feld(eintrag.get(name_feld)) or ident))
    return tuple(modelle)


def _grenzen_pruefen(ausgang: Ausgang) -> None:
    if len(ausgang.stdout) > MAX_BYTES or len(ausgang.stderr) > MAX_BYTES:
        raise GrenzFehler("Ausgabe überschreitet die feste Bytegrenze")
    if ausgang.stdout.count(b"\n") > MAX_ZEILEN:
        raise GrenzFehler("Ausgabe überschreitet die feste Zeilengrenze")


# --- Antworten der beiden realen Werkzeuge ------------------------------------

def _json_mit_models(stdout: bytes) -> dict | None:
    """Erstes JSON-Objekt mit `models` aus einer Codex-Antwort (auch wenn Rahmenzeilen davor stehen)."""
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        roh = json.loads(text)
    except ValueError:
        roh = None
    if isinstance(roh, dict) and "models" in roh:
        return roh
    for zeile in text.splitlines():
        if '"models"' not in zeile:
            continue
        try:
            kandidat = json.loads(zeile)
        except ValueError:
            continue
        if isinstance(kandidat, dict) and "models" in kandidat:
            return kandidat
    return roh if isinstance(roh, dict) else None


def _codex_modelle(ausgang: Ausgang) -> tuple[Modell, ...]:
    if ausgang.rc != 0:
        raise AbfrageFehler(f"Codex-Abfrage endete mit Rückgabewert {ausgang.rc}")
    roh = _json_mit_models(ausgang.stdout)
    if roh is None:
        raise AntwortFehler("Antwort enthält kein JSON mit models")
    modelle_roh = roh.get("models")
    if not isinstance(modelle_roh, list):
        raise AntwortFehler("Feld models fehlt oder ist kein Array")
    if len(modelle_roh) > MAX_MODELLE:
        raise GrenzFehler("Antwort meldet mehr Modelle als erlaubt")
    geprueft = _pruefe_modelle(modelle_roh, "slug", "display_name", nur_sichtbar=True)
    if not geprueft:
        raise KeineModelleFehler("Antwort meldet keine sichtbaren Modelle")
    return geprueft


def _claude_antwort(zeile: bytes, kennung: str) -> dict | None:
    """Die innere Antwort genau der eigenen, erfolgreichen control_response – sonst None."""
    text = zeile.strip()
    if not text:
        return None
    try:
        roh = json.loads(text.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(roh, dict) or roh.get("type") != "control_response":
        return None
    antwort = roh.get("response")
    if not isinstance(antwort, dict) or antwort.get("request_id") != kennung:
        return None
    if antwort.get("subtype") != "success":
        return None
    innen = antwort.get("response")
    return innen if isinstance(innen, dict) else None


def _claude_treffer(kennung: str):
    def treffer(stdout: bytes) -> bool:
        return any(_claude_antwort(zeile, kennung) is not None for zeile in stdout.split(b"\n"))
    return treffer


def _claude_modelle(stdout: bytes, kennung: str | None) -> tuple[Modell, ...]:
    if kennung is None:
        raise AntwortFehler("Anfragekennung fehlt")
    for zeile in stdout.split(b"\n"):
        antwort = _claude_antwort(zeile, kennung)
        if antwort is None:
            continue
        modelle_roh = antwort.get("models")
        if not isinstance(modelle_roh, list):
            raise AntwortFehler("Antwort enthält kein Feld models")
        if len(modelle_roh) > MAX_MODELLE:
            raise GrenzFehler("Antwort meldet mehr Modelle als erlaubt")
        geprueft = _pruefe_modelle(modelle_roh, "value", "displayName")
        if not geprueft:
            raise KeineModelleFehler("Antwort meldet keine Modelle")
        return geprueft
    raise AntwortFehler("Keine eigene erfolgreiche control_response in der Antwort")


def _auswerten(provider: str, ausgang: Ausgang, kennung: str | None) -> tuple[Modell, ...]:
    if not isinstance(ausgang, Ausgang):
        raise AbfrageFehler("Transport lieferte kein gültiges Ergebnis")
    _grenzen_pruefen(ausgang)
    if provider == "codex":
        return _codex_modelle(ausgang)
    return _claude_modelle(ausgang.stdout, kennung)


def _kategorie(fehler: BaseException) -> str:
    if isinstance(fehler, AbfrageFehler):
        return fehler.kategorie
    if isinstance(fehler, (FileNotFoundError, PermissionError, NotADirectoryError)):
        return PROGRAMM_FEHLT
    if isinstance(fehler, subprocess.TimeoutExpired):
        return ZEITUEBERSCHREITUNG
    return ABFRAGE_FEHLGESCHLAGEN


# --- Kindprozessaufrufe (Programm, Umgebung, Eingabe) -------------------------

def _umgebung() -> dict[str, str]:
    """Kindprozess-Umgebung ohne API-/Token-/Fremdprovider-Schlüssel; Elternumgebung bleibt unverändert."""
    schluessel_endungen = ("_API_KEY", "_API_TOKEN", "_AUTH_TOKEN", "_OAUTH_TOKEN", "_ACCESS_TOKEN", "_SECRET")
    fremd_praefixe = ("ANTHROPIC_", "OPENAI_", "OPENROUTER_", "GEMINI_", "GOOGLE_")
    sauber: dict[str, str] = {}
    for name, wert in os.environ.items():
        oben = name.upper()
        if oben.endswith(schluessel_endungen) or oben.startswith(fremd_praefixe):
            continue
        sauber[name] = wert
    return sauber


def _claude_kandidaten() -> tuple[Path, ...]:
    kandidaten = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        kandidaten.append(Path(appdata) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js")
    kandidaten.append(Path.home() / ".claude" / "local" / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js")
    kandidaten.append(Path.home() / ".claude" / "local" / "cli.js")
    return tuple(kandidaten)


def _claude_nativ_kandidaten() -> tuple[Path, ...]:
    """Natives Programm: npm-Pakete ab 2.1.3xx enthalten kein `cli.js` mehr, sondern `bin/claude.exe`."""
    kandidaten = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        kandidaten.append(Path(appdata) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe")
    kandidaten.append(Path.home() / ".local" / "bin" / "claude.exe")
    return tuple(kandidaten)


def _node_programm() -> str | None:
    eigen = os.environ.get("MASTER_SCHALTER_NODE")
    if eigen:
        return eigen
    appdata = os.environ.get("APPDATA")
    if appdata:
        neben_shim = Path(appdata) / "npm" / "node.exe"
        if neben_shim.is_file():
            return str(neben_shim)
    return shutil.which("node")


def claude_programm() -> tuple[str, ...] | None:
    """Aufrufpräfix der installierten Claude-Code-CLI – ohne .cmd-/Shellwrapper.

    `(node, cli.js)` für ältere npm-Pakete, `(claude.exe,)` für das native Programm.

    `MASTER_SCHALTER_CLAUDE_CLI` (und `MASTER_SCHALTER_NODE`) haben als explizite technische
    Umgebungsoption Vorrang; sonst werden bekannte installierte Pfade geprüft.
    """
    eigen = os.environ.get("MASTER_SCHALTER_CLAUDE_CLI")
    if eigen:
        node = _node_programm()
        return (node, eigen) if node else None
    node = _node_programm()
    for cli in _claude_kandidaten():
        if cli.is_file() and node:
            return (node, str(cli))
    for programm in _claude_nativ_kandidaten():
        if programm.is_file():
            return (str(programm),)
    return None


def _leerer_ordner() -> Path:
    """Dedizierter leerer Ordner als CLAUDE_CONFIG_DIR und Arbeitsverzeichnis der Abfragen."""
    ordner = daten_ordner() / "modelle-leer"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _aufruf_codex() -> Aufruf:
    programm = codex_senden.programm()
    if not programm:
        raise ProgrammFehlt("Codex-App-CLI wurde nicht gefunden")
    # Genau der belegte reine Metadatenaufruf; `--ignore-user-config` ist hier kein gültiges globales Flag.
    liste = (programm, "-c", "model_provider=openai", "-c", "forced_login_method=chatgpt", "debug", "models")
    return Aufruf(liste, _umgebung(), b"")


def _aufruf_claude() -> Aufruf:
    praefix = claude_programm()
    if praefix is None:
        raise ProgrammFehlt("Claude-Code-CLI wurde nicht gefunden")
    liste = (*praefix, "--bare", "--print", "--input-format", "stream-json", "--output-format", "stream-json",
             "--verbose", "--no-session-persistence", "--disable-slash-commands", "--tools", "",
             "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}')
    kennung = f"master-schalter-{uuid.uuid4().hex}"
    anfrage = {"type": "control_request", "request_id": kennung, "request": {"subtype": "initialize"}}
    umgebung = _umgebung()
    umgebung.update({
        "CLAUDE_CONFIG_DIR": str(_leerer_ordner()),
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "DISABLE_AUTOUPDATER": "1",
    })
    return Aufruf(liste, umgebung, json.dumps(anfrage, ensure_ascii=False).encode("utf-8") + b"\n", kennung)


def _aufruf(provider: str) -> Aufruf:
    return _aufruf_codex() if provider == "codex" else _aufruf_claude()


def _kennung_der_anfrage(eingabe: bytes) -> str | None:
    for zeile in eingabe.split(b"\n"):
        if not zeile.strip():
            continue
        try:
            roh = json.loads(zeile.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue
        if isinstance(roh, dict) and roh.get("type") == "control_request" and isinstance(roh.get("request_id"), str):
            return roh["request_id"]
    return None


# --- Prozesslauf mit Frist, Ausgabegrenzen und sicherer Bereinigung ----------

def bereinigungsvorbehalt() -> float:
    """Obergrenze des Zusatzverbrauchs der Bereinigung je Aufruf (Kill-Wartezeit + ein Einsammellauf)."""
    return BEREINIGUNG_SEKUNDEN + PIPE_SEKUNDEN


class _Stand:
    """Zeit- und mengelbegrenzter Ausgabespeicher beider Ströme (thread-sicher)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.aus = bytearray()
        self.fehler_aus = bytearray()
        self.zeilen = 0
        self.ueber = False

    def inhalt(self) -> bytes:
        with self.lock:
            return bytes(self.aus)

    def fehler_inhalt(self) -> bytes:
        with self.lock:
            return bytes(self.fehler_aus)


def _lesen_strom(strom, puffer: bytearray, stand: _Stand) -> None:
    while True:
        try:
            stueck = strom.read1(4096)
        except (OSError, ValueError):
            return
        if not stueck:
            return
        with stand.lock:
            puffer.extend(stueck)
            if puffer is stand.aus:
                stand.zeilen += stueck.count(b"\n")
            if len(stand.aus) > MAX_BYTES or len(stand.fehler_aus) > MAX_BYTES or stand.zeilen > MAX_ZEILEN:
                stand.ueber = True
                return


def _taskkill_argv(pid: int) -> list[str]:
    return ["taskkill", "/PID", str(pid), "/T", "/F"]


def _taskkill(pid: int) -> None:
    try:
        subprocess.run(_taskkill_argv(pid), capture_output=True, timeout=BEREINIGUNG_SEKUNDEN)
    except (OSError, subprocess.TimeoutExpired):
        pass  # Ob der Baum wirklich endete, prüft die Nachkontrolle in `_bereinigen`


def _baum_beenden(pid: int) -> None:
    """Unter Windows genau `taskkill /PID <eigene PID> /T /F`; auf POSIX nur die eigene neue Prozessgruppe."""
    if os.name == "nt":
        _taskkill(pid)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except OSError:
        pass


def _bereinigen(prozess: subprocess.Popen, threads: tuple[threading.Thread, ...], ende: float) -> None:
    """Eigenen Prozessbaum beenden und Pipes zeitbegrenzt einsammeln; Fehlschlag = sichtbarer Fehler.

    `ende` (monotone Zeit) ist die harte Obergrenze aller Wartezeiten dieser Bereinigung:
    Abfragefrist plus `bereinigungsvorbehalt()`. Im Hängefall wird die Kill-Wartezeit also
    budgetbewusst gekürzt, statt die Frist des Gesamtlaufs zu überziehen.
    """
    if prozess.poll() is None:
        _baum_beenden(prozess.pid)
        warte_ende = min(time.monotonic() + BEREINIGUNG_SEKUNDEN, ende)
        while prozess.poll() is None and time.monotonic() < warte_ende:
            time.sleep(TAKT_SEKUNDEN)
        if prozess.poll() is None:
            raise BereinigungsFehler(f"Prozessbaum um PID {prozess.pid} ließ sich nicht beenden")
    for thread in threads:
        thread.join(min(PIPE_SEKUNDEN, max(0.0, ende - time.monotonic())))
    if all(not thread.is_alive() for thread in threads):
        return
    # Ein Lesefaden hält die Lesesperre des gepufferten stdout/stderr; `close()` darauf würde bis zum Ende des
    # Lesens blockieren (z. B. wenn ein Kindprozess die Pipe nach dem Ende des Elternprozesses offen hält).
    # Deshalb werden die lesenden Ströme hier nie geschlossen: der Daemon-Faden bleibt liegen, der Fehler ist sichtbar.
    if prozess.stdin is not None:
        try:
            prozess.stdin.close()
        except (OSError, ValueError):
            pass
    raise BereinigungsFehler("Datenströme des Prozesses ließen sich nicht schließen")


def _lauf(liste: list[str], umgebung: dict[str, str], eingabe: bytes, frist: float,
          *, treffer=None) -> Ausgang:
    """Kindprozess starten, Ausgabe mengenbegrenzt einsammeln und den eigenen Baum sicher beenden.

    Es wird ausschließlich der selbst gestartete Prozess (über taskkill /T samt Baum) beendet –
    nie über einen Programmnamen gesucht. `treffer` bricht ab, sobald die Antwort vollständig
    gelesen ist (Claude); sonst zählt das natürliche Ende des Befehls (Codex).
    Budget: `frist` gilt für die Abfrage; die Bereinigung darf zusätzlich höchstens
    `bereinigungsvorbehalt()` verbrauchen, damit der Aufruf in Frist + Vorbehalt endet.
    """
    beginn = time.monotonic()
    try:
        leer = _leerer_ordner()
        prozess = subprocess.Popen(
            liste,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(leer),
            env=dict(umgebung),
            close_fds=True,
            start_new_session=(os.name != "nt"),
        )
    except (FileNotFoundError, PermissionError, NotADirectoryError) as fehler:
        raise ProgrammFehlt(f"Programm nicht startbar: {type(fehler).__name__}") from None
    except OSError as fehler:
        raise AbfrageFehler(f"Prozess nicht gestartet: {type(fehler).__name__}") from None

    stand = _Stand()
    threads = (
        threading.Thread(target=_lesen_strom, args=(prozess.stdout, stand.aus, stand), daemon=True),
        threading.Thread(target=_lesen_strom, args=(prozess.stderr, stand.fehler_aus, stand), daemon=True),
    )
    for thread in threads:
        thread.start()
    if prozess.stdin is not None:
        try:
            if eingabe:
                prozess.stdin.write(eingabe)
            prozess.stdin.flush()
            prozess.stdin.close()
        except (OSError, ValueError):
            pass  # früh beendetes Programm; das beurteilt der Rest des Laufs

    abfrage_ende = beginn + frist
    abbruch = None
    while True:
        if treffer is not None and treffer(stand.inhalt()):
            break
        if stand.ueber:
            abbruch = "limit"
            break
        if prozess.poll() is not None:
            break
        if time.monotonic() >= abfrage_ende:
            abbruch = "zeit"
            break
        time.sleep(TAKT_SEKUNDEN)
    _bereinigen(prozess, threads, abfrage_ende + bereinigungsvorbehalt())

    if abbruch == "limit":
        raise GrenzFehler("Ausgabe hat die feste Obergrenze überschritten")
    if abbruch == "zeit":
        raise ZeitFehler("Abfrage hat die Frist überschritten")
    rc = prozess.returncode if prozess.returncode is not None else -1
    return Ausgang(rc, stand.inhalt(), stand.fehler_inhalt())


def codex_transport(liste: list[str], umgebung: dict[str, str], eingabe: bytes, frist: float) -> Ausgang:
    """Standardtransport Codex: wartet auf das natürliche Ende des Befehls."""
    return _lauf(liste, umgebung, eingabe, frist)


def claude_transport(liste: list[str], umgebung: dict[str, str], eingabe: bytes, frist: float) -> Ausgang:
    """Standardtransport Claude: endet, sobald die eigene erfolgreiche control_response gelesen ist."""
    kennung = _kennung_der_anfrage(eingabe)
    treffer = _claude_treffer(kennung) if kennung else None
    return _lauf(liste, umgebung, eingabe, frist, treffer=treffer)


_TRANSPORTE: dict[str, Transport] = {"codex": codex_transport, "claude": claude_transport}


# --- Metadatencache (nur geprüfte Felder) ------------------------------------

def _roh_datei(pfad: Path) -> dict | None:
    """Cache-Dateiinhalt als dict oder None (fehlend, kaputt, fremde Version)."""
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(roh, dict) or roh.get("version") != VERSION:
        return None
    return roh


def _roh_fuer_schreiben(pfad: Path) -> dict:
    """Rohstruktur fürs Mergen; kaputte Datei wird ersetzt, fremde Version verweigert."""
    if not pfad.exists():
        return {}
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(roh, dict) or roh.get("version") != VERSION:
        raise KatalogFehler("Modellcache hat ein unbekanntes Format oder eine fremde Version")
    return roh


def _anbieter_map(roh: dict) -> dict:
    anbieter = roh.get("anbieter")
    if not isinstance(anbieter, dict):
        return {}
    return {p: e for p, e in anbieter.items() if isinstance(p, str) and isinstance(e, dict)}


def _veraltet(zeit: datetime | None, jetzt: datetime) -> bool:
    return zeit is None or jetzt - zeit > timedelta(hours=TTL_STUNDEN)


def _eintrag_pruefen(roh: object) -> tuple[tuple[Modell, ...], datetime | None, str | None] | None:
    """Einen Anbietereintrag des Caches streng prüfen; None = unbrauchbar."""
    if not isinstance(roh, dict):
        return None
    modelle_roh = roh.get("modelle")
    if not isinstance(modelle_roh, list) or len(modelle_roh) > MAX_MODELLE:
        return None
    fehler = roh.get("fehler")
    if fehler is not None and fehler not in KATEGORIEN:
        return None
    return _pruefe_modelle(modelle_roh, "id", "name"), signale._iso(roh.get("zeit")), fehler


def _lesen_aus(datei_pfad: Path | None, provider: str, jetzt: datetime) -> Katalog:
    roh = _roh_datei(datei_pfad or datei())
    anbieter = roh.get("anbieter") if roh else None
    eintrag = _eintrag_pruefen(anbieter.get(provider)) if isinstance(anbieter, dict) else None
    if eintrag is None:
        return Katalog(provider, (), None, KEINE_DATEN, True)
    modelle_, zeit, fehler = eintrag
    if not modelle_ and fehler is None:
        return Katalog(provider, (), None, KEINE_DATEN, True)
    return Katalog(provider, modelle_, zeit, fehler, _veraltet(zeit, jetzt))


def lesen(provider: str, *, datei_pfad: Path | None = None, jetzt: datetime | None = None) -> Katalog:
    """Nur den validierten lokalen Metadatencache lesen; nie eine Abfrage starten."""
    if provider not in PROVIDER:
        raise KatalogFehler(f"Unbekannter Modellprovider: {provider!r}")
    return _lesen_aus(datei_pfad, provider, jetzt or datetime.now(timezone.utc))


def _speichern(datei_pfad: Path | None, provider: str, eintrag: dict) -> None:
    """Unter der kurzen globalen Sperre frisch lesen, nur den eigenen Anbieter ersetzen, atomar schreiben."""
    with zustand.sperre(SCHREIB_FRIST):
        pfad = datei_pfad or datei()
        eintraege = _anbieter_map(_roh_fuer_schreiben(pfad))
        eintraege[provider] = eintrag
        _atomar_schreiben(pfad, json.dumps({"version": VERSION, "anbieter": eintraege}, ensure_ascii=False, indent=2))


def _merken(datei_pfad: Path | None, provider: str, modelle_: tuple[Modell, ...], jetzt: datetime) -> Katalog:
    eintrag = {"zeit": jetzt.isoformat(), "fehler": None,
               "modelle": [{"id": m.id, "name": m.name} for m in modelle_]}
    try:
        _speichern(datei_pfad, provider, eintrag)
    except (OSError, zustand.SperrFehler, KatalogFehler):
        return Katalog(provider, modelle_, jetzt, SPEICHERN_FEHLGESCHLAGEN, False)
    return Katalog(provider, modelle_, jetzt, None, False)


def _merken_fehler(datei_pfad: Path | None, provider: str, kategorie: str, jetzt: datetime) -> Katalog:
    """Letztes gutes Ergebnis behalten und nur den Fehlerstatus sichtbar vermerken."""
    alt = _lesen_aus(datei_pfad, provider, jetzt)
    eintrag = {"zeit": alt.zeit.isoformat() if alt.zeit else None, "fehler": kategorie,
               "modelle": [{"id": m.id, "name": m.name} for m in alt.modelle]}
    try:
        _speichern(datei_pfad, provider, eintrag)
    except (OSError, zustand.SperrFehler, KatalogFehler):
        pass  # Der Abfragefehler bleibt sichtbar; nur das Merken scheiterte zusätzlich.
    return Katalog(provider, alt.modelle, alt.zeit, kategorie, _veraltet(alt.zeit, jetzt))


# --- Single-Flight je Anbieter -----------------------------------------------

class _Flug:
    """Ein Abgleich je Anbieter gleichzeitig; wartende Aufrufer übernehmen dessen Ergebnis."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.gen = 0  # Anzahl abgeschlossener Abgleiche


_FLUG: dict[str, _Flug] = {}


def _flug(provider: str) -> _Flug:
    return _FLUG.setdefault(provider, _Flug())


def aktualisieren(provider: str, *, transport: Transport | None = None, datei_pfad: Path | None = None,
                  jetzt: datetime | None = None, frist: float = FRIST_ABFRAGE) -> Katalog:
    """Frisch abfragen und atomar speichern; bei Fehlern bleibt der letzte gute Katalog stehen.

    Der Transport erhält explizite Argumentliste, Umgebung, stdin-Eingabe und Frist.
    Überlappt ein zweiter Aufruf desselben Anbieters mit einem laufenden, wartet er auf
    dessen Abschluss und liest den frischen Cache (Single-Flight, genau ein Transport).
    """
    if provider not in PROVIDER:
        raise KatalogFehler(f"Unbekannter Modellprovider: {provider!r}")
    jetzt = jetzt or datetime.now(timezone.utc)
    lauf = _flug(provider)
    gesehen = lauf.gen
    with lauf.lock:
        if lauf.gen != gesehen:
            return _lesen_aus(datei_pfad, provider, jetzt)
        try:
            aufruf = _aufruf(provider)
            ausgang = (transport or _TRANSPORTE[provider])(
                list(aufruf.liste), dict(aufruf.umgebung), aufruf.eingabe, frist)
            geprueft = _auswerten(provider, ausgang, aufruf.kennung)
        except Exception as fehler:  # noqa: BLE001 – jede Störung wird zu einer einfachen Fehlerkategorie
            kategorie = _kategorie(fehler)
            lauf.gen += 1
            return _merken_fehler(datei_pfad, provider, kategorie, jetzt)
        lauf.gen += 1
        return _merken(datei_pfad, provider, geprueft, jetzt)


def alle_aktualisieren(*, claude: Transport | None = None, codex: Transport | None = None,
                       datei_pfad: Path | None = None, jetzt: datetime | None = None,
                       frist: float = FRIST_GESAMT) -> dict[str, Katalog]:
    """Beide Anbieter nacheinander abgleichen; die Gesamtfrist begrenzt die Summe der Abfragen
    samt deren Bereinigung.

    Je Anbieter wird der Bereinigungsvorbehalt vom Restbudget abgezogen; reicht das nicht mehr,
    wird der Anbieter ohne Abfrage als Zeitüberschreitung vermerkt. Ein Teilfehler lässt das
    letzte gute Ergebnis des betroffenen Anbieters sichtbar stehen.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    beginn = time.monotonic()
    ergebnis: dict[str, Katalog] = {}
    for provider, transport in (("claude", claude), ("codex", codex)):
        budget = frist - (time.monotonic() - beginn) - bereinigungsvorbehalt()
        if budget <= 0:
            ergebnis[provider] = _merken_fehler(datei_pfad, provider, ZEITUEBERSCHREITUNG, jetzt)
            continue
        ergebnis[provider] = aktualisieren(provider, transport=transport, datei_pfad=datei_pfad,
                                           jetzt=jetzt, frist=min(FRIST_ABFRAGE, budget))
    return ergebnis
