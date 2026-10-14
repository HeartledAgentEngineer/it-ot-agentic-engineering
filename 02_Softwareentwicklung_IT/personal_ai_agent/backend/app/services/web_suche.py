"""Websuche mit Namensverbot (Plan `websuche-namensverbot`, Fassung 7, 14.10.2026).

Einziger Weg ins Internet: ``suchen(anfrage, nutzer_nachricht)``.

1. Namensprüfung (``websuche_schutz``) gegen den Bestand aus
   ``werkzeuge.bekannte_namen_streng()``. Freigaben für fremde volle Namen kommen nur
   aus ``nutzer_nachricht`` – Sebastians eigenem Text, nie aus Modelltext.
2. Bei einem Treffer: keine Suche, kein Netz.
3. Sonst ein eigener, kontextfreier OpenRouter-Aufruf: Die EINZIGE Eingabe ist der
   geprüfte Suchtext (kein Verlauf, keine Erinnerungen, kein Systemtext), Plugin
   ``web``, ``data_collection: deny``. Die Suchmaschine formuliert ihre Anfrage
   selbst – wortgleich ist sie nicht, aber sie kennt nichts außer dem Suchtext.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from app.services import websuche_schutz

logger = logging.getLogger(__name__)

ABGELEHNT_NAME = ("Abgelehnt: Personennamen werden nicht im Internet gesucht. Formuliere "
                  "ohne Namen (Orte und Adressen sind erlaubt) oder nutze personen_liste/"
                  "person_auskunft.")
ABGELEHNT_LISTE = "Namensliste gerade nicht lesbar – keine Websuche."
STATUS_ABGELEHNT = "🔒 Suche ohne Namen – Websuche hier ausgelassen"
MAX_ZEICHEN = 4000


@dataclass
class Suchergebnis:
    ok: bool
    text: str
    quellen: List[Dict[str, str]] = field(default_factory=list)
    abgelehnt: bool = False


def pruefen(anfrage: str, nutzer_nachricht: str = "") -> str:
    """Leer = Suche erlaubt, sonst der Ablehnungstext."""
    from app.services import werkzeuge

    bestand = werkzeuge.bekannte_namen_streng()
    if bestand is None:
        return ABGELEHNT_LISTE
    frei = websuche_schutz.freigaben(nutzer_nachricht, bestand)
    if websuche_schutz.enthaelt_namen(anfrage, bestand, frei):
        return ABGELEHNT_NAME
    return ""


def suchen(anfrage: str, nutzer_nachricht: str = "") -> Suchergebnis:
    """Geprüfte, kontextfreie Websuche. Wirft nie."""
    anfrage = str(anfrage or "").strip()
    if not anfrage:
        return Suchergebnis(False, "Leere Suchanfrage.")
    try:
        grund = pruefen(anfrage, nutzer_nachricht)
    except Exception:
        logger.exception("Websuche: Pruefung fehlgeschlagen - abgelehnt")
        grund = ABGELEHNT_LISTE
    if grund:
        return Suchergebnis(False, grund, abgelehnt=True)

    from app.services.llm_service import WEB_MAX_RESULTS, llm_service

    if not llm_service.is_configured:
        return Suchergebnis(False, "Websuche nicht verfügbar (kein API-Schlüssel).")
    try:
        antwort = llm_service.client.chat.completions.create(
            model=llm_service.model,
            messages=[{"role": "user", "content": anfrage}],
            temperature=0.2,
            max_tokens=1500,
            extra_body={
                "provider": {"allow_fallbacks": True, "data_collection": "deny"},
                "plugins": [{"id": "web", "max_results": WEB_MAX_RESULTS}],
            },
        )
        nachricht = antwort.choices[0].message
        text = (nachricht.content or "").strip()
        quellen = llm_service._quellen(getattr(nachricht, "annotations", None))
    except Exception as e:
        logger.warning("Websuche fehlgeschlagen: %s", type(e).__name__)
        return Suchergebnis(False, f"Websuche fehlgeschlagen ({type(e).__name__}).")
    if len(text) > MAX_ZEICHEN:
        text = text[:MAX_ZEICHEN] + " …"
    return Suchergebnis(True, text or "Keine Treffer.", quellen)
