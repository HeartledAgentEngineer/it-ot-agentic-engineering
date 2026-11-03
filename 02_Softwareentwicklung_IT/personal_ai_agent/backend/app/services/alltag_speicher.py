"""Alltagsprotokoll S1: Speicher (03.11.2026).

Append-only JSONL wie ``erzaehl_service``: Jede Änderung ist eine neue Zeile.
Korrektur = neue Zeile mit ``ersetzt`` (Kennung des Vorgängers); Löschen = Zeile
``{"loeschen": id}``, die den Eintrag samt Vorgängern ausblendet. Kaputte Zeilen
werden übersprungen.

Arten:
  * ``stunde``      — ein Stundenbereich (Stimmung, Anspannung, Aktivität …; Slice 1)
  * ``schlaf``      — Schlaf-Ereignis per Knopf (schlafen / aufwachen / wach_liegen / wieder_schlafen)
  * ``schlafnacht`` — eine Schlafsitzung von der Uhr (Health Connect), idempotent je
                      ``quelle_kennung``; die Uhr darf eine Nacht nachträglich ändern.

Echte Einträge liegen nur auf dem Gerät (``~/alltagsprotokoll/eintraege.jsonl``,
übersteuerbar mit ``ALLTAGSPROTOKOLL_PFAD``). **Wirft nie** — Fehler als ``{"ok": False, "fehler"}``.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ORDNER = "alltagsprotokoll"
DATEINAME = "eintraege.jsonl"

ARTEN = ("stunde", "schlaf", "schlafnacht")
SCHLAF_EREIGNISSE = ("schlafen", "aufwachen", "wach_liegen", "wieder_schlafen")
# Health-Connect-Stufen, auf deutsche Namen gebracht (Kotlin schickt schon diese Namen).
SCHLAF_STUFEN = ("wach", "leicht", "tief", "rem", "schlafend", "aus_dem_bett", "unbekannt")
MAX_NACHT = timedelta(hours=24)

# Felder, die ein Eintrag tragen darf (alles andere fällt weg).
FELDER_STUNDE = ("von", "bis", "stimmung", "anspannung", "gefuehle", "vorherrschend",
                 "aktivitaet", "essen", "originalworte", "quelle")
FELDER_SCHLAF = ("zeit", "ereignis", "quelle", "originalworte")

_SPERRE = threading.Lock()


def speicher_pfad() -> str:
    ueber = os.environ.get("ALLTAGSPROTOKOLL_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), ORDNER, DATEINAME)


def _jetzt() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def zeit_lesen(wert: Any) -> Optional[datetime]:
    """ISO-Zeit mit Zeitzone lesen (``Z`` erlaubt); ohne Zone gilt die lokale. Sonst ``None``."""
    if not isinstance(wert, str) or not wert.strip():
        return None
    roh = wert.strip()
    if roh.endswith("Z"):
        roh = roh[:-1] + "+00:00"
    try:
        zeit = datetime.fromisoformat(roh)
    except ValueError:
        return None
    if zeit.tzinfo is None:
        zeit = zeit.astimezone()
    return zeit


# ── Datei ────────────────────────────────────────────────────────────────

def _zeilen_lesen() -> List[Dict[str, Any]]:
    pfad = speicher_pfad()
    if not os.path.isfile(pfad):
        return []
    zeilen: List[Dict[str, Any]] = []
    try:
        with open(pfad, "r", encoding="utf-8", errors="ignore") as datei:
            for zeile in datei:
                try:
                    obj = json.loads(zeile)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    zeilen.append(obj)
    except OSError as e:
        logger.warning("Alltagsprotokoll nicht lesbar: %s", type(e).__name__)
    return zeilen


def _anhaengen(zeilen: List[Dict[str, Any]]) -> None:
    pfad = speicher_pfad()
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as datei:
        for z in zeilen:
            datei.write(json.dumps(z, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())


def _aktuelle(zeilen: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nur die gültigen, neuesten Fassungen (ohne ersetzte und gelöschte)."""
    nach_id: Dict[str, Dict[str, Any]] = {}
    ersetzt_von: Dict[str, str] = {}
    geloescht: set = set()
    for z in zeilen:
        if "loeschen" in z:
            geloescht.add(str(z.get("loeschen")))
            continue
        kennung = z.get("id")
        if not isinstance(kennung, str) or z.get("art") not in ARTEN:
            continue
        nach_id[kennung] = z
        if isinstance(z.get("ersetzt"), str):
            ersetzt_von[z["ersetzt"]] = kennung

    # Löschen trifft den Eintrag samt seiner Vorgänger und Nachfolger (ganze Kette).
    def kette(kennung: str) -> List[str]:
        glieder, k = [kennung], kennung
        while k in nach_id and isinstance(nach_id[k].get("ersetzt"), str):
            k = nach_id[k]["ersetzt"]
            glieder.append(k)
        k = kennung
        while k in ersetzt_von:
            k = ersetzt_von[k]
            glieder.append(k)
        return glieder

    tot: set = set()
    for k in geloescht:
        tot.update(kette(k))
    return [z for k, z in nach_id.items() if k not in ersetzt_von and k not in tot]


