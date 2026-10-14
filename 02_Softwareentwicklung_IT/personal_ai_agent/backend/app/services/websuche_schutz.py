"""Websuche-Sperre bei persönlichen Fragen (Plan `websuche-persoenlich`, 13.10.2026).

Anlass: „Zeig eine Diashow mit Bildern von Opa …“ löste eine Websuche mit dem Namen
aus. Namen aus der Familie dürfen nicht an einen fremden Suchdienst gehen, außer
Sebastian verlangt die Suche ausdrücklich.

Regel (``wirksamer_modus``):
- Persönlich ist ein Text mit Bild-/Medienwort, Familienwort oder dem Namen einer
  bekannten Person.
- Geprüft wird alles, was das Modell sieht: die aktuelle Nachricht, alle
  Nutzer-Nachrichten des übertragenen Verlaufs und die übertragene Zusammenfassung.
  Ist etwas davon persönlich, wird die Websuche ``off``.
- Ausnahme nur bei einem Suchauftrag in der aktuellen Nachricht (Suchverb + Ort im
  Netz, oder „google“), und nur ohne Sperrwort („nicht“, „ohne“, „verzichte“ …).
  Bewusst grob: Im Zweifel bleibt die Sperre.

Ins Log geht nur der Grund, nie Nachrichtentext oder Namen.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

_BILD = re.compile(r"\b(foto|bild|diashow|dia-show|video|galerie|album)", re.IGNORECASE)
_FAMILIE = re.compile(
    r"\b(opa|oma|mama|papa|vater|mutter|bruder|schwester|onkel|tante|cousin|cousine|"
    r"neffe|nichte|sohn|tochter|schwager|schwägerin|enkel)",
    re.IGNORECASE,
)
_SUCHVERB = re.compile(r"\b(such|schau|guck|find|recherchier)", re.IGNORECASE)
_NETZORT = re.compile(r"\b(im internet|im netz|im web|online)\b", re.IGNORECASE)
# „Google“ nur als Verb („google mal …“, „googel nach …“, „googeln“), nicht als
# bloße Erwähnung („nutzt Google Drive“ – Codex-Ergebnisprüfung R1, Einwand 1).
_GOOGLE = re.compile(
    r"\b(goog(e)?le?\s+(mal|nach|bitte|doch)\b|googel\b|goog(e)?le?n\b)", re.IGNORECASE)
_SPERRWORT = re.compile(
    r"\b(nicht|kein\w*|ohne|nie|niemals|verzicht\w*|lass\w*|statt|außer|ausser)\b",
    re.IGNORECASE,
)
# Namensteile kürzer als das zählen nicht einzeln (der volle Name zählt immer).
_MIN_TEIL = 3


def _namensmuster(namen: Iterable[str]) -> Optional["re.Pattern[str]"]:
    teile: set = set()
    for name in namen or []:
        name = str(name or "").strip()
        if not name:
            continue
        teile.add(name)
        for teil in name.split():
            if len(teil) >= _MIN_TEIL:
                teile.add(teil)
    if not teile:
        return None
    alternativen = "|".join(re.escape(t) for t in sorted(teile, key=len, reverse=True))
    return re.compile(r"(?<!\w)(" + alternativen + r")(?!\w)", re.IGNORECASE)


def _grund(text: str, namen_muster: Optional["re.Pattern[str]"]) -> str:
    """``bild``, ``familie``, ``person`` oder leer."""
    text = str(text or "")
    if not text:
        return ""
    if _BILD.search(text):
        return "bild"
    if _FAMILIE.search(text):
        return "familie"
    if namen_muster is not None and namen_muster.search(text):
        return "person"
    return ""


def ist_suchauftrag(nachricht: str) -> bool:
    """Ausdrücklicher Suchauftrag ohne Sperrwort."""
    text = str(nachricht or "")
    if _SPERRWORT.search(text):
        return False
    return bool(_GOOGLE.search(text) or (_SUCHVERB.search(text) and _NETZORT.search(text)))


def wirksamer_modus(
    modus: str,
    nachricht: str,
    verlauf_nutzer: Iterable[str] = (),
    bekannte_namen: Iterable[str] = (),
) -> Tuple[str, str]:
    """Websuche-Modus nach der Sperre: ``(modus, grund)``.

    ``grund`` ist ``bild``/``familie``/``person`` (aktuelle Nachricht),
    ``verlauf`` (Verlauf oder Zusammenfassung) oder leer, wenn nichts gesperrt wurde.
    """
    if modus not in ("manual", "auto"):
        return modus, ""
    if ist_suchauftrag(nachricht):
        return modus, ""
    try:
        muster = _namensmuster(bekannte_namen)
    except Exception:
        muster = None
    grund = _grund(nachricht, muster)
    if not grund:
        for text in verlauf_nutzer or []:
            if _grund(text, muster):
                grund = "verlauf"
                break
    if grund:
        logger.info("Websuche fuer diese Frage aus (Grund: %s)", grund)
        return "off", grund
    return modus, ""


def nutzertexte(verlauf: Iterable[dict], zusammenfassung: str = "") -> List[str]:
    """Nutzer-Nachrichten eines Verlaufs plus die Zusammenfassung als Textliste."""
    texte: List[str] = []
    for eintrag in verlauf or []:
        if isinstance(eintrag, dict) and eintrag.get("role") == "user":
            inhalt = eintrag.get("content")
            if isinstance(inhalt, list):
                inhalt = " ".join(str(t.get("text") or "") for t in inhalt if isinstance(t, dict))
            texte.append(str(inhalt or ""))
    if zusammenfassung:
        texte.append(str(zusammenfassung))
    return texte
