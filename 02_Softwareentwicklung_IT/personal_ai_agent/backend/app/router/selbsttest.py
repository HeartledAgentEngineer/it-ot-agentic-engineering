"""Router: Selbsttest – GET /api/selbsttest

Warum es diesen Endpunkt gibt
-----------------------------
Das Backend läuft auf Sebastians Android-Handy in Termux. Wenn er unterwegs
ist, hat er kein Kabel (kein ADB) und kann nicht in die Termux-Konsole sehen –
er sieht nur, was die App selbst anzeigt. Bisher gab es keinen Ort, an dem der
Zustand des Systems ablesbar war: Commit-Stand, Archiv-Index, Inbox-Daemon,
letzte Protokollzeilen, Erinnerungen, Sprachmodelle, Serverzeit.

Dieser Endpunkt liefert genau das als JSON. Die Oberfläche (Blatt
„Selbsttest") macht daraus deutsche Klartext-Zeilen mit ✓/⚠/✗ — so lässt sich
der Zustand als Bildschirmfoto per Telegram teilen.

Eiserne Regeln
--------------
  * JEDES Feld ist IMMER vorhanden. Fehlt eine Quelle (Datei weg, git nicht
    installiert, Daemon nicht feststellbar), trägt das Feld einen ``error``-Text
    statt eines Werts — der Endpunkt antwortet trotzdem mit HTTP 200.
  * NIEMALS ein 500er. Jeder Block hat sein eigenes try/except mit Logging;
    ein unerwarteter Fehler wird als Text gemeldet, nicht als Absturz.
  * KEINE Geheimnisse. Es werden ausschließlich Namen (Modellketten), Pfade,
    Größen, Zähler und gekürzte Protokollzeilen ausgegeben — nie ein
    API-Schlüssel, nie ein Token. Die Protokoll-Auszüge sind bewusst auf
    :data:`AUSZUG_LAENGE` Zeichen gekürzt.
  * Nur lesend. Die Archiv-Datenbank wird mit ``mode=ro`` geöffnet.

Die Protokoll-/Postfach-Pfade folgen dem Muster der übrigen Router
(``~/hermes_inbox/``, ``~/archiv_index.db``) und sind über
:func:`index_pfad` / :func:`inbox_dir` kapselbar, damit Tests sie auf ein
temporäres Verzeichnis umbiegen können.
"""

import logging
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from app.config import BASE_DIR
from app.db.chroma_client import chroma_client
from app.services.llm_service import TRANSCRIBE_MODELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["selbsttest"])

# Wie viele Zeichen eines Protokoll-Auszugs höchstens ausgeliefert werden.
# Bewusst gekürzt: Die Zeilen können lang werden, und ein Bildschirmfoto soll
# lesbar bleiben. Ein eventuell vorhandener Schlüssel in einer Logzeile wird
# damit abgeschnitten, nicht ausgeliefert.
AUSZUG_LAENGE = 200

# Wie viele der letzten Logzeilen gezeigt werden.
LOG_LETZTE_ZEILEN = 3

# Zeitbudget für die SQLite-Zählung. Der Archiv-Index ist ~260 MB groß; ein
# COUNT(*) darüber braucht einen Moment, darf den Endpunkt aber nicht hängen.
DB_TIMEOUT_S = 3.0

# Name des Inbox-Daemon-Skripts (Wiedererkennung in der Prozessliste).
DAEMON_SKRIPT = "hermes_inbox_daemon.py"


# ── Pfade (kapselbar für Tests) ──────────────────────────────────────────────

def index_pfad() -> str:
    """Pfad zum Archiv-Index auf dem Gerät (``~/archiv_index.db``)."""
    return os.path.join(os.path.expanduser("~"), "archiv_index.db")


def inbox_dir() -> str:
    """Pfad zum Postfach/Protokoll (``~/hermes_inbox``)."""
    return os.path.join(os.path.expanduser("~"), "hermes_inbox")


# ── kleine Helfer ────────────────────────────────────────────────────────────

