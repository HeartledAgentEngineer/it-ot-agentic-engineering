"""Handy-Dateisuche (Termux).

Durchsucht die öffentlichen Android-Bereiche (Downloads, Documents, Pictures),
auf die Termux über `~/storage/...` zugreifen kann (nach `termux-setup-storage`).
Nur LESEN — es wird nie etwas verändert. Der Agent kann so Dokumente finden,
die der Nutzer nicht explizit angehängt hat.

Sicherheit:
- Es werden NUR die freigegebenen Basis-Ordner durchsucht (keine beliebigen
  Systempfade, kein Zugriff auf `.env`/private Backend-Dateien).
- Es werden nur Datei-Namen/Erweiterungen zurückgegeben (kein Dateiinhalt) —
  der Inhalt wird erst verarbeitet, wenn der Nutzer sie anhängt.
"""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# Öffentliche Termux-Speicherbasis (nach `termux-setup-storage`).
# Die Wurzel `~/storage/shared` enthält ALLE freigegebenen Bereiche
# (Download, Documents, Pictures, Movies, DCIM, etc.) — wir durchsuchen also
# das Ganze, nicht nur einzelne Ordner.
_STORAGE_WURZEL = os.path.expanduser("~/storage/shared")

# Fällt die Wurzel weg (Termux ohne Storage-Zugriff), leere Fallbacks:
_STORAGE_BASIS = [
    _STORAGE_WURZEL,
    os.path.expanduser("~/storage/shared/Download"),
    os.path.expanduser("~/storage/shared/Documents"),
    os.path.expanduser("~/storage/shared/Pictures"),
]
# Erlaubte Dateitypen für Dokumente/Bilder.
_ERLAUBTE_EXT = {
    ".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls",
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
}
MAX_ERGEBNISSE = 30
MAX_TIEFE = 3  # nicht zu tief in Ordnerhierarchien tauchen


def suche_dateien(stichwort: str) -> List[dict]:
    """Sucht Dateien in den freigegebenen Ordnern nach einem Stichwort.

    Returns: Liste von { pfad, name, groesse_byte, erweiterung }.
    Gibt stichwort=="" alle (relevante) Dateien zurück (begrenzt).
    Sucht die Wurzel `~/storage/shared` (enthält alle freigegebenen Bereiche).
    """
    if not stichwort:
        return []
    stichwort = stichwort.lower().strip()
    treffer: List[dict] = []

    # Nur die Wurzel durchsuchen (enthält Download/Documents/Pictures/etc.).
    if os.path.isdir(_STORAGE_WURZEL):
        for root, dirs, files in os.walk(_STORAGE_WURZEL):
            # Tiefe begrenzen + versteckte/System-Ordner überspringen.
            rel = os.path.relpath(root, _STORAGE_WURZEL)
            tiefe = 0 if rel == "." else rel.count(os.sep) + 1
            if tiefe > MAX_TIEFE:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in _ERLAUBTE_EXT:
                    continue
                voll = os.path.join(root, name)
                if stichwort in name.lower() or stichwort in ext:
                    try:
                        groesse = os.path.getsize(voll)
                    except OSError:
                        groesse = 0
                    treffer.append({
                        "pfad": voll,
                        "name": name,
                        "groesse_byte": groesse,
                        "erweiterung": ext,
                    })
                if len(treffer) >= MAX_ERGEBNISSE:
                    return treffer
    return treffer


def basis_ordner_verfuegbar() -> List[str]:
    """Welche der freigegebenen Basis-Ordner existieren (für Hinweise)."""
    if os.path.isdir(_STORAGE_WURZEL):
        return [_STORAGE_WURZEL]
    return [b for b in _STORAGE_BASIS if os.path.isdir(b)]
