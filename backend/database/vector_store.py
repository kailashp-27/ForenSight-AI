"""
vector_store.py
───────────────
Thin abstraction layer over the local vector database (FAISS or Chroma).

This file is a stub for Phase 3. The interface is defined now so all other
modules can program against it without knowing which backend is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VectorStore(ABC):
    """Common interface for all vector store backends."""

    @abstractmethod
    async def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict[str, Any]]) -> None:
        """Index a batch of embedding vectors with their metadata."""
        ...

    @abstractmethod
    async def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Return the top-k most similar chunks for a query embedding."""
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Remove vectors by their IDs (e.g., when a case is deleted)."""
        ...


# ── Concrete implementations (to be filled in Phase 3) ────────────────────────

class FAISSVectorStore(VectorStore):
    """FAISS flat-index implementation. Install faiss-cpu first."""

    async def add(self, ids, embeddings, metadatas):
        raise NotImplementedError("Phase 3: implement FAISS indexing here.")

    async def search(self, query_embedding, top_k=5):
        raise NotImplementedError("Phase 3: implement FAISS search here.")

    async def delete(self, ids):
        raise NotImplementedError("Phase 3: implement FAISS deletion here.")


class ChromaVectorStore(VectorStore):
    """ChromaDB implementation. Install chromadb first."""

    async def add(self, ids, embeddings, metadatas):
        raise NotImplementedError("Phase 3: implement Chroma indexing here.")

    async def search(self, query_embedding, top_k=5):
        raise NotImplementedError("Phase 3: implement Chroma search here.")

    async def delete(self, ids):
        raise NotImplementedError("Phase 3: implement Chroma deletion here.")
