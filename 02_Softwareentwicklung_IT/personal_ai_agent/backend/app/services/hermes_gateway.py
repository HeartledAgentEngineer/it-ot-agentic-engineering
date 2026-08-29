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
        Setzt bei Fehlern `self.letzter_fehler` (kurzer Grund), damit der
        Router dem Nutzer/Kanal erklären kann, warum es nicht am PC lief —
        OHNE dass parallel ein zweiter Track gestartet wird (exklusiv).
        """
        self.letzter_fehler = ""
        if not self.ist_konfiguriert:
            self.letzter_fehler = "PC-Hermes nicht konfiguriert (base_url/api_key fehlt)"
            logger.info("PC-Hermes nicht konfiguriert - Fallback")
            return None
        if not self.is_online():
            # is_online scheitert bei Timeout/401/Auth: Grund unterscheiden.
            self.letzter_fehler = self._online_hinweis()
            logger.info("PC-Hermes nicht erreichbar/Auth (%s) - Fallback", self.letzter_fehler)
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
            # 2xx + leere Antwort: der PC-Hermes HAT den Auftrag angenommen,
            # liefert aber (noch) keinen Text. Kein Fallback auf Handy —
            # sonst laufen beide. Bestätigung liefern.
            self.letzter_fehler = "PC-Hermes hat angenommen (leere Antwort)"
            logger.warning("PC-Hermes 2xx mit leerer Antwort - kein Fallback")
            return (
                "🧩 **Hermes-Aufgabe wurde an den PC-Hermes übergeben.**\n\n"
                "Der PC-Hermes arbeitet an der Aufgabe. Das Ergebnis erscheint, "
                "sobald es vorliegt."
            )
        except httpx.TimeoutException:
            # Der PC-Hermes HAT den Auftrag angenommen (der POST kam durch),
            # aber die Antwort dauert länger als das Timeout. NIEMALS auf den
            # Handy-Hermes zurückfallen — der würde parallel arbeiten und
            # hängen. Stattdessen Bestätigung liefern (Router bleibt bei PC).
            self.letzter_fehler = "PC-Hermes arbeitet (Antwort > Timeout)"
            logger.warning("PC-Hermes arbeitet laenger als %ss - kein Fallback", self.timeout)
            return (
                "🧩 **Hermes-Aufgabe wurde an den PC-Hermes übergeben.**\n\n"
                "Der PC-Hermes arbeitet gerade an der Aufgabe. Sobald sein "
                "Ergebnis vorliegt, erscheint es hier. (Antwort hat länger "
                "als das Timeout gedauert — der Auftrag läuft trotzdem.)"
            )
        except Exception as e:
            self.letzter_fehler = f"PC-Hermes-Anfrage fehlgeschlagen: {e}"
            logger.warning("PC-Hermes-Anfrage fehlgeschlagen (%s) - Fallback", e)
            return None

    def _online_hinweis(self) -> str:
        """Kurzer Grund, warum der Erreichbarkeits-Check scheiterte (Auth/Netz)."""
        if not self.ist_konfiguriert:
            return "nicht konfiguriert"
        try:
            r = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=min(self.timeout, 5),
            )
            if r.status_code in (401, 403):
                return "Auth-Fehler (API-Key falsch/fehlt)"
            if r.status_code == 200:
                return "ok"
            return f"Status {r.status_code}"
        except Exception as e:  # pragma: no cover - Netz/Timeout
            return f"nicht erreichbar ({e.__class__.__name__})"


hermes_gateway = HermesGateway()
