"""Router: Auftragsbuch fuer den Coding-Agenten.

  POST   /api/auftraege                   Auftrag eintragen (Oberflaeche)
  GET    /api/auftraege                   Liste mit Stand (Oberflaeche)
  GET    /api/auftraege/naechster         naechsten offenen abholen (Hermes)
  GET    /api/auftraege/{id}              einzelner Stand (Oberflaeche)
  POST   /api/auftraege/{id}/ergebnis     Rueckmeldung (Hermes)
  POST   /api/auftraege/{id}/status       Zwischenmeldung (Hermes)
  POST   /api/auftraege/{id}/rueckfrage   Rueckfrage ans Nutzer (Hermes)
  POST   /api/auftraege/{id}/antwort      Antwort auf Rueckfrage (Nutzer)
  GET    /api/auftraege/{id}/chat         Aufbereitet fuer Chat-Ausgabe
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    AuftragCreate,
    AuftragItem,
    AuftragListResponse,
    ErgebnisCreate,
    StatusMeldungCreate,
    RueckfrageCreate,
    AntwortCreate,
    EingabeCreate,
)
from app.services.auftrag_service import auftrag_service
from app.services.hermes_local import hat_mehrwert as hermes_hat_mehrwert
from app.services.hermes_local import hermes_registry
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auftraege", tags=["auftraege"])


@router.post("", response_model=AuftragItem, status_code=201)
def auftrag_anlegen(auftrag: AuftragCreate):
    """Traegt einen Auftrag ein."""
    try:
        return auftrag_service.anlegen(
            auftrag.auftrag,
            auftrag.hinweis,
            kategorie=auftrag.kategorie,
            komplexitaet=auftrag.komplexitaet,
        )
    except Exception as fehler:
        logger.error("Auftrag anlegen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.get("", response_model=AuftragListResponse)
def auftraege_auflisten(limit: int = Query(default=50, ge=1, le=200)):
    """Alle Auftraege, neueste zuerst."""
    try:
        auftraege = [
            AuftragItem.model_validate(eintrag)
            for eintrag in auftrag_service.alle(limit=limit)
        ]
        return AuftragListResponse(auftraege=auftraege, total=len(auftraege))
    except Exception as fehler:
        logger.error("Auftraege auflisten fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.get("/naechster")
def naechsten_auftrag_abholen():
    """Gibt den aeltesten offenen Auftrag aus - fuer den Coding-Agenten."""
    try:
        auftrag = auftrag_service.naechster_offener()
        if auftrag is None:
            return {"auftrag": None, "hinweis": "Nichts zu tun."}
        return {"auftrag": auftrag}
    except Exception as fehler:
        logger.error("Auftrag abholen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.get("/{auftrag_id}", response_model=AuftragItem)
def auftrag_ansehen(auftrag_id: str):
    """Stand eines einzelnen Auftrags."""
    auftrag = auftrag_service.einzeln(auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return auftrag


@router.get("/{auftrag_id}/chat")
def auftrag_chat_ausgabe(auftrag_id: str):
    """Liefert den Auftrag als strukturierte Chat-Daten."""
    auftrag = auftrag_service.einzeln(auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

    # Einzelne Status-Meldungen aufbereiten
    alle_meldungen = auftrag.get("status_meldungen", [])
    meldungen = []
    for m in alle_meldungen:
        if "|" in m:
            emoji, rest = m.split("|", 1)
        else:
            emoji, rest = "", m
        meldungen.append({
            "roh": m,
            "emoji": emoji.strip(),
            "text": rest.strip(),
        })

    # Ergebnis parsen für Details
    ergebnis = auftrag.get("ergebnis", "")
    ergebnis_details = {}
    if ergebnis:
        if "Commit:" in ergebnis:
            commit_match = __import__("re").search(r"Commit:\s*`([^`]+)`", ergebnis)
            if commit_match:
                ergebnis_details["commit"] = commit_match.group(1)
        if "gepusht" in ergebnis.lower() or "Push" in ergebnis:
            ergebnis_details["gepusht"] = "Push fehlgeschlagen" not in ergebnis
        ergebnis_details["text_kurz"] = ergebnis[:300]

    # Gesamttext (für Rückwärtskompatibilität)
    zeilen = [f"📋 **Auftrag {auftrag['id'][:8]}**"]
    zeilen.append(f"**Aufgabe:** {auftrag['auftrag'][:100]}…")
    if auftrag.get("hinweis"):
        zeilen.append(f"**Hinweis:** {auftrag['hinweis']}")
    zeilen.append(f"**Status:** {_status_emoji(auftrag['status'])} {auftrag['status']}")
    if meldungen:
        zeilen.append("\n**Zwischenmeldungen:**")
        for m in meldungen[-10:]:
            zeilen.append(f"- {m['roh']}")
    if ergebnis:
        zeilen.append(f"\n**Ergebnis:** {ergebnis[:300]}")

    return {
        "text": "\n".join(zeilen),
        "status": auftrag["status"],
        "meldungen": [m["roh"] for m in meldungen],
        "meldungen_count": len(meldungen),
        "offene_rueckfragen": auftrag.get("rueckfragen", []),
        "ergebnis_details": ergebnis_details or None,
    }


@router.post("/{auftrag_id}/eingabe", response_model=AuftragItem)
def kommentar_senden(auftrag_id: str, eingabe: EingabeCreate):
    """Nutzer-Kommentar waehrend eines laufenden Coding-Auftrags.

    Sendet den Kommentar per `tmux send-keys` an den laufenden lokalen Hermes
    (Track C, interaktive Session). Parallel wird der Kommentar — nur falls er
    persoenlichen Mehrwert hat (keine reine Bestaetigung) — durch das
    persoenliche Gedaechtnis gefuehrt, damit der eigene Assistent mitlernt.
    """
    auftrag = auftrag_service.einzeln(auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

    text = eingabe.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Leerer Kommentar")

    # Die Registry fuehrt Jobs unter der VOLLEN UUID. Der Endpoint akzeptiert
    # aber auch die Kurzform (8 Zeichen) aus der URL — deshalb hier die volle
    # UUID aus dem (bereits aufgeloesten) Auftrag verwenden.
    volle_id = auftrag["id"]
    gesendet = hermes_registry.sende_an(volle_id, text)
    if not gesendet:
        # Kein laufender Job (mehr) fuer diese Auftrag-ID.
        raise HTTPException(
            status_code=409,
            detail="Kein laufender Hermes-Job fuer diesen Auftrag (evtl. schon abgeschlossen)",
        )

    # Gedaechtnis mitlernen — nur bei persoenlichem Mehrwert.
    try:
        if hermes_hat_mehrwert(text):
            memory_service.store_memory(
                content=text,
                category="fact",
                importance=3,
                conversation_id=f"auftrag:{auftrag_id[:8]}",
            )
            logger.info("Kommentar gelernt (Mehrwert): %s", text[:60])
    except Exception as e:  # pragma: no cover
        logger.warning("Gedaechtnis-Lernen des Kommentars fehlgeschlagen: %s", e)

    # Hinweis im Auftrag fuer den Chat-Tracker (volle ID, denn der Service
    # matcht exakt — die Kurzform wuerde ins Leere laufen).
    auftrag_service.statusmeldung_hinzufuegen(volle_id, f"📨 Kommentar an Agent: {text}")
    return auftrag


@router.post("/{auftrag_id}/ergebnis", response_model=AuftragItem)
def ergebnis_melden(auftrag_id: str, ergebnis: ErgebnisCreate):
    """Nimmt die Rueckmeldung des Coding-Agenten entgegen."""
    try:
        auftrag = auftrag_service.ergebnis_eintragen(
            auftrag_id, ergebnis.ergebnis, ergebnis.erfolg
        )
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Ergebnis eintragen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.post("/{auftrag_id}/abbrechen", response_model=AuftragItem)
def auftrag_abbrechen(auftrag_id: str):
    """Bricht einen laufenden Hermes-Auftrag ab (z. B. wenn der Nutzer eine
    fälschlich erkannte Aufgabe doch an den normalen LLM weiterleiten will).

    Beendet die lokale tmux-Session (Registry-Cleanup) und markiert den Auftrag
    im Buch als 'fehler' (erfolg=False), damit kein Worker weiterläuft.
    """
    try:
        auftrag = auftrag_service.einzeln(auftrag_id)
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        volle_id = auftrag["id"]
        # Lokale tmux-Session des Hermes sofort beenden (killt den Prozess).
        try:
            hermes_registry.entferne(volle_id)
        except Exception as e:  # pragma: no cover - Cleanup darf nicht crashen
            logger.warning("Registry-Cleanup beim Abbruch fehlgeschlagen: %s", e)
        # Auftrag im Buch als abgebrochen (fehler) markieren.
        auftrag = auftrag_service.ergebnis_eintragen(
            volle_id, "Abgebrochen – Aufgabe wird vom LLM beantwortet.", False
        )
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag abgebrochen, nicht gefunden")
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Auftrag abbrechen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.post("/{auftrag_id}/wechseln-handy", response_model=AuftragItem)
def auftrag_wechseln_handy(auftrag_id: str):
    """Wechselt einen laufenden Auftrag auf den LOKALEN Handy-Hermes (Track C).

    Der Nutzer-Controller will z. B. vom PC-Hermes (der nicht zielfuehrend
    arbeitet) auf den Handy-Hermes wechseln: den laufenden Auftrag abbrechen
    (tmux/Buch-Cleanup wie /abbrechen) und DENSELBEN Auftrag lokal neu starten.
    Liefert den Auftrag im Zustand 'offen' (laeuft lokal weiter).
    """
    try:
        auftrag = auftrag_service.einzeln(auftrag_id)
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        volle_id = auftrag["id"]
        # 1) Laufenden (PC-)Hermes-/tmux-Kontext sauber beenden.
        try:
            from app.services.hermes_local import lokale_jobs_beenden_fuer
            lokale_jobs_beenden_fuer(volle_id)
        except Exception:
            pass  # kein lokaler Job — egal
        # 2) Auftrag lokal neu starten (Track C).
        from app.router.chat import _starte_lokale_hermes
        starte_lokale_hermes(
            auftrag.get("auftrag", ""),
            hinweis="Vom Nutzer auf Handy-Hermes gewechselt",
            kategorie=auftrag.get("kategorie"),
            komplexitaet=auftrag.get("komplexitaet"),
            chat_verknuepfung=auftrag.get("conversation_id") or "",
        )
        # 3) Auftrag im Buch als offen/laeuft markieren.
        try:
            auftrag = auftrag_service.status_aendern(volle_id, "offen")
        except Exception:
            pass
        logger.info("Auftrag %s auf Handy-Hermes gewechselt", volle_id[:8])
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Wechsel auf Handy fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.post("/{auftrag_id}/status", response_model=AuftragItem)
def statusmeldung_hinzufuegen(auftrag_id: str, meldung: StatusMeldungCreate):
    """Zwischenstand des Coding-Agenten eintragen."""
    try:
        auftrag = auftrag_service.statusmeldung_hinzufuegen(
            auftrag_id, meldung.meldung
        )
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Statusmeldung fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.post("/{auftrag_id}/rueckfrage", response_model=AuftragItem)
def rueckfrage_stellen(auftrag_id: str, rueckfrage: RueckfrageCreate):
    """Coding-Agent stellt eine Rueckfrage."""
    try:
        auftrag = auftrag_service.rueckfrage_stellen(
            auftrag_id, rueckfrage.frage, rueckfrage.kontext
        )
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Rueckfrage fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.post("/{auftrag_id}/antwort/{antwort_idx}", response_model=AuftragItem)
def rueckfrage_beantworten(auftrag_id: str, antwort_idx: int, antwort: AntwortCreate):
    """Nutzer beantwortet eine Rueckfrage."""
    try:
        auftrag = auftrag_service.rueckfrage_beantworten(
            auftrag_id, antwort_idx, antwort.antwort
        )
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag oder Rueckfrage nicht gefunden")
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Antwort fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


def _status_emoji(status: str) -> str:
    return {"offen": "🟡", "laeuft": "🔄", "fertig": "✅", "fehler": "❌"}.get(status, "❓")
