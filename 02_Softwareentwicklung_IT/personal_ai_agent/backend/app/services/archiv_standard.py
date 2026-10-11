"""
Der Standard-Wissensspeicher: erst der volle Index, dann der alte.

Was das hier ist
================

Der Agent hat zwei Wege in die alten Gespraeche:

  **Der volle Index** (``app.services.archiv_suche``) liest den Index des
  Schwesternprojekts *mit* dem WhatsApp-Vollbestand (52.679 Chunks, 241.402
  WhatsApp-Nachrichten); die Vektoren liegen direkt in der Datenbank.

  **Der alte Dienst** (``app.services.archiv_service``) sucht im selben oder
  im alten Heimindex und holt die Vektoren aus der externen Datei
  (``archiv_vektor_path``, 30.891 x 1024 = Stand *vor* dem WhatsApp-Import).
  Er findet Wortlaut, aber aus den WhatsApp-Daten keine Bedeutung mehr.

Die Standard-Suche des Chats (``router.chat._archiv_treffer``) und das
Modell-Werkzeug ``archiv_suchen`` nutzten bisher den **alten** Dienst. Genau
deshalb kam aus den WhatsApp-Daten nie ein Zusammenhang an (Sebastians Befund
vom 10.10.2026) — die Daten waren da, der Weg dorthin fehlte.

Diese eine Stelle entscheidet
=============================

:class:`StandardArchiv` kapselt die Wahl: **erst der volle Index, dann der
alte.** Faellt der volle aus (Index auf dem Geraet nicht gefunden, Fehler),
traegt der alte allein; findet der volle nichts, bekommt der alte eine zweite
Chance. Ist keiner erreichbar, ist ``is_available`` ehrlich False und
``hybrid`` liefert eine leere Liste statt zu werfen — kein Chat wird
lahmgelegt, nichts wird still verschluckt.

Beide Dienste bleiben unveraendert. Welcher gerade traegt, sagt ``quelle``
(„voll", „alt" oder None) — nur zum Nachweis, nie eine Behauptung.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _voll() -> Any:
    """Der volle Index (``archiv_suche``) — frisch geholt, damit Tests ihn ersetzen."""
    from app.services.archiv_suche import archiv_suche
    return archiv_suche


def _alt() -> Any:
    """Der alte Dienst (``archiv_service``) — frisch geholt, damit Tests ihn ersetzen."""
    from app.services.archiv_service import archiv_service
    return archiv_service


def _als_liste(ergebnis: Any) -> List[Dict[str, Any]]:
    """Beide Rueckgabeformen auf eine Trefferliste bringen.

    Der alte Dienst gibt eine Liste zurueck, der volle ein Ergebnis-Dict mit
    ``treffer`` (samt ``sicher``/``grund``/``hinweis``). Die Form darf nicht
    nach aussen lecken — sonst prueft der Aufrufer das Falsche.
    """
    if isinstance(ergebnis, dict):
        treffer = ergebnis.get("treffer")
        return list(treffer) if isinstance(treffer, list) else []
    return list(ergebnis or [])


class StandardArchiv:
    """Ein Wissensspeicher nach aussen, zwei dahinter.

    ``voll``/``alt`` sind injizierbar (Tests); ohne Angabe werden die echten
    Dienste bei jedem Zugriff geholt.
    """

    def __init__(self, voll: Optional[Any] = None, alt: Optional[Any] = None):
        self._voll = voll
        self._alt = alt

    @property
    def voll(self) -> Any:
        return self._voll if self._voll is not None else _voll()

    @property
    def alt(self) -> Any:
        return self._alt if self._alt is not None else _alt()

    @property
    def quelle(self) -> Optional[str]:
        """„voll", „alt" oder None — wer gerade traegt (Nachweis, kein Versprechen)."""
        if getattr(self.voll, "is_available", False):
            return "voll"
        if getattr(self.alt, "is_available", False):
            return "alt"
        return None

    @property
    def is_available(self) -> bool:
        return self.quelle is not None

    def hybrid(self, frage: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Treffer aus dem vollen Index; faellt der aus oder leer aus, aus dem alten."""
        k = top_k or 5

        if getattr(self.voll, "is_available", False):
            try:
                treffer = _als_liste(self.voll.hybrid(frage, top_k=k))
            except Exception as e:  # nie gegen eine Ausnahme anlaufen
                logger.warning("Voller Index scheiterte (%s) — alter Dienst uebernimmt", e)
                treffer = []
            if treffer:
                return treffer

        if getattr(self.alt, "is_available", False):
            try:
                return _als_liste(self.alt.hybrid(frage, top_k=k))
            except Exception as e:
                logger.warning("Alter Archivdienst scheiterte ebenfalls: %s", e)
        return []


# Einzige Instanz fuer den Standardweg (die Dienste darin werden trotzdem
# bei jedem Zugriff frisch geholt, siehe oben).
standard_archiv = StandardArchiv()
