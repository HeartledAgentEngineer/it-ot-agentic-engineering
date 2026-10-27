"""Tagesimport im Checks-Fenster (C3, 26.10.2026): Stand lesen, Schalter und Ordner setzen.

Plan: ``.hermes/plans/2026-10-25_tagesimport-handy.md``, Abschnitt "C3 im Einzelnen".

Das Werkzeug ``tools/handy/tageslauf.py`` (C1) schreibt Bericht und Stand und liest die
Schalterdatei. Dieser Dienst zeigt sie an und ändert die Schalterdatei auf Wunsch der
Oberfläche. Das Backend importiert aus ``tools/`` nichts; die Regeln (Ordnerform, Schreiben
atomar, keine Links, nicht im Repo) sind deshalb hier bewusst nachgebaut.

Dateien im Datenordner (Umgebungsvariable ``TAGESLAUF_DATEN``, sonst ``~/foto_sortierung``):
    ``tageslauf.json``           Schalter, Kamera-Ordner, letzter Gemini-Export (gelesen, geschrieben)
    ``tageslauf_bericht.json``   letzter Bericht des Werkzeugs (nur gelesen)
    ``.tageslauf_stand.json``    Stand des letzten vollständigen Laufs (nur gelesen)

Lesen wirft nie und legt nichts an. Schreiben ist Lesen-Ändern-Schreiben: fremde Schlüssel der
Schalterdatei bleiben stehen. Gibt es einen Fehler, bleibt die Datei unverändert.
"""
from __future__ import annotations

import datetime
import json
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple

UMGEBUNG_DATEN = "TAGESLAUF_DATEN"
STANDARD_DATEN = "~/foto_sortierung"
EINSTELLUNGEN_NAME = "tageslauf.json"
BERICHT_NAME = "tageslauf_bericht.json"
STAND_NAME = ".tageslauf_stand.json"

GEMINI_TAGE = 60
KAMERA_MAX_ZEICHEN = 200
LESEN_MAX_BYTES = 1_000_000
BAUSTEINE_MAX = 10
TEXT_MAX = 300

ERLAUBTE_FELDER = ("an", "kamera_ordner", "gemini_export_heute")


class Ablehnung(Exception):
    """Eine Änderung wird nicht ausgeführt. ``status`` ist der HTTP-Status, ``text`` ein fester Satz."""

    def __init__(self, status: int, text: str) -> None:
        super().__init__(text)
        self.status = status
        self.text = text


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _heute() -> datetime.date:
    return datetime.date.today()


def daten_ordner() -> str:
    return os.path.expanduser(os.environ.get(UMGEBUNG_DATEN) or STANDARD_DATEN)


def _json_lesen(pfad: str) -> Tuple[str, Any]:
    """``("fehlt"|"ok"|"defekt", Daten)`` — wirft nie."""
    if not os.path.exists(pfad):
        return "fehlt", None
    try:
        with open(pfad, "rb") as datei:
            roh = datei.read(LESEN_MAX_BYTES + 1)
        if len(roh) > LESEN_MAX_BYTES:
            return "defekt", None
        return "ok", json.loads(roh.decode("utf-8"))
    except (OSError, ValueError):
        return "defekt", None


def _dict_lesen(pfad: str) -> Dict[str, Any]:
    status, daten = _json_lesen(pfad)
    return daten if status == "ok" and isinstance(daten, dict) else {}


def _einstellungen_lesen(ordner: str) -> Tuple[Dict[str, Any], bool]:
    """``(Einstellungen, lesbar)``. Fehlende Datei: leer und lesbar."""
    status, daten = _json_lesen(os.path.join(ordner, EINSTELLUNGEN_NAME))
    if status == "fehlt":
        return {}, True
    if status == "ok" and isinstance(daten, dict):
        return daten, True
    return {}, False


