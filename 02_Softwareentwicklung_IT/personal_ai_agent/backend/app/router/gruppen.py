"""Personen benennen im Gruppenmodus — Routen (Plan Foto-Gedaechtnis Schritt 2, 01.10.2026).

  GET  /api/gruppen/stand         Ueberblick (Gruppen, benannt, offen, Namen)
  GET  /api/gruppen/naechste      groesste offene Gruppe mit Beispielen + Zwillingen
  POST /api/gruppen/antwort       {kennung, art, name?, ziel?} -> speichern + naechste
  POST /api/gruppen/rueckgaengig  letzte Antwort zuruecknehmen
  GET  /api/gruppen/bilder        ?namen=Leon,Tim&modus=alle|eine|genau&limit=100
  GET  /api/gruppen/profil        ?name=Leon -> Beziehung + Erinnerungen
  POST /api/gruppen/profil        {name, beziehung?, notiz?, kennung?} -> anhaengen
  GET  /api/gruppen/suche         ?q=Le&limit=12 -> benannte Personen, dann Kontakte

Immer HTTP 200 mit ``ok`` und deutschem ``fehler``-Text (wie fotos/erzaehlen) —
die Oberflaeche zeigt den Text an, statt an einem Statuscode zu scheitern.
Die Logik steht in ``app/services/gruppen_quiz.py``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import gruppen_quiz

router = APIRouter(prefix="/api/gruppen", tags=["gruppen"])


class GruppenAntwort(BaseModel):
    kennung: str
    art: str
    name: Optional[str] = None
    ziel: Optional[str] = None
    beziehung: Optional[str] = None
    notiz: Optional[str] = None
    kontakt_id: Optional[str] = None


class ProfilEingabe(BaseModel):
    name: str
    beziehung: Optional[str] = None
    notiz: Optional[str] = None
    kennung: Optional[str] = None


@router.get("/stand")
def stand() -> Dict[str, Any]:
    return gruppen_quiz.stand()


@router.get("/naechste")
def naechste() -> Dict[str, Any]:
    return gruppen_quiz.naechste()


@router.post("/antwort")
def antwort(eingabe: GruppenAntwort) -> Dict[str, Any]:
    return gruppen_quiz.antworten(eingabe.kennung, eingabe.art, eingabe.name, eingabe.ziel,
                                  eingabe.beziehung, eingabe.notiz, eingabe.kontakt_id)


@router.post("/rueckgaengig")
def rueckgaengig() -> Dict[str, Any]:
    return gruppen_quiz.rueckgaengig()


@router.get("/bilder")
def bilder(
    namen: str = Query(..., description="Namen, mit Komma getrennt"),
    modus: str = Query(default="alle", pattern="^(alle|eine|genau)$"),
    limit: int = Query(default=100, ge=1, le=gruppen_quiz.BILDER_LIMIT_MAX),
) -> Dict[str, Any]:
    return gruppen_quiz.bilder_mit(namen.split(","), modus, limit)


@router.get("/profil")
def profil(name: str = Query(..., min_length=1, max_length=60)) -> Dict[str, Any]:
    return gruppen_quiz.profil(name)


@router.post("/profil")
def profil_ergaenzen(eingabe: ProfilEingabe) -> Dict[str, Any]:
    return gruppen_quiz.profil_ergaenzen(eingabe.name, eingabe.beziehung, eingabe.notiz,
                                         eingabe.kennung)


@router.get("/suche")
def suche(q: str = Query(default="", max_length=60),
          limit: int = Query(default=12, ge=1, le=gruppen_quiz.SUCHE_LIMIT_MAX)) -> Dict[str, Any]:
    return gruppen_quiz.suche(q, limit)
