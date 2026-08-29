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

# Fallback-Wurzeln: Falls die Termux-Symlinks fehlen (Android-Berechtigung /
# termux-setup-storage nie gelaufen), greifen direkte Android-Pfade. Die
# Kamera-/Bild-Ordner liegen dann unter /sdcard/DCIM etc.
_FALLBACK_WURZELN = [
    "/sdcard",              # Android-Storage (direkt, falls Termux-Symlink fehlt)
    os.path.join(os.path.expanduser("~"), "storage", "shared"),
]

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


def suche_dateien(stichwort: str, neueste_zuerst: bool = False) -> List[dict]:
    """Sucht Dateien in den freigegebenen Ordnern nach einem Stichwort.

    Returns: Liste von { pfad, name, groesse_byte, erweiterung, mtime }.
    - `stichwort` wird im Dateinamen (und Erweiterung) gesucht.
    - Leeres Stichwort + `neueste_zuerst=True` liefert ALLE Dateien sortiert
      (für "das letzte Bild" — kein Namens-Match nötig).
    - `neueste_zuerst=True` sortiert nach Änderungsdatum (neueste zuerst).
    Sucht die Wurzel `~/storage/shared` (enthält alle freigegebenen Bereiche).
    """
    stichwort = (stichwort or "").lower().strip()
    alle = neueste_zuerst and not stichwort  # "letztes Bild" → alles sortiert
    treffer: List[dict] = []
    gesehen: set = set()

    # Mehrere Wurzeln durchsuchen: primär ~/storage/shared, Fallback /sdcard
    # (falls die Termux-Symlinks fehlen). Dedupe über den echten Pfad.
    wurzeln = [_STORAGE_WURZEL] + [w for w in _FALLBACK_WURZELN if w != _STORAGE_WURZEL]
    for basis in wurzeln:
        if not os.path.isdir(basis):
            continue
        for root, dirs, files in os.walk(basis):
            # Tiefe begrenzen + versteckte/System-Ordner überspringen.
            rel = os.path.relpath(root, basis)
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
                try:
                    ident = os.path.realpath(voll)
                except OSError:
                    ident = voll
                if ident in gesehen:
                    continue
                # Match: Jedes Kern-Wort einzeln (OR) — "meinen lebenslauf"
                # findet die Datei "lebenslauf_sebastian.pdf" (lebenslauf
                # allein reicht). Nur als Phrase würde nichts matchen.
                name_lower = name.lower()
                matcht = alle
                if not matcht:
                    for wort in stichwort.split():
                        if wort in name_lower or wort in ext:
                            matcht = True
                            break
                if matcht:
                    gesehen.add(ident)
                    try:
                        mtime = os.path.getmtime(voll)
                        groesse = os.path.getsize(voll)
                    except OSError:
                        mtime, groesse = 0.0, 0
                    treffer.append({
                        "pfad": voll,
                        "name": name,
                        "groesse_byte": groesse,
                        "erweiterung": ext,
                        "mtime": mtime,
                    })
                if len(treffer) >= MAX_ERGEBNISSE:
                    break
            if len(treffer) >= MAX_ERGEBNISSE:
                break
        if len(treffer) >= MAX_ERGEBNISSE:
            break
    if neueste_zuerst:
        treffer.sort(key=lambda t: t.get("mtime") or 0, reverse=True)
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
                    roh = f.read()
                # Sehr große Bilder werden verkleinert (max. 1280px), statt
                # abgeschnitten — ein abgeschnittenes PNG lehnt der Vision-LLM
                # mit "Provided image is not valid" ab. Pillow ist Standard.
                if len(roh) > 3_000_000:  # > ~3 MB → verkleinern
                    try:
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(roh))
                        img.thumbnail((1280, 1280))
                        buf = io.BytesIO()
                        img.convert("RGB").save(buf, format="JPEG", quality=82)
                        roh = buf.getvalue()
                        ext = ".jpg"
                    except Exception:
                        pass  # kein Pillow → Original senden (ggf. zu groß)
                b64 = base64.b64encode(roh).decode()
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
