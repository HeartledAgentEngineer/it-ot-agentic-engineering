"""PC-Hermes-Anbindung (Track A) — sendet erkannte Programmierauftraege an den
lokalen Hermes-API-Server auf dem PC, wenn dieser im selben WLAN erreichbar ist.

Warum dieser Dienst:
  Das Backend laeuft auf dem Handy. Erkennt die Auftragserkennung eine
  Programmieraufgabe, soll sie moeglichst direkt von Hermes auf dem PC
  bearbeitet werden (voller PC-Zugriff: Terminal, Dateien, Git) — statt nur ins
  Auftragsbuch gelegt zu werden und auf einen manuellen Abholer zu warten.

  Ist der PC nicht erreichbar, liefert dieser Dienst `None`, und die Weiche
  faellt aufs Auftragsbuch zurueck (Track B, unveraendert). Er reisst nie die
  Anfrage: Ein toter PC darf den Chat nicht kaputt machen.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Der System-Prompt, mit dem der PC-Hermes den Auftrag bekommt.
_SYSTEM_PROMPT = (
    "Du bist der Coding-Agent des persoenlichen KI-Assistenten. Ein "
    "Coding-/Werkzeug-Auftrag des Nutzers wurde dir uebergeben. Bearbeite ihn "
    "auf diesem Rechner (Terminal, Dateien, Git), wo der Zugriff moeglich ist. "
    "Wenn etwas unklar ist, stelle eine Rueckfrage. Antworte auf Deutsch und "
    "fasse zum Schluss zusammen, was du getan hast."
)


class HermesGateway:
    """Leichtgewichtiger Client fuer den PC-Hermes-API-Server (OpenAI-Format)."""

    def __init__(self) -> None:
        self.base_url = settings.hermes_pc_base_url.rstrip("/")
        self.api_key = settings.hermes_pc_api_key
        self.timeout = settings.hermes_pc_timeout

    @property
    def ist_konfiguriert(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def is_online(self) -> bool:
        """Kurzer Erreichbarkeits-Check gegen /v1/models.

        Bewusst als eigener Call, damit der Chat-Weg nicht fuer den Check
        einen teuren Chat-Completion braucht. Scheitert bei Timeout/401/Netz.
        """
        if not self.ist_konfiguriert:
            return False
        try:
            r = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=min(self.timeout, 5),
            )
            return r.status_code == 200
        except Exception as e:  # pragma: no cover - Netz/Timeout
            logger.debug("PC-Hermes is_online: nicht erreichbar (%s)", e)
            return False

    def sende_auftrag(self, auftrag: str) -> Optional[str]:
        """Sendet einen Programmierauftrag an den PC-Hermes und liefert die Antwort.

        Returns:
            Die Antwort des PC-Hermes als Text, oder None, wenn der PC nicht
            erreichbar/konfiguriert ist (dann faellt die Weiche aufs Buch).
        """
        if not self.ist_konfiguriert:
            logger.info("PC-Hermes nicht konfiguriert (base_url/api_key fehlt) - Buch-Fallback")
            return None
        if not self.is_online():
            logger.info("PC-Hermes nicht erreichbar - Buch-Fallback")
            return None

        payload = {
            "model": "hermes-agent",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": auftrag},
            ],
            "stream": False,
        }
        try:
            r = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            r.raise_for_status()
            daten = r.json()
            antwort = (
                daten.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if antwort:
                return antwort
            logger.warning("PC-Hermes lieferte leere Antwort")
            return None
        except Exception as e:
            logger.warning("PC-Hermes-Anfrage fehlgeschlagen (%s) - Buch-Fallback", e)
            return None


hermes_gateway = HermesGateway()
