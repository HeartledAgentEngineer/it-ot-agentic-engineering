"""Router: Fotos-Übersicht – GET /api/fotos/uebersicht (N11, Teil B, 27.09.2026).

Warum es diesen Endpunkt gibt
-----------------------------
Der Nutzer fragt in der App am Handy „wie viele Events gab's?" oder „zeig mir
die Urlaube 2021". Die Sortierdaten (Sortierschlüssel, ``themen.jsonl``,
``kategorien.json``) liegen **nur auf dem PC**; am Handy gibt es sie nicht.
Der Nachtlauf-Schritt N11 zieht daraus eine **kleine** Datei
(``~/foto_sortierung/fotos_uebersicht.json``) — nur Zahlen und Event-Namen,
ohne Bilder. Dieser Endpunkt liefert genau diese Zahlen als JSON; die
Chat-Anhängung (``_fotos_uebersicht_tool`` in ``router/chat.py``) nutzt
denselben Dienst.

Eiserne Regeln
--------------
  * **IMMER HTTP 200** und **immer dieselben Felder**. Fehlt die Datei (der
    Normalfall auf einem frisch eingerichteten Handy), steht das als deutscher
    ``error``-Text im JSON und ``ok`` ist ``false`` — nie ein 500er, nie ein
    Absturz.
  * **Nur lesend, kein Netz, keine Bilder.** Der Dienst liest ausschließlich
    die lokale Übersichtsdatei; es werden keine Bilddateien angefasst und
    keine Fremdsysteme aufgerufen.
  * **Keine Geheimnisse.** Ausgegeben werden Zahlen, Stand, Listen und der
    Dateiname der Quelle — kein Schlüssel, kein Token.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.services import foto_uebersicht

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fotos", tags=["fotos"])


@router.get("/uebersicht")
def fotos_uebersicht(
    jahr: Optional[int] = Query(None, description="Nur Events dieses Jahres"),
    kategorie: Optional[str] = Query(None, max_length=200,
                                     description="Nur Events dieser Kategorie"),
    suche: Optional[str] = Query(None, max_length=200,
                                 description="Teilzeichenkette im Event-Namen"),
    limit: int = Query(25, description="Höchstzahl der Events (1…200)"),
) -> Dict[str, Any]:
    """Zahlen und Event-Namen aus der lokalen Fotos-Übersicht.

    Antwortet immer mit HTTP 200 und allen Feldern
    ``ok``, ``quelle``, ``stand``, ``zahlen``, ``jahre``, ``themen``,
    ``kategorien``, ``events``, ``error``. Fehlt die Übersichtsdatei, sind
    ``ok`` falsch, die Listen leer und ``error`` trägt einen deutschen Text —
    der Endpunkt bleibt erreichbar, damit die App ehrlich melden kann, dass
    die Zahlen noch auf dem PC liegen.
    """
    antwort: Dict[str, Any] = {
        "ok": False,
        "quelle": None,
        "stand": None,
        "zahlen": {},
        "jahre": [],
        "themen": [],
        "kategorien": [],
        "events": [],
        "error": None,
    }

    try:
        daten = foto_uebersicht.uebersicht_laden()

        pfad = daten.get("pfad")
        if isinstance(pfad, str) and pfad.strip():
            antwort["quelle"] = os.path.basename(pfad) or None

        if not daten.get("existiert"):
            # Kein Wurf, kein 500er: Der Grund steht als Text in der Antwort.
            antwort["error"] = daten.get("error") or "Fotos-Übersicht nicht gefunden"
            return antwort

        antwort["ok"] = True
        antwort["error"] = None

        stand = daten.get("stand")
        antwort["stand"] = stand if isinstance(stand, str) else None

        zahlen = daten.get("zahlen")
        antwort["zahlen"] = zahlen if isinstance(zahlen, dict) else {}

        for feld in ("jahre", "themen", "kategorien"):
            wert = daten.get(feld)
            antwort[feld] = wert if isinstance(wert, list) else []

        antwort["events"] = foto_uebersicht.events_finden(
            jahr=jahr, kategorie=kategorie, suche=suche, limit=limit
        )
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Fotos-Übersicht fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["error"] = f"Fotos-Übersicht nicht lesbar ({type(e).__name__})"

    return antwort
