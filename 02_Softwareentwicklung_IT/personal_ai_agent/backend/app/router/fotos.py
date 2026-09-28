"""Router: Fotos – GET /api/fotos/uebersicht und GET /api/fotos/bilder.

Warum es diese Endpunkte gibt
-----------------------------
Der Nutzer fragt in der App am Handy „wie viele Events gab's?", „zeig mir
die Urlaube 2021" oder „zeig mir die Bilder vom Urlaub 2021". Die
Sortierdaten (Sortierschlüssel, ``themen.jsonl``, ``kategorien.json``) liegen
**nur auf dem PC**; am Handy gibt es sie nicht. Die Nachtlauf-Schritte ziehen
daraus **kleine** Dateien in ``~/foto_sortierung``:

  * ``fotos_uebersicht.json`` (N11) — nur Zahlen und Event-Namen, **bewusst
    ohne Datei-Kennungen**; daraus entsteht ``GET /api/fotos/uebersicht``,
  * ``fotos_dateien.json`` (N13a) — je Event die Datei-Kennungen
    (``datei_id`` und Name), erst damit lässt sich am Handy ein Vorschaubild
    laden; daraus entsteht ``GET /api/fotos/bilder``.

Die Chat-Anhängung (``_fotos_uebersicht_tool`` in ``router/chat.py``) nutzt
denselben Dienst wie ``/api/fotos/uebersicht``.

Eiserne Regeln
--------------
  * **IMMER HTTP 200** und **immer dieselben Felder**. Fehlt eine Datei (der
    Normalfall auf einem frisch eingerichteten Handy), steht das als deutscher
    ``error``-Text im JSON und ``ok`` ist ``false`` — nie ein 500er, nie ein
    Absturz.
  * **Nur lesend, kein Netz, keine Bilder.** Die Dienste lesen ausschließlich
    die lokalen Dateien; es werden keine Bilddateien angefasst, keine
    Bilddaten ausgeliefert und keine Fremdsysteme aufgerufen.
  * **Keine Geheimnisse.** Ausgegeben werden Zahlen, Stand, Listen, der
    Dateiname der Quelle und die Kennungen aus der lokalen Datei — kein
    Schlüssel, kein Token.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.services import foto_bilder, foto_uebersicht

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


@router.get("/bilder")
def fotos_bilder(
    jahr: Optional[int] = Query(None, description="Nur Events dieses Jahres"),
    kategorie: Optional[str] = Query(None, max_length=200,
                                     description="Nur Events dieser Kategorie"),
    event: Optional[str] = Query(None, max_length=200,
                                 description="Teilzeichenkette im Event-Namen"),
    limit: int = Query(5, description="Höchstzahl der Events (1…50)"),
    pro_event: int = Query(40, description="Höchstzahl der Dateien je Event (1…200)"),
) -> Dict[str, Any]:
    """Events mit den Datei-Kennungen aus der lokalen Kennungsdatei (N13a).

    Antwortet immer mit HTTP 200 und allen Feldern ``ok``, ``quelle``,
    ``stand``, ``zahlen``, ``events``, ``anzahl``, ``error``. Fehlt die Datei,
    sind ``ok`` falsch, die Listen leer und ``error`` trägt einen deutschen
    Text — der Endpunkt bleibt erreichbar, damit die App ehrlich melden kann,
    dass die Kennungen noch auf dem PC liegen.

    ``pro_event`` kürzt die Dateiliste je Event; die Zeile trägt weiter
    ``anzahl`` mit der echten Gesamtzahl, damit die App „42 Bilder, 40
    gezeigt" sagen kann. Es werden **keine Bilddaten** ausgeliefert, nur
    Kennung und Dateiname.
    """
    antwort: Dict[str, Any] = {
        "ok": False,
        "quelle": None,
        "stand": None,
        "zahlen": {},
        "events": [],
        "anzahl": 0,
        "error": None,
    }

    try:
        daten = foto_bilder.dateien_laden()

        pfad = daten.get("pfad")
        if isinstance(pfad, str) and pfad.strip():
            antwort["quelle"] = os.path.basename(pfad) or None

        if not daten.get("existiert"):
            # Kein Wurf, kein 500er: Der Grund steht als Text in der Antwort.
            antwort["error"] = daten.get("error") or "Datei-Kennungen nicht gefunden"
            return antwort

        antwort["ok"] = True
        antwort["error"] = None

        stand = daten.get("stand")
        antwort["stand"] = stand if isinstance(stand, str) else None

        zahlen = daten.get("zahlen")
        zahlen = zahlen if isinstance(zahlen, dict) else {}
        # Bewusst nur zwei Zahlen: Wie viele Events und wie viele Dateien die
        # Quelle kennt — der Rest der Datei ist für die Anzeige nicht nötig.
        for feld in ("events", "dateien"):
            wert = zahlen.get(feld)
            antwort["zahlen"][feld] = (
                wert if isinstance(wert, int) and not isinstance(wert, bool) else None
            )

        antwort["events"] = foto_bilder.bilder_finden(
            jahr=jahr, kategorie=kategorie, event=event, limit=limit,
            pro_event=pro_event,
        )
        antwort["anzahl"] = len(antwort["events"])
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Datei-Kennungen fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["zahlen"] = {}
        antwort["events"] = []
        antwort["anzahl"] = 0
        antwort["error"] = f"Datei-Kennungen nicht lesbar ({type(e).__name__})"

    return antwort

