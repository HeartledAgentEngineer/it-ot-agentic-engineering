"""Server-Protokoll: Ausgaben des Servers in EINE Datei, die die Oberflaeche liest.

To-do Punkt 16 (Sebastian, 16.10.2026): „Frueher war es so, dass in Termux der
Server gesteuert wurde und ich den Verlauf sehen konnte — die Prompts, eine
Liste mit Verbindungen, so ein Log. Das ist nicht mehr moeglich."

Ursache: der Server laeuft abgekoppelt im Hintergrund (damit er das Schliessen
von Termux ueberlebt); seine Ausgaben landen dadurch nirgends sichtbar.

Loesung (zwei getrennte Aufgaben, bewusst getrennt):

* **Schreiben** — ``einrichten()`` haengt einen ``RotatingFileHandler`` an die
  Loggereihenfolge (Wurzel + uvicorn). Zeitstempel und Rotation kommen damit
  aus der Standardbibliothek, nicht aus einem selbstgebauten Filter: eine
  Umleitung der Serverausgabe mit ``|`` wuerde die Abkopplung (``setsid``)
  zerstoeren und den Server wieder an die Sitzung binden, die er ueberleben
  soll.
* **Lesen** — ``protokoll_lesen()`` liefert die letzten Zeilen fuer die Route
  ``GET /api/system/protokoll``. Nur lesend, nie werfend, ohne Dateiinhalte zu
  deuten.

**Geschrieben wird nur, wenn der Startweg den Pfad setzt**
(``AGENT_SERVER_PROTOKOLL``, gesetzt von ``termux/server-protokoll.sh`` ueber
``termux/backend-starten.sh``). Auf einem Rechner ohne diesen Startweg — z. B.
beim Entwickeln oder im Test — entsteht deshalb **keine** Datei im
Heimverzeichnis; die Route meldet das ehrlich als „nicht eingeschaltet".
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import Any

PROTOKOLL_ENV = "AGENT_SERVER_PROTOKOLL"
STANDARD_DATEI = "agent-server.log"
MAX_BYTES = 256 * 1024          # je Datei; darueber wird rotiert
SICHERUNGEN = 2                 # Datei.1, Datei.2
MAX_LESE_BYTES = 256 * 1024     # so viel wird beim Lesen hoechstens angefasst
STANDARD_ZEILEN = 200
MAX_ZEILEN = 1000

# ANSI-Farbschluessel (uvicorn faerbt seine Ausgabe). In der Datei sollen sie
# nicht stehen — die Oberflaeche zeigt Klartext, und Steuerzeichen wuerden dort
# nur als Zeichensalat auftauchen.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

_formatter = logging.Formatter(
    fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# uvicorn setzt in seiner Standardkonfiguration propagate=False; ein Handler
# allein an der Wurzel bekaeme seine Zeilen deshalb NICHT. Darum genau diese
# Namen mitnehmen (uvicorn und uvicorn.error tragen Start/Betrieb, uvicorn.access
# die Zugriffe = Sebastians „Liste mit Verbindungen").
LOGGER_NAMEN = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "app")


def protokoll_pfad() -> Path:
    """Pfad der Protokolldatei: aus der Umgebung, sonst neben dem Heimverzeichnis."""
    roh = (os.environ.get(PROTOKOLL_ENV) or "").strip()
    if roh:
        return Path(roh).expanduser()
    return Path(os.path.expanduser("~")) / STANDARD_DATEI


def eingeschaltet() -> bool:
    """Schreibt dieser Startweg ueberhaupt ein Protokoll?"""
    return bool((os.environ.get(PROTOKOLL_ENV) or "").strip())


def einrichten() -> Path | None:
    """Protokoll einschalten (idempotent). Gibt den Pfad zurueck oder ``None``.

    Ohne gesetzten Pfad (``AGENT_SERVER_PROTOKOLL``) passiert **nichts** — kein
    Schreibzugriff, keine Datei. Wirft nie: ein nicht beschreibbares Protokoll
    darf den Server nicht am Start hindern.
    """
    if not eingeschaltet():
        return None
    pfad = protokoll_pfad()
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            pfad, maxBytes=MAX_BYTES, backupCount=SICHERUNGEN, encoding="utf-8"
        )
        handler.setFormatter(_formatter)
        handler.setLevel(logging.INFO)
        gesetzt = 0
        for name in LOGGER_NAMEN:
            logger = logging.getLogger(name)
            schon_da = any(getattr(h, "_agent_protokoll", False) for h in logger.handlers)
            if schon_da:                       # mehrfacher Start: nicht doppelt anhaengen
                gesetzt += 1
                continue
            handler._agent_protokoll = True    # type: ignore[attr-defined]
            logger.addHandler(handler)
            # Nur einen unbestimmten Pegel auffuellen. Bewusst NICHT hochziehen:
            # app/main.py legt uvicorn.error absichtlich auf ERROR, damit der
            # WARN-Spam von abklopfenden Fremdgeraeten weder Terminal noch
            # Protokoll flutet. uvicorn.access traegt seine Zugriffszeilen
            # (Sebastians „Liste mit Verbindungen") mit eigenem Pegel INFO.
            if logger.level == logging.NOTSET:
                logger.setLevel(logging.INFO)
            gesetzt += 1
        if not gesetzt:
            return pfad
        logger = logging.getLogger(__name__)
        logger.info("Server-Protokoll eingeschaltet: %s", pfad)
        return pfad
    except Exception:                          # noqa: BLE001 — Start darf nie scheitern
        logging.getLogger(__name__).warning(
            "Server-Protokoll konnte nicht eingerichtet werden (%s).", pfad, exc_info=True
        )
        return None


def _letzte_zeilen(pfad: Path, anzahl: int, max_bytes: int) -> tuple[list[str], bool, int]:
    """Letzte ``anzahl`` Zeilen lesen, ohne die ganze Datei zu laden.

    Gibt (Zeilen, gekappt, Groesse) zurueck. ``gekappt`` heisst: es wurde nur
    das Dateiende gelesen — die erste Zeile kann angeschnitten sein und wird
    dann verworfen (sonst stuende ein halber Satz in der Anzeige).
    """
    groesse = pfad.stat().st_size
    with pfad.open("rb") as datei:
        gekappt = groesse > max_bytes
        if gekappt:
            datei.seek(groesse - max_bytes)
        roh = datei.read()
    text = _ANSI.sub("", roh.decode("utf-8", errors="replace"))
    zeilen = text.splitlines()
    if gekappt and zeilen:
        zeilen = zeilen[1:]
    return zeilen[-anzahl:], gekappt, groesse


def protokoll_lesen(anzahl: int = STANDARD_ZEILEN, pfad: Path | None = None,
                    max_bytes: int = MAX_LESE_BYTES) -> dict[str, Any]:
    """Zustand und letzte Zeilen des Server-Protokolls — nur lesend, wirft nie.

    Rueckgabe ist fuer die Oberflaeche gedacht und enthaelt **nur** Zahlen,
    Zeitstempel und die Protokollzeilen selbst (keine Umgebungsdaten, keine
    Zugangsdaten — die Zeilen stammen aus dem Serverprotokoll des Geraets).
    """
    ziel = Path(pfad) if pfad is not None else protokoll_pfad()
    try:
        n = int(anzahl)
    except (TypeError, ValueError):
        n = STANDARD_ZEILEN
    n = max(1, min(n, MAX_ZEILEN))

    ergebnis: dict[str, Any] = {
        "pfad": str(ziel),
        "eingeschaltet": eingeschaltet(),
        "vorhanden": False,
        "groesse": 0,
        "gekappt": False,
        "zeilen": [],
        "hinweis": None,
    }

    try:
        if not ziel.is_file():
            ergebnis["hinweis"] = (
                "Kein Protokoll vorhanden. Es entsteht, wenn der Server ueber den "
                "Startweg des Geraets gestartet wird (termux/backend-starten.sh)."
            )
            return ergebnis
        zeilen, gekappt, groesse = _letzte_zeilen(ziel, n, max_bytes)
        ergebnis["vorhanden"] = True
        ergebnis["gekappt"] = gekappt
        ergebnis["groesse"] = groesse
        ergebnis["zeilen"] = zeilen
        if not zeilen:
            ergebnis["hinweis"] = "Das Protokoll ist leer — der Server hat noch nichts geschrieben."
        elif not ergebnis["eingeschaltet"]:
            ergebnis["hinweis"] = (
                "Protokoll vorhanden, aber in diesem Start nicht eingeschaltet "
                "(Startweg ohne Protokolldatei)."
            )
    except OSError as fehler:
        ergebnis["hinweis"] = f"Protokoll nicht lesbar: {fehler.strerror or fehler}"
    except Exception as fehler:                 # noqa: BLE001 — Anzeige darf nie werfen
        ergebnis["hinweis"] = f"Protokoll nicht lesbar: {fehler}"
    return ergebnis
