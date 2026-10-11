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

Die Standard-Suche des Chats (``router.chat._archiv_treffer``), das
Modell-Werkzeug ``archiv_suchen`` und die Nachschau-Endpunkte
(``router.archiv``: ``/api/archiv/status`` und ``/api/archiv/suche``) nutzten
bisher den **alten** Dienst. Genau deshalb kam aus den WhatsApp-Daten nie ein
Zusammenhang an (Sebastians Befund vom 10.10.2026) — die Daten waren da, der Weg
dorthin fehlte. Bei den Nachschau-Endpunkten wog es doppelt: eine Fehlersuche,
die den alten Stand zeigt, verdeckt genau den Fehler, den sie finden soll.

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

    def _ueber_weg(self, frage: str, top_k: Optional[int],
                   methode_voll: str, methode_alt: str) -> List[Dict[str, Any]]:
        """Einen Suchweg ueber beide Dienste fahren: erst voll, dann alt.

        ``methode_voll``/``methode_alt`` sind die **Methodennamen** der beiden
        Dienste — sie heissen unterschiedlich (der volle Index kennt
        ``volltext_suche``, der alte ``suche``; ``semantische_suche`` und
        ``hybrid`` heissen gleich). Fehlt einem Dienst die Methode, wird er
        uebergangen statt zu werfen. Beide Rueckgabeformen bringt
        :func:`_als_liste` auf eine Liste.
        """
        k = top_k or 5

        if getattr(self.voll, "is_available", False):
            fn = getattr(self.voll, methode_voll, None)
            if callable(fn):
                try:
                    treffer = _als_liste(fn(frage, top_k=k))
                except Exception as e:  # nie gegen eine Ausnahme anlaufen
                    logger.warning("Voller Index scheiterte (%s) — alter Dienst uebernimmt", e)
                    treffer = []
                if treffer:
                    return treffer

        if getattr(self.alt, "is_available", False):
            fn = getattr(self.alt, methode_alt, None)
            if callable(fn):
                try:
                    return _als_liste(fn(frage, top_k=k))
                except Exception as e:
                    logger.warning("Alter Archivdienst scheiterte ebenfalls: %s", e)
        return []

    def hybrid(self, frage: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Treffer aus dem vollen Index; faellt der aus oder leer aus, aus dem alten."""
        return self._ueber_weg(frage, top_k, "hybrid", "hybrid")

    def suche(self, frage: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Volltextsuche ueber den Standardweg (voll: ``volltext_suche``, alt: ``suche``)."""
        return self._ueber_weg(frage, top_k, "volltext_suche", "suche")

    def semantische_suche(self, frage: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Bedeutungssuche ueber den Standardweg (beide Dienste: ``semantische_suche``)."""
        return self._ueber_weg(frage, top_k, "semantische_suche", "semantische_suche")

    def status(self) -> Dict[str, Any]:
        """Stand des **tragenden** Dienstes, plus ``quelle`` („voll"/„alt"/None).

        Der Endpunkt ``/api/archiv/status`` soll zeigen, was der Chat
        tatsaelich benutzt — sonst meldet die Fehlersuche den alten Stand
        (ohne WhatsApp) und verdeckt den Fehler, den sie finden soll. Der
        tragende Dienst liefert seinen eigenen Stand (``status`` beim alten,
        ``statistik`` beim vollen Index); fehlt beides, bleibt es ehrlich bei
        ``verfuegbar: True`` ohne weitere Felder.
        """
        quelle = self.quelle
        if quelle is None:
            return {"verfuegbar": False, "quelle": None}

        dienst = self.voll if quelle == "voll" else self.alt
        roh: Any = {}
        for name in ("status", "statistik"):
            fn = getattr(dienst, name, None)
            if callable(fn):
                try:
                    roh = fn() or {}
                except Exception as e:
                    logger.warning("Archiv-Status des tragenden Dienstes nicht lesbar: %s", e)
                    roh = {}
                break
        ergebnis: Dict[str, Any] = dict(roh) if isinstance(roh, dict) else {}
        ergebnis.setdefault("verfuegbar", True)
        ergebnis["quelle"] = quelle
        return ergebnis


# Einzige Instanz fuer den Standardweg (die Dienste darin werden trotzdem
# bei jedem Zugriff frisch geholt, siehe oben).
standard_archiv = StandardArchiv()