def kamera_pfad(wert: Any) -> Optional[str]:
    """Der pCloud-Pfad oder ``None``. Dieselben Regeln wie ``tools/handy/tageslauf.py``."""
    if not isinstance(wert, str):
        return None
    pfad = wert.strip()
    if not pfad.startswith("/") or len(pfad) < 2 or len(pfad) > KAMERA_MAX_ZEICHEN:
        return None
    if ".." in pfad or "\\" in pfad or "//" in pfad:
        return None
    if any(ord(zeichen) < 32 or ord(zeichen) == 127 for zeichen in pfad):
        return None
    if any("crypto" in teil.casefold() for teil in pfad.split("/")):
        return None
    return pfad


def _text(wert: Any, grenze: int = TEXT_MAX) -> Optional[str]:
    return wert[:grenze] if isinstance(wert, str) else None


def _datum(wert: Any) -> Optional[datetime.date]:
    if not isinstance(wert, str):
        return None
    try:
        return datetime.date.fromisoformat(wert.strip())
    except ValueError:
        return None


# ── Lesen ──────────────────────────────────────────────────────────────────

def _gemini(einstellungen: Dict[str, Any]) -> Dict[str, Any]:
    letzter = _datum(einstellungen.get("gemini_letzter_export"))
    tage = (_heute() - letzter).days if letzter is not None else None
    if tage is not None and tage < 0:                      # Datum in der Zukunft: nicht glaubwürdig
        letzter, tage = None, None
    faellig = tage is None or tage > GEMINI_TAGE
    return {"letzter_export": letzter.isoformat() if letzter else None,
            "tage_seit_export": tage, "faellig": faellig}


