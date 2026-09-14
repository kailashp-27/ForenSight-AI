"""
backend/routes/analysis.py
──────────────────────────
Forensic AI Analysis routes powered by local Ollama.
"""

import json
import logging
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import settings
from backend.database.db import get_db, write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    model: Optional[str] = None
    custom_instructions: Optional[str] = None


@router.get("/models")
async def list_models():
    """Discover available local Ollama models — only those capable of text completion."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                # Filter: only include models with 'completion' capability (exclude embedding-only models)
                completion_models = [
                    m.get("name") for m in data.get("models", [])
                    if "completion" in (m.get("capabilities") or ["completion"])
                ]
                if not completion_models:
                    # Fallback: include all if capabilities field is missing (older Ollama versions)
                    completion_models = [m.get("name") for m in data.get("models", [])]
                
                # Prefer the configured default if it's in the list
                default = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL in completion_models else (completion_models[0] if completion_models else settings.OLLAMA_MODEL)
                return {"models": completion_models, "default": default}
    except Exception as e:
        logger.warning(f"Failed to query Ollama tags: {e}")
    
    return {"models": [settings.OLLAMA_MODEL], "default": settings.OLLAMA_MODEL}


@router.post("/evidence/{evidence_id}")
async def analyze_evidence(evidence_id: str, payload: AnalyzeRequest = AnalyzeRequest(), request: Request = None):
    """
    Perform forensic AI analysis on evidence transcript/data using Ollama LLM.
    """
    db = await get_db()
    try:
        # Fetch evidence record
        row = await db.execute("SELECT * FROM evidence WHERE id = %s", (evidence_id,))
        evidence = dict(await row.fetchone() or {})
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")

        # Fetch case record
        case_row = await db.execute("SELECT * FROM cases WHERE id = %s", (evidence["case_id"],))
        case = dict(await case_row.fetchone() or {})

        # Fetch text chunks
        chunk_cursor = await db.execute(
            "SELECT * FROM text_chunks WHERE evidence_id = %s ORDER BY chunk_index",
            (evidence_id,),
        )
        chunks = [dict(r) for r in await chunk_cursor.fetchall()]
    finally:
        await db.close()

    # Build context transcript — safe string formatting regardless of DB type
    def _fmt_time(val):
        try:
            return f"{float(val):.1f}s"
        except (TypeError, ValueError):
            return "0.0s"

    if chunks:
        transcript_lines = []
        for c in chunks:
            ts = f"[{_fmt_time(c.get('start_time'))} - {_fmt_time(c.get('end_time'))}]"
            transcript_lines.append(f"{ts} {c.get('content', '').strip()}")
        transcript_text = "\n".join(transcript_lines)
    elif evidence.get("transcript"):
        transcript_text = evidence["transcript"]
    else:
        transcript_text = None

    case_title       = case.get('title', 'Unknown Case')
    case_number      = case.get('case_number', 'N/A')
    case_description = case.get('description') or 'No description provided.'
    evidence_name    = evidence.get('file_name', 'Unknown File')
    evidence_type    = evidence.get('file_type', 'UNKNOWN')

    if transcript_text:
        user_message = f"""You are a forensic AI analyst. Analyze the following audio transcript from a criminal investigation and produce a structured intelligence report.

CASE INFORMATION:
- Case Number: {case_number}
- Case Title: {case_title}
- Case Description: {case_description}

EVIDENCE FILE: {evidence_name} (Type: {evidence_type})

WHISPER TRANSCRIPT (with timestamps):
{transcript_text}

Provide a professional, factual Markdown report with exactly these headings. Base your analysis ONLY on what is actually said in the transcript above. Do not invent details not present in the transcript.

### 🔍 Executive Forensic Summary
Summarize what was actually discussed in the recording.

### 💰 Financial & Key Entity Mentions
List any amounts, names, account numbers, locations, or dates explicitly mentioned.

### ⚠️ Inconsistencies & Investigative Red Flags
Identify contradictions, suspicious instructions, or unusual patterns in the dialogue.

