"""Datenstand: liegt eine Fotoquelle WIRKLICH auf diesem Gerät? (T0)

Auftrag: ``.hermes/plans/gesamtplan-foto-erinnerungen-2026-10-11.md``, Abschnitt
**T0** („Fotoquellen wirklich bis zum Handy nachweisen"). Ergebnis für den
Nutzer ist **unter „Datenstand" eine Statuszeile pro Quelle**:

    entpackt → Bildindex → Gesichtserkennung → Gruppenbestand → auf diesem Handy

Die Messung selbst ist fertig (``app.services.import_status``, mit eigenen
Tests); dieser Weg bringt sie in die Oberfläche. Er ändert an der Messung
nichts: **derselbe Berichtsvertrag**, dieselben Regeln — nur Summen, kein Pfad,
kein Name, kein Ortswert, keine Bild-ID, kein Vektor; fehlender Messwert ist
``null`` und nicht ``0``.

Zwei Entscheidungen, die hier festgeschrieben sind:

* **Gemessen wird auf dem Gerät, nicht am PC.** Läuft diese Route, dann läuft
  der Server auf dem Handy und liest dessen Dateien — deshalb geht
  ``handy_stand_geprueft`` hier als ``True`` in den Bericht (die fünfte Station
  „auf diesem Handy" ist damit wirklich beantwortet und nicht geraten).
* **Ein Stand gilt für eine Weile** (``import_status.STANDARD_CACHE_SEKUNDEN``).
  Eine volle Messung liest auf dem Gerät rund 250 MB an Plan- und
  Vektordateien; eine Anzeige, die bei jedem Öffnen misst, würde das Gerät
  blockieren. ``?neu=true`` misst ausdrücklich frisch (Knopf „Neu messen").

Nur lesend, kein Netz, kein Schreibzugriff, kein Bild und kein Modellaufruf.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.router import auth
from app.sicherheit import client_ist_loopback
from app.services import import_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datenstand", tags=["datenstand"])


@router.get("/fotoquellen")
def fotoquellen_stand(
    request: Request,
    neu: bool = Query(False, description="Wahr = jetzt frisch messen statt den "
                                         "gespeicherten Stand zu liefern."),
):
    """Der datensparsame Quellenstatus für die Oberfläche (nur lesend).

    Schutz wie beim Server-Protokoll und beim Update-Knopf: **das Gerät selbst
    (Loopback) darf immer** — die Anzeige ist für das Handy gedacht, dort läuft
    der Server. Für **fremde** Geräte (LAN, Tailscale) bleibt die Sperre: nur
    über HTTPS.

    Geliefert werden je Quelle die Zahlen des Berichtsvertrags, der Stand des
    Gruppenbestands, die Messdauer und die ehrliche Liste der Werte, die nicht
    gemessen werden konnten (``fehlende_werte``). Es wird nichts geschrieben.
    """
    vom_geraet_selbst = client_ist_loopback(request.scope)
    if not vom_geraet_selbst and not auth._ist_https(request):
        raise HTTPException(status_code=403,
                            detail="Der Datenstand ist von fremden Geräten nur über HTTPS abrufbar.")

    ergebnis = import_status.status_gecacht(neu=neu, handy_geprueft=True)
    bericht = ergebnis["bericht"]
    dauer = ergebnis.get("dauer_sekunden")
    return {
        "ok": True,
        **bericht,
        "aus_cache": bool(ergebnis.get("aus_cache")),
        "dauer_sekunden": round(float(dauer), 2) if isinstance(dauer, (int, float)) else None,
        "gemessen_sekunden": round(float(ergebnis.get("gemessen_sekunden") or 0.0), 2),
    }