def _kuerzen(text: Any, laenge: int = AUSZUG_LAENGE) -> str:
    """Text auf ``laenge`` Zeichen kürzen (Zeilenumbrüche zu Leerzeichen).

    Wird für Protokoll-Auszüge benutzt. ``None`` wird zu leerem String, damit
    die JSON-Ausgabe stabil bleibt.
    """
    if text is None:
        return ""
    einzeilig = str(text).replace("\r", " ").replace("\n", " ").strip()
    return einzeilig[:laenge]


def _letzte_zeilen(pfad: str, anzahl: int = LOG_LETZTE_ZEILEN,
                   max_bytes: int = 16384) -> List[str]:
    """Die letzten ``anzahl`` nicht-leeren Zeilen einer Textdatei.

    Es wird nur das Dateiende gelesen (``max_bytes``), nicht die ganze Datei:
    ``daemon.log`` kann über Monate groß werden, und der Endpunkt soll
    schnell bleiben.
    """
    try:
        groesse = os.path.getsize(pfad)
        with open(pfad, "rb") as f:
            if groesse > max_bytes:
                f.seek(groesse - max_bytes)
            rohdaten = f.read()
        text = rohdaten.decode("utf-8", "replace")
        # Beim Sprung in die Dateimitte kann die erste Zeile angeschnitten sein
        # — sie wird verworfen, wenn der Puffer voll war.
        zeilen = text.splitlines()
        if groesse > max_bytes and zeilen:
            zeilen = zeilen[1:]
        zeilen = [z.strip() for z in zeilen if z.strip()]
        return [_kuerzen(z) for z in zeilen[-anzahl:]]
    except OSError as e:
        logger.warning("Selbsttest: Log nicht lesbar (%s): %s", pfad, e)
        return []


def _letzte_nicht_leere_zeile(pfad: str) -> Optional[str]:
    """Letzte inhaltliche Zeile einer JSONL-Datei (ohne Zeilenumbruch)."""
    gefunden: Optional[str] = None
    with open(pfad, "r", encoding="utf-8", errors="replace") as f:
        for zeile in f:
            if zeile.strip():
                gefunden = zeile.strip()
    return gefunden


def _zeilen_zaehlen(pfad: str) -> int:
    """Anzahl nicht-leerer Zeilen (die Protokolldateien sind klein)."""
    anzahl = 0
    with open(pfad, "r", encoding="utf-8", errors="replace") as f:
        for zeile in f:
            if zeile.strip():
                anzahl += 1
    return anzahl


# ── Block: letzter git-Commit ────────────────────────────────────────────────

def _letzter_commit() -> Dict[str, Any]:
    """Letzter Commit im Repo über ``git log --oneline -1``.

    Abgesichert gegen alles: fehlendes git, kaputtes Repo, Hänger. Statt einer
    Ausnahme kommt ein ``error``-Text zurück.
    """
    ergebnis: Dict[str, Any] = {"ok": False, "zeile": None, "error": None}
    try:
        lauf = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=8,
        )
    except FileNotFoundError:
        ergebnis["error"] = "git ist auf diesem Gerät nicht installiert"
        return ergebnis
    except subprocess.TimeoutExpired:
        ergebnis["error"] = "git log hat zu lange gebraucht (Timeout)"
        return ergebnis
    except Exception as e:  # noqa: BLE001 – bewusst breit, nie 500
        logger.warning("Selbsttest: git-Abfrage fehlgeschlagen: %s", e)
        ergebnis["error"] = f"git-Abfrage fehlgeschlagen ({type(e).__name__})"
        return ergebnis

    if lauf.returncode != 0:
        stderr = _kuerzen(lauf.stderr or "")
        ergebnis["error"] = f"git log Exit {lauf.returncode}: {stderr}" if stderr \
            else f"git log Exit {lauf.returncode}"
        return ergebnis

    zeilen = [z for z in (lauf.stdout or "").splitlines() if z.strip()]
    if not zeilen:
        ergebnis["error"] = "git log lieferte keine Zeile (leeres Repo?)"
        return ergebnis

    ergebnis["ok"] = True
    ergebnis["zeile"] = _kuerzen(zeilen[0])
    return ergebnis


# ── Block: Archiv-Index ──────────────────────────────────────────────────────

