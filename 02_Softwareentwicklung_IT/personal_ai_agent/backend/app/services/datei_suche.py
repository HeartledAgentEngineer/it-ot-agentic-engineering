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


def lese_datei_info(pfad: str, max_zeichen: int = 8000) -> dict:
    """Liest den Inhalt einer Datei (für die Information/Stufe B).

    Liefert { "name", "erweiterung", "text", "ist_bild", "fehler" }.
    - PDF: Text via pdfminer (falls installiert).
    - TXT/MD/CSV/DOCX-ähnlich: roh als Text (gekürzt).
    - Bilder: markiert als ist_bild=True (kein Text; der Vision-LLM würde sie
      über lesbare Base64 verarbeiten — hier nur der Dateiname).
    Sicher: nur lesend, nur erlaubte Erweiterungen, nie GitHub.
    """
    import base64

    try:
        ext = os.path.splitext(pfad)[1].lower()
        name = os.path.basename(pfad)

        # Bilder: nicht als Text lesbar, aber für Vision verfügbar.
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            try:
                with open(pfad, "rb") as f:
                    b64 = base64.b64encode(f.read(2_000_000)).decode()  # max 2MB
                return {
                    "name": name, "erweiterung": ext,
                    "text": "", "ist_bild": True,
                    "data_url": f"data:image/{ext[1:]};base64,{b64}",
                    "fehler": None,
                }
            except Exception as e:
                return {"name": name, "erweiterung": ext, "text": "", "ist_bild": True,
                        "data_url": "", "fehler": str(e)}

        # Text-Dokumente
        text = ""
        try:
            if ext == ".pdf":
                text = _pdf_text(pfad)
            else:
                with open(pfad, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
        except Exception as e:
            return {"name": name, "erweiterung": ext, "text": "", "ist_bild": False,
                    "data_url": "", "fehler": str(e)}
        if len(text) > max_zeichen:
            text = text[:max_zeichen] + "…"
        return {"name": name, "erweiterung": ext, "text": text, "ist_bild": False,
                "data_url": "", "fehler": None}
    except Exception as e:
        return {"name": os.path.basename(pfad), "erweiterung": "", "text": "",
                "ist_bild": False, "data_url": "", "fehler": str(e)}


def _pdf_text(pfad: str) -> str:
    """Extrahiert Text aus einer PDF-Datei (via pdfminer, fallback leer)."""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pfad) or ""
    except Exception:
        # pdfminer fehlt oder PDF kaputt → leere Ausgabe (kein Crash).
        return ""
