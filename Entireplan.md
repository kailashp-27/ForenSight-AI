Here is a detailed project outline and methodological approach for the "ForenSight AI: Intelligent Evidence Investigation System". Your background in full-stack web applications, database management systems, and artificial intelligence training will translate perfectly into building the on-premise architecture, particularly when connecting the local vector stores to the LLM backend.

### Phase 1: Vision and Explainability (Stage 1)

* **Object Detection:** Fine-tune the YOLOv8 model to detect specific evidence objects, such as weapons, vehicles, or persons of interest, across images and CCTV frames.


* **Explainable AI (XAI):** Integrate Grad-CAM to generate visual saliency heatmaps alongside the YOLOv8 detections. This will explicitly show why an object was flagged in a frame, directly addressing the "black-box" trust gap often found in legal AI.


* **Visual Guardrails:** Train a secondary custom classifier to detect non-conclusive stain-like texture and color patterns. Ensure this classifier is trained strictly on synthetic or surrogate data and designed so it never declares a definitive biological conclusion.



### Phase 2: Data Extraction (Stage 2)

* **Text Processing:** Implement Optical Character Recognition (OCR) to extract data and convert multi-modal files, such as case PDFs, into standardized text chunks.


* **Audio Processing:** Utilize Whisper to transcribe audio logs into text, helping to break down massive evidence overload.



### Phase 3: Domain-Specific Retrieval (Stage 3)

* **Custom Embeddings:** Replace generic off-the-shelf text vectors by fine-tuning an open-source embedding model specifically on investigative and forensic terminology.


* **Local Vector Database:** Index all the standardized text chunks and object metadata into a local FAISS or Chroma vector database to ensure high-accuracy semantic search. Keeping this on-premise ensures sensitive forensic data is never exposed to external cloud APIs.



### Phase 4: Grounded Summarization (Stage 4)

* **Localized LLM Deployment:** Deploy a localized Ollama LLM, such as Llama or Mistral, to handle chronological case summarization.


* **Retrieval-Augmented Generation (RAG):** Query the local vector store to synthesize the cross-modal evidence into an explainable, cited master timeline.


* **Evidence Mapping:** Hardcode the LLM assistant to map every summary claim back to exact source evidence IDs, document lines, and Grad-CAM timestamps.


* **Ethical Boundaries:** Restrict the LLM to factual generation so the system acts purely as an assistive tool that never infers guilt, suggests charges, makes legal determinations, or finalizes reports without human verification.



### Phase 5: Pipeline Integration and Evaluation

* **System Integration:** Bridge the computer vision and natural language processing components into a fully self-hosted pipeline that runs entirely on-premise.


* **Performance Review:** Evaluate the three fine-tuned models—YOLOv8, the embedding model, and the stain-like texture classifier—using quantifiable metrics to ensure the system is production-ready.

Here is the recommended language stack for your architecture:

1. Python (The AI & Data Pipeline Core)
Python is absolutely essential for the backend machine learning and data processing stages. The entire ecosystem for your proposed methodology revolves around it.

Computer Vision (Stage 1): Training and running inference with YOLOv8, as well as generating Grad-CAM heatmaps, are natively supported and documented in Python.

Audio & Text Extraction (Stage 2): OpenAI's Whisper and popular OCR libraries (like Tesseract or EasyOCR) have primary Python APIs.

RAG & Vector Stores (Stage 3 & 4): Interfacing with FAISS or Chroma, fine-tuning embedding models (using HuggingFace), and connecting your localized Ollama LLM are best orchestrated using Python frameworks like LangChain or LlamaIndex.

2. JavaScript / TypeScript (The Full-Stack Application Layer)
To build the actual self-hosted interface where investigators will interact with the system, JavaScript or TypeScript using a Node.js environment is ideal.

Real-Time Processing: You can implement real-time processing updates (e.g., live CCTV analysis feeds or progress bars on document parsing) using WebSockets and Socket.io.

System Integration: A Node.js backend can serve as the API gateway, handling user authentication and file uploads, and then passing the heavy lifting off to your Python microservices.

3. SQL (Relational Database Management)
While FAISS/Chroma will handle the semantic vector searches, you will still need a robust relational database management system to handle standard application data (user accounts, case metadata, strict audit logs, and evidence ID mapping).

Data Modeling: You can efficiently manage these relationships using an ORM like Prisma.

Custom Logic: For complex audit trails or automated logging of user queries (to maintain those ethical guardrails), you can utilize SQL triggers and stored procedures.

