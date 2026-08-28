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
    # Nur Sekunden-Genauigkeit — kein .µs-Zeug, das die Meldung unlesbar macht
    # und unnötig lang/tokenreich ist. (Vorher isoformat() ohne timespec → volle
    # Mikrosekunden + Zeitzone, z. B. [2026-08-24T13:47:54.383882+02:00].)
    return datetime.now().astimezone().isoformat(timespec="seconds")


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

    def anlegen_als_arbeitender(
        self,
        auftrag: str,
        hinweis: Optional[str] = None,
        kategorie: Optional[str] = None,
        komplexitaet: Optional[str] = None,
    ) -> dict:
        """Traegt einen neuen Auftrag ein und markiert ihn sofort als laeuft.

        Fuer den Fall, dass der lokale Hermes (Track C) eine erkannte Aufgabe
        direkt uebernimmt: Der Job startet sofort, deshalb darf der Auftrag
        nicht als ``offen`` im Buch liegen — sonst wuerde ihn der Watcher
        parallel claimen und noch einmal aufmachen. Er wird nie ``offen``,
        sondern direkt ``laeuft``/``abgeholt`` angelegt.
        """
        eintrag = self.anlegen(auftrag, hinweis, kategorie, komplexitaet)
        eintrag["status"] = LAEUFT
        eintrag["abgeholt"] = _jetzt()
        with self._sperre:
            auftraege = self._lesen()
            for a in auftraege:
                if a.get("id") == eintrag["id"]:
                    a["status"] = LAEUFT
                    a["abgeholt"] = eintrag["abgeholt"]
                    self._schreiben(auftraege)
                    break
        logger.info(
            "Auftrag direkt in Bearbeitung: %s (Kategorie: %s)",
            eintrag["id"][:8], kategorie,
        )
        return eintrag

    def alle(self, limit: int = 50) -> list[dict]:
        with self._sperre:
            auftraege = self._lesen()
        return sorted(auftraege, key=lambda a: a.get("erstellt", ""), reverse=True)[:limit]

    def einzeln(self, auftrag_id: str) -> Optional[dict]:
        with self._sperre:
            for eintrag in self._lesen():
                if eintrag.get("id", "").startswith(auftrag_id):
                    return eintrag
        return None

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
            for eintrag in auftraege:
                if eintrag.get("id") != auftrag_id:
                    continue
                eintrag["status"] = FERTIG if erfolg else FEHLER
                eintrag["ergebnis"] = ergebnis
                eintrag["beendet"] = _jetzt()
                self._schreiben(auftraege)
                # Das Ergebnis ist die eigentliche Antwort von Hermes — sie
                # gehoert auch in den persistenten Chat-Verlauf, falls dieser
                # Auftrag aus einem Gespraech entstand.
                self._in_verlauf_anhaengen(
                    eintrag.get("conversation_id"), "assistant", ergebnis
                )
                logger.info("Auftrag %s: %s", auftrag_id[:8], "fertig" if erfolg else "fehlgeschlagen")
                return eintrag
        return None

    def statusmeldung_hinzufuegen(self, auftrag_id: str, meldung: str) -> Optional[dict]:
        """Fuegt eine Zwischenmeldung des Coding-Agenten hinzu."""
        with self._sperre:
            auftraege = self._lesen()
            for eintrag in auftraege:
                if eintrag.get("id") != auftrag_id:
                    continue
                if "status_meldungen" not in eintrag:
                    eintrag["status_meldungen"] = []
                zeichen = f"[{_jetzt()}] {meldung}"
                eintrag["status_meldungen"].append(zeichen)
                # Maximal 20 Meldungen behalten
                if len(eintrag["status_meldungen"]) > 20:
                    eintrag["status_meldungen"] = eintrag["status_meldungen"][-20:]
                self._schreiben(auftraege)
                # Zwischenmeldung auch in den persistenten Chat-Verlauf
                # uebernehmen, damit sie ein Neuladen ueberlebt.
                self._in_verlauf_anhaengen(
                    eintrag.get("conversation_id"), "assistant", zeichen
                )
                logger.info("Statusmeldung fuer %s: %s", auftrag_id[:8], meldung[:60])
                return eintrag
        return None

    def rueckfrage_stellen(self, auftrag_id: str, frage: str, kontext: Optional[str] = None) -> Optional[dict]:
        """Hermes stellt eine Rueckfrage zum Auftrag."""
        with self._sperre:
            auftraege = self._lesen()
            for eintrag in auftraege:
                if eintrag.get("id") != auftrag_id:
                    continue
                if "rueckfragen" not in eintrag:
                    eintrag["rueckfragen"] = []
                eintrag["rueckfragen"].append({
                    "frage": frage,
                    "kontext": kontext,
                    "gestellt_um": _jetzt(),
                    "antwort": None,
                })
                self._schreiben(auftraege)
                logger.info("Rueckfrage fuer %s: %s", auftrag_id[:8], frage[:60])
                return eintrag
        return None

    def rueckfrage_beantworten(self, auftrag_id: str, antwort_idx: int, antwort: str) -> Optional[dict]:
        """Nutzer beantwortet eine Rueckfrage."""
        with self._sperre:
            auftraege = self._lesen()
            for eintrag in auftraege:
                if eintrag.get("id") != auftrag_id:
                    continue
                rueckfragen = eintrag.get("rueckfragen", [])
                if antwort_idx < 0 or antwort_idx >= len(rueckfragen):
                    return None
                rueckfragen[antwort_idx]["antwort"] = antwort
                rueckfragen[antwort_idx]["beantwortet_um"] = _jetzt()
                self._schreiben(auftraege)
                logger.info("Rueckfrage %d fuer %s beantwortet", antwort_idx, auftrag_id[:8])
                return eintrag
        return None

    def offene_rueckfragen(self, auftrag_id: str) -> list[dict]:
        """Alle noch unbeantworteten Rueckfragen."""
        eintrag = self.einzeln(auftrag_id)
        if not eintrag:
            return []
        return [r for r in eintrag.get("rueckfragen", []) if r.get("antwort") is None]

    def setze_chat_verknuepfung(
        self, auftrag_id: str, conversation_id: Optional[str]
    ) -> Optional[dict]:
        """Verknuepft einen Coding-Auftrag mit dem Chat-Gespraech, das ihn
        ausgeloest hat.

        Nur dann kann das Auftragsbuch Hermes-Live-Nachrichten
        (Zwischenmeldungen, Ergebnis) in den persistenten Chat-Verlauf
        uebernehmen. Ohne Verknuepfung (z. B. Auftrag direkt aus dem
        Auftragsbuch) bleibt der Verlauf unveraendert.
        """
        with self._sperre:
            auftraege = self._lesen()
            for eintrag in auftraege:
                if eintrag.get("id") != auftrag_id:
                    continue
                eintrag["conversation_id"] = conversation_id
                self._schreiben(auftraege)
                return eintrag
        return None

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _in_verlauf_anhaengen(
        self, conversation_id: Optional[str], role: str, content: str
    ) -> None:
        """Reicht eine Agenten-Nachricht an den Chat-Verlauf weiter.

        Geschieht nur, wenn der Auftrag mit einem Gespraech verknuepft ist.
        Fehler gehen nicht ins Ohr: Eine Stoerung beim Verlauf darf das
        Auftragsbuch selbst nicht brechen.
        """
        if not conversation_id:
            return
        try:
            # Bewusst lazy importiert: ``chat`` importiert diesen Service,
            # ein Modul-Level-Import hierher wuerde einen Kreislauf bilden.
            from app.router.chat import verlauf_nachricht_anhaengen

            verlauf_nachricht_anhaengen(conversation_id, role, content)
        except Exception as fehler:
            logger.warning(
                "Live-Nachricht nicht an den Verlauf uebergeben (%s): %s",
                conversation_id[:12],
                fehler,
            )

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
            if (jetzt - abgeholt).total_seconds() > grenze:
                logger.warning(
                    "Auftrag %s lief laenger als %d Minuten - wieder offen",
                    eintrag.get("id")[:8],
                    settings.auftrag_timeout_minuten,
                )
                eintrag["status"] = OFFEN
                eintrag["abgeholt"] = None


auftrag_service = AuftragService()
