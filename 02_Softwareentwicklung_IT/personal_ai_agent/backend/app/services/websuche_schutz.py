"""Namensverbot für die Websuche (Plan `websuche-namensverbot`, Fassung 7, 14.10.2026).

Sebastians Regel: Allgemeines, Orte und Adressen dürfen im Internet gesucht werden,
**Personennamen aus seinem Leben nie**. Öffentliche Personen, die nicht im
Bestand sind, dürfen gesucht werden.

Bausteine:
- ``bestand_bauen(personen, kontakte)``: Namen aus dem Personenbestand (Quiz bzw.
  alter Katalog; jeder Teil ab 2 Zeichen zählt) und volle Namen der
  WhatsApp-Kontakte (nur Folgen aus mindestens zwei Wörtern).
- ``enthaelt_namen(text, bestand, freigaben)``: Trifft der Text einen Namen?
  ``bestand is None`` (Namensliste nicht lesbar) zählt als Treffer.
- ``freigaben(nachricht, bestand)``: Volle fremde Namen, die Sebastian in SEINER
  Nachricht ausdrücklich suchen lässt („Such im Internet nach …“). Eine Freigabe
  öffnet nur gemeinsame Vornamen/Einzelteile, nie einen bekannten vollen Namen.

Vergleich nach Umschrift (ä→ae, ö→oe, ü→ue, ß→ss, Groß/Klein egal), Endungen
``s``/``'s``/``’s`` am Wortende sind erlaubt. Ins Log geht nur ein Zähler, nie Text.

Grenzen (bewusst, siehe Changelog): Namen, die nur in Archiv/Erinnerungen stehen,
kennt die Liste nicht; ein Vorname allein aus einem Kontakt wird nicht erkannt;
andere Umschriften („Myller“) auch nicht.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORT = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")
_MIN_TEIL = 2

_SUCHVERB = re.compile(r"\b(such|schau|guck|find|recherchier)", re.IGNORECASE)
_NETZORT = re.compile(r"\b(im internet|im netz|im web|online)\b", re.IGNORECASE)
# „Google“ nur als Verb („google mal …“, „googel nach …“, „googeln“).
_GOOGLE = re.compile(
    r"\b(goog(e)?le?\s+(mal|nach|bitte|doch)\b|googel\b|goog(e)?le?n\b)", re.IGNORECASE)
_SPERRWORT = re.compile(
    r"\b(nicht|kein\w*|ohne|nie|niemals|verzicht\w*|lass\w*|statt|außer|ausser)\b",
    re.IGNORECASE,
)


def norm(wort: str) -> str:
    """Wort für den Vergleich: klein, Umschrift ä→ae usw."""
    return str(wort or "").lower().translate(_UMSCHRIFT)


def _woerter(text: str) -> List[str]:
    return _WORT.findall(str(text or ""))


def _passt(token: str, name: str) -> bool:
    """Token (normalisiert) gleich Namensteil, auch mit Endung s / 's / ’s."""
    if token == name:
        return True
    for endung in ("s", "'s", "’s"):
        if token == name + endung:
            return True
    return False


@dataclass
class NamensBestand:
    # Einzelteile aus dem Personenbestand (normalisiert), ab 2 Zeichen.
    teile: Set[str] = field(default_factory=set)
    # Volle Namen als Wortfolgen (Bestand mit >= 2 Wörtern und Kontakte).
    volle: List[Tuple[str, ...]] = field(default_factory=list)
    # Letzte Wörter der mehrteiligen Bestandsnamen (Nachnamen).
    nachnamen: Set[str] = field(default_factory=set)

    def anzahl(self) -> dict:
        return {"teile": len(self.teile), "volle": len(self.volle)}


