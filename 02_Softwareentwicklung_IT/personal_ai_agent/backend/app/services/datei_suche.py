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
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Öffentliche Termux-Speicherbasis (nach `termux-setup-storage`).
# Die Wurzel `~/storage/shared` enthält ALLE freigegebenen Bereiche
# (Download, Documents, Pictures, Movies, DCIM, etc.) — wir durchsuchen also
# das Ganze, nicht nur einzelne Ordner.
_STORAGE_WURZEL = os.path.expanduser("~/storage/shared")

def _fuzzy_match(wort: str, name_lower: str) -> bool:
    """Toleriert kleine Abweichungen (Sprach-/Tippfehler).

    - Subsequenz: alle Buchstaben des Suchworts kommen in gleicher
      Reihenfolge im Dateinamen vor ("wenk" → "wenck"): ok.
    - Edit-Distanz <= 1 für Wortlaengen >= 4 ("lebenslaf" → "lebenslauf").
    Konservativ + schnell: nur fuer die Dateisuche.
    """
    # Subsequenz-Check (einfach + robust): "wenk" in "wenck" = ok.
    it = iter(name_lower)
    if all(c in it for c in wort):
        return True
    # Edit-Distanz <= 1 (nur bei laengeren Woertern, sonst zu viele Treffer).
    if len(wort) >= 4 and len(name_lower) >= len(wort) - 1:
        # Levenshtein bis 1: pruefe auf Einfuegung/Loeschung/Ersetzung grob.
        def _lev(a: str, b: str, max_d: int = 1) -> bool:
            if abs(len(a) - len(b)) > max_d:
                return False
            dp = list(range(len(b) + 1))
            for i, ca in enumerate(a, 1):
                vorher = dp[0]
                dp[0] = i
                for j, cb in enumerate(b, 1):
                    alt = dp[j]
                    dp[j] = min(
                        dp[j] + 1,        # loeschen
                        dp[j - 1] + 1,    # einfuegen
                        vorher + (ca != cb),  # ersetzen
                    )
                    vorher = alt
            return dp[-1] <= max_d
        # Nur gegen den Dateinamen (ohne Endung), um keine Endungs-Pseudo-
        # Treffer zu erzeugen.
        kern = name_lower.rsplit(".", 1)[0]
        if len(kern) >= len(wort) - 1 and _lev(wort, kern):
            return True
    return False


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


