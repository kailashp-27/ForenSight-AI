"""
modules/rag/__init__.py
───────────────────────
Phase 4 — Retrieval-Augmented Generation module.

Queries the local FAISS/Chroma vector store, constructs grounded prompts,
and streams responses from the local Ollama LLM (Llama/Mistral).

Ethical guardrails are hardcoded at this layer — the LLM is never permitted
to infer guilt, suggest charges, or make legal determinations.

Stub. Implement when Phase 4 begins.
"""
