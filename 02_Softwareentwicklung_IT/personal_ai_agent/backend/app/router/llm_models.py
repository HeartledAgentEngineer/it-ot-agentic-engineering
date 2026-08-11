"""
Router: Modellauswahl

  GET /api/models                  Alle nutzbaren Modelle mit Preis und Kontext
  GET /api/models/{id}/details     Wer bedient das Modell, was macht er mit den Daten

Warum diese Datei nicht `models.py` heisst: `app.models` gibt es bereits
(die Pydantic-Schemata). Zwei Module gleichen Namens im selben Namensraum
sind in Python zwar erlaubt, aber eine Falle fuer den naechsten Leser.

Der Katalog kommt von `GET /models/user` – der filtert serverseitig nach
Provider-Whitelist, Privacy-Einstellungen und Guardrails des Kontos. Der
oeffentliche Katalog wuerde auch zeigen, was gesperrt ist; eine Auswahl mit
nicht waehlbaren Eintraegen ist keine Auswahl.

Sicherheit:
  - Kein API-Key in Request oder Antwort
  - Nur lesende Aufrufe, keine Kosten
"""

import logging

from fastapi import APIRouter

from app.config import settings
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["models"])

# Steht so auch in der Oberflaeche. Ein Werkzeug, das mehr verspricht als es
# haelt, ist schaedlicher als keines: Die Angaben helfen bei der Auswahl,
# sie ersetzen weder einen Auftragsverarbeitungsvertrag noch eine
# Rechtsgrundlage, Betroffenenrechte oder ein Verarbeitungsverzeichnis.
HAFTUNGSHINWEIS = (
    "Auswahlhilfe, kein Konformitätsnachweis. Die Angaben stammen von "
    "OpenRouter und ersetzen keinen Auftragsverarbeitungsvertrag."
)


# Bewusst `def` statt `async def`: Der Katalogaufbau macht rund 110 parallele
# HTTP-Abrufe und braucht etwa eine Sekunde. In einer async-Funktion würde das
# den Event-Loop blockieren und den laufenden Chat-Stream ausbremsen; als
# synchrone Funktion schiebt FastAPI sie in einen Threadpool.
@router.get("/models")
def models():
    """Alle Modelle, die dieses Konto tatsächlich benutzen darf.

    `eu: true` heisst: Dieses Modell *wuerde* ueber den EU-Endpunkt bedient.
    Nutzbar ist das nur mit Enterprise-Vertrag – der Chat darueber wird fuer
    ein normales Konto mit HTTP 403 abgelehnt. Deshalb ist es ein Abzeichen
    und kein Schalter.
    """
    liste = llm_service.list_models()
    notliste = bool(liste) and liste[0].get("notliste")

    if notliste:
        logger.warning(
            "Modellkatalog nicht erreichbar – Notliste aus "
            "allowed_models_fallback wird ausgeliefert."
        )

    return {
        "aktuell": settings.llm_model,
        "favoriten": settings.favorite_models,
        "models": liste,
        "total": len(liste),
        "eu_verfuegbar": sum(1 for m in liste if m.get("eu")),
        "speicherfrei_verfuegbar": sum(1 for m in liste if m.get("speicherfrei")),
        # Damit das Frontend erklaeren kann, warum die Liste kurz ist,
        # statt eine leere Auswahl zu zeigen.
        "notliste": notliste,
        "konfiguriert": llm_service.is_configured,
        "hinweis": HAFTUNGSHINWEIS,
    }


@router.get("/models/{model_id:path}/details")
def model_details(model_id: str):
    """Anbieter eines Modells samt Datenschutz-Profil.

    `model_id` enthaelt einen Schraegstrich (`anthropic/claude-sonnet-5`),
    deshalb `:path` – sonst matcht die Route nur den Teil bis zum Slash.
    """
    details = llm_service.model_details(model_id)
    details["hinweis"] = HAFTUNGSHINWEIS
    return details
