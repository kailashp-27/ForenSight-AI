# ForenSight AI — Intelligent Evidence Investigation System

> A privacy-preserving, on-premise AI pipeline that ingests multi-modal forensic
> evidence (CCTV, audio logs, case PDFs) and assists investigators with
> explainable detections, grounded summarization, and an immutable audit trail —
> **without making autonomous legal decisions**.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11 · FastAPI · Uvicorn |
| Real-Time | Socket.io (python-socketio + socketio-client) |
| Database ORM | Prisma (PostgreSQL) |
| Frontend | React 18 · Vite · TypeScript · Tailwind CSS |
| State Management | Zustand |
| Vision (Phase 1) | YOLOv8 · Grad-CAM |
| Extraction (Phase 2) | OpenAI Whisper · Tesseract / EasyOCR |
| Embeddings (Phase 3) | Fine-tuned HuggingFace model · FAISS / Chroma |
| LLM / RAG (Phase 4) | Ollama (Llama 3 / Mistral) · LangChain |

---

## Repository Structure

```
ForenSight-AI/
├── backend/
│   ├── main.py              ← FastAPI + Socket.io entry-point
│   ├── config.py            ← Typed settings (pydantic-settings)
│   ├── database/
│   │   ├── schema.prisma    ← Relational DB schema (PostgreSQL)
│   │   └── vector_store.py  ← FAISS / Chroma abstraction layer
│   ├── modules/
│   │   ├── vision/          ← Phase 1: YOLOv8 + Grad-CAM
│   │   ├── extraction/      ← Phase 2: Whisper + OCR
│   │   ├── embeddings/      ← Phase 3: domain-specific embeddings
│   │   └── rag/             ← Phase 4: Ollama RAG pipeline
│   ├── routes/              ← FastAPI routers (cases, evidence, analysis, chat)
│   └── storage/             ← Local evidence file storage (git-ignored)
├── frontend/                ← Vite + React + TypeScript SPA
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MySQL (running locally or via Docker)
- Ollama (for Phase 4)

### 1. Backend

```bash
# Create and activate venv
python -m venv backend/.venv
# Windows:
backend\.venv\Scripts\activate
# macOS/Linux:
source backend/.venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL

# (Optional) Generate Prisma client if using Prisma ORM features in the future
prisma generate --schema=backend/database/schema.prisma

# Run the dev server (MySQL tables will be auto-created on startup)
uvicorn backend.main:socket_app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev          # Starts on http://localhost:5173
```

---

## Development Phases

| Phase | Focus | Status |
|---|---|---|
| Phase 1 | YOLOv8 detection + Grad-CAM XAI | 🔲 Pending |
| Phase 2 | Whisper transcription + OCR extraction | 🔲 Pending |
| Phase 3 | Domain embeddings + FAISS/Chroma indexing | 🔲 Pending |
| Phase 4 | Ollama RAG + cited chronological timeline | 🔲 Pending |
| Phase 5 | Pipeline integration + evaluation metrics | 🔲 Pending |

---

## Ethical Guardrails

- The blood-stain / texture classifier is trained **exclusively on synthetic data** and will never declare a definitive biological conclusion.
- The LLM assistant is hardcoded to **never infer guilt, suggest charges, or finalize legal determinations** without human verification.
- Every investigator action is immutably recorded in the `AuditLog` table.