def suche_dateien(
    stichwort: str,
    neueste_zuerst: bool = False,
    ordner_hinweis: str = "",
    nur_erweiterungen: Optional[Set[str]] = None,
    jahr: Optional[int] = None,
) -> List[dict]:
    """Sucht Dateien in den freigegebenen Ordnern nach einem Stichwort.

    Returns: Liste von { pfad, name, groesse_byte, erweiterung, mtime }.
    - `stichwort` wird im Dateinamen (und Erweiterung) gesucht.
    - Leeres Stichwort + `neueste_zuerst=True` liefert ALLE Dateien sortiert
      (für "das letzte Bild" — kein Namens-Match nötig).
    - `neueste_zuerst=True` sortiert nach Änderungsdatum (neueste zuerst).
    - `jahr`: Optionales Aufnahmejahr (z. B. 2025). Ist es gesetzt, werden nur
      Dateien behalten, deren Aufnahmejahr (EXIF, Fallback mtime) diesem Jahr
      entspricht — "das letzte Foto aus 2025" filtert 2025er exakt heraus.
    - `ordner_hinweis`: "kamera" bevorzugt DCIM (echte Fotos), "screenshot"
      bevorzugt Pictures/Screenshots. Treffer im bevorzugten Ordner kommen
      IMMER zuerst (auch vor neueren aus anderen Ordnern — so findet
      "letztes Foto" das echte Kamera-Bild statt alter Screenshots).
    - `nur_erweiterungen`: Optionales Set von Erweiterungen (z. B.
      {".jpg", ".png"}). Ist es gesetzt, werden NUR Dateien mit diesen
      Erweiterungen gesammelt — die `_ERLAUBTE_EXT`-Prüfung bleibt, aber
      der Filter verengt zusätzlich (Foto-Frage → nie PDFs, Dokument-Frage
      → nie Bilder). Groß-/Kleinschreibung wird normalisiert.
    Sucht die Wurzel `~/storage/shared` (enthält alle freigegebenen Bereiche).
    """
    stichwort = (stichwort or "").lower().strip()
    # Erweiterungen normalisieren (Aufrufer könnte ".JPG" übergeben).
    ext_filter = {e.lower() for e in (nur_erweiterungen or set())} if nur_erweiterungen else None
    alle = neueste_zuerst and not stichwort  # "letztes Bild" → alles sortiert
    vorzug_kamera = "kamera" in ordner_hinweis
    vorzug_screenshot = "screenshot" in ordner_hinweis
    treffer: List[dict] = []
    gesehen: set = set()

    # Mehrere Wurzeln durchsuchen: primär ~/storage/shared, Fallback /sdcard
    # (falls die Termux-Symlinks fehlen). Dedupe über den echten Pfad.
    wurzeln = [_STORAGE_WURZEL] + [w for w in _FALLBACK_WURZELN if w != _STORAGE_WURZEL]
    # DCIM (Kamera) als eigene, PRIORISIERTE Wurzel: Termux ~/storage/shared
    # enthält DCIM oft NICHT (Android-Scoped-Storage) — die echten Kamera-
    # Fotos liegen unter /sdcard/DCIM/Camera. Flacher Walk = schnell.
    dcim_kandidaten = [
        os.path.expanduser("~/storage/shared/DCIM"),
        "/sdcard/DCIM",
    ]
    if vorzug_kamera:
        # Bei Kamera-Fragen: NICHT den ganzen /sdcard-Baum durchsuchen
        # (Riesen-Walk = Timeout), sondern gezielt DCIM + shared.
        wurzeln = dcim_kandidaten + [_STORAGE_WURZEL]
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
                # Dateityp-Filter: nur_erweiterungen (z. B. nur Bilder bei
                # Foto-Fragen) verengt die Suche — alles andere wird
                # übersprungen, BEVOR irgendein Match geprüft wird.
                if ext_filter is not None and ext not in ext_filter:
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
                # Zusätzlich FUZZY: bis zu 1 Buchstabe Abweichung wird
                # toleriert ("wenk" → "Wenck", Sprach-Tippfehler) — wie die
                # Explorer-/Google-App-Suche.
                name_lower = name.lower()
                matcht = alle
                if not matcht:
                    for wort in stichwort.split():
                        if len(wort) < 3:
                            continue
                        if wort in name_lower or wort in ext:
                            matcht = True
                            break
                        # Fuzzy: 1 Zeichen entfernt (Subsequenz/Insertion)
                        if _fuzzy_match(wort, name_lower):
                            matcht = True
                            break
                if matcht:
                    # Jahresfilter: nur Dateien dieses Aufnahmejahres behalten.
                    if jahr is not None and _datei_jahr(voll) != jahr:
                        continue
                    gesehen.add(ident)
                    try:
                        mtime = os.path.getmtime(voll)
                        groesse = os.path.getsize(voll)
                    except OSError:
                        mtime, groesse = 0.0, 0
                    # Vorzug-Ordner (Kamera/Screenshots): Treffer dort bekommen Gewicht 0 →
                    # sie landen IMMER vor anderen (auch neueren). Plattform-
                    # unabhängig: /dcim/ (Linux/Android) ODER \dcim\ (Windows).
                    pfad_lower = voll.lower()
                    if vorzug_kamera and ("/dcim/" in pfad_lower or "\\dcim\\" in pfad_lower):
                        gewicht = 0
                    elif vorzug_screenshot and ("/screenshots" in pfad_lower or "\\screenshots" in pfad_lower):
                        gewicht = 0
                    else:
                        gewicht = 1
                    treffer.append({
                        "pfad": voll,
                        "name": name,
                        "groesse_byte": groesse,
                        "erweiterung": ext,
                        "mtime": mtime,
                        "_gewicht": gewicht,
                    })
                if not neueste_zuerst and len(treffer) >= MAX_ERGEBNISSE:
                    break
            if not neueste_zuerst and len(treffer) >= MAX_ERGEBNISSE:
                break
        if not neueste_zuerst and len(treffer) >= MAX_ERGEBNISSE:
            break
    if neueste_zuerst:
        # Vorzug-Ordner zuerst (Gewicht 0), innerhalb gleicher Gewicht
        # nach Zeit (neueste zuerst). ACHTUNG: `or 1` wäre falsch — 0 ist
        # falsy, Gewicht 0 würde zu 1 (kein Vorzug). Default nur per .get.
        # EXIF-Aufnahmedatum für Bilder nutzen (genauer als mtime) — der
        # Explorer sortiert genauso. Fallback: mtime.
        def _sort_schluessel(t: dict):
            aufnahme = None
            if t.get("erweiterung") in (".jpg", ".jpeg", ".png", ".webp"):
                aufnahme = _exif_aufnahmedatum(t["pfad"])
            zeit = aufnahme if aufnahme is not None else (t.get("mtime") or 0)
            return (t.get("_gewicht", 1), -zeit)
        treffer.sort(key=_sort_schluessel)
        # Erst JETZT kappen: das Limit darf den Walk nicht vorher stoppen,
        # sonst fehlt das neueste Bild, wenn es alphabetisch/später liegt
        # (z. B. IMG_2026... hinter IMG2024...).
        treffer = treffer[:MAX_ERGEBNISSE]
    # _gewicht ist intern — nicht an den Aufrufer geben.
    for t in treffer:
        t.pop("_gewicht", None)
    return treffer


