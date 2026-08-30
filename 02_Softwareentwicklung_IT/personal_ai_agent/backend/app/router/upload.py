"""File upload API routes.

Ermöglicht das Hochladen von Bildern und PDFs, die dann im Chat
als Kontext an den LLM übergeben werden können.
"""

import base64
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from app.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

# Erlaubte Dateitypen
ERLAUBTE_BILDER = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ERLAUBTE_PDFS = {"application/pdf"}
ERLAUBTE_TYPEN = ERLAUBTE_BILDER | ERLAUBTE_PDFS

# Upload-Verzeichnis (persistent, neben chroma_data)
UPLOAD_DIR = BASE_DIR / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Abhängigkeiten testen (Android hat oft nur Stubs ohne native .so) ──────
_HAT_PIL: bool = False
try:
    from PIL import Image as _PIL_Image  # noqa: F401
    _HAT_PIL = True
except Exception:
    logger.info("PIL/Pillow nicht verfügbar – Bilder ohne Resize verarbeitet")

_HAT_PDFMINER: bool = False
try:
    from pdfminer.high_level import extract_text  # noqa: F401
    _HAT_PDFMINER = True
except Exception:
    logger.info("pdfminer nicht verfügbar – PDF-Text-Extraktion deaktiviert")


def _ist_erlaubt(content_type: str) -> bool:
    """Prüft, ob der Dateityp hochgeladen werden darf."""
    return content_type in ERLAUBTE_TYPEN


def _datei_typ(content_type: str) -> str:
    """Ermittelt den menschenlesbaren Dateityp."""
    if content_type in ERLAUBTE_BILDER:
        return "image"
    if content_type == "application/pdf":
        return "pdf"
    return "unknown"


async def _bild_als_base64(pfad: Path) -> Optional[str]:
    """Liest eine Bilddatei und gibt sie als Base64-String zurück.

    Nutzt PIL für optionales Resizing, falls verfügbar.
    Ohne PIL werden die Roh-Bytes direkt codiert (kein Resize).

    WICHTIG: Die Originaldatei wird NIE überschrieben. Die EXIF-Drehung
    (z. B. 6 = Hochformat bei Handy-Fotos) wird nur in-memory in die Pixel
    eingebacken und als Base64 zurückgegeben. So bleibt das Original auf der
    Platte unangetastet — der 'Bild wieder anzeigen'-Button lädt es später
    frisch über den Pfad.
    """
    if _HAT_PIL:
        try:
            from PIL import Image, ImageOps
            import io
            img = Image.open(pfad)
            # EXIF-Orientierung in die Pixel einbacken, BEVOR ggf. verkleinert
            # wird. Ohne diesen Schritt erscheint das Bild im Chat um 90°/180°
            # verdreht (der Browser kann nicht nachkorrigieren, weil das
            # Backend bewusst ohne exif-Tag speichert).
            gedreht = ImageOps.exif_transpose(img)
            geaendert = gedreht is not img
            img = gedreht
            max_dim = 2048
            if img.width > max_dim or img.height > max_dim:
                faktor = max_dim / max(img.width, img.height)
                img = img.resize(
                    (int(img.width * faktor), int(img.height * faktor)),
                    Image.LANCZOS,
                )
                geaendert = True
            # Nur bei echter Aenderung in-memory neu encodieren (vermeidet
            # unnötiges Neu-Encoden, z. B. von animierten GIFs). Die Datei
            # auf der Platte bleibt unverändert.
            if geaendert:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            logger.warning("Image-Resizing fehlgeschlagen, verwende Rohdaten: %s", e)
    # Mit oder ohne PIL: Rohdaten lesen und codieren
    with open(pfad, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def _pdf_als_text(pfad: Path) -> Optional[str]:
    """Extrahiert Text aus einer PDF-Datei (nur mit pdfminer).

    Funktioniert nur bei PDFs mit Textlayer (Scans ohne OCR
    liefern leeren Text). Für gescannte PDFs bräuchte es OCR.
    """
    if not _HAT_PDFMINER:
        logger.info("PDF-Text-Extraktion nicht verfügbar (pdfminer fehlt)")
        return "[PDF-Text-Extraktion auf diesem Gerät nicht verfügbar]"
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(pfad))
        zeilen = [z.strip() for z in text.split("\n") if z.strip()]
        text = "\n".join(zeilen)
        if len(text) > 10000:
            text = text[:10000] + "\n[…] (gekürzt)"
        return text
    except Exception as e:
        logger.warning("PDF-Text-Extraktion fehlgeschlagen: %s", e)
        return "[PDF konnte nicht gelesen werden – möglicherweise ein Scan ohne Textlayer]"


