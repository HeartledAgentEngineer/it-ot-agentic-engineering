"""Auftragsbuch fuer den Coding-Agenten.

Der Agent auf dem Handy kann Hermes nicht anrufen - die App hat keinen
eingehenden HTTP-Zugang. Nur Hermes kann von sich aus fragen. Deshalb
liegt hier ein Buch, in das die Oberflaeche Auftraege eintraegt und aus
dem Hermes sich im eigenen Takt bedient.

Erweiterungen:
  - Kategorie und Komplexitaet pro Auftrag
  - Status-Meldungen (Hermes meldet Zwischenstaende)
  - Rueckfragen (Hermes kann den Nutzer etwas fragen)
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

OFFEN = "offen"
LAEUFT = "laeuft"
FERTIG = "fertig"
FEHLER = "fehler"


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuftragService:
    """Liest und schreibt das Auftragsbuch."""

    def __init__(self) -> None:
        self._pfad = Path(settings.auftraege_datei)
        self._sperre = threading.Lock()

    # ------------------------------------------------------------------
    # Dateizugriff
    # ------------------------------------------------------------------

    def _lesen(self) -> list[dict]:
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
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        entwurf = self._pfad.with_suffix(".json.tmp")
        with entwurf.open("w", encoding="utf-8") as datei:
            json.dump(auftraege, datei, ensure_ascii=False, indent=2)
        entwurf.replace(self._pfad)

    # ------------------------------------------------------------------
    # Auftragssuche
    # ------------------------------------------------------------------

    @staticmethod
    def _finden(auftraege: list[dict], auftrag_id: str) -> Optional[dict]:
        """Sucht einen Auftrag ueber die volle ID oder ein eindeutiges Praefix.

        Sichtbar ist ueberall nur die achtstellige Kurzform - im Chat, in der
        Oberflaeche, in den Logzeilen. Hermes und der Termux-Watcher melden
        genau damit zurueck. Ein exakter Vergleich laesst deshalb jede
        Rueckmeldung ins Leere laufen: der Auftrag bleibt fuer immer auf
        "laeuft" stehen, ohne dass irgendwo ein Fehler sichtbar wird.

        Bei mehreren Treffern kommt None zurueck, nicht der erste. Eine
        Meldung am falschen Auftrag ist schlimmer als gar keine.
        """
        if not auftrag_id:
            return None

        treffer = [
            eintrag
            for eintrag in auftraege
            if eintrag.get("id", "").startswith(auftrag_id)
        ]
        if len(treffer) == 1:
            return treffer[0]
        if len(treffer) > 1:
            logger.warning(
                "Auftrags-ID %s ist mehrdeutig (%d Treffer) - keine Zuordnung",
                auftrag_id,
                len(treffer),
            )
        return None

    # ------------------------------------------------------------------
    # Oeffentliche Schnittstelle
    # ------------------------------------------------------------------

    def anlegen(
        self,
        auftrag: str,
        hinweis: Optional[str] = None,
        kategorie: Optional[str] = None,
        komplexitaet: Optional[str] = None,
    ) -> dict:
        """Traegt einen neuen Auftrag ein."""
        eintrag = {
            "id": str(uuid.uuid4()),
            "auftrag": auftrag,
            "hinweis": hinweis,
            "kategorie": kategorie or "unbekannt",
            "komplexitaet": komplexitaet or "mittel",
            "status": OFFEN,
            "erstellt": _jetzt(),
            "abgeholt": None,
            "beendet": None,
            "ergebnis": None,
            "status_meldungen": [],
            "rueckfragen": [],
        }
        with self._sperre:
            auftraege = self._lesen()
            auftraege.append(eintrag)
            self._schreiben(auftraege)
        logger.info("Auftrag angelegt: %s (Kategorie: %s)", eintrag["id"][:8], kategorie)
        return eintrag

    def alle(self, limit: int = 50) -> list[dict]:
        with self._sperre:
            auftraege = self._lesen()
        return sorted(auftraege, key=lambda a: a.get("erstellt", ""), reverse=True)[:limit]

    def einzeln(self, auftrag_id: str) -> Optional[dict]:
        with self._sperre:
            return self._finden(self._lesen(), auftrag_id)

    def naechster_offener(self) -> Optional[dict]:
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

        logger.info("Auftrag ausgegeben: %s", naechster["id"][:8])
        return naechster

    def ergebnis_eintragen(
        self, auftrag_id: str, ergebnis: str, erfolg: bool = True
    ) -> Optional[dict]:
        with self._sperre:
            auftraege = self._lesen()
            eintrag = self._finden(auftraege, auftrag_id)
            if eintrag is None:
                return None
            eintrag["status"] = FERTIG if erfolg else FEHLER
            eintrag["ergebnis"] = ergebnis
            eintrag["beendet"] = _jetzt()
            self._schreiben(auftraege)

        logger.info(
            "Auftrag %s: %s",
            eintrag["id"][:8],
            "fertig" if erfolg else "fehlgeschlagen",
        )
        return eintrag

    def statusmeldung_hinzufuegen(self, auftrag_id: str, meldung: str) -> Optional[dict]:
        """Fuegt eine Zwischenmeldung des Coding-Agenten hinzu."""
        with self._sperre:
            auftraege = self._lesen()
            eintrag = self._finden(auftraege, auftrag_id)
            if eintrag is None:
                return None
            if "status_meldungen" not in eintrag:
                eintrag["status_meldungen"] = []
            eintrag["status_meldungen"].append(f"[{_jetzt()}] {meldung}")
            # Maximal 20 Meldungen behalten
            if len(eintrag["status_meldungen"]) > 20:
                eintrag["status_meldungen"] = eintrag["status_meldungen"][-20:]
            self._schreiben(auftraege)

        logger.info("Statusmeldung fuer %s: %s", eintrag["id"][:8], meldung[:60])
        return eintrag

    def rueckfrage_stellen(self, auftrag_id: str, frage: str, kontext: Optional[str] = None) -> Optional[dict]:
        """Hermes stellt eine Rueckfrage zum Auftrag."""
        with self._sperre:
            auftraege = self._lesen()
            eintrag = self._finden(auftraege, auftrag_id)
            if eintrag is None:
                return None
            if "rueckfragen" not in eintrag:
                eintrag["rueckfragen"] = []
            eintrag["rueckfragen"].append({
                "frage": frage,
                "kontext": kontext,
                "gestellt_um": _jetzt(),
                "antwort": None,
            })
            self._schreiben(auftraege)

        logger.info("Rueckfrage fuer %s: %s", eintrag["id"][:8], frage[:60])
        return eintrag

    def rueckfrage_beantworten(self, auftrag_id: str, antwort_idx: int, antwort: str) -> Optional[dict]:
        """Nutzer beantwortet eine Rueckfrage."""
        with self._sperre:
            auftraege = self._lesen()
            eintrag = self._finden(auftraege, auftrag_id)
            if eintrag is None:
                return None
            rueckfragen = eintrag.get("rueckfragen", [])
            if antwort_idx < 0 or antwort_idx >= len(rueckfragen):
                return None
            rueckfragen[antwort_idx]["antwort"] = antwort
            rueckfragen[antwort_idx]["beantwortet_um"] = _jetzt()
            self._schreiben(auftraege)

        logger.info(
            "Rueckfrage %d fuer %s beantwortet", antwort_idx, eintrag["id"][:8]
        )
        return eintrag

    def offene_rueckfragen(self, auftrag_id: str) -> list[dict]:
        """Alle noch unbeantworteten Rueckfragen."""
        eintrag = self.einzeln(auftrag_id)
        if not eintrag:
            return []
        return [r for r in eintrag.get("rueckfragen", []) if r.get("antwort") is None]

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _verwaiste_freigeben(self, auftraege: list[dict]) -> None:
        grenze = settings.auftrag_timeout_minuten * 60
        jetzt = datetime.now(timezone.utc)

        for eintrag in auftraege:
            if eintrag.get("status") != LAEUFT or not eintrag.get("abgeholt"):
                continue
            try:
                abgeholt = datetime.fromisoformat(eintrag["abgeholt"])
            except (ValueError, TypeError):
                continue
            # Aeltere Eintraege koennen einen Zeitstempel ohne Zone tragen.
            # Ohne diese Zeile wirft der Vergleich einen TypeError - und weil
            # der Watcher alle 3 Sekunden hier durchlaeuft, wuerde ein
            # einziger solcher Eintrag die gesamte Auftragskette lahmlegen.
            if abgeholt.tzinfo is None:
                abgeholt = abgeholt.replace(tzinfo=timezone.utc)
            if (jetzt - abgeholt).total_seconds() > grenze:
                logger.warning(
                    "Auftrag %s lief laenger als %d Minuten - wieder offen",
                    eintrag.get("id", "")[:8],
                    settings.auftrag_timeout_minuten,
                )
                eintrag["status"] = OFFEN
                eintrag["abgeholt"] = None


auftrag_service = AuftragService()
