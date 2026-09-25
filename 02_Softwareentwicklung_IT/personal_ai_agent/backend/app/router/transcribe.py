"""
Router: Spracheingabe – POST /api/sprache/transkript (kanonisch) und
POST /api/transcribe (älterer Pfad, bleibt gültig)

Verhalten (exakt wie TypeFREE):
  1. Nimmt WAV/WebM-Audio entgegen
  2. Sendet an OpenRouter (Modellkette: mai-transcribe-1.5 → whisper-large-v3)
  3. Glättet Text (Füllwörter entfernen) über POLISH_MODELS
  4. Gibt bereinigten Text zurück

Zwei Pfade, EINE Umsetzung: Der kanonische Weg ist der aus der Roadmap
zugesagte `/api/sprache/transkript` (D3). `/api/transcribe` war der erste
Name und wird weiter bedient, damit ältere Aufrufer nicht brechen. Beide
landen in `transcribe_audio()` — es gibt keine zweite Kopie der Logik.

Sicherheit:
  - Maximale Dateigröße: 25 MB (DoS-Schutz)
  - Timeout: 30 Sekunden pro API-Call
  - Fehlerbehandlung: try-except mit HTTP 502
  - Kein API-Key im Request
  - Audio lebt NUR im Speicher (kein tempfile, kein Schreiben auf Platte)
    und wird nach der Transkription verworfen
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
    Nimmt eine Audio-Datei entgegen, transkribiert sie über die OpenRouter-Kette
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


@router.post("/sprache/transkript")
async def sprache_transkript(file: UploadFile = File(...)):
    """Kanonischer Sprachweg: POST /api/sprache/transkript (Roadmap D3).

    Gleiche Strecke wie `/api/transcribe` — dieselbe Funktion, kein zweiter
    Codepfad. Der Name ist der, den die Roadmap dem Frontend zusagt
    („Audio → Backend (`POST /api/sprache/transkript`) → Kette → Glättung").

    Datenschutz: Das Audio wird hier nur im Speicher gehalten und nach der
    Transkription verworfen; es geht ausschließlich an OpenRouter — denselben
    Empfänger, den auch der Text-Chat nutzt. Kein weiterer Anbieter.
    """
    return await transcribe_audio(file)