# ForenSight AI

A prototype workspace for organising investigation cases and reviewing uploaded evidence. The current implementation supports case records, evidence files, audio/video transcription with Whisper, and transcript analysis through a local Ollama model.

The interface is built with React and TypeScript. FastAPI provides the API, Socket.IO reports processing progress, and an async MySQL connection stores case and evidence records.

## Current implementation

- Create and browse cases and their associated evidence.
- Upload supported audio, video, image, and document files.
- Transcribe audio/video with Whisper's `base` model and review timestamped segments.
- Generate a structured transcript report with a selected Ollama model.
- View timelines, processing updates, and recorded activity.

YOLO detection, OCR extraction, embeddings, and vector retrieval are planned or stubbed. The checked-in Prisma schema and SQLite file are not the runtime database used by `backend/database/db.py`.

## Run locally

Use Python 3.11, Node.js 22.12+, MySQL, Ollama, and FFmpeg. Make sure `ffmpeg` is available on your PATH for transcription.

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install httpx
```

On Windows, activate with `.venv\Scripts\activate`. `httpx` is used by the analysis routes but is currently missing from `requirements.txt`.

Create a MySQL database named `forensight`. The configured database user must be able to create tables; the app creates them on startup.

Copy `.env.example` to `.env` and update the connection and model settings:

```env
DATABASE_URL=mysql://username:password@localhost:3306/forensight
STORAGE_DIR=backend/storage
CORS_ORIGINS=["http://localhost:5173"]
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
```

Prepare the local text model and keep Ollama running:

```bash
ollama pull llama3.2:1b
```

Start the API from the repository root:

```bash
uvicorn backend.main:socket_app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [localhost:5173](http://localhost:5173). API documentation is at [localhost:8000/api/docs](http://localhost:8000/api/docs). Whisper downloads its model on the first transcription.

## Code guide

| Path | Purpose |
| --- | --- |
| `backend/main.py` | FastAPI and Socket.IO entry point |
| `backend/database/db.py` | MySQL connections and table setup |
| `backend/routes/` | Cases, evidence, and transcript analysis |
| `backend/modules/whisper_processor.py` | Transcription and segment storage |
| `backend/storage/` | Local uploaded evidence |
| `frontend/src/` | Case screens, evidence viewer, timelines, and state |

From `frontend/`, use `npm run build` to create the browser bundle.

## Interpreting AI output

Transcripts and generated reports need review against the original evidence. The prototype does not establish forensic validity, infer guilt, or replace an investigator's judgment. Its database activity records are ordinary stored records, not a verified immutable audit system.

---

## CCTV Forensic Workbench (ROI inspection)

Open a video evidence item and choose **Open in Forensic Workbench** (or visit `/workbench`).

**Operator flow:** scrub / frame-step (← →) → drag a reticle over a region → **Regional Scan**.
The backend crops the exact frame region (+10 % context), applies CLAHE + unsharp mask,
letterboxes to 448×448 and sends it to a **local** vision-language model through Ollama.
The result is stored as an **Unverified Draft**; an investigator must press
**Verify & Approve for Report** before it appears in the entity graph / timeline.

| Concern | Implementation |
|---|---|
| Air-gap | `vlm_client.py` refuses any non-loopback endpoint |
| Objective lexicon | `objective_lexicon.py` rewrites "blood" → "red fluid stain", etc.; flag `objective_lexicon_compliant` |
| Chain of custody | `audit_trail` table: SHA-256 hash chain, append-only triggers, `GET /api/v1/audit/verify` |
| Raw model output | AES-256-GCM encrypted inside the audit entry (key: `AUDIT_KEY_PATH`) |
| Human-in-the-loop | edits reset verification; verify/revoke are audited |

**Setup:** `pip install -r requirements.txt`, then `ollama pull qwen2.5vl:7b`
(override with `OLLAMA_VISION_MODEL`). The Vite dev proxy targets port **8001**
(`frontend/vite.config.ts`), so run `uvicorn backend.main:socket_app --port 8001`.

**Tests:** `python -m pytest backend/tests -q` (no MySQL or Ollama needed).