Here is the comprehensive master blueprint for the **ForenSight AI** project. This document synthesizes the entire architectural plan, tech stack, and methodology into a structured format perfectly suited for a coding agent to use as a primary reference guide.

---

# ForenSight AI: Master Architecture & Implementation Blueprint

**Architecture Style:** Unified Monolithic Application (Python Backend + Bundled React Frontend)

---

## 1. Core Project Objectives & Novelties

The system is a privacy-preserving, on-premise pipeline designed to ingest multi-modal evidence and assist investigators without making autonomous legal decisions. The agent must implement the following core novelties:

* **End-to-End Explainability (XAI):** Pair YOLOv8 detections with Grad-CAM visual heatmaps to show exactly why an object was flagged. Map LLM text generation claims back to exact source evidence IDs and timestamps.


* **Domain-Specific Embeddings:** Fine-tune an open-source embedding model on investigative terminology to improve RAG accuracy over generic off-the-shelf vectors.


* **Strict Ethical Guardrails:** Train the blood-stain classifier strictly on synthetic data to flag non-conclusive textures, never declaring a definitive biological conclusion. Hardcode the LLM to never infer guilt, suggest charges, or finalize legal determinations.



---

## 2. Comprehensive Technology Stack

### Application & AI Backend

* **Core Framework:** Python with FastAPI (for asynchronous API routes and background task management).
* **Vision Models:** Fine-tuned YOLOv8 for object detection and a custom synthetic-data classifier for texture analysis.


* **Audio & Text Extraction:** Whisper for audio transcription and OCR for document parsing.


* **Generative AI & RAG:** Localized Ollama (Llama/Mistral) combined with FAISS or Chroma for the vector database.



### Dedicated Frontend

* **Core Framework:** React compiled via Vite (TypeScript), served statically through the FastAPI monolith.
* **Styling & UI:** Tailwind CSS with shadcn/ui for a clean, professional investigative dashboard interface.
* **State Management:** Zustand for lightweight, cross-component synchronization (e.g., matching the LLM chat timeline with the active video player frame).

### Database Management & Real-Time Sync

* **Relational Database:** PostgreSQL managed via the Prisma ORM for highly structured case metadata, user accounts, and strict audit logs.
* **Real-Time Communication:** Socket.io implementation bridging the Python backend and React frontend to stream live progress bars during heavy file processing.

---

## 3. Directory & Repository Structure

The coding agent should adhere to the following single-repository modular structure:

```text
ForenSight-AI/
├── backend/                     
│   ├── main.py                  
│   ├── config.py                
│   ├── database/                
│   │   ├── schema.prisma        
│   │   └── vector_store.py      
│   ├── modules/                 
│   │   ├── vision/              
│   │   ├── extraction/          
│   │   ├── embeddings/          
│   │   └── rag/                 
│   ├── routes/                  
│   └── storage/                 
│
├── frontend/                    
│   ├── package.json
│   ├── src/
│   │   ├── components/          
│   │   ├── pages/               
│   │   ├── store/               
│   │   └── services/            
│
├── requirements.txt
└── README.md

```

---

## 4. Execution Workflow & Implementation Phases

**Phase 1: Ingestion & Asynchronous Processing**

* Create a FastAPI route to accept large file uploads (CCTV, Audio, PDFs).


* Save the file to local storage and generate a relational database entry using Prisma.
* Trigger a FastAPI `BackgroundTasks` job to prevent blocking the event loop.
* Emit Socket.io events to the React frontend to update the investigator on the processing status.

**Phase 2: The AI Processing Pipeline**

* Route video/images through YOLOv8 to detect evidence objects.


* Generate Grad-CAM heatmaps and save them as static assets.


* Run the synthetic-data trained classifier on localized image patches for texture flagging.


* Route audio through Whisper and PDFs through OCR to generate standardized text chunks.



**Phase 3: Vector Indexing & RAG Retrieval**

* Pass the extracted text chunks through the fine-tuned domain-specific embedding model.


* Store the resulting vectors and their metadata (timestamps, file IDs) in the local FAISS or Chroma instance.


* Expose an LLM chat endpoint where the localized Ollama model queries the vector store to synthesize chronological timelines.



**Phase 4: Frontend Visualization**

* Build a dedicated dashboard using React and Tailwind CSS.
* Implement a synchronized media viewer that highlights Grad-CAM overlays or specific document lines when the investigator clicks the corresponding citation in the Ollama-generated summary.