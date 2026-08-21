"""Lokale Hermes-CLI-Anbindung (Track C) — bearbeitet erkannte Programmierauftraege
direkt auf dem Geraet (dem Handy). So kann ein Coding-Auftrag unterwegs ohne
PC vom Hermes auf dem Termux uebernommen werden, statt nur im Auftragsbuch zu
warten.

Warum dieser Dienst:
  - Ohne PC (unterwegs, Zug/Wochenende) ist der PC-Hermes nicht erreichbar.
  - Dieses Modul ruft den lokalen `hermes`-CLI (Termux) auf, der den Auftrag
    mit vollem lokalem Zugriff (Dateien, Git) bearbeitet.
  - Ist `hermes` nicht installiert oder der Aufruf schlaegt fehl, liefert es
    `None`, und die Weiche faellt aufs Auftragsbuch zurueck (Track B).
"""

import logging
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Wie lange der lokale Hermes-CLI hoechstens fuer einen Auftrag arbeitet.
# Coding-Auftraege koennen lange dauern (Dateien anlegen, testen, commiten).
# Grosszuegig, damit ein echter Auftrag nicht mittendrin abbricht.
DEFAULT_TIMEOUT = 600


def ist_verfuegbar() -> bool:
    """True, wenn der lokale Hermes-CLI auf dem Geraet installiert ist."""
    return shutil.which("hermes") is not None


def sende_auftrag(auftrag: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Uebergibt einen Programmier-/Werkzeug-Auftrag an den lokalen Hermes-CLI.

    Returns:
        Die Antwort des lokalen Hermes, oder None, wenn `hermes` fehlt oder
        der Aufruf scheitert (dann faellt die Weiche aufs Auftragsbuch).
    """
    if not ist_verfuegbar():
        logger.info("Lokale Hermes-CLI (`hermes`) nicht gefunden - Buch-Fallback")
        return None

    # Einfacher, wartbarer Aufruf: hermes chat -q "<auftrag>".
    # Der Agent bearbeitet den Auftrag lokal und gibt die Antwort zurueck.
    try:
        result = subprocess.run(
            ["hermes", "chat", "-q", auftrag],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("hermes-CLI nicht ausfuehrbar - Buch-Fallback")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("Lokaler Hermes-Auftrag dauerte zu lange - Buch-Fallback")
        return None
    except Exception as e:  # pragma: no cover - sonstige Aufruffehler
        logger.warning("Lokaler Hermes-Aufruf fehlgeschlagen (%s) - Buch-Fallback", e)
        return None

    if result.returncode != 0:
        logger.warning(
            "Lokaler Hermes beendete mit Code %s - Buch-Fallback", result.returncode
        )
        return None

    antwort = (result.stdout or "").strip()
    if not antwort:
        logger.warning("Lokaler Hermes lieferte leere Antwort - Buch-Fallback")
        return None
    return antwort
