"""Routing für Coding-/Werkzeug-Aufträge (aus chat.py extrahiert — Refactoring).

Kapselt die Weiche, die entscheidet, wohin ein erkannter Programmier-/Werkzeug-
Auftrag geht (die "Hermes als Toolcall"-Logik):

  1. Track A — PC-Hermes (im WLAN erreichbar) → Antwort direkt.
  2. Track C — Lokaler Hermes auf dem Gerät (Termux-CLI) → Live bearbeiten.
  3. Track B — Auftragsbuch (nur wenn beides nicht verfügbar/erfolgreich).

Die Funktionen `_finish_exchange` / `_get_or_create_conversation` sowie
`_starte_lokale_hermes` werden injiziert, damit der Service isoliert testbar ist
und keinen harten Import auf den Router braucht.
"""

import logging
from typing import Any, Dict, Optional

from app.services.hermes_gateway import hermes_gateway
from app.services.hermes_local import ist_verfuegbar as hermes_local_ist_verfuegbar

logger = logging.getLogger(__name__)


def statusmeldung_wartet(eintrag_id: str) -> None:
    """Kurze 'wartet auf Bearbeitung'-Meldung für das Frontend-Tracking."""
    from app.services.auftrag_service import auftrag_service
    auftrag_service.statusmeldung_hinzufuegen(
        eintrag_id, "⏳ **Hermes wurde benachrichtigt** – wartet auf Bearbeitung..."
    )


def anlegen_im_buch(auftrag: str, begruendung: str,
                    kategorie: Optional[str], komplexitaet: Optional[str]) -> Any:
    from app.services.auftrag_service import auftrag_service
    return auftrag_service.anlegen(
        auftrag, hinweis=f"Automatische Erkennung: {begruendung}",
        kategorie=kategorie, komplexitaet=komplexitaet,
    )


def verknuepfe_chat(eintrag_id: str, conversation_id: str) -> None:
    from app.services.auftrag_service import auftrag_service
    auftrag_service.setze_chat_verknuepfung(eintrag_id, conversation_id)


def _starte_lokale_hermes_default(auftrag, hinweis, kategorie, komplexitaet, chat_verknuepfung):
    """Fallback-Platzhalter; wird vom Router beim Verdrahten überschrieben."""
    raise NotImplementedError("starte_lokale_hermes nicht injiziert")


def route_auftrag(
    message: str,
    begruendung: str,
    kategorie: Optional[str],
    komplexitaet: Optional[str],
    finish_exchange,
    get_or_create_conversation,
    starte_lokale_hermes,
) -> Dict[str, Any]:
    """Führt die Track-A/C/B-Weiche für einen erkannten Coding-Auftrag aus.

    Returns ein Dict mit den Feldern der Chat-Antwort:
        { "art": "pc"|"lokal"|"buch", "reply": str, "conversation_id": str }
    Aufrufer baut daraus die ChatResponse/SSE.
    """
    # 1) PC-Hermes (Track A)
    hermes_antwort = hermes_gateway.sende_auftrag(message)
    if hermes_antwort is not None:
        conv_id = get_or_create_conversation(None)
        finish_exchange(conv_id, message, hermes_antwort)
        return {"art": "pc", "reply": hermes_antwort, "conversation_id": conv_id}

    # 2) Lokaler Hermes (Track C)
    if hermes_local_ist_verfuegbar():
        conv_id = get_or_create_conversation(None)
        eintrag = starte_lokale_hermes(
            message,
            hinweis=f"Automatische Erkennung: {begruendung}",
            kategorie=kategorie,
            komplexitaet=komplexitaet,
            chat_verknuepfung=conv_id,
        )
        reply_text = (
            "🧩 **Coding-Auftrag erkannt – lokaler Hermes übernimmt.**\n\n"
            f"📋 **Aufgabe:** {message[:150]}…\n\n"
            "Gedanken & Zwischenschritte erscheinen hier live, das "
            "Endergebnis danach.\n"
        )
        finish_exchange(conv_id, message, reply_text)
        return {"art": "lokal", "reply": reply_text, "conversation_id": conv_id}

    # 3) Auftragsbuch (Track B)
    eintrag = anlegen_im_buch(message, begruendung, kategorie, komplexitaet)
    statusmeldung_wartet(eintrag["id"])
    reply_text = (
        "🧩 **Coding-Auftrag erkannt – wird bearbeitet.**\n\n"
        f"📋 **Aufgabe:** {message[:150]}…\n\n"
        "Hermes nimmt sich der Aufgabe an. Sobald ein Ergebnis vorliegt, "
        "erscheint es live hier.\n"
    )
    conv_id = get_or_create_conversation(None)
    finish_exchange(conv_id, message, reply_text)
    verknuepfe_chat(eintrag["id"], conv_id)
    return {"art": "buch", "reply": reply_text, "conversation_id": conv_id}
