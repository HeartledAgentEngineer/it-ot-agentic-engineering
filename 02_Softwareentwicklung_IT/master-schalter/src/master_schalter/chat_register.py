"""Register der zuletzt benutzten Chats aus Claude Code, Codex und Hermes (nur Metadaten, nur lesend).

Das Register kennt je Chat Werkzeug, Kennung, Titel, Arbeitsordner und Zeit der letzten Nutzung –
sonst nichts. Nachrichteninhalte werden nie gelesen. Vier Quellen, jede einzeln fehlertolerant:

* `claude-desktop`: `<wurzel>/*/claude-code-sessions/**/local_*.json` (je Datei höchstens 256 KB;
  gelesen werden nur `cliSessionId`, `title`, `cwd`, `lastActivityAt`, `isArchived`).
* `claude-cli`: `<wurzel>/*/<uuid>.jsonl` (nur direkte Kinder je Projektordner). Zeit = Änderungszeit
  der Datei; nur Dateien im Zeitfenster werden geöffnet. Von jeder Zeile wird nur dann etwas
  geparst, wenn sie mit `{"type":"custom-title"` bzw. `{"type":"ai-title"` beginnt. Ergänzt nur Kennungen, die
  `claude-desktop` nicht schon geliefert hat.
* `codex`: SQLite-Datei, Tabelle `threads`, ausdrückliche Spaltenliste. Gibt es die Spalte
  `thread_source`, zählen nur Chats von Sebastian (`user`); automatische Prüf-Threads
  (`guardian_review`), Subagenten und von Agenten angelegte Threads bleiben draußen.
* `hermes`: SQLite-Datei, Tabelle `sessions`, ausdrückliche Spaltenliste (nie die Tabelle `messages`).
* `agy`: SQLite-Übersichtsdatei je Ausprägung von Antigravity (`antigravity`, `antigravity-cli`,
  `antigravity-ide`) unter `~/.gemini/<Ausprägung>/conversation_summaries.db`, Tabelle
  `conversation_summaries`, ausdrückliche Spaltenliste (nie `preview`, `raw_summary`, `user_body`
  oder `agent_body`).

SQLite-Dateien werden ausschließlich schreibgeschützt (`mode=ro`) geöffnet; vor der Abfrage prüft
`PRAGMA table_info`, ob die erwarteten Spalten vorhanden sind (sonst Status „schema unbekannt“).

Datenschutz (Regel G9): Titel, Ordner und Kennungen sind persönlich. Sie werden nur lokal gelesen
und nie an Modelle weitergegeben; auch die Statusangaben enthalten höchstens den Namen einer
Ausnahmeklasse, nie deren Text (der könnte Pfade enthalten).
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

KENNUNG_MUSTER = re.compile(r"[A-Za-z0-9_-]{1,80}")
UUID_DATEINAME = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
TITEL_MAX = 200
DESKTOP_DATEI_MAX_BYTES = 256 * 1024
HERMES_QUELLEN = ("cli", "desktop", "telegram", "api_server")
QUELLEN = ("claude-desktop", "claude-cli", "codex", "hermes", "agy")
ZUKUNFT_TOLERANZ = timedelta(minutes=5)

ENV_CLAUDE_DESKTOP = "MASTER_SCHALTER_CLAUDE_DESKTOP"
ENV_CLAUDE_PROJEKTE = "MASTER_SCHALTER_CLAUDE_PROJEKTE"
ENV_CODEX_STATE = "MASTER_SCHALTER_CODEX_STATE"
ENV_HERMES_STATE = "MASTER_SCHALTER_HERMES_STATE"
ENV_AGY_HEIM = "MASTER_SCHALTER_AGY_HEIM"

CODEX_PFLICHT = ("id", "cwd", "title", "updated_at_ms", "archived")
HERMES_PFLICHT = ("id", "source", "title", "cwd", "started_at")
# Die drei Ausprägungen von Antigravity legen ihre Übersicht je in einem eigenen Ordner ab.
AGY_AUSPRAEGUNGEN = ("antigravity", "antigravity-cli", "antigravity-ide")
AGY_PFLICHT = ("conversation_id", "title", "last_modified_time", "workspace_uris")


@dataclass(frozen=True)
class Chat:
    werkzeug: str        # "claude" | "codex" | "hermes" | "agy"
    kennung: str         # Claude: CLI-Sitzungs-UUID; Codex: Thread-ID; Hermes: Sitzungs-ID; agy: Konversations-UUID
    titel: str           # "" wenn unbekannt; auf 200 Zeichen gekürzt
    ordner: str          # Arbeitsordner (cwd), "" wenn unbekannt
    zuletzt: datetime    # UTC, letzte Nutzung
    quelle: str          # "claude-desktop" | "claude-cli" | "codex" | "hermes" | "agy"


@dataclass(frozen=True)
class Ergebnis:
    chats: tuple[Chat, ...]          # neueste zuerst, je (werkzeug, kennung) höchstens einmal
    quellen: dict[str, str]          # quelle -> "ok" | "fehlt" | "nicht lesbar: <grund>" | "schema unbekannt"


class _Unlesbar(Exception):
    """Interner Abbruch einer Quelle, deren Dateien alle unbrauchbar waren (Text = Grund ohne Pfade)."""


# --- Hilfen ------------------------------------------------------------------

def _umgebung(name: str) -> Path | None:
    wert = os.environ.get(name)
    return Path(wert) if wert else None


def _lokal() -> Path:
    wert = os.environ.get("LOCALAPPDATA")
    return Path(wert) if wert else Path.home() / "AppData" / "Local"


def _desktop_wurzel() -> Path:
    return _umgebung(ENV_CLAUDE_DESKTOP) or _lokal() / "Claude-Data"


def _projekte_wurzel() -> Path:
    return _umgebung(ENV_CLAUDE_PROJEKTE) or Path.home() / ".claude" / "projects"


def _codex_pfad() -> Path:
    return _umgebung(ENV_CODEX_STATE) or Path.home() / ".codex" / "state_5.sqlite"


def _hermes_pfad() -> Path:
    eigen = _umgebung(ENV_HERMES_STATE)
    if eigen:
        return eigen
    heim = os.environ.get("HERMES_HOME")
    return (Path(heim) if heim else _lokal() / "hermes") / "state.db"


def _text(wert: object, grenze: int = TITEL_MAX) -> str:
    """Nur Text; Leerraum (auch Zeilenumbrüche) wird zu einem Leerzeichen, dann gekürzt."""
    if not isinstance(wert, str):
        return ""
    return " ".join(wert.split())[:grenze]


def _ordner(wert: object) -> str:
    """Arbeitsordner als Text; das Windows-Präfix `\\\\?\\` wird entfernt."""
    text = _text(wert, 500)
    return text[4:] if text.startswith("\\\\?\\") else text


def _kennung(wert: object) -> str | None:
    return wert if isinstance(wert, str) and KENNUNG_MUSTER.fullmatch(wert) else None


def _epoche(wert: object, teiler: float) -> datetime | None:
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(wert / teiler, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _grund(fehler: BaseException) -> str:
    """`gesperrt` bzw. nur der Klassenname – der Text einer Ausnahme kann Pfade oder Titel enthalten.

    Der Ausnahmetext wird nur geprüft (Sperre erkennen), nie ausgegeben.
    """
    if isinstance(fehler, PermissionError) or (
            isinstance(fehler, sqlite3.OperationalError) and "locked" in str(fehler).lower()):
        return "gesperrt"
    return f"nicht lesbar: {type(fehler).__name__}"


def _sqlite_oeffnen(pfad: Path) -> sqlite3.Connection:
    """Ausschließlich schreibgeschützt (`mode=ro`); Sonderzeichen im Pfad werden URI-kodiert."""
    adresse = urllib.parse.quote(pfad.as_posix(), safe="/:")
    return sqlite3.connect(f"file:{adresse}?mode=ro", uri=True, timeout=1.0)


def _spalten(verbindung: sqlite3.Connection, tabelle: str) -> set[str]:
    """Spaltennamen laut `PRAGMA table_info`; `tabelle` kommt nur aus diesem Modul (feste Namen)."""
    return {zeile[1] for zeile in verbindung.execute(f"PRAGMA table_info({tabelle})")}


# --- Claude Desktop ------------------------------------------------------------

def _claude_desktop(grenze: datetime, archiviert: set[str] | None = None) -> tuple[list[Chat], str]:
    """Desktop-Sitzungen; Kennungen archivierter Sitzungen landen (unabhängig vom Zeitfenster) in `archiviert`."""
    wurzel = _desktop_wurzel()
    if not wurzel.is_dir():
        return [], "fehlt"
    chats: dict[str, Chat] = {}
    gelesen = kaputt = 0
    letzter: BaseException | None = None
    for datei in wurzel.glob("*/claude-code-sessions/**/local_*.json"):
        try:
            if not datei.is_file() or datei.stat().st_size > DESKTOP_DATEI_MAX_BYTES:
                continue
            roh = json.loads(datei.read_text(encoding="utf-8"))
            if not isinstance(roh, dict):
                raise TypeError("kein JSON-Objekt")
        except (OSError, ValueError, TypeError) as fehler:
            kaputt += 1
            letzter = fehler
            continue
        gelesen += 1
        kennung = _kennung(roh.get("cliSessionId"))
        if kennung is not None and roh.get("isArchived") is True:
            if archiviert is not None:
                archiviert.add(kennung)
            continue
        zeit = _epoche(roh.get("lastActivityAt"), 1000.0)
        if kennung is None or zeit is None or zeit < grenze:
            continue
        chat = Chat("claude", kennung, _text(roh.get("title")), _ordner(roh.get("cwd")), zeit, "claude-desktop")
        bisher = chats.get(kennung)
        if bisher is None or chat.zuletzt > bisher.zuletzt:
            chats[kennung] = chat
    if kaputt and not gelesen:
        return [], _grund(letzter) if letzter else "nicht lesbar"
    return list(chats.values()), "ok"


# --- Claude CLI (jsonl) ----------------------------------------------------------

TITELZEILE = re.compile(rb'\s*\{\s*"type"\s*:\s*"(?:custom-title|ai-title)"')


def _jsonl_titel(datei: Path) -> str:
    """Titel aus `custom-title`/`ai-title`-Zeilen; alle anderen Zeilen werden nicht geparst.

    Geparst wird nur eine Zeile, die mit `{"type":"custom-title"` bzw. `{"type":"ai-title"` beginnt
    (so schreibt Claude Code diese Ereignisse). Eine Nachricht, deren Text das Wort nur enthält,
    bleibt ungeparst; steht `type` einmal nicht vorn, fehlt schlimmstenfalls der Titel.
    """
    titel = {"custom-title": "", "ai-title": ""}
    schluessel = {"custom-title": "customTitle", "ai-title": "aiTitle"}
    with datei.open("rb") as quelle:
        for zeile in quelle:
            if TITELZEILE.match(zeile) is None:
                continue
            try:
                roh = json.loads(zeile)
            except ValueError:
                continue
            art = roh.get("type") if isinstance(roh, dict) else None
            if art not in titel:
                continue
            wert = _text(roh.get(schluessel[art])) or _text(roh.get("title"))
            if wert:
                titel[art] = wert
    return titel["custom-title"] or titel["ai-title"]


def _claude_cli(grenze: datetime) -> tuple[list[Chat], str]:
    wurzel = _projekte_wurzel()
    if not wurzel.is_dir():
        return [], "fehlt"
    chats: list[Chat] = []
    gelesen = kaputt = 0
    letzter: BaseException | None = None
    for datei in wurzel.glob("*/*.jsonl"):
        if UUID_DATEINAME.fullmatch(datei.stem) is None:
            continue
        try:
            if not datei.is_file():
                continue
            zeit = datetime.fromtimestamp(datei.stat().st_mtime, timezone.utc)
            if zeit < grenze:
                continue
            titel = _jsonl_titel(datei)
        except (OSError, OverflowError, ValueError) as fehler:
            kaputt += 1
            letzter = fehler
            continue
        gelesen += 1
        chats.append(Chat("claude", datei.stem, titel, "", zeit, "claude-cli"))
    if kaputt and not gelesen:
        return [], _grund(letzter) if letzter else "nicht lesbar"
    return chats, "ok"


# --- Codex ------------------------------------------------------------------------

def _codex(grenze: datetime) -> tuple[list[Chat], str]:
    pfad = _codex_pfad()
    if not pfad.is_file():
        return [], "fehlt"
    with contextlib.closing(_sqlite_oeffnen(pfad)) as verbindung:
        spalten = _spalten(verbindung, "threads")
        if not set(CODEX_PFLICHT) <= spalten:
            return [], "schema unbekannt"
        auswahl = ", ".join(CODEX_PFLICHT[:4] + (("name",) if "name" in spalten else ()))
        nur_nutzer = " AND thread_source = 'user'" if "thread_source" in spalten else ""
        zeilen = verbindung.execute(
            f"SELECT {auswahl} FROM threads WHERE archived = 0 AND updated_at_ms >= ?{nur_nutzer}",
            (int(grenze.timestamp() * 1000),)).fetchall()
    chats: list[Chat] = []
    for zeile in zeilen:
        kennung, ordner, titel, ms = zeile[:4]
        name = zeile[4] if len(zeile) > 4 else None
        kennung, zeit = _kennung(kennung), _epoche(ms, 1000.0)
        if kennung is None or zeit is None or zeit < grenze:
            continue
        chats.append(Chat("codex", kennung, _text(name) or _text(titel), _ordner(ordner), zeit, "codex"))
    return chats, "ok"


# --- Hermes -----------------------------------------------------------------------

def _hermes(grenze: datetime) -> tuple[list[Chat], str]:
    pfad = _hermes_pfad()
    if not pfad.is_file():
        return [], "fehlt"
    with contextlib.closing(_sqlite_oeffnen(pfad)) as verbindung:
        spalten = _spalten(verbindung, "sessions")
        if not set(HERMES_PFLICHT) <= spalten:
            return [], "schema unbekannt"
        aktivitaet = "last_activity_at" in spalten
        auswahl = ", ".join(HERMES_PFLICHT + (("last_activity_at",) if aktivitaet else ()))
        bedingungen = [f"source IN ({', '.join('?' for _ in HERMES_QUELLEN)})"]
        for name in ("archived", "hidden"):
            if name in spalten:
                bedingungen.append(f"({name} IS NULL OR {name} = 0)")
        zeit_ausdruck = "COALESCE(last_activity_at, started_at)" if aktivitaet else "started_at"
        bedingungen.append(f"{zeit_ausdruck} >= ?")
        zeilen = verbindung.execute(
            f"SELECT {auswahl} FROM sessions WHERE {' AND '.join(bedingungen)}",
            (*HERMES_QUELLEN, grenze.timestamp())).fetchall()
    chats: list[Chat] = []
    for zeile in zeilen:
        kennung, quelle, titel, ordner, gestartet = zeile[:5]
        letzte = zeile[5] if len(zeile) > 5 else None
        kennung = _kennung(kennung)
        zeit = _epoche(letzte, 1.0) or _epoche(gestartet, 1.0)
        if kennung is None or quelle not in HERMES_QUELLEN or zeit is None or zeit < grenze:
            continue
        chats.append(Chat("hermes", kennung, _text(titel), _ordner(ordner), zeit, "hermes"))
    return chats, "ok"


# --- Antigravity (agy) -------------------------------------------------------------

def _agy_heim() -> Path:
    return _umgebung(ENV_AGY_HEIM) or Path.home() / ".gemini"


def _agy_ordner(wert: object) -> str:
    """Ersten Arbeitsordner aus `workspace_uris` (JSON-Array mit `file://`-Adressen) als Windows-Pfad.

    Alles Unbrauchbare (kein JSON, keine Dateiadresse) ergibt `""` – das Register darf daran nie scheitern.
    """
    if not isinstance(wert, str):
        return ""
    try:
        adressen = json.loads(wert)
    except ValueError:
        return ""
    if not isinstance(adressen, list):
        return ""
    for adresse in adressen:
        if not isinstance(adresse, str) or not adresse.startswith("file:"):
            continue
        pfad = urllib.parse.unquote(adresse[len("file:"):]).lstrip("/")
        pfad = re.sub(r"^([A-Za-z]):", lambda treffer: treffer.group(1).upper() + ":", pfad)
        return _ordner(pfad.replace("/", "\\"))
    return ""


def _agy_zeit(wert: object) -> datetime | None:
    """ISO-Zeitstempel der Antigravity-Übersicht als UTC; ein naiver Wert gilt als UTC, Unsinn als `None`."""
    if not isinstance(wert, str):
        return None
    try:
        zeit = datetime.fromisoformat(wert.strip())
    except ValueError:
        return None
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _agy(grenze: datetime) -> tuple[list[Chat], str]:
    """Antigravity-Sitzungen aus der Übersichtsdatenbank jeder Ausprägung (App, CLI, IDE).

    Gelesen werden ausschließlich Kennung, Titel, Änderungszeit und Arbeitsordner. Die Spalten mit
    Inhalten (`preview`, `raw_summary`, `user_body`, `agent_body`) werden nicht angefasst (Regel G9).
    Gefiltert wird in Python, weil die Übersicht den Zeitstempel als Text in eigener Schreibweise
    ablegt – ein Textvergleich in SQL wäre bei anderem Trenner falsch.
    """
    heim = _agy_heim()
    chats: dict[str, Chat] = {}
    vorhanden = gelesen = schema_falsch = 0
    letzter: BaseException | None = None
    for name in AGY_AUSPRAEGUNGEN:
        pfad = heim / name / "conversation_summaries.db"
        if not pfad.is_file():
            continue
        vorhanden += 1
        try:
            with contextlib.closing(_sqlite_oeffnen(pfad)) as verbindung:
                if not set(AGY_PFLICHT) <= _spalten(verbindung, "conversation_summaries"):
                    schema_falsch += 1
                    continue
                zeilen = verbindung.execute(
                    "SELECT conversation_id, title, last_modified_time, workspace_uris "
                    "FROM conversation_summaries").fetchall()
        except (sqlite3.Error, OSError, ValueError) as fehler:
            letzter = fehler
            continue
        gelesen += 1
        for kennung, titel, zeit, arbeit in zeilen:
            kennung, zeit = _kennung(kennung), _agy_zeit(zeit)
            if kennung is None or zeit is None or zeit < grenze:
                continue
            chat = Chat("agy", kennung, _text(titel), _agy_ordner(arbeit), zeit, "agy")
            bisher = chats.get(kennung)
            if bisher is None or chat.zuletzt > bisher.zuletzt:
                chats[kennung] = chat
    if not vorhanden:
        return [], "fehlt"
    if not gelesen:
        if schema_falsch == vorhanden:
            return [], "schema unbekannt"
        return [], _grund(letzter) if letzter else "nicht lesbar"
    return list(chats.values()), "ok"


# --- Zusammenführen -----------------------------------------------------------------

def _sicher(quelle: Callable[[datetime], tuple[list[Chat], str]],
            grenze: datetime) -> tuple[list[Chat], str]:
    """Jede Ausnahme einer Quelle wird zu deren Status; die anderen Quellen laufen weiter."""
    try:
        return quelle(grenze)
    except Exception as fehler:  # noqa: BLE001 - bewusst breit: eine Quelle darf nie das Register stoppen
        return [], _grund(fehler)


def lesen(jetzt: datetime | None = None, fenster: timedelta = timedelta(hours=24)) -> Ergebnis:
    """Alle in `fenster` benutzten Chats aller Quellen, neueste zuerst; wirft nie.

    Je `(werkzeug, kennung)` höchstens ein Eintrag: `claude-desktop` verdrängt `claude-cli`,
    innerhalb einer Quelle gewinnt die jüngere Nutzung. Eine in Claude Desktop archivierte Sitzung
    kommt auch über `claude-cli` nicht zurück. Zeiten mehr als `ZUKUNFT_TOLERANZ` nach `jetzt` werden
    verworfen (die Toleranz deckt Dateien ab, in die ein laufender Chat gerade schreibt).
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    if jetzt.tzinfo is None:
        jetzt = jetzt.replace(tzinfo=timezone.utc)
    grenze = jetzt - fenster
    quellen: dict[str, str] = {}
    gesammelt: dict[tuple[str, str], Chat] = {}
    archiviert: set[str] = set()
    for name, funktion in (("claude-desktop", lambda g: _claude_desktop(g, archiviert)),
                           ("claude-cli", _claude_cli), ("codex", _codex),
                           ("hermes", _hermes), ("agy", _agy)):
        chats, status = _sicher(funktion, grenze)
        quellen[name] = status
        for chat in chats:
            if chat.zuletzt > jetzt + ZUKUNFT_TOLERANZ:
                continue
            if chat.quelle == "claude-cli" and chat.kennung in archiviert:
                continue
            schluessel = (chat.werkzeug, chat.kennung)
            bisher = gesammelt.get(schluessel)
            if bisher is None or (bisher.quelle == chat.quelle and chat.zuletzt > bisher.zuletzt):
                gesammelt[schluessel] = chat
    geordnet = sorted(gesammelt.values(), key=lambda c: (c.zuletzt, c.kennung), reverse=True)
    return Ergebnis(tuple(geordnet), quellen)
