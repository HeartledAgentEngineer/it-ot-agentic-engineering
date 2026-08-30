"""Gesichter-Katalog-Endpoints (Personen-Merkliste).

Ermöglicht, den Katalog zu lesen (wie viele Personen kennt der Agent) und
Personen zu pflegen (anlegen/ändern, löschen). Der eigentliche Abgleich
("wer ist auf dem Foto?") passiert im Chat-Flow über den Vision-LLM mit
dem katalog_kontext()-Boost — hier wird nur der Speicher verwaltet.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import gesichter_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gesichter", tags=["gesichter"])


class PersonCreate(BaseModel):
    """Eingabe fürs Anlegen/Aktualisieren einer Person."""
    name: str = Field(..., min_length=1, max_length=100)
    rolle: str = Field(default="", max_length=200)
    beziehung: str = Field(default="", max_length=500)
    beschreibung: str = Field(default="", max_length=1000)
    # NUR der Pfad — die Originaldatei bleibt unangetastet (Sebastian-Regel).
    # Aus diesem Pfad erzeugt der Service automatisch eine kleine eingebettete
    # Miniatur, die auch pCloud-Transfers des Originals übersteht.
    referenz_bild_pfad: str = Field(default="", max_length=1000)


@router.get("")
def gesichter_liste():
    """Alle gelernten Personen (Name, Rolle, Beschreibung, Referenzbild-Pfad)."""
    return {
        "personen": gesichter_service.liste_personen(),
        "anzahl": len(gesichter_service.liste_personen()),
    }


@router.post("")
def gesichter_speichern(person: PersonCreate):
    """Person anlegen oder (nach Name) aktualisieren."""
    try:
        p = gesichter_service.person_speichern(
            name=person.name,
            rolle=person.rolle,
            beziehung=person.beziehung,
            beschreibung=person.beschreibung,
            referenz_bild_pfad=person.referenz_bild_pfad,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"person": p}


@router.delete("/{name}")
def gesichter_loeschen(name: str):
    """Gelernte Person nach Name löschen."""
    entschluesselt = name  # FastAPI-URL-Pfad, bereits decodiert
    if not gesichter_service.person_entfernen(entschluesselt):
        raise HTTPException(status_code=404, detail=f"Person '{name}' nicht gefunden")
    return {"status": "deleted", "name": name}


@router.get("/kontext")
def gesichter_kontext():
    """Der Kontext-Block für den Prompt (Tests/Frontend-Debug)."""
    return {"kontext": gesichter_service.katalog_kontext()}