def _sortzeit(e: Dict[str, Any]) -> str:
    return str(e.get("ende") or e.get("bis") or e.get("zeit") or e.get("erfasst_um") or "")


def eintraege(art: Optional[str] = None, von: Optional[str] = None,
              bis: Optional[str] = None) -> List[Dict[str, Any]]:
    """Aktuelle Einträge, zeitlich sortiert. ``von``/``bis`` (JJJJ-MM-TT, inklusiv) gegen das Ende."""
    with _SPERRE:
        aktuell = _aktuelle(_zeilen_lesen())
    if art:
        aktuell = [e for e in aktuell if e.get("art") == art]
    if von or bis:
        gefiltert = []
        for e in aktuell:
            zeit = zeit_lesen(_sortzeit(e))
            tag = zeit.date().isoformat() if zeit else ""
            if not tag or (von and tag < von) or (bis and tag > bis):
                continue
            gefiltert.append(e)
        aktuell = gefiltert
    return sorted(aktuell, key=_sortzeit)


# ── Schreiben ────────────────────────────────────────────────────────────

def _neue_zeile(art: str, felder: Dict[str, Any], ersetzt: Optional[str] = None) -> Dict[str, Any]:
    zeile = {"id": uuid.uuid4().hex, "art": art, "erfasst_um": _jetzt(), **felder}
    if ersetzt:
        zeile["ersetzt"] = ersetzt
    return zeile


def _felder_fuer(art: str, roh: Dict[str, Any]) -> Dict[str, Any]:
    erlaubt = FELDER_STUNDE if art == "stunde" else FELDER_SCHLAF
    return {k: roh[k] for k in erlaubt if k in roh}


def eintrag_anhaengen(eintrag: Dict[str, Any]) -> Dict[str, Any]:
    """Einen ``stunde``- oder ``schlaf``-Eintrag speichern (Schlafnächte: :func:`schlafnaechte_uebernehmen`)."""
    if not isinstance(eintrag, dict) or eintrag.get("art") not in ("stunde", "schlaf"):
        return {"ok": False, "fehler": "Unbekannte Art des Eintrags."}
    art = eintrag["art"]
    if art == "schlaf" and eintrag.get("ereignis") not in SCHLAF_EREIGNISSE:
        return {"ok": False, "fehler": "Unbekanntes Schlaf-Ereignis."}
    zeile = _neue_zeile(art, _felder_fuer(art, eintrag))
    try:
        with _SPERRE:
            _anhaengen([zeile])
    except OSError as e:
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({type(e).__name__})."}
    return {"ok": True, "eintrag": zeile}


def korrigieren(kennung: str, felder: Dict[str, Any]) -> Dict[str, Any]:
    """Neue Fassung eines ``stunde``/``schlaf``-Eintrags mit geänderten Feldern."""
    with _SPERRE:
        aktuell = {e["id"]: e for e in _aktuelle(_zeilen_lesen())}
        alt = aktuell.get(str(kennung))
        if alt is None or alt.get("art") not in ("stunde", "schlaf"):
            return {"ok": False, "fehler": "Eintrag nicht gefunden."}
        art = alt["art"]
        neu_felder = {**_felder_fuer(art, alt), **_felder_fuer(art, felder or {})}
        zeile = _neue_zeile(art, neu_felder, ersetzt=alt["id"])
        try:
            _anhaengen([zeile])
        except OSError as e:
            return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({type(e).__name__})."}
    return {"ok": True, "eintrag": zeile}