def _index_info() -> Dict[str, Any]:
    """Zustand des Archiv-Index (``~/archiv_index.db``).

    Nur Größe und Zähler — die Datenbank bleibt unangetastet (``mode=ro``).
    Fehlt sie oder sind Tabellen nicht lesbar, steht das als ``error`` drin.
    """
    pfad = index_pfad()
    info: Dict[str, Any] = {
        "pfad": pfad,
        "existiert": False,
        "groesse_mb": None,
        "nachrichten": None,
        "chunks": None,
        "error": None,
    }

    try:
        if not os.path.isfile(pfad):
            info["error"] = "Archiv-Index nicht gefunden"
            return info
        info["existiert"] = True
        info["groesse_mb"] = round(os.path.getsize(pfad) / (1024 * 1024), 1)
    except OSError as e:
        logger.warning("Selbsttest: Index nicht prüfbar (%s): %s", pfad, e)
        info["error"] = f"Index nicht prüfbar ({type(e).__name__})"
        return info

    # Zählung getrennt abgesichert: Die Datei kann existieren und trotzdem
    # keine dieser Tabellen haben (anderer Aufbau) — Größe bleibt dann gültig.
    fehler: List[str] = []
    try:
        uri = Path(pfad).as_uri() + "?mode=ro"
        verbindung = sqlite3.connect(uri, uri=True, timeout=DB_TIMEOUT_S)
        try:
            verbindung.execute("PRAGMA query_only = ON")
            for tabelle in ("nachrichten", "chunks"):
                try:
                    kurser = verbindung.execute(f"SELECT COUNT(*) FROM {tabelle}")
                    info[tabelle] = int(kurser.fetchone()[0])
                except sqlite3.Error as e:
                    logger.warning("Selbsttest: Tabelle %s nicht zählbar: %s", tabelle, e)
                    fehler.append(f"{tabelle} nicht zählbar")
        finally:
            verbindung.close()
    except sqlite3.Error as e:
        logger.warning("Selbsttest: Index nicht öffenbar (%s): %s", pfad, e)
        fehler.append(f"Datenbank nicht lesbar ({type(e).__name__})")

    if fehler:
        info["error"] = "; ".join(fehler)
    return info


# ── Block: Inbox-Daemon ──────────────────────────────────────────────────────

def _daemon_laeuft() -> Optional[bool]:
    """Läuft ``hermes_inbox_daemon.py``? True/False, oder None = unklar.

    Erst ``pgrep`` (Termux/Android, Linux), dann die Prozessliste ``/proc``.
    Findet sich beides nicht (z. B. Windows), ist die Antwort „unklar" (None)
    statt einer falschen Behauptung.
    """
    pgrep = shutil.which("pgrep")
    if pgrep:
        try:
            lauf = subprocess.run(
                [pgrep, "-f", DAEMON_SKRIPT],
                capture_output=True, text=True, timeout=5,
            )
            return bool(lauf.stdout.strip())
        except Exception as e:  # noqa: BLE001 – dann weiter zu /proc
            logger.warning("Selbsttest: pgrep fehlgeschlagen: %s", e)

    if os.path.isdir("/proc"):
        try:
            for eintrag in os.listdir("/proc"):
                if not eintrag.isdigit():
                    continue
                try:
                    with open(f"/proc/{eintrag}/cmdline", "rb") as f:
                        kommandos = f.read().decode("utf-8", "replace")
                except OSError:
                    continue
                if DAEMON_SKRIPT in kommandos:
                    return True
            return False
        except Exception as e:  # noqa: BLE001 – nie 500
            logger.warning("Selbsttest: /proc nicht durchsuchbar: %s", e)

    return None


def _daemon_info() -> Dict[str, Any]:
    """Daemon-Zustand + Größe, Alter und die letzten Zeilen von ``daemon.log``."""
    log_pfad = os.path.join(inbox_dir(), "daemon.log")
    info: Dict[str, Any] = {
        "laeuft": None,
        "log_pfad": log_pfad,
        "log_groesse_bytes": None,
        "log_alter_s": None,
        "log_letzte_zeilen": [],
        "error": None,
    }

    try:
        info["laeuft"] = _daemon_laeuft()
    except Exception as e:  # noqa: BLE001 – nie 500
        logger.warning("Selbsttest: Daemon-Prüfung fehlgeschlagen: %s", e)
        info["error"] = f"Daemon-Prüfung fehlgeschlagen ({type(e).__name__})"

    try:
        if os.path.isfile(log_pfad):
            stat = os.stat(log_pfad)
            info["log_groesse_bytes"] = stat.st_size
            info["log_alter_s"] = round(max(0.0, time.time() - stat.st_mtime), 1)
            info["log_letzte_zeilen"] = _letzte_zeilen(log_pfad)
        else:
            hinweis = "daemon.log fehlt"
            info["error"] = f"{info['error']}; {hinweis}" if info["error"] else hinweis
    except OSError as e:
        logger.warning("Selbsttest: daemon.log nicht lesbar: %s", e)
        hinweis = f"daemon.log nicht lesbar ({type(e).__name__})"
        info["error"] = f"{info['error']}; {hinweis}" if info["error"] else hinweis

    return info


