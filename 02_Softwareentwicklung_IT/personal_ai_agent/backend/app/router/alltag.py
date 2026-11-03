"""Alltagsprotokoll: Schlafnächte der Uhr und Einträge (03.11.2026).

* ``POST /api/alltag/schlaf``        ``{naechte: [...]}`` von Hey Agent (Health Connect) — idempotent.
* ``GET  /api/alltag/schlaf``        ``?von=JJJJ-MM-TT&bis=JJJJ-MM-TT`` (Standard: letzte 14 Tage).
* ``GET  /api/alltag/schlaf/stand``  Anzahl, letzte Nacht, letzter Abgleich (für das Checks-Fenster).
* ``GET  /api/alltag/offen``         ``{offene_stunden, schlaeft, letzter_eintrag}`` für das Pop-up (S5).
* ``GET  /api/alltag/tag``           ``?datum=JJJJ-MM-TT`` — Einträge des Tages mit ``fehlt`` + Uhr-Nächte.
* ``POST   /api/alltag/eintrag``      ``{text, quelle}`` → Struktur über ``alltag_struktur`` (S3) → gespeichert.
* ``POST   /api/alltag/ereignis``     ``{ereignis}`` — Schlaf-Schnellknopf, Zeit = jetzt, ohne Modell (S6).
* ``GET    /api/alltag/vorgaben``     Grundgefühle und Stimmungsstufen für die Rückfragen (S6).
* ``PATCH  /api/alltag/eintrag/{id}`` Felder korrigieren (neue Fassung, append-only).
* ``DELETE /api/alltag/eintrag/{id}`` Löschmarker.

Hängt in ``main.py`` am API-Key. Fachlogik: ``alltag_speicher`` (Speicher) und
``alltag_rechnen`` (Auswertung). Daten bleiben auf dem Gerät.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from app.services import alltag_rechnen, alltag_speicher, alltag_struktur, werkzeuge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alltag", tags=["alltag"])

STANDARD_TAGE = 14


@router.post("/schlaf")
async def schlaf_uebernehmen(request: Request) -> Dict[str, Any]:
    try:
        koerper = await request.json()
    except Exception:  # noqa: BLE001 – kein JSON
        raise HTTPException(status_code=400, detail="Die Anfrage ist kein JSON.")
    naechte = koerper.get("naechte") if isinstance(koerper, dict) else None
    if not isinstance(naechte, list):
        raise HTTPException(status_code=400, detail="Erwartet wird {naechte: [...]}.")
    erg = alltag_speicher.schlafnaechte_uebernehmen(naechte)
    if not erg.get("ok"):
        raise HTTPException(status_code=400, detail=erg.get("fehler") or "Nicht übernommen.")
    return erg


def _zeitraum(von: Optional[str], bis: Optional[str]) -> tuple:
    heute = date.today()
    return (von or (heute - timedelta(days=STANDARD_TAGE)).isoformat(), bis or heute.isoformat())


@router.get("/schlaf")
def schlaf_lesen(von: Optional[str] = None, bis: Optional[str] = None) -> Dict[str, Any]:
    von, bis = _zeitraum(von, bis)
    try:
        naechte = alltag_speicher.eintraege(art="schlafnacht", von=von, bis=bis)
        return {
            "ok": True, "von": von, "bis": bis,
            "naechte": alltag_rechnen.auswerten(naechte),
            "zusammenfassung": alltag_rechnen.zusammenfassung(naechte),
            "text": alltag_rechnen.schlaf_text(naechte),
        }
    except Exception as e:  # noqa: BLE001 – nie 500
        logger.warning("Schlaf: nicht lesbar: %s", type(e).__name__)
        return {"ok": False, "fehler": f"Schlafdaten nicht lesbar ({type(e).__name__})."}


@router.get("/schlaf/stand")
def schlaf_stand() -> Dict[str, Any]:
    naechte = alltag_speicher.eintraege(art="schlafnacht")
    if not naechte:
        return {"ok": True, "anzahl": 0, "letzte_nacht_zum": None, "letzter_abgleich": None}
    ausgewertet = alltag_rechnen.auswerten(naechte)
    return {
        "ok": True,
        "anzahl": len(naechte),
        "letzte_nacht_zum": ausgewertet[-1]["nacht_zum"] if ausgewertet else None,
        "letzter_abgleich": max(str(n.get("erfasst_um") or "") for n in naechte) or None,
    }


# ── Einträge (S5, ohne Sprachmodell) ───────────────────────────────────────

@router.get("/offen")
def offen() -> Dict[str, Any]:
    jetzt = datetime.now(timezone.utc)
    stand = alltag_rechnen.letzter_stand(
        alltag_speicher.eintraege(art="stunde") + alltag_speicher.eintraege(art="schlaf"), jetzt=jetzt)
    return {"ok": True,
            "offene_stunden": alltag_rechnen.offene_stunden(stand["letzter_eintrag"], jetzt,
                                                            stand["schlaeft"]),
            **stand}


@router.get("/tag")
def tag(datum: str) -> Dict[str, Any]:
    try:
        date.fromisoformat(datum)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datum als JJJJ-MM-TT angeben.")
    eintraege = [dict(e, fehlt=alltag_rechnen.fehlende_felder(e))
                 for e in alltag_speicher.eintraege(von=datum, bis=datum)
                 if e.get("art") in ("stunde", "schlaf")]
    naechte = alltag_speicher.eintraege(art="schlafnacht", von=datum, bis=datum)
    return {"ok": True, "datum": datum, "eintraege": eintraege,
            "naechte_uhr": alltag_rechnen.auswerten(naechte)}


@router.post("/eintrag")
async def eintrag_aus_satz(request: Request) -> Dict[str, Any]:
    """Satz → Struktur (S3) → gespeichert. Klappt die Struktur nicht, werden nur die Originalworte gesichert."""
    try:
        koerper = await request.json()
    except Exception:  # noqa: BLE001 – kein JSON
        raise HTTPException(status_code=400, detail="Die Anfrage ist kein JSON.")
    text = koerper.get("text") if isinstance(koerper, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="Erwartet wird {text, quelle}.")
    quelle = str(koerper.get("quelle") or "tastatur")

    namen = werkzeuge.namen_fuer_maskierung()
    if namen is None:
        erg = {"ok": False, "grund": "Die Namensliste fehlt oder ist nicht lesbar — der Satz ging nicht ans Modell."}
    else:
        erg = alltag_struktur.strukturieren(text, quelle=quelle, namen=namen)
    eintrag = erg["eintrag"] if erg.get("ok") else alltag_struktur.nur_originalworte(text, quelle)

    gespeichert = alltag_speicher.eintrag_anhaengen(eintrag)
    if not gespeichert.get("ok"):
        return {"ok": False, "grund": gespeichert.get("fehler") or "Nicht gespeichert."}
    antwort = {"ok": bool(erg.get("ok")), "eintrag": gespeichert["eintrag"],
               "fehlt": alltag_rechnen.fehlende_felder(gespeichert["eintrag"])}
    if erg.get("ok"):
        antwort.update(modell=erg.get("modell"), kosten_usd=erg.get("kosten_usd"))
    else:
        antwort["grund"] = erg.get("grund")
    return antwort


@router.post("/ereignis")
async def schlaf_knopf(request: Request) -> Dict[str, Any]:
    """Schnellknopf (S6): Schlaf-Ereignis mit der Zeit von jetzt, ohne Modell."""
    try:
        koerper = await request.json()
    except Exception:  # noqa: BLE001 – kein JSON
        raise HTTPException(status_code=400, detail="Die Anfrage ist kein JSON.")
    ereignis = koerper.get("ereignis") if isinstance(koerper, dict) else None
    if ereignis not in alltag_speicher.SCHLAF_EREIGNISSE:
        raise HTTPException(status_code=400, detail="Unbekanntes Schlaf-Ereignis.")
    jetzt = datetime.now().astimezone().isoformat(timespec="seconds")
    erg = alltag_speicher.eintrag_anhaengen({"art": "schlaf", "ereignis": ereignis, "zeit": jetzt,
                                            "quelle": "knopf"})
    if not erg.get("ok"):
        return {"ok": False, "grund": erg.get("fehler") or "Nicht gespeichert."}
    return {"ok": True, "eintrag": erg["eintrag"]}


@router.get("/vorgaben")
def vorgaben() -> Dict[str, Any]:
    """Grundgefühle und Stimmungsstufen für die Rückfragen der Oberfläche (S6)."""
    return {"ok": True, "grundgefuehle": list(alltag_struktur.GRUNDGEFUEHLE),
            "stimmung": [{"wert": wert, "wort": wort} for wert, wort in alltag_struktur.STIMMUNG]}


@router.patch("/eintrag/{kennung}")
async def eintrag_korrigieren(kennung: str, request: Request) -> Dict[str, Any]:
    try:
        felder = await request.json()
    except Exception:  # noqa: BLE001 – kein JSON
        raise HTTPException(status_code=400, detail="Die Anfrage ist kein JSON.")
    if not isinstance(felder, dict):
        raise HTTPException(status_code=400, detail="Erwartet wird ein Objekt mit Feldern.")
    erg = alltag_speicher.korrigieren(kennung, felder)
    if not erg.get("ok"):
        raise HTTPException(status_code=404 if "nicht gefunden" in (erg.get("fehler") or "") else 400,
                            detail=erg.get("fehler") or "Nicht korrigiert.")
    return erg


@router.delete("/eintrag/{kennung}")
def eintrag_loeschen(kennung: str) -> Dict[str, Any]:
    erg = alltag_speicher.loeschen(kennung)
    if not erg.get("ok"):
        raise HTTPException(status_code=404 if "nicht gefunden" in (erg.get("fehler") or "") else 400,
                            detail=erg.get("fehler") or "Nicht gelöscht.")
    return erg
