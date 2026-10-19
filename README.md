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


---

## Automatic investigation board

Open a case and choose **Investigation board** (`/cases/<id>/investigation`), then **Run automatic analysis**.
Uploads are also analysed automatically after ingestion.

| Evidence | What is extracted automatically |
|---|---|
| Video | frames sampled across the whole clip -> YOLOv8 objects (+ colour), EasyOCR on vehicle crops and full frames |
| Image | YOLOv8 objects, EasyOCR text, EXIF GPS + capture time |
| PDF / transcript | text per page / segment -> plates, phones, e-mails, amounts, alphanumeric IDs |

Clues that appear in **two or more** evidence items are linked and explained
(`EXACT`, `OCR_VARIANT`, `FUZZY`, weak `APPEARANCE`). The board shows the matches,
a map (EXIF GPS or manual location), an evidence<->clue graph and a printable HTML
report (Download / Print to PDF). Open any file's **Clues** tab to see which of its
clues also occur elsewhere; matching boxes are highlighted on images.

Notes:
- YOLOv8n and EasyOCR are **pre-trained** checkpoints (COCO / English); they are not fine-tuned on forensic data. Weights download once to `backend/storage/models/`.
- Everything automatic is **unverified**; reports separate verified findings from machine observations. Appearance-only matches are weak and never imply the same object or person.
- Map tiles need internet unless `VITE_MAP_TILE_URL` points at an on-prem tile server. `VITE_API_TARGET` overrides the Vite proxy target.
- Tests: `python -m pytest backend/tests -q`.


---

## Video analysis v2 (tracking, voting, review loop)

The default video analyser is `backend/modules/video_pipeline.py`:

1. **Detect + track** (YOLOv8 + ByteTrack, ~3 fps). One physical object = one track, so a scene with
   4 people yields 4 detections, not hundreds of per-frame boxes.
2. **Open-vocabulary classes** (YOLO-World, no training): `license plate, knife, crowbar, hammer, backpack,
   duffel bag, helmet, face mask, gloves, gun` (edit `OPEN_VOCAB_CLASSES`). Sharp-edged items are reported
   as shapes ("knife-shaped metallic object"), never as weapons.
3. **Best crops**: each track keeps its sharpest/largest crops; class and colour are voted over the track.
4. **OCR ensemble** (EasyOCR + RapidOCR, GPU when available) on vehicle/plate crops and on the sharpest frames
   of each 1 s window.
5. **Plate consolidation**: reads of the same plate are clustered, format-corrected (Indian `LL DD L{1,3} DDDD`
   and UK formats, valid state codes) and confidence-voted. The clue records the reads it came from.

### Measure it (don't trust it)

```bash
python -m backend.tools.benchmark_video --clips 16 --seed 21 --image people.jpg
python -m backend.tools.benchmark_video --clips 16 --seed 5 --hard      # much harsher degradation
python -m backend.tools.benchmark_video --videos DIR --truth truth.json # YOUR labelled clips
```

Synthetic clips only approximate real CCTV: use your own labelled footage for real numbers.

### Review -> fine-tune loop

Investigation board -> **Review detections**: confirm / reject / relabel. Rejected items leave the clue set and
report. Decisions are the training labels:

```bash
python -m backend.training.cli export --out data/yolo_case --case <case_id>
python -m backend.training.cli train  --data data/yolo_case/data.yaml --epochs 40
# then set YOLO_MODEL=<printed path> in .env and restart; re-run the benchmark before switching
```

Fine-tuning needs hundreds of reviewed boxes covering ALL classes you care about; a narrow dataset makes the
model forget the rest. First run downloads: yolov8s (22 MB), YOLO-World (~50 MB) and CLIP (~340 MB), then offline.


---

## One clue pool: speech, documents and regional scans

Every evidence item feeds the **same** clue pool, derived at read time so nothing goes stale:

| Source | What becomes a clue |
|---|---|
| Speech transcripts (Whisper) | plates, phones, e-mails, IDs, **names**, **object descriptions** ("white van", "black backpack") |
| PDF text, and **OCR of scanned/photographed pages** | same as above |
| Regional scans (VLM) | the object label, visible text, and names/objects in the model's notes |
| Video / photo analysis | tracked objects, plates (voted), on-screen text, EXIF |

Investigation board tabs: **Matching clues**, **All clues** (click "Clues extracted"; filter by type/source,
see which clues are shared), **Transcripts & text** (every passage, clues highlighted, amber where the same
clue appears in other evidence), Review detections, Map, Graph, Report.