# ── Block: letzte Antwort / Status ───────────────────────────────────────────

def _jsonl_info(dateiname: str) -> Dict[str, Any]:
    """Länge und gekürzter Auszug der letzten Zeile einer JSONL-Datei.

    Bewusst gekürzt (:data:`AUSZUG_LAENGE`): Der volle Inhalt einer Antwort ist
    für die Zustandsprüfung nicht nötig, und ein Bildschirmfoto soll lesbar
    bleiben. Zusätzlich werden nur Länge und Auszug ausgegeben — nicht die
    ganze Datei.
    """
    pfad = os.path.join(inbox_dir(), dateiname)
    info: Dict[str, Any] = {
        "pfad": pfad,
        "existiert": False,
        "zeilen": None,
        "laenge": None,
        "auszug": None,
        "error": None,
    }

    try:
        if not os.path.isfile(pfad):
            info["error"] = f"{dateiname} fehlt"
            return info
        info["existiert"] = True

        letzte = _letzte_nicht_leere_zeile(pfad)
        if letzte is None:
            info["zeilen"] = 0
            info["laenge"] = 0
            info["auszug"] = ""
            info["error"] = "keine Zeilen"
            return info

        info["zeilen"] = _zeilen_zaehlen(pfad)
        info["laenge"] = len(letzte)
        info["auszug"] = _kuerzen(letzte)
    except OSError as e:
        logger.warning("Selbsttest: %s nicht lesbar: %s", dateiname, e)
        info["error"] = f"{dateiname} nicht lesbar ({type(e).__name__})"

    return info


def _letzte_antwort_info() -> Dict[str, Any]:
    """Antwort- und Status-Protokoll des Postfachs."""
    blocks: Dict[str, Any] = {}
    for name, schluessel in (("antworten.jsonl", "antworten"), ("status.jsonl", "status")):
        try:
            blocks[schluessel] = _jsonl_info(name)
        except Exception as e:  # noqa: BLE001 – nie 500
            logger.warning("Selbsttest: %s nicht auswertbar: %s", name, e)
            blocks[schluessel] = {
                "pfad": os.path.join(inbox_dir(), name),
                "existiert": False,
                "zeilen": None,
                "laenge": None,
                "auszug": None,
                "error": f"Auswertung fehlgeschlagen ({type(e).__name__})",
            }
    return blocks


# ── Block: Gedächtnis ────────────────────────────────────────────────────────

def _gedaechtnis_anzahl() -> int:
    """Anzahl Erinnerungen — derselbe Weg wie ``/api/memory/count``."""
    return chroma_client.count()


def _gedaechtnis_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"anzahl": None, "error": None}
    try:
        info["anzahl"] = int(_gedaechtnis_anzahl())
    except Exception as e:  # noqa: BLE001 – nie 500
        logger.warning("Selbsttest: Gedächtnis nicht zählbar: %s", e)
        info["error"] = f"Gedächtnis nicht lesbar ({type(e).__name__})"
    return info


# ── Block: Sprache ───────────────────────────────────────────────────────────

