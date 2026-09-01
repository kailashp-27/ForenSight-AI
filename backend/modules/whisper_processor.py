"""
backend/modules/whisper_processor.py
──────────────────────────────────────
Real-time audio transcription using OpenAI Whisper.
Saves extracted speech segments as TextChunks to the database.
"""

import uuid
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import logging

# ── Inject ffmpeg into the current process PATH ───────────────────────────────
# winget installs to AppData; the PATH update requires a new shell session.
# We inject it directly so the backend worker can find it immediately.
_FFMPEG_CANDIDATES = [
    # winget install path
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-9.0.1-full_build" / "bin",
    # Common manual install locations
    Path("C:/ffmpeg/bin"),
    Path("C:/Program Files/ffmpeg/bin"),
    Path("C:/Program Files (x86)/ffmpeg/bin"),
]

for _candidate in _FFMPEG_CANDIDATES:
    if _candidate.exists() and (_candidate / "ffmpeg.exe").exists():
        os.environ["PATH"] = str(_candidate) + os.pathsep + os.environ.get("PATH", "")
        logging.getLogger(__name__).info(f"[Whisper] ffmpeg injected from: {_candidate}")
        break
# ──────────────────────────────────────────────────────────────────────────────

from backend.database.db import get_db

logger = logging.getLogger(__name__)

# Cache the Whisper model globally to avoid reloading on every call
_whisper_model = None


def get_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        logger.info("Loading Whisper 'base' model (this may take a moment on first run)...")
        _whisper_model = whisper.load_model("base")
        logger.info("Whisper model loaded and ready.")
    return _whisper_model


async def run_whisper_extraction(evidence_id: str, file_path: str):
    """
    Transcribes an audio/video file using OpenAI Whisper and saves the
    resulting speech segments as TextChunks in the database.

    This is a real, working transcription pipeline.
    No mock data is used — output depends entirely on the actual audio content.
    """
    logger.info(f"[Whisper] Starting transcription for evidence: {evidence_id}")

    from backend.main import sio

    db = await get_db()

    try:
        # ── Step 1: Mark evidence as TRANSCRIBING ──────────────────────────
        await db.execute(
            "UPDATE evidence SET transcription_status = 'TRANSCRIBING' WHERE id = %s",
            (evidence_id,)
        )
        await db.commit()
        await sio.emit("transcription:progress", {
            "evidence_id": evidence_id, "status": "TRANSCRIBING", "progress": 5
        })

        # ── Step 2: Load Whisper model (cached after first call) ───────────
        try:
            model = get_model()
        except Exception as e:
            logger.error(f"[Whisper] Failed to load model: {e}")
            raise RuntimeError(f"Could not load Whisper model: {e}") from e

        # ── Step 3: Run transcription in thread executor (blocking I/O) ────
        logger.info(f"[Whisper] Running model.transcribe() on: {file_path}")
        await sio.emit("transcription:progress", {
            "evidence_id": evidence_id, "status": "TRANSCRIBING", "progress": 20
        })

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(file_path, language=None, verbose=False)
        )

        logger.info(f"[Whisper] Transcription complete. Detected language: {result.get('language')}")
        await sio.emit("transcription:progress", {
            "evidence_id": evidence_id, "status": "TRANSCRIBING", "progress": 75
        })

    except Exception as e:
        logger.error(f"[Whisper] FATAL — transcription failed: {e}")
        await db.execute(
            "UPDATE evidence SET transcription_status = 'FAILED' WHERE id = %s",
            (evidence_id,)
        )
        await db.commit()
        await sio.emit("transcription:progress", {
            "evidence_id": evidence_id, "status": "FAILED", "progress": 0,
            "error": str(e)
        })
        await db.close()
        raise

    # ── Step 4: Persist segments as TextChunks ────────────────────────────
    segments = result.get("segments", [])
    full_text = result.get("text", "").strip()
    language = result.get("language", "unknown")

    try:
        # Delete any existing chunks for this evidence (re-transcription support)
        await db.execute(
            "DELETE FROM text_chunks WHERE evidence_id = %s", (evidence_id,)
        )

        inserted = 0
        for idx, segment in enumerate(segments):
            text = segment.get("text", "").strip()
            if not text:
                continue

            start = segment.get("start")
            end   = segment.get("end")
            chunk_id = uuid.uuid4().hex

            await db.execute(
                """INSERT INTO text_chunks
                   (id, chunk_index, content, source_type, start_time, end_time, evidence_id, created_at)
                   VALUES (%s, %s, %s, 'whisper', %s, %s, %s, %s)""",
                (chunk_id, idx, text, start, end, evidence_id, datetime.utcnow().isoformat())
            )
            inserted += 1

        # Update evidence record with full transcript and final status
        await db.execute(
            """UPDATE evidence
               SET transcript = %s,
                   transcription_status = 'TRANSCRIBED',
                   processed_at = %s
               WHERE id = %s""",
            (full_text, datetime.utcnow().isoformat(), evidence_id)
        )
        await db.commit()

        logger.info(f"[Whisper] Saved {inserted} text chunks. Language: {language}. Evidence: {evidence_id}")

        # ── Step 5: Emit completion + AI lead ─────────────────────────────
        await sio.emit("transcription:progress", {
            "evidence_id": evidence_id,
            "status": "TRANSCRIBED",
            "progress": 100,
            "chunk_count": inserted,
            "language": language,
        })

        # Generate an AI lead based on the transcript if any content was extracted
        if full_text:
            new_lead = {
                "id": f"L-{uuid.uuid4().hex[:6]}",
                "title": f"Audio transcript extracted — {inserted} speech segments",
                "subtitle": f"Whisper AI · {language.upper()} · {len(full_text.split())} words",
                "type": "lead",
                "risk": "medium",
                "confidence": 78,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                "aiReasoning": f"Whisper speech-to-text pipeline successfully transcribed {inserted} segments in '{language}'. Review transcript for key entities, monetary amounts, and contradictory statements.",
                "details": {
                    "Segments": str(inserted),
                    "Language": language.upper(),
                    "Words": str(len(full_text.split())),
                    "Source": "Whisper AI",
                },
                "relatedItems": [
                    {"label": "Evidence", "value": evidence_id},
                    {"label": "Pipeline", "value": "Whisper-base"},
                ]
            }
            await sio.emit("intelligence:new_lead", new_lead)

    except Exception as e:
        logger.error(f"[Whisper] Database error saving text chunks: {e}")
        await db.execute(
            "UPDATE evidence SET transcription_status = 'FAILED' WHERE id = %s",
            (evidence_id,)
        )
        await db.commit()
        await sio.emit("transcription:progress", {
            "evidence_id": evidence_id, "status": "FAILED", "progress": 0
        })
    finally:
        await db.close()

    return result
