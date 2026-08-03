"""
Router: POST /api/transcribe – Spracheingabe via OpenRouter Whisper + Glättung

Verhalten (exakt wie TypeFREE):
  1. Nimmt WAV/WebM-Audio entgegen
  2. Sendet an OpenRouter Whisper (openai/whisper-large-v3)
  3. Glättet Text (Füllwörter entfernen) via Gemini Flash
  4. Gibt bereinigten Text zurück

Sicherheit:
  - Maximale Dateigröße: 25 MB (DoS-Schutz)
  - Timeout: 30 Sekunden pro API-Call
  - Fehlerbehandlung: try-except mit HTTP 502
  - Kein API-Key im Request
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["transcribe"])

# Maximale Upload-Größe: 25 MB (DoS-Schutz, wie von /critic gefordert)
MAX_FILE_SIZE = 25 * 1024 * 1024


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Nimmt eine Audio-Datei entgegen, transkribiert sie via OpenRouter Whisper
    und glättet den Text (Füllwörter entfernen).

    Rückgabe: {"text": "bereinigter Text"} oder {"text": null, "error": "..."}
    """
    # ── 1. Dateigröße prüfen (🔴 /critic Befund #1) ─────────────────────────
    content_length = 0
    chunk_size = 8192
    audio_chunks = []

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content_length += len(chunk)
        # /critic Befund #3: Prüfung VOR dem append, nicht danach
        if content_length > MAX_FILE_SIZE:
            logger.warning("Upload abgelehnt: Datei zu groß (%d Bytes)", content_length)
            raise HTTPException(
                status_code=413,
                detail=f"Datei zu groß. Maximum: {MAX_FILE_SIZE // (1024*1024)} MB",
            )
        audio_chunks.append(chunk)

    audio_bytes = b"".join(audio_chunks)
    logger.info("Audio empfangen: %s, %d Bytes", file.filename or "unbenannt", len(audio_bytes))

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Leere Audio-Datei")

    # ── 2. Whisper-Transkription ────────────────────────────────────────────
    try:
        raw_text = llm_service.transcribe(audio_bytes)
    except Exception as e:
        logger.exception("Whisper-Transkription fehlgeschlagen")
        raise HTTPException(
            status_code=502,
            detail=f"Transkription fehlgeschlagen: {str(e)}",
        )

    # /critic Befund #4: explizit auf None prüfen
    if raw_text is None:
        logger.warning("Whisper-Transkription fehlgeschlagen (None)")
        return {"text": None, "error": "Transkription fehlgeschlagen"}

    if not raw_text.strip():
        logger.warning("Whisper lieferte leeren Text")
        return {"text": None, "error": "Keine Sprache erkannt"}

    logger.info("Transkribiert (%d Zeichen): %s", len(raw_text), raw_text[:100])

    # ── 3. Text-Glättung (Füllwörter entfernen, wie TypeFREE) ──────────────
    try:
        polished = llm_service.polish_text(raw_text)
    except Exception as e:
        logger.exception("Text-Glättung fehlgeschlagen – Rohtext wird verwendet")
        polished = None

    final_text = polished if polished else raw_text
    logger.info("Geglättet (%d Zeichen): %s", len(final_text), final_text[:100])

    return {"text": final_text}