def bestand_bauen(personen: Iterable[str], kontakte: Iterable[str] = ()) -> NamensBestand:
    """Namensbestand aus Bestandsnamen und Kontaktnamen bauen (wirft nie)."""
    b = NamensBestand()
    volle: Set[Tuple[str, ...]] = set()
    for name in personen or []:
        if not isinstance(name, str):
            continue
        woerter = tuple(norm(w) for w in _woerter(name))
        if not woerter:
            continue
        for w in woerter:
            if len(w) >= _MIN_TEIL:
                b.teile.add(w)
        if len(woerter) >= 2:
            volle.add(woerter)
            b.nachnamen.add(woerter[-1])
    for name in kontakte or []:
        if not isinstance(name, str):
            continue
        woerter = tuple(norm(w) for w in _woerter(name))
        if len(woerter) >= 2:
            volle.add(woerter)
    b.volle = sorted(volle)
    return b


def _folge_an(tokens: Sequence[str], start: int, folge: Tuple[str, ...]) -> bool:
    if start + len(folge) > len(tokens):
        return False
    for i, teil in enumerate(folge):
        tok = tokens[start + i]
        if i == len(folge) - 1:
            if not _passt(tok, teil):
                return False
        elif tok != teil:
            return False
    return True


def _enthaelt_folge(tokens: Sequence[str], folge: Tuple[str, ...]) -> bool:
    return any(_folge_an(tokens, i, folge) for i in range(len(tokens)))


def enthaelt_namen(text: str, bestand: Optional[NamensBestand],
                   freigaben_liste: Iterable[Tuple[str, ...]] = ()) -> bool:
    """True, wenn ``text`` einen geschützten Namen enthält (oder die Liste fehlt)."""
    if bestand is None:
        logger.info("Websuche: Namensliste nicht lesbar - abgelehnt")
        return True
    try:
        tokens = [norm(w) for w in _woerter(text)]
        # 1) Volle Namen: immer Treffer, keine Freigabe hebt sie auf.
        for folge in bestand.volle:
            if _enthaelt_folge(tokens, folge):
                logger.info("Websuche: Name abgelehnt (voll)")
                return True
        # 2) Einzelteile: Treffer, außer sie liegen in einer gültigen Freigabe.
        abgedeckt: Set[int] = set()
        for folge in freigaben_liste or []:
            for i in range(len(tokens)):
                if _folge_an(tokens, i, tuple(folge)):
                    abgedeckt.update(range(i, i + len(folge)))
        for i, tok in enumerate(tokens):
            if i in abgedeckt:
                continue
            if any(_passt(tok, teil) for teil in bestand.teile):
                logger.info("Websuche: Name abgelehnt (Teil)")
                return True
        return False
    except Exception:
        logger.exception("Websuche: Namenspruefung fehlgeschlagen - abgelehnt")
        return True


def ist_suchauftrag(nachricht: str) -> bool:
    """Ausdrücklicher Suchauftrag ohne Sperrwort."""
    text = str(nachricht or "")
    if _SPERRWORT.search(text):
        return False
    return bool(_GOOGLE.search(text) or (_SUCHVERB.search(text) and _NETZORT.search(text)))


def freigaben(nachricht: str, bestand: Optional[NamensBestand]) -> List[Tuple[str, ...]]:
    """Volle fremde Namen, die Sebastian in seiner Nachricht ausdrücklich suchen lässt.

    Kandidaten sind Folgen aus mindestens zwei großgeschriebenen Wörtern in einer
    Nachricht mit Suchauftrag. Ungültig ist eine Folge, wenn sie einen bekannten
    vollen Namen enthält, ein Wort davon ein bekannter Nachname ist oder alle Wörter
    bekannte Teile sind. Nur aus Sebastians eigener Nachricht aufrufen, nie mit
    Modelltext.
    """
    if bestand is None or not ist_suchauftrag(nachricht):
        return []
    ergebnis: List[Tuple[str, ...]] = []
    lauf: List[str] = []
    for wort in _woerter(nachricht) + [""]:
        if wort and wort[0].isupper():
            lauf.append(wort)
            continue
        if len(lauf) >= 2:
            folge = tuple(norm(w) for w in lauf)
            gueltig = (
                not any(_enthaelt_folge(folge, v) for v in bestand.volle)
                and not any(_passt(w, n) for w in folge for n in bestand.nachnamen)
                and not all(any(_passt(w, t) for t in bestand.teile) for w in folge)
            )
            if gueltig:
                ergebnis.append(folge)
        lauf = []
    return ergebnis
