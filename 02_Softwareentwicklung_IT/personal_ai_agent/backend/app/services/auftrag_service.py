"""Auftragsbuch fuer den Coding-Agenten.

Der Agent auf dem Handy kann Hermes nicht anrufen - die App hat keinen
eingehenden HTTP-Zugang. Nur Hermes kann von sich aus fragen. Deshalb
liegt hier ein Buch, in das die Oberflaeche Auftraege eintraegt und aus
dem Hermes sich im eigenen Takt bedient.

Warum eine JSON-Datei und nicht ChromaDB: Auftraege sind kein Wissen,
das nach Bedeutung gesucht wird, sondern eine kurze Liste mit Zustand.
Eine Datei laesst sich im Zweifel mit blossem Auge lesen und von Hand
reparieren - bei einem System, das sich selbst veraendern soll, ist das
kein Rueckschritt, sondern die Bremse.

Sicherheit: Auftraege enthalten, was der Nutzer diktiert hat. Die Datei
gehoert deshalb in die .gitignore - das Repo ist oeffentlich.
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Zustaende eines Auftrags. Mehr braucht es nicht: Wer "laeuft" nicht von
# "offen" unterscheidet, gibt denselben Auftrag zweimal aus, wenn sich zwei
# Cron-Laeufe ueberholen.
OFFEN = "offen"
LAEUFT = "laeuft"
FERTIG = "fertig"
FEHLER = "fehler"


def _jetzt() -> str:
    """Zeitstempel in UTC, ISO-Format.

    Bewusst UTC: Das Handy wechselt Zeitzonen, die Datei soll deshalb
    unabhaengig davon vergleichbar bleiben.
    """
    return datetime.now(timezone.utc).isoformat()


class AuftragService:
    """Liest und schreibt das Auftragsbuch.

    Die Sperre ist nicht uebervorsichtig: Die Oberflaeche legt Auftraege an,
    waehrend Hermes sich welche abholt. Ohne sie koennten sich zwei
    Schreibvorgaenge ueberlagern und die Datei zerstoeren - und mit ihr die
    gesamte Liste, nicht nur den einen Eintrag.
    """

    def __init__(self) -> None:
        self._pfad = Path(settings.auftraege_datei)
        self._sperre = threading.Lock()

    # ------------------------------------------------------------------
    # Dateizugriff
    # ------------------------------------------------------------------

    def _lesen(self) -> list[dict]:
        """Alle Auftraege aus der Datei.

        Fehlt die Datei oder ist sie beschaedigt, kommt eine leere Liste
        zurueck statt einer Ausnahme. Grund: Ein kaputtes Auftragsbuch darf
        nicht den ganzen Agenten lahmlegen - der Chat muss weiterlaufen.
        """
        if not self._pfad.exists():
            return []
        try:
            with self._pfad.open("r", encoding="utf-8") as datei:
                daten = json.load(datei)
            return daten if isinstance(daten, list) else []
        except (json.JSONDecodeError, OSError) as fehler:
            logger.error("Auftragsbuch nicht lesbar (%s): %s", self._pfad, fehler)
            return []

    def _schreiben(self, auftraege: list[dict]) -> None:
        """Schreibt die Liste zurueck - erst daneben, dann umbenennen.

        Das Umbenennen ist auf einem Dateisystem unteilbar. Ohne diesen
        Umweg wuerde ein Absturz mitten im Schreiben eine halbe Datei
        hinterlassen, und die waere unlesbar.
        """
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        entwurf = self._pfad.with_suffix(".json.tmp")
        with entwurf.open("w", encoding="utf-8") as datei:
            json.dump(auftraege, datei, ensure_ascii=False, indent=2)
        entwurf.replace(self._pfad)

    # ------------------------------------------------------------------
    # Oeffentliche Schnittstelle
    # ------------------------------------------------------------------

    def anlegen(self, auftrag: str, hinweis: Optional[str] = None) -> dict:
        """Traegt einen neuen Auftrag ein und gibt ihn zurueck."""
        eintrag = {
            "id": str(uuid.uuid4()),
            "auftrag": auftrag,
            "hinweis": hinweis,
            "status": OFFEN,
            "erstellt": _jetzt(),
            "abgeholt": None,
            "beendet": None,
            "ergebnis": None,
        }
        with self._sperre:
            auftraege = self._lesen()
            auftraege.append(eintrag)
            self._schreiben(auftraege)
        logger.info("Auftrag angelegt: %s", eintrag["id"])
        return eintrag

    def alle(self, limit: int = 50) -> list[dict]:
        """Die neuesten Auftraege, neueste zuerst."""
        with self._sperre:
            auftraege = self._lesen()
        return sorted(auftraege, key=lambda a: a.get("erstellt", ""), reverse=True)[:limit]

    def einzeln(self, auftrag_id: str) -> Optional[dict]:
        """Ein Auftrag samt Stand, oder None."""
        with self._sperre:
            for eintrag in self._lesen():
                if eintrag.get("id") == auftrag_id:
                    return eintrag
        return None

    def naechster_offener(self) -> Optional[dict]:
        """Gibt den aeltesten offenen Auftrag aus und markiert ihn als laufend.

        Ausgabe und Markierung in einem Schritt, unter derselben Sperre: Nur
        so bekommt ein zweiter Abruf nicht denselben Auftrag noch einmal.

        Ein Auftrag, der zu lange laeuft, gilt wieder als offen - Hermes
        arbeitet in kurzlebigen Sitzungen, und eine abgebrochene Sitzung
        wuerde einen Auftrag sonst fuer immer blockieren.
        """
        with self._sperre:
            auftraege = self._lesen()
            self._verwaiste_freigeben(auftraege)

            offene = [a for a in auftraege if a.get("status") == OFFEN]
            if not offene:
                self._schreiben(auftraege)
                return None

            naechster = min(offene, key=lambda a: a.get("erstellt", ""))
            naechster["status"] = LAEUFT
            naechster["abgeholt"] = _jetzt()
            self._schreiben(auftraege)

        logger.info("Auftrag ausgegeben: %s", naechster["id"])
        return naechster

    def ergebnis_eintragen(
        self, auftrag_id: str, ergebnis: str, erfolg: bool = True
    ) -> Optional[dict]:
        """Nimmt die Rueckmeldung entgegen."""
        with self._sperre:
            auftraege = self._lesen()
            for eintrag in auftraege:
                if eintrag.get("id") != auftrag_id:
                    continue
                eintrag["status"] = FERTIG if erfolg else FEHLER
                eintrag["ergebnis"] = ergebnis
                eintrag["beendet"] = _jetzt()
                self._schreiben(auftraege)
                logger.info(
                    "Auftrag %s: %s", auftrag_id, "fertig" if erfolg else "fehlgeschlagen"
                )
                return eintrag
        return None

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _verwaiste_freigeben(self, auftraege: list[dict]) -> None:
        """Setzt zu lange laufende Auftraege zurueck auf offen.

        Aendert die uebergebene Liste an Ort und Stelle; der Aufrufer haelt
        bereits die Sperre und schreibt danach.
        """
        grenze = settings.auftrag_timeout_minuten * 60
        jetzt = datetime.now(timezone.utc)

        for eintrag in auftraege:
            if eintrag.get("status") != LAEUFT or not eintrag.get("abgeholt"):
                continue
            try:
                abgeholt = datetime.fromisoformat(eintrag["abgeholt"])
            except (ValueError, TypeError):
                continue
            if (jetzt - abgeholt).total_seconds() > grenze:
                logger.warning(
                    "Auftrag %s lief laenger als %d Minuten - wieder offen",
                    eintrag.get("id"),
                    settings.auftrag_timeout_minuten,
                )
                eintrag["status"] = OFFEN
                eintrag["abgeholt"] = None


auftrag_service = AuftragService()
