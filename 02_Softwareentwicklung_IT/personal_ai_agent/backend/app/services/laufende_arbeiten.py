"""Was laeuft gerade im Hintergrund? — Datenquelle fuer die Statusleiste.

Befund (Sebastian, 10.10.2026): "muss jederzeit ersichtlich sein, welche
Hintergrundprozesse laufen" — gestern lief eine Bildanalyse 20 bis 30 Minuten,
im Chat war nichts davon zu sehen. Der Endpunkt ``GET /api/laeuft``
(``app/router/laeuft.py``) fasst deshalb die drei Quellen zusammen, die es im
Projekt wirklich gibt:

1. ``backend_arbeiten()`` — Arbeiten, die sich im Serverprozess ANMELDEN
   (``merke_start``/``beende``; asyncio-Tasks ueber ``merke_task``, das sich
   beim Ende selbst wieder abmeldet). Angemeldet wird u. a. jede
   Werkzeug-Ausfuehrung der Schleife (``werkzeug_schleife``) — lange Suchen
   und Scans sind so sichtbar, waehrend sie laufen.
   BEWUSST keine rohe ``asyncio.all_tasks()``-Liste: die enthaelt im Betrieb
   die Server- und Verbindungs-Tasks von uvicorn selbst. Damit stuende dort
   IMMER etwas, und "Keine Hintergrundarbeit" waere nie wahr.
2. ``auftraege_laufend()`` — Auftraege im Buch mit Status ``laeuft``
   (Track C: der lokale Hermes bearbeitet eine Aufgabe). Bewusst NUR
   ``laeuft``: ``offen`` ist eine Warteschlange, kein laufender Prozess.
3. ``protokolle()`` — Protokolldateien ``*.log`` in den bekannten,
   kabel-lesbaren Ordnern auf dem Geraet (``hermes_diag``,
   ``termux-sicherung``); je Datei die letzte Zeile und ein erkannter
   Fortschritt (z. B. "1234 von 17580" oder "7 %").

Je Eintrag liefert der Endpunkt: Name, Art, Zustand, Startzeit (``seit``),
Dauer, letzte Zeile und Fortschritt (soweit erkennbar).

Regeln: rein lesend, fehlertolerant — fehlende Ordner/Dateien und kaputte
Zeilen stoeren nie, keine Ausnahme verlaesst dieses Modul. Sortierung:
laufende Eintraege zuerst, darin die am laengsten laufenden oben.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Ordner unterhalb der geteilten Download-Ablage, in denen Protokolle liegen.
LOG_ORDNER = ("hermes_diag", "termux-sicherung")
LOG_MUSTER = "*.log"

# Eine Protokolldatei gilt als "laeuft", wenn ihr letzter Schreibzugriff
# hoechstens so lange her ist. Darueber ist sie "steht" (abgeschlossener oder
# abgebrochener Lauf) — nie als laufende Arbeit ausgeben, was steht.
FRISCH_SEKUNDEN = 180

# Obergrenzen, damit die Antwort klein bleibt.
MAX_ZEILEN_PROTOKOLL = 1  # je Datei nur die letzte Zeile
MAX_ZEICHEN_ZEILE = 300
TAIL_BYTES = 8192

_FORTSCHRITT_VON = re.compile(r"(\d+)\s*(?:von|/)\s*(\d+)")
_FORTSCHRITT_PROZENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_ISO_PRAEFIX = re.compile(r"^(?:\[[^\]]*\]\s*)+")  # auch mehrfach (Meldung + Buch-Stempel)

# ── Anmeldung laufender Backend-Arbeiten ────────────────────────────────────

_REGISTER: Dict[str, Dict[str, Any]] = {}
_REGISTER_SPERRE = threading.Lock()


def merke_start(name: str, *, art: str = "arbeit", detail: str = "") -> str:
    """Meldet eine laufende Hintergrundarbeit an. Liefert die Kennung.

    Wirft nie. Wird die Arbeit beendet, ``beende(kennung)`` aufrufen.
    """
    kennung = f"arb-{uuid.uuid4().hex[:12]}"
    eintrag = {
        "name": (str(name or "").strip() or "Hintergrundarbeit")[:200],
        "art": (str(art or "arbeit").strip() or "arbeit")[:30],
        "detail": (str(detail or "").strip())[:300],
        "start": time.time(),
        "zustand": "laeuft",
        "letzte_zeile": "",
        "fortschritt": "",
    }
    try:
        with _REGISTER_SPERRE:
            _REGISTER[kennung] = eintrag
    except Exception:  # pragma: no cover - darf nie den Aufrufer brechen
        logger.warning("Hintergrundarbeit nicht angemeldet: %s", eintrag["name"])
    return kennung


def setze(
    kennung: str,
    *,
    zustand: Optional[str] = None,
    letzte_zeile: Optional[str] = None,
    fortschritt: Optional[str] = None,
) -> None:
    """Aktualisiert eine angemeldete Arbeit (Zustand/letzte Zeile/Fortschritt)."""
    try:
        with _REGISTER_SPERRE:
            eintrag = _REGISTER.get(kennung)
            if eintrag is None:
                return
            if zustand is not None:
                eintrag["zustand"] = str(zustand)[:30]
            if letzte_zeile is not None:
                eintrag["letzte_zeile"] = str(letzte_zeile)[:MAX_ZEICHEN_ZEILE]
            if fortschritt is not None:
                eintrag["fortschritt"] = str(fortschritt)[:120]
    except Exception:  # pragma: no cover
        logger.warning("Hintergrundarbeit nicht aktualisiert (%s)", kennung)


def beende(kennung: str) -> None:
    """Meldet eine angemeldete Arbeit wieder ab. Wirft nie."""
    try:
        with _REGISTER_SPERRE:
            _REGISTER.pop(kennung, None)
    except Exception:  # pragma: no cover
        logger.warning("Hintergrundarbeit nicht abgemeldet (%s)", kennung)


def merke_task(task: Any, name: str = "") -> str:
    """Meldet einen laufenden asyncio-Task an und meldet ihn beim Ende ab.

    Damit sind echte asyncio-Hintergrund-Tasks sichtbar (Name, Startzeit,
    Zustand), ohne dass rohe Framework-Tasks mitgezaehlt werden. Der
    done-Callback raeumt den Eintrag automatisch weg (auch bei Abbruch/Fehler).
    """
    beschreibung = str(name or "").strip()
    if not beschreibung:
        try:
            beschreibung = f"Aufgabe {task.get_name()}"
        except Exception:
            beschreibung = "Aufgabe"
    kennung = merke_start(beschreibung, art="task")
    try:
        task.add_done_callback(lambda _t: beende(kennung))
    except Exception:  # pragma: no cover - Nicht-Task uebergeben
        logger.warning("Kein gueltiger Task fuer die Anmeldung: %s", beschreibung)
    return kennung


# ── Gemeinsame Bausteine ────────────────────────────────────────────────────

def _iso(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).astimezone().isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return ""


def _dauer(ts: Optional[float], jetzt: float) -> Optional[int]:
    try:
        if ts is None:
            return None
        return max(0, int(jetzt - float(ts)))
    except (TypeError, ValueError):
        return None


def _eintrag(
    name: str,
    art: str,
    zustand: str,
    seit_ts: Optional[float],
    jetzt: float,
    letzte_zeile: str = "",
    fortschritt: str = "",
) -> Dict[str, Any]:
    return {
        "name": str(name or "Hintergrundarbeit")[:200],
        "art": art,
        "zustand": zustand,
        "seit": _iso(seit_ts) if seit_ts else "",
        "dauer_sekunden": _dauer(seit_ts, jetzt),
        "letzte_zeile": str(letzte_zeile or "")[:MAX_ZEICHEN_ZEILE],
        "fortschritt": str(fortschritt or "")[:120],
    }


def fortschritt_aus_text(text: str) -> str:
    """Erkennt einfachen Fortschritt in einer Protokollzeile.

    Erkannt werden "N von M", "N/M" und "X %" (deutsches Komma erlaubt).
    Ohne Treffer: leerer Text ("nicht erkennbar") — es wird nichts geraten.
    """
    zeile = str(text or "")
    treffer = _FORTSCHRITT_VON.search(zeile)
    if treffer:
        return f"{treffer.group(1)} von {treffer.group(2)}"
    treffer = _FORTSCHRITT_PROZENT.search(zeile)
    if treffer:
        return f"{treffer.group(1).replace('.', ',')} %"
    return ""


# ── Quelle 1: angemeldete Backend-Arbeiten ──────────────────────────────────

def backend_arbeiten(jetzt: Optional[float] = None) -> List[Dict[str, Any]]:
    jetzt_f = time.time() if jetzt is None else jetzt
    try:
        with _REGISTER_SPERRE:
            roh = [dict(e) for e in _REGISTER.values()]
    except Exception:  # pragma: no cover
        return []
    eintraege = []
    for e in roh:
        start = e.get("start")
        eintraege.append(_eintrag(
            e.get("name") or "Hintergrundarbeit",
            e.get("art") or "arbeit",
            e.get("zustand") or "laeuft",
            start,
            jetzt_f,
            letzte_zeile=e.get("letzte_zeile") or "",
            fortschritt=e.get("fortschritt") or "",
        ))
    return eintraege


# ── Quelle 2: laufende Auftraege im Buch (Track C) ──────────────────────────

def _ts_aus_iso(wert: Any) -> Optional[float]:
    """ISO-Zeitstempel (mit/ohne Zeitzone) in Sekunden — sonst None."""
    text = str(wert or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def auftraege_laufend(jetzt: Optional[float] = None) -> List[Dict[str, Any]]:
    jetzt_f = time.time() if jetzt is None else jetzt
    try:
        from app.services.auftrag_service import auftrag_service

        alle = auftrag_service.alle(limit=50)
    except Exception as fehler:
        logger.warning("Auftragsbuch fuer /api/laeuft nicht lesbar: %s", fehler)
        return []
    eintraege = []
    for auftrag in alle or []:
        if not isinstance(auftrag, dict) or auftrag.get("status") != "laeuft":
            continue
        aufgabe = str(auftrag.get("auftrag") or "").strip()
        kurz = aufgabe.splitlines()[0].strip() if aufgabe else ""
        name = f"Hermes: {kurz[:140]}" if kurz else "Hermes-Auftrag"
        meldungen = auftrag.get("status_meldungen") or []
        letzte = ""
        if meldungen:
            letzte = _ISO_PRAEFIX.sub("", str(meldungen[-1] or "")).strip()
        start = _ts_aus_iso(auftrag.get("abgeholt")) or _ts_aus_iso(auftrag.get("erstellt"))
        eintraege.append(_eintrag(
            name, "hermes", "laeuft", start, jetzt_f,
            letzte_zeile=letzte, fortschritt=fortschritt_aus_text(letzte),
        ))
    return eintraege


# ── Quelle 3: Protokolldateien in den bekannten Ordnern ─────────────────────

def _log_basen() -> List[str]:
    """Basis-Orte der kabel-lesbaren Protokollordner.

    Reihenfolge: Umgebungs-Override (Tests), Termux-Realitaet
    ``~/storage/downloads``, Auffangpfad ``/sdcard/Download``.
    """
    ueber = os.environ.get("LAEUFT_LOG_BASIS", "").strip()
    if ueber:
        return [ueber]
    heim = os.path.expanduser("~")
    return [os.path.join(heim, "storage", "downloads"), "/sdcard/Download"]


def letzte_zeile(pfad: str) -> str:
    """Letzte nicht-leere Zeile einer Datei — nur das Dateiende wird gelesen.

    Wirft nie; fehlende/unlesbare Dateien ergeben "".
    """
    try:
        groesse = os.path.getsize(pfad)
        with open(pfad, "rb") as datei:
            if groesse > TAIL_BYTES:
                datei.seek(-TAIL_BYTES, os.SEEK_END)
            roh = datei.read()
        text = roh.decode("utf-8", errors="replace")
        for zeile in reversed(text.splitlines()):
            sauber = zeile.strip()
            if sauber:
                return sauber[:MAX_ZEICHEN_ZEILE]
        return ""
    except OSError:
        return ""
    except Exception as fehler:  # pragma: no cover - absichtlich breit
        logger.warning("Protokollzeile nicht lesbar (%s): %s", pfad, fehler)
        return ""


def _protokoll_eintrag(pfad: str, jetzt: float) -> Optional[Dict[str, Any]]:
    try:
        zustand_info = os.stat(pfad)
    except OSError:
        return None
    letzte = letzte_zeile(pfad)
    if zustand_info.st_size == 0:
        zustand = "leer"
    elif jetzt - zustand_info.st_mtime <= FRISCH_SEKUNDEN:
        zustand = "laeuft"
    else:
        zustand = "steht"
    return {
        "eintrag": _eintrag(
            f"Protokoll {os.path.basename(pfad)}",
            "protokoll",
            zustand,
            zustand_info.st_mtime,
            jetzt,
            letzte_zeile=letzte,
            fortschritt=fortschritt_aus_text(letzte),
        ),
        "mtime": zustand_info.st_mtime,
    }


def protokolle(jetzt: Optional[float] = None) -> List[Dict[str, Any]]:
    jetzt_f = time.time() if jetzt is None else jetzt
    gesehen: set = set()
    roh: List[Dict[str, Any]] = []
    for basis in _log_basen():
        for ordner in LOG_ORDNER:
            verzeichnis = os.path.join(basis, ordner)
            try:
                if not os.path.isdir(verzeichnis):
                    continue
                pfade = sorted(glob.glob(os.path.join(verzeichnis, LOG_MUSTER)))
            except OSError as fehler:  # pragma: no cover
                logger.warning("Protokollordner nicht lesbar (%s): %s", verzeichnis, fehler)
                continue
            for pfad in pfade:
                try:
                    schluessel = os.path.realpath(pfad)
                except OSError:
                    schluessel = pfad
                if schluessel in gesehen:
                    continue  # ~/storage/downloads und /sdcard/Download koennen dasselbe sein
                gesehen.add(schluessel)
                gebaut = _protokoll_eintrag(pfad, jetzt_f)
                if gebaut:
                    roh.append(gebaut)
    roh.sort(key=lambda g: g["mtime"], reverse=True)
    return [g["eintrag"] for g in roh]


# ── Alles zusammen ──────────────────────────────────────────────────────────

def _sortierschluessel(eintrag: Dict[str, Any]) -> tuple:
    laeuft = 0 if eintrag.get("zustand") == "laeuft" else 1
    seit = eintrag.get("seit") or ""
    return (laeuft, seit)


def alles(jetzt: Optional[float] = None) -> Dict[str, Any]:
    """Alle bekannten Hintergrundarbeiten als EIN Dict (fuer den Endpunkt).

    Wirft nie: faellt eine Quelle aus, liefert sie eben nichts.
    """
    jetzt_f = time.time() if jetzt is None else jetzt
    arbeiten: List[Dict[str, Any]] = []
    for quelle in (backend_arbeiten, auftraege_laufend, protokolle):
        try:
            arbeiten.extend(quelle(jetzt=jetzt_f))
        except Exception as fehler:  # pragma: no cover - darf nie hochschlagen
            logger.warning("Quelle %s fuer /api/laeuft ausgefallen: %s",
                           getattr(quelle, "__name__", quelle), fehler)
    arbeiten.sort(key=_sortierschluessel)
    return {
        "anzahl": len(arbeiten),
        "keine": not arbeiten,
        "arbeiten": arbeiten,
    }