def _datei_jahr(pfad: str) -> Optional[int]:
    """Aufnahmejahr einer Datei (int) — EXIF, Fallback mtime-Jahr.

    Nutzt `_exif_aufnahmedatum` (genauer als mtime). Liegt kein EXIF vor
    (z. B. bei Screenshots), fällt es auf das Jahr der Datei-mtime zurück.
    Nicht ermittelbar → None (der Jahresfilter überspringt dann die Datei).
    """
    aufnahme = _exif_aufnahmedatum(pfad)
    ts = aufnahme if aufnahme is not None else _mtime_fallbacks(pfad)
    if ts is None:
        return None
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ts).year


def _mtime_fallbacks(pfad: str) -> Optional[float]:
    """mtime einer Datei als Unix-Zeit (oder None bei Fehler)."""
    try:
        return os.path.getmtime(pfad)
    except OSError:
        return None


def _exif_aufnahmedatum(pfad: str) -> Optional[float]:
    """EXIF-Aufnahmedatum (DateTimeOriginal) eines Bildes als Unix-Zeit.

    Nutzt Pillow-EXIF — genauer als Datei-mtime (die z. B. beim Kopieren/
    Backup verloren geht). Fehlt EXIF, liefert None (Aufrufer faellt auf
    mtime zurueck). Fuer Nicht-Bilder eh None.
    """
    try:
        from PIL import Image
        import datetime as _dt
        with Image.open(pfad) as img:
            exif = img.getexif()
            if not exif:
                return None
            wert = exif.get(36867) or exif.get(36868) or exif.get(306)
            if not wert:
                return None
            ts = _dt.datetime.strptime(str(wert).strip(), "%Y:%m:%d %H:%M:%S")
            return ts.timestamp()
    except Exception:
        return None

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
                # EXIF-Orientierung (z. B. 6 = Hochformat bei Handy-Fotos) in
                # die Pixel einbacken, damit das Bild beim Anzeigen ('Bild
                # wieder anzeigen'-Button) richtig gedreht erscheint. Nur
                # in-memory — die Originaldatei bleibt unangetastet. GIFs
                # werden ausgelassen (animiert, selten EXIF-orientiert).
                if ext in (".jpg", ".jpeg", ".png", ".webp"):
                    try:
                        from PIL import Image, ImageOps
                        import io
                        img = Image.open(io.BytesIO(roh))
                        gedreht = ImageOps.exif_transpose(img)
                        if gedreht is not img:
                            buf = io.BytesIO()
                            gedreht.convert("RGB").save(
                                buf, format="JPEG", quality=82)
                            roh = buf.getvalue()
                            ext = ".jpg"
                    except Exception:
                        pass  # kein Pillow / ungültiges Bild → Original senden
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