def _sprache_info() -> Dict[str, Any]:
    """Erkennungsmodelle der Kette und ob die Sprach-Endpunkte registriert sind."""
    info: Dict[str, Any] = {
        "modelle": [],
        "transcribe_registriert": False,
        "speak_registriert": False,
        "error": None,
    }

    try:
        info["modelle"] = [
            eintrag[0] if isinstance(eintrag, (tuple, list)) else str(eintrag)
            for eintrag in TRANSCRIBE_MODELS
        ]
    except Exception as e:  # noqa: BLE001 – nie 500
        logger.warning("Selbsttest: Modellkette nicht lesbar: %s", e)
        info["error"] = f"Modellkette nicht lesbar ({type(e).__name__})"

    try:
        # Erst hier importieren: main.py importiert diesen Router, ein
        # Import auf Modulebene wäre ein Ringschluss.
        from app.main import app as _app

        for route in getattr(_app, "routes", []):
            pfad = getattr(route, "path", None)
            methoden = getattr(route, "methods", set()) or set()
            if pfad == "/api/transcribe" and "POST" in methoden:
                info["transcribe_registriert"] = True
            elif pfad == "/api/speak" and "POST" in methoden:
                info["speak_registriert"] = True
    except Exception as e:  # noqa: BLE001 – nie 500
        logger.warning("Selbsttest: Routen nicht prüfbar: %s", e)
        hinweis = f"Routen nicht prüfbar ({type(e).__name__})"
        info["error"] = f"{info['error']}; {hinweis}" if info["error"] else hinweis

    return info


# ── Block: Uhrzeit ───────────────────────────────────────────────────────────

def _uhrzeit_info() -> Dict[str, Any]:
    """Aktuelle Serverzeit (für die Zeitstempel-Prüfung).

    Der Nutzer hatte gemeldet, dass Zeitstempel VOR dem Text erschienen — mit
    dieser Angabe lässt sich vergleichen, ob die Serverzeit zur erwarteten
    Zeit passt. ``iso`` ist maschinenlesbar, ``lokal`` fürs Auge.
    """
    jetzt = datetime.now(timezone.utc).astimezone()
    return {
        "iso": jetzt.isoformat(timespec="seconds"),
        "lokal": jetzt.strftime("%d.%m.%Y %H:%M:%S"),
        "zeitzone": jetzt.tzname() or "",
        "error": None,
    }


# ── Endpunkt ─────────────────────────────────────────────────────────────────

@router.get("/selbsttest")
def selbsttest() -> Dict[str, Any]:
    """Selbsttest des Systems als JSON — jedes Feld immer vorhanden, nie 500.

    Bewusst ``def`` statt ``async def``: SQLite-Zählung und ``git``/``pgrep``
    sind blockierend. Synchron schiebt FastAPI den Aufruf in einen Threadpool,
    statt den Event-Loop (und damit laufende Chat-Streams) anzuhalten.
    """
    ergebnis: Dict[str, Any] = {
        "commit": {"ok": False, "zeile": None, "error": "nicht geprüft"},
        "index": {"pfad": None, "existiert": False, "groesse_mb": None,
                  "nachrichten": None, "chunks": None, "error": "nicht geprüft"},
        "daemon": {"laeuft": None, "log_pfad": None, "log_groesse_bytes": None,
                   "log_alter_s": None, "log_letzte_zeilen": [], "error": "nicht geprüft"},
        "letzte_antwort": {"antworten": None, "status": None},
        "gedaechtnis": {"anzahl": None, "error": "nicht geprüft"},
        "sprache": {"modelle": [], "transcribe_registriert": False,
                    "speak_registriert": False, "error": "nicht geprüft"},
        "uhrzeit": {"iso": None, "lokal": None, "zeitzone": None, "error": "nicht geprüft"},
    }

    # Jeder Block einzeln abgesichert: Ein Fehler in einem Bereich darf die
    # übrigen Anzeigen nicht mitreißen und schon gar keinen 500er auslösen.
    for feld, bauer in (
        ("commit", _letzter_commit),
        ("index", _index_info),
        ("daemon", _daemon_info),
        ("letzte_antwort", _letzte_antwort_info),
        ("gedaechtnis", _gedaechtnis_info),
        ("sprache", _sprache_info),
        ("uhrzeit", _uhrzeit_info),
    ):
        try:
            ergebnis[feld] = bauer()
        except Exception as e:  # noqa: BLE001 – nie 500
            logger.error("Selbsttest: Block %s fehlgeschlagen: %s", feld, e)
            ergebnis[feld] = {"error": f"Block {feld} fehlgeschlagen ({type(e).__name__})"}

    return ergebnis
