"""Personen benennen im Gruppenmodus — Routen (Plan Foto-Gedaechtnis Schritt 2, 01.10.2026).

  GET  /api/gruppen/stand         Ueberblick (Gruppen, benannt, offen, Namen)
  GET  /api/gruppen/naechste      groesste offene Gruppe mit Beispielen + Zwillingen
  POST /api/gruppen/antwort       {kennung, art, name?, ziel?} -> speichern + naechste
  POST /api/gruppen/rueckgaengig  letzte Antwort zuruecknehmen
  GET  /api/gruppen/bilder        ?namen=Leon,Tim&modus=alle|eine|genau&limit=100
  GET  /api/gruppen/profil        ?name=Leon -> Beziehung + Erinnerungen
  POST /api/gruppen/profil        {name, beziehung?, notiz?, kennung?, kontakt_id?,
                                  vorname?, nachname?, spitznamen?} -> anhaengen/setzen
                                  (Namensfelder 20.10.2026: nur uebergebene Felder,
                                  leer = Handfeld entfernen)
  GET  /api/gruppen/suche         ?q=Le&limit=12 -> benannte Personen, dann Kontakte
  GET  /api/gruppen/gesichter     ?kennung=Person_1001&seite=1 -> alle Gesichter, je 48
                                  ?name=Leon&seite=1 -> alle Gesichter der Person ueber alle
                                  Vorschlaege, je Gesicht seine kennung (07.10.2026)
  GET  /api/gruppen/bild-gesichter ?fileid=123 -> Gesichter eines Fotos mit Name/Rahmen
                                  (Erzaehlen, 07.10.2026: benennen / „ist nicht X“)
  POST /api/gruppen/ausschliessen {kennung, gesichter: ["bild_id:index"]}
  POST /api/gruppen/person/ausschliessen {name, gesichter: [{kennung, gid}]} (07.10.2026)
  GET  /api/gruppen/personen      benannte Personen (Liste), je Person ``gruppen``:
                                  Gruppenmetadaten (kennung, groesse, von, bis)
                                  fuer den Gruppenfilter in „Benannt“ (16.10.2026)
  GET  /api/gruppen/person        ?name=Leon -> Vorschlaege + Profil
  POST /api/gruppen/umbenennen    {alt, neu} (gleicher Name = zusammenfuehren)
  POST /api/gruppen/loesen        {kennung} -> Vorschlag wieder offen
  POST /api/gruppen/aufloesen     {kennung, trocken?} -> zugeordnete Gruppe aus der
                                  Gruppenliste nehmen (To-do Punkt 14). ``trocken=true``
                                  zaehlt nur (Gruppe, Person, Gesichter) und schreibt
                                  nichts. Bilder/Zuordnungen bleiben unberuehrt.

Immer HTTP 200 mit ``ok`` und deutschem ``fehler``-Text (wie fotos/erzaehlen) —
die Oberflaeche zeigt den Text an, statt an einem Statuscode zu scheitern.
Die Logik steht in ``app/services/gruppen_quiz.py``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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


class AusschlussEingabe(BaseModel):
    kennung: str
    gesichter: List[str]


class PersonAusschlussEingabe(BaseModel):
    """Ausschließen in der Gesamtansicht einer Person (07.10.2026): je Gesicht seine Kennung."""
    name: str
    gesichter: List[Dict[str, str]]


class UmbenennenEingabe(BaseModel):
    alt: str
    neu: str


class LoesenEingabe(BaseModel):
    kennung: str


class AufloesenEingabe(BaseModel):
    """Gruppe aufloesen (To-do Punkt 14, 18.10.2026); ``trocken`` = nur zaehlen."""
    kennung: str
    trocken: bool = False


class ProfilEingabe(BaseModel):
    """Profil erweitern. Namensfelder (20.10.2026): nur die uebergebenen Felder
    aendern sich (``None`` = nicht angefasst), leer = Handfeld entfernen."""
    name: str
    beziehung: Optional[str] = None
    notiz: Optional[str] = None
    kennung: Optional[str] = None
    kontakt_id: Optional[str] = None
    vorname: Optional[str] = None
    nachname: Optional[str] = None
    spitznamen: Optional[List[str]] = None


@router.get("/stand")
def stand() -> Dict[str, Any]:
    return gruppen_quiz.stand()


@router.get("/naechste")
def naechste() -> Dict[str, Any]:
    return gruppen_quiz.naechste()


@router.get("/liste")
def liste(
    status: str = Query(default="offen", pattern="^(offen|spaeter|benannt|ausgeblendet|aufgeloest)$"),
    seite: int = Query(default=1, ge=1, le=10000),
    je_seite: int = Query(default=24, ge=1, le=100),
) -> Dict[str, Any]:
    return gruppen_quiz.liste(status, seite, je_seite)


@router.get("/detail/{kennung}")
def detail(kennung: str) -> Dict[str, Any]:
    return gruppen_quiz.detail(kennung)


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
                                         eingabe.kennung, eingabe.kontakt_id,
                                         eingabe.vorname, eingabe.nachname, eingabe.spitznamen)


@router.get("/suche")
def suche(q: str = Query(default="", max_length=60),
          limit: int = Query(default=12, ge=1, le=gruppen_quiz.SUCHE_LIMIT_MAX)) -> Dict[str, Any]:
    return gruppen_quiz.suche(q, limit)


@router.get("/gesichter")
def gesichter(kennung: Optional[str] = Query(default=None, min_length=1, max_length=40),
              name: Optional[str] = Query(default=None, min_length=1, max_length=120),
              seite: int = Query(default=1, ge=1, le=10000),
              ordnung: str = Query(default="guete", pattern="^(guete|zeit)$")) -> Dict[str, Any]:
    """Gesichter eines Vorschlags (``kennung``) oder einer Person über alle Vorschläge (``name``).
    ``ordnung=zeit`` (10.10.2026): nach Aufnahme sortiert, für Zeitblöcke."""
    if name:
        return gruppen_quiz.gesichter_person(name, seite, ordnung=ordnung)
    if kennung:
        return gruppen_quiz.gesichter(kennung, seite, ordnung=ordnung)
    return {"ok": False, "fehler": "Bitte einen Vorschlag (kennung) oder eine Person (name) angeben."}


@router.get("/bild-gesichter")
def bild_gesichter(fileid: str = Query(..., min_length=1, max_length=20)) -> Dict[str, Any]:
    """Die Gesichter eines Fotos (Erzählen, 07.10.2026) — Benennen/Ausschließen über die vorhandenen Routen."""
    return gruppen_quiz.gesichter_auf_bild(fileid)


@router.post("/ausschliessen")
def ausschliessen(eingabe: AusschlussEingabe) -> Dict[str, Any]:
    return gruppen_quiz.ausschliessen(eingabe.kennung, eingabe.gesichter)


@router.post("/person/ausschliessen")
def person_ausschliessen(eingabe: PersonAusschlussEingabe) -> Dict[str, Any]:
    return gruppen_quiz.ausschliessen_person(eingabe.name, eingabe.gesichter)


@router.post("/zuordnen")
def zuordnen(eingabe: PersonAusschlussEingabe) -> Dict[str, Any]:
    """Markierte Gesichter fest einer benannten Person zuordnen (10.10.2026).
    Gleiche Form wie ``/person/ausschliessen``: ``name`` = Ziel, je Gesicht seine Kennung."""
    return gruppen_quiz.zuordnen(eingabe.name, eingabe.gesichter)


@router.get("/personen")
def personen() -> Dict[str, Any]:
    return gruppen_quiz.personen()


@router.get("/person")
def person(name: str = Query(..., min_length=1, max_length=60)) -> Dict[str, Any]:
    return gruppen_quiz.person(name)


@router.post("/umbenennen")
def umbenennen(eingabe: UmbenennenEingabe) -> Dict[str, Any]:
    return gruppen_quiz.umbenennen(eingabe.alt, eingabe.neu)


@router.post("/loesen")
def loesen(eingabe: LoesenEingabe) -> Dict[str, Any]:
    return gruppen_quiz.loesen(eingabe.kennung)


@router.post("/aufloesen")
def aufloesen(eingabe: AufloesenEingabe) -> Dict[str, Any]:
    return gruppen_quiz.aufloesen(eingabe.kennung, eingabe.trocken)
