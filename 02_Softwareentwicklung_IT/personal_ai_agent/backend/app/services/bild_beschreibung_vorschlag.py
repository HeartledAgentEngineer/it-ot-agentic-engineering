"""Vision-Vorschlag für die Beschreibung EINES Bildes (G2, 02.11.2026).

Warum es dieses Modul gibt
--------------------------
Im Vollbild-Editor kann Sebastian für ein einzelnes Bild eine neue Beschreibung
vorschlagen lassen („✨ Neu beschreiben lassen“). Dieses Modul holt dafür die
Vorschau des Bildes aus der pCloud (mittlere Größe) und stellt EINE Vision-Anfrage
über den vorhandenen OpenRouter-Weg (``OpenRouterZDRClient``, ZDR erzwungen).

Eiserne Regeln
--------------
  * **Es wird nichts gespeichert.** Das Ergebnis geht nur zurück an den Aufrufer;
    gespeichert wird erst durch ``erzaehl_service.beschreibung_uebernehmen_ki``.
  * ``data_collection: deny`` steht im Aufruf selbst (zusätzlich zur Härtung des Clients).
  * Zeitgrenze 30 s, Ausgabe auf ``MAX_TOKENS`` begrenzt.
  * Fehler kommen als ``{"ok": False, "grund": ...}`` mit ehrlichem Klartext zurück —
    nie mit Schlüssel, URL oder dem Text der Ausnahme.
  * Im Log stehen nur Modell, Dauer, Zeichenzahl und Kosten — nie der Text, nie die fileid.
  * Der Client und der Bildabruf sind einspielbar (Tests arbeiten mit Attrappen).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Callable, Dict, Optional

import httpx

from app.config import settings
from app.services.modell_router import MODELL_VISION
from app.services.openrouter_client import OpenRouterZDRClient
from app.services.pcloud_service import (
    PCloudFehler,
    PCloudNichtKonfiguriert,
    media_typ_fuer_bild,
    pcloud_service,
)

logger = logging.getLogger(__name__)

ZEITGRENZE_S = 30
MAX_TOKENS = 400
VORSCHAU_GROESSE = "480x480"
BESCHREIBUNG_MAX_LAENGE = 600     # wie ``erzaehl_service.BESCHREIBUNG_MAX_LAENGE`` (was angezeigt wird, wird gespeichert)

PROMPT = (
    "Beschreibe sachlich auf Deutsch in 2–4 Sätzen, was auf dem Bild zu sehen ist; "
    "erfinde keine Namen."
)

# Preise in USD je 1 Mio Token (Eingang, Ausgang) — OpenRouter, live abgefragt am 27.09.2026
# (docs/plan-nachtlauf-2026-09-26.md). Nur ein Rückfall, falls die Antwort keine Kosten nennt.
PREISE_USD_PRO_MIO: Dict[str, tuple] = {
    MODELL_VISION: (0.75, 3.75),
}


class BildNichtLadbar(Exception):
    """Das Vorschaubild konnte nicht geholt werden — der Text ist ein ehrlicher Klartext."""


def _schluessel() -> str:
    return (getattr(settings, "openrouter_api_key", "") or "").strip()


def standard_client() -> OpenRouterZDRClient:
    """Der vorhandene OpenRouter-Client mit erzwungenem ZDR und der Zeitgrenze dieses Moduls."""
    return OpenRouterZDRClient(api_key=_schluessel(), timeout=float(ZEITGRENZE_S))


def standard_bild_holer(fileid: int) -> bytes:
    """Vorschaubild (mittlere Größe) über den vorhandenen pCloud-Dienst."""
    if not pcloud_service.ist_konfiguriert():
        raise BildNichtLadbar("pCloud ist nicht eingerichtet — das Bild kann nicht geholt werden.")
    try:
        return pcloud_service.thumb(int(fileid), VORSCHAU_GROESSE)
    except PCloudNichtKonfiguriert as e:
        raise BildNichtLadbar(str(e)) from e
    except PCloudFehler as e:
        raise BildNichtLadbar(str(e)) from e


def _text_begrenzen(roh: str) -> str:
    """Leerraum ordnen und auf die Speicherlänge kürzen (am liebsten am Satzende)."""
    text = " ".join(roh.split())
    if len(text) <= BESCHREIBUNG_MAX_LAENGE:
        return text
    kurz = text[:BESCHREIBUNG_MAX_LAENGE]
    ende = max(kurz.rfind(". "), kurz.rfind("! "), kurz.rfind("? "))
    if ende > BESCHREIBUNG_MAX_LAENGE // 2:
        return kurz[:ende + 1]
    return kurz


def _kosten(antwort: Dict[str, Any], modell: str) -> Optional[float]:
    """Kosten in USD: ``usage.cost`` der Antwort, sonst aus Token und bekannten Preisen, sonst ``None``."""
    usage = antwort.get("usage") if isinstance(antwort, dict) else None
    if not isinstance(usage, dict):
        return None
    kosten = usage.get("cost")
    if isinstance(kosten, (int, float)) and not isinstance(kosten, bool):
        return float(kosten)
    ein, aus = usage.get("prompt_tokens"), usage.get("completion_tokens")
    preise = PREISE_USD_PRO_MIO.get(modell)
    if preise and isinstance(ein, (int, float)) and isinstance(aus, (int, float)):
        return (ein * preise[0] + aus * preise[1]) / 1_000_000
    return None


def _fehler(grund: str) -> Dict[str, Any]:
    return {"ok": False, "grund": grund}


def vorschlag_fuer_fileid(
    fileid: Any,
    *,
    bild_holer: Optional[Callable[[int], bytes]] = None,
    client: Any = None,
    modell: str = MODELL_VISION,
) -> Dict[str, Any]:
    """Beschreibungsvorschlag für ein Bild. **Speichert nichts, wirft nie.**

    Erfolg ``{"ok": True, "vorschlag", "modell", "kosten_usd"}``, Fehler
    ``{"ok": False, "grund"}``. ``bild_holer`` und ``client`` sind einspielbar
    (``client`` braucht ``chat_completion(messages, model, temperature, max_tokens,
    extra_payload)``).
    """
    try:
        fid = int(str(fileid).strip())
    except (TypeError, ValueError):
        return _fehler("Ungültige Bildkennung.")
    if fid < 0:
        return _fehler("Ungültige Bildkennung.")

    if client is None:
        if not _schluessel():
            return _fehler("Kein OpenRouter-Schlüssel eingerichtet — es wurde nichts angefragt.")
        client = standard_client()

    holer = bild_holer or standard_bild_holer
    try:
        bild = holer(fid)
    except BildNichtLadbar as e:
        return _fehler(str(e) or "Das Vorschaubild konnte nicht geholt werden.")
    except Exception as e:  # noqa: BLE001 – ehrlich, aber ohne den Text der Ausnahme
        logger.warning("Bildbeschreibung-Vorschlag: Bildabruf fehlgeschlagen (%s)", type(e).__name__)
        return _fehler("Das Vorschaubild konnte nicht geholt werden.")
    if not bild:
        return _fehler("Das Vorschaubild war leer.")

    data_url = f"data:{media_typ_fuer_bild(bild)};base64,{base64.b64encode(bild).decode('ascii')}"
    nachrichten = [{
        "role": "user",
        "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]

    start = time.monotonic()
    try:
        antwort = client.chat_completion(
            nachrichten,
            model=modell,
            temperature=0.2,
            max_tokens=MAX_TOKENS,
            extra_payload={"provider": {"data_collection": "deny"}, "usage": {"include": True}},
        )
    except httpx.TimeoutException:
        logger.warning("Bildbeschreibung-Vorschlag: Zeitgrenze (%s s) überschritten, Modell %s", ZEITGRENZE_S, modell)
        return _fehler(f"Die Zeitgrenze von {ZEITGRENZE_S} Sekunden wurde überschritten — bitte später noch einmal versuchen.")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else "?"
        logger.warning("Bildbeschreibung-Vorschlag: HTTP %s, Modell %s", status, modell)
        return _fehler(f"Der Modelldienst hat die Anfrage abgelehnt (HTTP {status}).")
    except httpx.HTTPError as e:
        logger.warning("Bildbeschreibung-Vorschlag: Verbindungsfehler (%s), Modell %s", type(e).__name__, modell)
        return _fehler("Der Modelldienst ist nicht erreichbar.")
    except Exception as e:  # noqa: BLE001
        logger.warning("Bildbeschreibung-Vorschlag: Fehler (%s), Modell %s", type(e).__name__, modell)
        return _fehler("Der Vorschlag konnte nicht erstellt werden.")
    dauer = time.monotonic() - start

    try:
        roh = antwort["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        roh = None
    if not isinstance(roh, str) or not roh.strip():
        logger.warning("Bildbeschreibung-Vorschlag: leere Antwort, Modell %s, %.1f s", modell, dauer)
        return _fehler("Das Modell hat keine Beschreibung geliefert.")

    text = _text_begrenzen(roh)
    kosten = _kosten(antwort, modell)
    logger.info("Bildbeschreibung-Vorschlag: Modell %s, %.1f s, %d Zeichen, Kosten %s",
                modell, dauer, len(text), "unbekannt" if kosten is None else f"{kosten:.6f} USD")
    return {"ok": True, "vorschlag": text, "modell": modell, "kosten_usd": kosten}