def _bericht(roh: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(roh, dict):
        return None
    exit_code = roh.get("exit")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        exit_code = None
    bausteine: List[Dict[str, Any]] = []
    liste = roh.get("bausteine")
    for eintrag in (liste if isinstance(liste, list) else []):
        if not isinstance(eintrag, dict):
            continue
        name, status, text = _text(eintrag.get("name"), 40), _text(eintrag.get("status"), 40), _text(eintrag.get("text"))
        if name is None or text is None:
            continue
        bausteine.append({"name": name, "status": status or "", "text": text})
        if len(bausteine) >= BAUSTEINE_MAX:
            break
    datum = _datum(roh.get("datum"))
    return {"datum": datum.isoformat() if datum else None, "zeit": _text(roh.get("zeit"), 40),
            "exit": exit_code, "stand_fortgeschrieben": roh.get("stand_fortgeschrieben") is True,
            "bausteine": bausteine}


def status() -> Dict[str, Any]:
    """Der Stand für die Oberfläche. Wirft nie; legt nichts an; nennt keinen Pfad des Datenordners."""
    ordner = daten_ordner()
    einstellungen, lesbar = _einstellungen_lesen(ordner)
    heute = _heute().isoformat()
    roh_ordner = einstellungen.get("kamera_ordner")
    ordner_wert = _text(roh_ordner, KAMERA_MAX_ZEICHEN) if isinstance(roh_ordner, str) and roh_ordner.strip() else None
    bericht = _bericht(_dict_lesen(os.path.join(ordner, BERICHT_NAME)) or None)
    stand = _dict_lesen(os.path.join(ordner, STAND_NAME))
    return {
        "ok": True,
        "heute": heute,
        "an": lesbar and einstellungen.get("an") is True,
        "einstellungen_lesbar": lesbar,
        "kamera_ordner": {"gesetzt": ordner_wert is not None, "wert": ordner_wert},
        "gemini": _gemini(einstellungen),
        "heute_gelaufen": stand.get("letzter_gesamtlauf") == heute,
        "bericht_veraltet": bericht is not None and bericht["datum"] != heute,
        "bericht": bericht,
    }


# ── Schreiben ──────────────────────────────────────────────────────────────

def _im_repo(pfad: str) -> bool:
    kandidat = os.path.realpath(os.path.expanduser(pfad))
    while True:
        if os.path.exists(os.path.join(kandidat, ".git")):
            return True
        eltern = os.path.dirname(kandidat)
        if eltern == kandidat:
            return False
        kandidat = eltern


def _ziel_pruefen(ordner: str, pfad: str) -> None:
    if _im_repo(ordner):
        raise Ablehnung(403, "Nicht gespeichert: Der Datenordner liegt in einem Git-Repo.")
    meldung = "Nicht gespeichert: Die Einstellungsdatei ist ein Link."
    if os.path.islink(pfad):
        raise Ablehnung(403, meldung)
    try:
        if os.stat(pfad).st_nlink > 1:
            raise Ablehnung(403, meldung)
    except FileNotFoundError:
        pass


def _atomar_schreiben(pfad: str, text: str) -> None:
    ordner = os.path.dirname(pfad) or "."
    os.makedirs(ordner, exist_ok=True)
    temp = os.path.join(ordner, f"{os.path.basename(pfad)}.{secrets.token_hex(4)}.tmp")
    try:
        with open(temp, "xb") as datei:
            datei.write(text.encode("utf-8"))
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(temp, pfad)
    except OSError:
        try:
            os.remove(temp)          # nur die eigene Temp-Datei
        except OSError:
            pass
        raise


def einstellungen_pruefen(koerper: Any) -> Dict[str, Any]:
    """Prüft den Anfragekörper und liefert die zu setzenden Schlüssel. Sonst ``Ablehnung(400)``."""
    if not isinstance(koerper, dict) or not koerper:
        raise Ablehnung(400, "Nicht gespeichert: Es fehlt eine Angabe.")
    fremd = [k for k in koerper if k not in ERLAUBTE_FELDER]
    if fremd:
        raise Ablehnung(400, "Nicht gespeichert: Unbekannte Angabe.")
    neu: Dict[str, Any] = {}
    if "an" in koerper:
        if not isinstance(koerper["an"], bool):
            raise Ablehnung(400, "Nicht gespeichert: Der Schalter muss ein Ja oder Nein sein.")
        neu["an"] = koerper["an"]
    if "kamera_ordner" in koerper:
        pfad = kamera_pfad(koerper["kamera_ordner"])
        if pfad is None:
            raise Ablehnung(400, "Nicht gespeichert: Der Kamera-Ordner ist nicht zulässig "
                                 "(mit / beginnen, höchstens 200 Zeichen, kein .., kein \\, kein //, "
                                 "kein Crypto-Ordner).")
        neu["kamera_ordner"] = pfad
    if "gemini_export_heute" in koerper:
        if koerper["gemini_export_heute"] is not True:
            raise Ablehnung(400, "Nicht gespeichert: Gemini-Export heute erledigt braucht ein Ja.")
        neu["gemini_letzter_export"] = _heute().isoformat()
    return neu


def einstellungen_aendern(koerper: Any) -> Dict[str, Any]:
    """Setzt die gewünschten Schlüssel (Lesen-Ändern-Schreiben) und liefert den neuen Stand.

    ``Ablehnung`` bei ungültiger Eingabe (400), unlesbarer Datei (409), Link oder Repo (403),
    nicht schreibbarem Ordner (500). In jedem Fehlerfall bleibt die Datei unverändert.
    """
    neu = einstellungen_pruefen(koerper)
    ordner = daten_ordner()
    pfad = os.path.join(ordner, EINSTELLUNGEN_NAME)
    _ziel_pruefen(ordner, pfad)
    aktuell, lesbar = _einstellungen_lesen(ordner)
    if not lesbar:
        raise Ablehnung(409, "Nicht gespeichert: Die Einstellungsdatei ist nicht lesbar "
                             "und wird nicht überschrieben.")
    aktuell.update(neu)
    try:
        _atomar_schreiben(pfad, json.dumps(aktuell, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        raise Ablehnung(500, "Nicht gespeichert: Der Datenordner ist nicht beschreibbar.")
    return status()