def _mime_zu_data_url(mime: str, base64_str: str) -> str:
    """Baut eine Data-URL aus MIME-Typ und Base64-Codierung."""
    return f"data:{mime};base64,{base64_str}"


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Datei hochladen (Bild oder PDF).

    Returns:
        JSON mit id, filename, url (zum Abruf), type, size, mime
    """
    if not file.content_type:
        raise HTTPException(status_code=400, detail="Datei ohne Content-Type")

    if not _ist_erlaubt(file.content_type):
        raise HTTPException(
            status_code=400,
            detail=f"Dateityp {file.content_type} nicht erlaubt. "
                   f"Erlaubt: JPEG, PNG, GIF, WebP, PDF",
        )

    # Eindeutige ID generieren, um Kollisionen zu vermeiden
    file_id = uuid.uuid4().hex[:12]
    # Dateiname bereinigen
    original_name = file.filename or "unnamed"
    # Sichere Endung aus dem Original übernehmen
    suffix = Path(original_name).suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"):
        suffix = {t: ext for t, ext in [
            ("image/jpeg", ".jpg"),
            ("image/png", ".png"),
            ("image/gif", ".gif"),
            ("image/webp", ".webp"),
            ("application/pdf", ".pdf"),
        ]}.get(file.content_type, ".bin")

    speicher_name = f"{file_id}{suffix}"
    speicher_pfad = UPLOAD_DIR / speicher_name

    try:
        content = await file.read()
        # Größenbegrenzung: 20 MB
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Datei zu groß. Maximal 20 MB erlaubt.",
            )
        with open(speicher_pfad, "wb") as f:
            f.write(content)

        typ = _datei_typ(file.content_type)

        # Für den Chat konvertieren: Bilder → Base64, PDFs → Text
        konvertiert = None
        if typ == "image":
            konvertiert = await _bild_als_base64(speicher_pfad)
        elif typ == "pdf":
            konvertiert = await _pdf_als_text(speicher_pfad)

        return {
            "id": file_id,
            "filename": original_name,
            "url": f"/api/uploads/{file_id}/{speicher_name}",
            "type": typ,
            "size": len(content),
            "mime": file.content_type,
            "konvertiert": konvertiert,
            "data_url": _mime_zu_data_url(file.content_type, konvertiert)
                if typ == "image" else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=f"Upload fehlgeschlagen: {e}")


@router.get("/uploads/{file_id}/{filename}")
async def get_upload(file_id: str, filename: str):
    """Hochgeladene Datei abrufen.

    Dient der Anzeige von Bildvorschauen im Frontend.
    """
    # Gegen Path-Traversal schützen
    if ".." in file_id or ".." in filename or "/" in file_id or "/" in filename:
        raise HTTPException(status_code=400, detail="Ungültiger Pfad")

    pfad = UPLOAD_DIR / f"{file_id}{Path(filename).suffix}"
    if not pfad.exists():
        # Auch ohne Suffix versuchen
        pfad = UPLOAD_DIR / filename
    if not pfad.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    return FileResponse(pfad)


@router.delete("/uploads/{file_id}")
async def delete_upload(file_id: str):
    """Hochgeladene Datei löschen."""
    for pfad in UPLOAD_DIR.iterdir():
        if pfad.name.startswith(file_id):
            pfad.unlink()
            return {"status": "deleted", "id": file_id}
    raise HTTPException(status_code=404, detail="Datei nicht gefunden")
