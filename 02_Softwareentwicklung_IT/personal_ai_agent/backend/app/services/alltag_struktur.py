"""Alltagsprotokoll S3: freier Satz → Eintrag nach dem S1-Schema (03.11.2026).

Plan ``.hermes/plans/alltagsprotokoll.md`` S3. Ein Modellaufruf, die Antwort wird streng
geprüft: unbekannte Felder fallen weg, Bereiche werden geprüft, Unlesbares wird ``None``
(``fehlt`` zeigt es dann an), statt etwas zu raten.

* Nur über OpenRouter mit ``data_collection: deny``; registrierte Namen gehen nur als
  Kürzel raus (``PIIShield``) und werden in der Antwort zurückgesetzt.
* Die Originalworte bleiben lokal und unmaskiert im Eintrag.
* Ins Log kommen nur Modell, Dauer, Zeichenzahl und Kosten — nie der Satz.
* ``essen`` wird bewusst nicht erkannt (Entscheidung D steht noch aus).

Speichert nichts; das übernimmt der Aufrufer mit ``alltag_speicher.eintrag_anhaengen``.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services import alltag_rechnen
from app.services.alltag_speicher import SCHLAF_EREIGNISSE
from app.services.modell_router import MODELL_FLASH
from app.services.openrouter_client import OpenRouterZDRClient
from app.services.pii_shield import PIIShield

logger = logging.getLogger(__name__)

MODELL_STRUKTUR = MODELL_FLASH
ZEITGRENZE_S = 30
MAX_TOKENS = 300
MAX_TEXT = 2000
MAX_GEFUEHL = 40
MAX_GEFUEHLE = 8
MAX_AKTIVITAET = 300
QUELLEN = ("sprache", "tastatur")

# Vorläufig — die Liste wird noch mit der Begleitperson abgestimmt (Alignment, offener Punkt).
GRUNDGEFUEHLE = ("Freude", "Trauer", "Angst", "Ärger", "Ekel", "Überraschung", "Scham",
                 "Schuld", "Ruhe", "Erschöpfung")

STIMMUNG_STUFEN = "sehr gut = 5, gut = 4, mittel = 3, schlecht = 2, sehr schlecht = 1"

SYSTEM_PROMPT = (
    "Du wandelst einen kurzen, oft eingesprochenen Satz aus einem Stimmungsprotokoll in JSON um. "
    "Antworte ausschließlich mit einem JSON-Objekt, ohne Erklärung. Erfinde nichts: was der Satz "
    "nicht sagt, ist null bzw. eine leere Liste. Platzhalter wie [PERSON_01] übernimmst du unverändert."
)

_UHRZEIT = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*$")


def _schluessel() -> str:
    return (getattr(settings, "openrouter_api_key", "") or "").strip()


def standard_client() -> OpenRouterZDRClient:
    return OpenRouterZDRClient(api_key=_schluessel(), timeout=float(ZEITGRENZE_S))


def _fehler(grund: str) -> Dict[str, Any]:
    return {"ok": False, "grund": grund}


def baue_nachricht(text: str, jetzt: datetime) -> str:
    """Nutzer-Nachricht mit Schema und Regeln. Rein und testbar; enthält nur den Satz und die Uhrzeit."""
    return "\n".join([
        f"Jetzt ist es {jetzt:%H:%M} Uhr.",
        "Felder:",
        '- "art": "stunde" für Stimmung/Tätigkeit, "schlaf" für Schlafen gehen, Aufwachen, Wachliegen, Wiedereinschlafen.',
        f'- "stimmung": ganze Zahl 1–5 ({STIMMUNG_STUFEN}) oder null.',
        '- "anspannung": ganze Zahl 0–100 oder null.',
        f'- "gefuehle": Liste; bevorzugt aus {", ".join(GRUNDGEFUEHLE)} (z. B. genervt → Ärger), '
        "sonst ein eigenes kurzes Wort.",
        '- "vorherrschend": das stärkste Gefühl oder null.',
        '- "aktivitaet": was getan wurde, kurz in den Worten des Satzes, oder null.',
        '- "von", "bis": Uhrzeit "HH:MM", nur wenn der Satz einen Zeitraum nennt, sonst null.',
        f'- "ereignis": nur bei art "schlaf", einer von {", ".join(SCHLAF_EREIGNISSE)}.',
        '- "zeit": nur bei art "schlaf", Uhrzeit "HH:MM", sonst null.',
        "",
        f"Satz: {text}",
    ])


def baue_schild(namen: Optional[List[str]], text: str = "") -> PIIShield:
    """Namen samt Teilen ab 3 Zeichen registrieren (Muster ``geschichte_erzaehlen_ki``).

    Der Schild maskiert ohne Rücksicht auf Groß-/Kleinschreibung; zurück kommt jedes Kürzel
    in der Schreibweise, in der es im Satz stand.
    """
    schild = PIIShield()
    for name in namen or []:
        name = (name or "").strip()
        if name:
            schild.register_person(name, aliases=[t for t in name.split() if len(t) >= 3 and t != name])
    for klar, kuerzel in list(schild.plain_to_token.items()):
        treffer = re.search(rf"\b{re.escape(klar)}\b", text, flags=re.IGNORECASE)
        if treffer:
            schild.token_to_plain[kuerzel] = treffer.group(0)
    return schild


# ── Prüfen ─────────────────────────────────────────────────────────────────

def _ganzzahl(wert: Any, unten: int, oben: int) -> Optional[int]:
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    if isinstance(wert, float) and not wert.is_integer():
        return None
    return int(wert) if unten <= wert <= oben else None


def _gefuehl(wert: Any) -> Optional[str]:
    if not isinstance(wert, str):
        return None
    wort = " ".join(wert.split())
    if not wort or len(wort) > MAX_GEFUEHL:
        return None
    for grund in GRUNDGEFUEHLE:
        if wort.lower() == grund.lower():
            return grund
    return wort


def _gefuehle(liste: Any, vorherrschend: Optional[str]) -> List[str]:
    worte: List[str] = []
    for roh in liste if isinstance(liste, list) else []:
        wort = _gefuehl(roh)
        if wort and wort not in worte:
            worte.append(wort)
    if vorherrschend:
        worte = [vorherrschend] + [w for w in worte if w != vorherrschend]
    return worte[:MAX_GEFUEHLE]


def _uhrzeit(wert: Any, jetzt: datetime) -> Optional[datetime]:
    """``"HH:MM"`` → der letzte solche Zeitpunkt bis ``jetzt`` (später als jetzt = gestern)."""
    treffer = _UHRZEIT.match(wert) if isinstance(wert, str) else None
    if not treffer:
        return None
    stunde, minute = int(treffer.group(1)), int(treffer.group(2) or 0)
    if stunde > 23 or minute > 59:
        return None
    zeitpunkt = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    return zeitpunkt - timedelta(days=1) if zeitpunkt > jetzt else zeitpunkt


def _iso(zeitpunkt: datetime) -> str:
    return zeitpunkt.isoformat(timespec="seconds")


def _zeitraum(roh: Dict[str, Any], jetzt: datetime) -> tuple:
    """Stundenbereich; nie in der Zukunft. Ohne Angabe die letzte Stunde."""
    jetzt = jetzt.replace(second=0, microsecond=0)
    von, bis = _uhrzeit(roh.get("von"), jetzt), _uhrzeit(roh.get("bis"), jetzt)
    if von and bis:
        if von >= bis:                       # 23:00 bis 01:00 — über Mitternacht
            von -= timedelta(days=1)
        return _iso(von), _iso(bis)
    if bis is None:
        bis = min(von + timedelta(hours=1), jetzt) if von else jetzt
    if von is None or von >= bis:
        von = bis - timedelta(hours=1)
    return _iso(von), _iso(bis)


def pruefen(roh: Any, *, text: str, quelle: str, jetzt: datetime, schild: PIIShield) -> Dict[str, Any]:
    """Modellantwort → Eintrag. Rein. Fehler ``{"ok": False, "grund"}`` nur, wenn gar nichts passt."""
    if not isinstance(roh, dict):
        return _fehler("Die Antwort des Modells ist kein Eintrag.")
    art = roh.get("art")
    if art == "schlaf":
        ereignis = roh.get("ereignis")
        if ereignis not in SCHLAF_EREIGNISSE:
            return _fehler("Das Schlaf-Ereignis wurde nicht erkannt.")
        zeit = _uhrzeit(roh.get("zeit"), jetzt) or jetzt.replace(microsecond=0)
        return {"ok": True, "eintrag": {"art": "schlaf", "ereignis": ereignis, "zeit": _iso(zeit),
                                        "originalworte": text, "quelle": quelle}}
    if art != "stunde":
        return _fehler("Die Art des Eintrags wurde nicht erkannt.")

    def zurueck(wert: Any) -> Any:
        return schild.decode(wert) if isinstance(wert, str) else wert

    vorherrschend = _gefuehl(zurueck(roh.get("vorherrschend")))
    aktivitaet = zurueck(roh.get("aktivitaet"))
    aktivitaet = " ".join(aktivitaet.split())[:MAX_AKTIVITAET] if isinstance(aktivitaet, str) else ""
    von, bis = _zeitraum(roh, jetzt)
    return {"ok": True, "eintrag": {
        "art": "stunde", "von": von, "bis": bis,
        "stimmung": _ganzzahl(roh.get("stimmung"), 1, 5),
        "anspannung": _ganzzahl(roh.get("anspannung"), 0, 100),
        "gefuehle": _gefuehle([zurueck(g) for g in roh.get("gefuehle") or []]
                              if isinstance(roh.get("gefuehle"), list) else [], vorherrschend),
        "vorherrschend": vorherrschend,
        "aktivitaet": aktivitaet or None,
        "originalworte": text, "quelle": quelle,
    }}


def nur_originalworte(text: str, quelle: str = "tastatur", jetzt: Optional[datetime] = None) -> Dict[str, Any]:
    """Rückfall ohne Modell: Stunden-Eintrag für die letzte Stunde, nur mit den Originalworten."""
    von, bis = _zeitraum({}, jetzt or datetime.now().astimezone())
    return {"art": "stunde", "von": von, "bis": bis, "originalworte": (text or "").strip()[:MAX_TEXT],
            "quelle": quelle if quelle in QUELLEN else "tastatur"}


def _json_lesen(inhalt: str) -> Any:
    rein = inhalt.strip()
    if rein.startswith("```"):
        rein = rein.strip("`").strip()
        if rein.lower().startswith("json"):
            rein = rein[4:]
    try:
        return json.loads(rein)
    except ValueError:
        return None


# ── Aufruf ─────────────────────────────────────────────────────────────────

def strukturieren(text: str, *, quelle: str = "tastatur", jetzt: Optional[datetime] = None,
                  client: Any = None, namen: Optional[List[str]] = None,
                  modell: str = MODELL_STRUKTUR) -> Dict[str, Any]:
    """Satz → ``{"ok": True, "eintrag", "fehlt", "modell", "kosten_usd"}``. **Speichert nichts, wirft nie.**

    ``namen``: Personen, die nur maskiert rausgehen dürfen. ``client`` ist einspielbar
    (``chat_completion(messages, model, temperature, max_tokens, extra_payload)``).
    """
    text = (text or "").strip()
    if not text:
        return _fehler("Es wurde nichts gesagt oder geschrieben.")
    if len(text) > MAX_TEXT:
        return _fehler(f"Der Text ist zu lang (höchstens {MAX_TEXT} Zeichen).")
    quelle = quelle if quelle in QUELLEN else "tastatur"
    jetzt = jetzt or datetime.now().astimezone()
    if client is None:
        if not _schluessel():
            return _fehler("Kein OpenRouter-Schlüssel eingerichtet — es wurde nichts angefragt.")
        client = standard_client()

    schild = baue_schild(namen, text)
    nachrichten = [{"role": "system", "content": SYSTEM_PROMPT},
                   {"role": "user", "content": schild.encode(baue_nachricht(text, jetzt))}]
    start = time.monotonic()
    try:
        antwort = client.chat_completion(
            nachrichten, model=modell, temperature=0.0, max_tokens=MAX_TOKENS,
            extra_payload={"provider": {"data_collection": "deny"}, "usage": {"include": True},
                           "reasoning": {"enabled": False}},
        )
    except httpx.TimeoutException:
        logger.warning("Alltag-Struktur: Zeitgrenze (%s s), Modell %s", ZEITGRENZE_S, modell)
        return _fehler("Das Modell hat zu lange gebraucht — bitte noch einmal versuchen.")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else "?"
        logger.warning("Alltag-Struktur: HTTP %s, Modell %s", status, modell)
        return _fehler(f"Der Modelldienst hat die Anfrage abgelehnt (HTTP {status}).")
    except httpx.HTTPError as e:
        logger.warning("Alltag-Struktur: Verbindungsfehler (%s), Modell %s", type(e).__name__, modell)
        return _fehler("Der Modelldienst ist nicht erreichbar.")
    except Exception as e:  # noqa: BLE001 – ehrlich, aber ohne den Text der Ausnahme
        logger.warning("Alltag-Struktur: Fehler (%s), Modell %s", type(e).__name__, modell)
        return _fehler("Der Eintrag konnte nicht erkannt werden.")
    dauer = time.monotonic() - start

    try:
        inhalt = antwort["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        inhalt = None
    roh = _json_lesen(inhalt) if isinstance(inhalt, str) else None
    erg = pruefen(roh, text=text, quelle=quelle, jetzt=jetzt, schild=schild)
    usage = antwort.get("usage") if isinstance(antwort, dict) else None
    kosten = usage.get("cost") if isinstance(usage, dict) else None
    kosten = float(kosten) if isinstance(kosten, (int, float)) and not isinstance(kosten, bool) else None
    logger.info("Alltag-Struktur: Modell %s, %.1f s, %d Zeichen, %s, Kosten %s", modell, dauer,
                len(inhalt) if isinstance(inhalt, str) else 0, "erkannt" if erg["ok"] else "nicht erkannt",
                "unbekannt" if kosten is None else f"{kosten:.6f} USD")
    if not erg["ok"]:
        return erg
    return {**erg, "fehlt": alltag_rechnen.fehlende_felder(erg["eintrag"]),
            "modell": modell, "kosten_usd": kosten}