Matching notes: names and free text are rated at most MEDIUM; appearance-only matches are WEAK; a vehicle
mentioned in speech without a colour is not matched (a bare "car" would match every car).

The dashboard **Intelligence Strip** is live: Leads = strongest shared clues across cases, Gaps = concrete
unfinished/missing items, Activity = recent custody-log entries. There are no hypotheses or hard-coded items.

**Keywords, dates and numbers.** Beyond plates, names and objects, every meaningful word in a transcript, PDF or scan note becomes a KEYWORD clue (filler words are dropped using a word-frequency table); dates are normalised (`11/10/2026` = `11 October 2026`) and long digit strings become NUMBER clues. Shared keywords are listed in their own section of **Matching clues**; they are always rated WEAK because ordinary words can coincide by chance, while shared dates and numbers are MEDIUM.

**Identifier matching.** Plates, camera/serial IDs and scan readouts are compared as one family, so a partly read plate from a regional scan (`TX-88-2`) links to the full plate in a PDF (`Plate: Tx-882-V`). A reading is linked when it is identical, differs only by OCR confusions, is within 1-2 character edits, or is contained in the other (`RACK04` in `Server Rack #04`; shown as a PARTIAL match). A word such as "plate" or "registration" before an identifier marks it as a plate even when its shape is unusual. Scene-OCR near-duplicates are clustered and voted into one clue. Re-run automatic analysis on an existing video to apply the consolidation to its stored OCR clues.

---

## Key findings and event timeline

**Chat / message exports** (Slack JSON, WhatsApp-style `.txt`, `.csv`, logs) can be uploaded as evidence. Each message keeps its
author and time; authors become NAME clues, so a chat user `j.vance` links to a badge reading `J.VANCE`.

**Key findings** tab: *Victim & suspects* (name, role, photo), *IDs & badges*, *Tools / weapons / stolen items*, *Vehicle & number
plate*, each with the supporting observations from other evidence. When you verify a regional scan you can give it a **role**
(suspect, victim, stolen item, weapon, plate, ID...) and a **name**; investigator-assigned roles always outrank automatic
text cues, and verified findings become clues that the rest of the case is searched for.

**Event timeline** tab: chat messages, times mentioned in text ("window at 1:00 AM"), speech and video frames on one clock.
A video's real start time is read from its burned-in overlay (needs >= 2 consistent frames) or set with
`PUT /api/v1/evidence/{id}/recording-start`. Events that are close in time and share a place, person, plate or ID are grouped;
events with no time are attached only through such a shared term and marked as linked by content. Times without a date are
placed on the case's most common date and flagged as assumed.

---

## People involved: the investigator chooses who is who

The **People** tab lists everyone named, badged or carded in the evidence: names in speech, documents and chat, chat
authors, and badge / ID-card / visitor-pass readings (an ID with no name beside it appears as "Holder of ..."). For each
person you can choose **Victim, Suspect, Person of interest, Witness, Cleared** or **Guilty**, merge two entries ("same
person as..."), attach a badge/ID to a person, or add someone by hand.

- Roles are the **investigator's designations**: saved with your operator ID and time, written to the tamper-evident
  custody log, and shown in the report with who set them.
- The system only *suggests* victim / suspect / witness from a nearby word (shown as a suggestion with its reason).
  It never suggests or sets guilt.
- **Guilty** is deliberately hard to set: explicit confirmation plus a written basis (>= 20 characters). The report
  labels it "Guilty (investigator's determination)" and states it is not a finding of the system or a legal verdict.
- Names you merge or IDs you attach are remembered as aliases, so later matching across evidence uses them.

API: `GET /api/v1/cases/{id}/people`, `PUT|DELETE /api/v1/cases/{id}/people/{key}`, `POST .../people`,
`POST .../people/{key}/aliases`.


## Citizen register

A reference database of people (fictional test data, `backend/seed/citizens.xlsx`). The `citizens` and
`citizen_links` tables are created on first start and the register is seeded when empty.

- **Page:** `/citizens` lists everyone with search (name, ID, phone, address, occupation, record) and filters.
  Click a person for their file: all details, a placeholder photo (upload a real one later for matching) and the cases they are linked to.
- **Linking:** people in a case's People tab are matched to the register by name, initials and phone number.
  A match is only a **suggestion** until an investigator clicks "This is them" (audited). Identical names stay ambiguous.
- **Repeat people:** when one citizen is linked to two or more cases (confirmed, or a likely suggestion), an alert shows in the
  header bell, the Intelligence Strip, the People tab and the citizen's file.
