"""Frei formulierte KI-Erzählung für Bild- und Anlassgeschichten (02.11.2026).

Warum es dieses Modul gibt
--------------------------
Die Geschichte wurde bisher aus einer festen Vorlage zusammengesetzt
(``erzaehl_service.verschmelze_geschichte``). Das wirkte stakkato-artig und
„zusammengereimt". Wunsch Sebastian: Das KI-Modell soll aus den KI-Bild-
beschreibungen, den Personen und seiner eigenen Erinnerung EINE zusammen-
hängende, warmherzige Geschichte auf Deutsch formulieren. Englische
Bildbeschreibungen schreibt das Modell dabei in deutsche Prosa um.

Eiserne Regeln (wie ``bild_beschreibung_vorschlag.py``)
-------------------------------------------------------
  * Ein Aufruf über den vorhandenen ``OpenRouterZDRClient`` (ZDR erzwungen),
    ``data_collection: deny`` steht zusätzlich im Aufruf selbst.
  * Zeitgrenze, Ausgabe auf ``MAX_TOKENS`` begrenzt.
  * Fehler als ``{"ok": False, "grund": ...}`` mit ehrlichem Klartext — nie mit
    Schlüssel, URL oder dem Text der Ausnahme.
  * Im Log stehen nur Modell, Dauer, Zeichenzahl und Kosten — nie der Text,
    nie Namen, nie die Erinnerung.
  * Der Client ist einspielbar (Tests arbeiten mit Attrappen, kein Netz).
  * Es wird NICHTS gespeichert — nur der Text geht an den Aufrufer zurück;
    gespeichert wird (wie bisher) erst über ``erzaehl_service.geschichte_speichern``.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.modell_router import MODELL_FLASH
from app.services.openrouter_client import OpenRouterZDRClient

logger = logging.getLogger(__name__)

MODELL_ERZAEHLUNG = MODELL_FLASH      # günstig + flink; frei formulierter deutscher Text
ZEITGRENZE_S = 45
MAX_TOKENS = 500

SYSTEM_PROMPT = (
    "Du bist ein einfühlsamer Erzähler. Du schreibst kurze, warmherzige "
    "Erinnerungs-Geschichten auf Deutsch in fließender Prosa. Du hältst dich "
    "strikt an die gegebenen Angaben und erfindest keine Namen, Orte oder "
    "Ereignisse dazu."
)

# Nur ein Rückfall, falls die Antwort keine Kosten nennt (für MODELL_FLASH sind
# die Preise hier bewusst nicht fest hinterlegt — die Antwort liefert ``usage.cost``).
PREISE_USD_PRO_MIO: Dict[str, tuple] = {}


def _schluessel() -> str:
    return (getattr(settings, "openrouter_api_key", "") or "").strip()


def verfuegbar() -> bool:
    """Gibt es einen OpenRouter-Schlüssel? Nur dann lohnt der Modellaufruf."""
    return bool(_schluessel())


def standard_client() -> OpenRouterZDRClient:
    """Der vorhandene OpenRouter-Client mit erzwungenem ZDR und der Zeitgrenze dieses Moduls."""
    return OpenRouterZDRClient(api_key=_schluessel(), timeout=float(ZEITGRENZE_S))


def _perspektive_zeile(perspektive: str) -> str:
    if str(perspektive).lower().startswith("erz"):
        return "Perspektive: neutrale Erzählersicht (dritte Person)."
    return "Perspektive: Ich-Form (erzähle aus meiner Sicht, als wäre es meine eigene Erinnerung)."


def baue_nachricht(
    *,
    titel: str = "",
    datum_text: str = "",
    ort: str = "",
    personen: Optional[List[str]] = None,
    beschreibungen: Optional[List[str]] = None,
    notiz: str = "",
    anzahl_dateien: int = 1,
    perspektive: str = "ich",
) -> str:
    """Baut die Nutzer-Nachricht (reiner Text) aus den Angaben. Rein und testbar.

    Nimmt nur auf, was wirklich da ist — leere Felder werden weggelassen, damit das
    Modell nichts über leere Platzhalter erfindet.
    """
    pers = [p.strip() for p in (personen or []) if p and p.strip()]
    beschr = [b.strip() for b in (beschreibungen or []) if b and b.strip()]
    mehrere = (anzahl_dateien or 1) > 1 or len(beschr) > 1

    regeln = (
        "Regeln: fließender Fließtext (kein Stakkato, keine Aufzählung, keine "
        "Zwischenüberschriften); verwende nur die folgenden Angaben und erfinde keine "
        "Namen, Orte oder Ereignisse; schreibe englische Bildbeschreibungen in "
        "natürliches Deutsch um; setze keine Anführungszeichen um meine Erinnerung; "
        + ("6–10 Sätze." if mehrere else "4–8 Sätze.")
    )

    auftrag = (
        "Schreibe aus den folgenden Angaben EINE zusammenhängende, warmherzige "
        + ("Anlass-Geschichte" if mehrere else "Erinnerungs-Geschichte")
        + " auf Deutsch."
    )

    zeilen: List[str] = [auftrag, _perspektive_zeile(perspektive), regeln, ""]
    if titel:
        zeilen.append(f"Anlass/Titel: {titel}")
    if datum_text:
        zeilen.append(f"Zeit: {datum_text}")
    if ort:
        zeilen.append(f"Ort: {ort}")
    if pers:
        zeilen.append(f"Personen auf dem Bild: {', '.join(pers)}")
    if beschr:
        if len(beschr) == 1:
            zeilen.append(f"Was auf dem Bild zu sehen ist: {beschr[0]}")
        else:
            zeilen.append("Was auf den Bildern zu sehen ist:")
            zeilen.extend(f"- {b}" for b in beschr)
    if notiz and notiz.strip():
        zeilen.append(f"Meine Erinnerung dazu: {notiz.strip()}")

    return "\n".join(zeilen)


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


def erzaehle_geschichte(
    *,
    titel: str = "",
    datum_text: str = "",
    ort: str = "",
    personen: Optional[List[str]] = None,
    beschreibungen: Optional[List[str]] = None,
    notiz: str = "",
    anzahl_dateien: int = 1,
    perspektive: str = "ich",
    client: Any = None,
    modell: str = MODELL_ERZAEHLUNG,
) -> Dict[str, Any]:
    """Frei formulierte deutsche Geschichte. **Speichert nichts, wirft nie.**

    Erfolg ``{"ok": True, "geschichte", "modell", "kosten_usd"}``, Fehler
    ``{"ok": False, "grund"}``. ``client`` ist einspielbar und braucht
    ``chat_completion(messages, model, temperature, max_tokens, extra_payload)``.
    """
    if client is None:
        if not _schluessel():
            return _fehler("Kein OpenRouter-Schlüssel eingerichtet — es wurde nichts angefragt.")
        client = standard_client()

    user = baue_nachricht(
        titel=titel, datum_text=datum_text, ort=ort, personen=personen,
        beschreibungen=beschreibungen, notiz=notiz, anzahl_dateien=anzahl_dateien,
        perspektive=perspektive,
    )
    nachrichten = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]

    start = time.monotonic()
    try:
        antwort = client.chat_completion(
            nachrichten,
            model=modell,
            temperature=0.7,
            max_tokens=MAX_TOKENS,
            extra_payload={"provider": {"data_collection": "deny"}, "usage": {"include": True}},
        )
    except httpx.TimeoutException:
        logger.warning("KI-Erzählung: Zeitgrenze (%s s) überschritten, Modell %s", ZEITGRENZE_S, modell)
        return _fehler(f"Die Zeitgrenze von {ZEITGRENZE_S} Sekunden wurde überschritten — bitte später noch einmal versuchen.")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else "?"
        logger.warning("KI-Erzählung: HTTP %s, Modell %s", status, modell)
        return _fehler(f"Der Modelldienst hat die Anfrage abgelehnt (HTTP {status}).")
    except httpx.HTTPError as e:
        logger.warning("KI-Erzählung: Verbindungsfehler (%s), Modell %s", type(e).__name__, modell)
        return _fehler("Der Modelldienst ist nicht erreichbar.")
    except Exception as e:  # noqa: BLE001 – ehrlich, aber ohne den Text der Ausnahme
        logger.warning("KI-Erzählung: Fehler (%s), Modell %s", type(e).__name__, modell)
        return _fehler("Die Geschichte konnte nicht erstellt werden.")
    dauer = time.monotonic() - start

    try:
        roh = antwort["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        roh = None
    if not isinstance(roh, str) or not roh.strip():
        logger.warning("KI-Erzählung: leere Antwort, Modell %s, %.1f s", modell, dauer)
        return _fehler("Das Modell hat keine Geschichte geliefert.")

    text = " ".join(roh.split())
    kosten = _kosten(antwort, modell)
    logger.info("KI-Erzählung: Modell %s, %.1f s, %d Zeichen, Kosten %s",
                modell, dauer, len(text), "unbekannt" if kosten is None else f"{kosten:.6f} USD")
    return {"ok": True, "geschichte": text, "modell": modell, "kosten_usd": kosten}