### 🔗 Relevance to Case: {case_title}
How does this recording relate to the case described above?

### 📋 Recommended Next Steps
List concrete investigative actions the analyst should take based on this transcript.

### 🚨 Risk Assessment
Explicitly state: "RISK_LEVEL: [HIGH, MEDIUM, or LOW]" followed by a 1-sentence justification. Base this on actual suspicious activity found in the transcript (do not mark HIGH just because the case is about fraud, only if the transcript contains suspicious activity)."""
    else:
        user_message = f"""You are a forensic AI analyst. A {evidence_type} file named '{evidence_name}' has been submitted for case '{case_title}' ({case_number}).

Case Description: {case_description}

The Whisper transcription pipeline has not yet produced a transcript for this file. Provide a brief analysis note explaining:
1. That no transcript is available yet.
2. What the investigator should do next (re-run Whisper transcription).
3. What forensic value this type of file ({evidence_type}) typically provides.

Be brief and professional."""

    chosen_model = payload.model or settings.OLLAMA_MODEL
    analysis_text = ""
    risk_level = "MEDIUM"
    ollama_error = None

    # Call Ollama using /api/chat (instruction-following messages format)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            ollama_payload = {
                "model": chosen_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional forensic intelligence analyst. You produce factual, structured Markdown reports based strictly on provided evidence. Never fabricate facts not present in the source material."
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 1200,
                    "top_p": 0.9,
                }
            }
            res = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=ollama_payload)
            if res.status_code == 200:
                data = res.json()
                raw_response = data.get("message", {}).get("content", "").strip()
                if raw_response and len(raw_response) > 50:
                    analysis_text = raw_response
                    # Parse risk level from response if present
                    import re
                    match = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW)", analysis_text, re.IGNORECASE)
                    if match:
                        risk_level = match.group(1).upper()
                    else:
                        # Fallback heuristic avoiding case description words
                        if any(kw in analysis_text.lower() for kw in ["structuring", "smurfing", "bribe", "laundering", "covert", "destroy evidence"]):
                            risk_level = "HIGH"
                        elif "suspicious" in analysis_text.lower():
                            risk_level = "MEDIUM"
                        else:
                            risk_level = "LOW"
                else:
                    ollama_error = f"Ollama returned empty or too-short response (status {res.status_code})"
                    logger.warning(ollama_error)
            else:
                ollama_error = f"Ollama HTTP {res.status_code}: {res.text[:200]}"
                logger.warning(ollama_error)
    except Exception as e:
        ollama_error = str(e)
        logger.warning(f"Ollama call failed or timed out: {e}")

    # Honest fallback — do NOT fabricate fake data
    if not analysis_text:
        no_transcript_note = "" if transcript_text else "\n\n> ⚠️ **Note:** No Whisper transcript has been generated yet. Please click 'Generate Whisper Transcript' first, then re-run this analysis."
        analysis_text = f"""### ⚠️ Ollama Analysis Unavailable

Could not generate AI analysis at this time.

**Reason:** {ollama_error or 'Unknown error'}

**Model Attempted:** `{chosen_model}`
**Evidence:** `{evidence_name}`
**Case:** {case_number} — {case_title}{no_transcript_note}

**What to check:**
- Is Ollama running? (`ollama serve`)
- Is `{chosen_model}` installed? (`ollama pull {chosen_model}`)
- Does this model support text completion (not just embeddings)?
- Is there a Whisper transcript? (Check 'Whisper Transcript' tab)
"""

    # Audit log
    await write_audit_log(
        action="AI_TRANSCRIPT_ANALYSIS",
        case_id=evidence.get("case_id"),
        metadata={
            "evidence_id": evidence_id,
            "model": chosen_model,
            "transcript_length": len(transcript_text) if transcript_text else 0,
        },
        ip_address=request.client.host if request and request.client else None,
    )

    return {
        "evidence_id": evidence_id,
        "model_used": chosen_model,
        "risk_level": risk_level,
        "analysis": analysis_text,
        "timestamp": evidence.get("uploaded_at"),
    }