def loeschen(kennung: str) -> Dict[str, Any]:
    with _SPERRE:
        if str(kennung) not in {e["id"] for e in _aktuelle(_zeilen_lesen())}:
            return {"ok": False, "fehler": "Eintrag nicht gefunden."}
        try:
            _anhaengen([{"loeschen": str(kennung), "erfasst_um": _jetzt()}])
        except OSError as e:
            return {"ok": False, "fehler": f"Löschen fehlgeschlagen ({type(e).__name__})."}
    return {"ok": True}


# ── Schlafnächte von der Uhr ─────────────────────────────────────────────

def _phase_saeubern(roh: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(roh, dict):
        return None
    beginn, ende = zeit_lesen(roh.get("beginn")), zeit_lesen(roh.get("ende"))
    if not beginn or not ende or ende <= beginn:
        return None
    stufe = roh.get("stufe") if roh.get("stufe") in SCHLAF_STUFEN else "unbekannt"
    return {"stufe": stufe, "beginn": roh["beginn"], "ende": roh["ende"]}


def nacht_saeubern(roh: Any) -> Optional[Dict[str, Any]]:
    """Eine gelieferte Schlafsitzung prüfen und auf erlaubte Felder bringen — sonst ``None``."""
    if not isinstance(roh, dict):
        return None
    kennung = str(roh.get("quelle_kennung") or "").strip()
    beginn, ende = zeit_lesen(roh.get("beginn")), zeit_lesen(roh.get("ende"))
    if not kennung or not beginn or not ende or ende <= beginn or ende - beginn > MAX_NACHT:
        return None
    phasen = [p for p in (_phase_saeubern(x) for x in roh.get("phasen") or []) if p]
    nacht = {"quelle_kennung": kennung[:200], "beginn": roh["beginn"], "ende": roh["ende"],
             "phasen": phasen, "quelle": "uhr"}
    app = roh.get("app")
    if isinstance(app, str) and app.strip():
        nacht["app"] = app.strip()[:120]
    return nacht


def _vergleich(n: Dict[str, Any]) -> str:
    return json.dumps({k: n.get(k) for k in ("beginn", "ende", "phasen", "app")}, sort_keys=True)


def schlafnaechte_uebernehmen(naechte: Any) -> Dict[str, Any]:
    """Schlafsitzungen der Uhr übernehmen — idempotent je ``quelle_kennung``.

    Rückgabe ``{"ok", "neu", "aktualisiert", "unveraendert", "abgelehnt"}``.
    """
    if not isinstance(naechte, list):
        return {"ok": False, "fehler": "Erwartet wird eine Liste von Nächten."}
    zaehler = {"neu": 0, "aktualisiert": 0, "unveraendert": 0, "abgelehnt": 0}
    with _SPERRE:
        vorhanden = {e.get("quelle_kennung"): e for e in _aktuelle(_zeilen_lesen())
                     if e.get("art") == "schlafnacht"}
        neue_zeilen: List[Dict[str, Any]] = []
        for roh in naechte:
            nacht = nacht_saeubern(roh)
            if nacht is None:
                zaehler["abgelehnt"] += 1
                continue
            alt = vorhanden.get(nacht["quelle_kennung"])
            if alt is None:
                zeile = _neue_zeile("schlafnacht", nacht)
                zaehler["neu"] += 1
            elif _vergleich(alt) == _vergleich(nacht):
                zaehler["unveraendert"] += 1
                continue
            else:
                zeile = _neue_zeile("schlafnacht", nacht, ersetzt=alt["id"])
                zaehler["aktualisiert"] += 1
            vorhanden[nacht["quelle_kennung"]] = zeile
            neue_zeilen.append(zeile)
        if neue_zeilen:
            try:
                _anhaengen(neue_zeilen)
            except OSError as e:
                return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({type(e).__name__})."}
    logger.info("Schlafnächte übernommen: %s", zaehler)
    return {"ok": True, **zaehler}
