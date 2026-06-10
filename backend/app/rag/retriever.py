"""
Hybrid RAG Retriever — Dense (BGE-M3) + Reranker (BGE-Reranker-v2-m3).

Pipeline:
  Query → Normalize (Arabic) → BGE-M3 embed → ChromaDB top-K →
          BGE cross-encoder rerank → return top-N with metadata

Arabic-specific handling:
  - Alef/Ya/Ta-marbuta normalisation before embedding
  - Tashkeel (diacritics) stripped
  - ISRI stemming for BM25 tokenisation
  - BGE-M3 handles cross-lingual retrieval natively (no translation needed)
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ARABIC_QUERY_INSTRUCTION   = "Represent this question for searching relevant Arabic HR policy documents: "
ARABIC_PASSAGE_INSTRUCTION = "Represent this HR policy document passage for retrieval: "

# Tashkeel (diacritics) unicode range
_TASHKEEL_PATTERN = re.compile(r"[ً-ٰٟ]")
_TATWEEL_PATTERN  = re.compile(r"ـ+")
_WHITESPACE_CLEAN = re.compile(r"\s+")


class ArabicTextProcessor:
    """
    Arabic text normalization, diacritics removal, and BM25 tokenisation.
    All methods are pure functions — no side effects.
    """

    def __init__(self) -> None:
        from nltk.stem.isri import ISRIStemmer
        self._stemmer = ISRIStemmer()

    # ── Public API ─────────────────────────────────────────────────────────

    def normalize(self, text: str) -> str:
        """
        Full normalization pipeline:
          1. Remove tashkeel (diacritics)
          2. Normalise alef variants → ا
          3. Normalise ya variants   → ي
          4. Normalise ta marbuta    → ه
          5. Remove tatweel
          6. Collapse whitespace
        """
        if not text:
            return ""
        text = self.remove_diacritics(text)
        text = re.sub(r"[إأآ]", "ا", text)
        text = re.sub(r"[ىي]",  "ي", text)
        text = re.sub(r"ة",     "ه", text)
        text = _TATWEEL_PATTERN.sub("", text)
        text = _WHITESPACE_CLEAN.sub(" ", text)
        return text.strip()

    def remove_diacritics(self, text: str) -> str:
        """Remove Arabic tashkeel (vowel marks) from text."""
        if not text:
            return ""
        return _TASHKEEL_PATTERN.sub("", text)

    def stem(self, text: str) -> str:
        """Apply ISRI Arabic stemming."""
        words = text.split()
        return " ".join(self._stemmer.stem(w) for w in words)

    def tokenize_for_bm25(self, text: str) -> list[str]:
        """
        Normalise → stem → split into tokens for BM25 indexing / scoring.
        Returns a list of stemmed Arabic tokens.
        """
        if not text:
            return []
        normalised = self.normalize(text)
        stemmed    = self.stem(normalised)
        tokens     = [t for t in stemmed.split() if len(t) > 1]
        return tokens

    def detect_language(self, text: str) -> str:
        """Return 'ar', 'en', or 'mixed' based on character ratio."""
        arabic_chars = sum(1 for c in text if "؀" <= c <= "ۿ")
        total_chars  = max(len(text.replace(" ", "")), 1)
        ratio        = arabic_chars / total_chars
        if ratio > 0.4:
            return "ar"
        if ratio < 0.15:
            return "en"
        return "mixed"


# ── Singleton model loaders ───────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embedding_model():
    """Load BGE-M3 model once per process — cached singleton."""
    from FlagEmbedding import FlagModel

    logger.info("Loading BGE-M3 embedding model", model=settings.EMBEDDING_MODEL)
    return FlagModel(
        settings.EMBEDDING_MODEL,
        cache_dir=settings.MODELS_CACHE_DIR,
        use_fp16=True,
        devices=settings.EMBEDDING_DEVICE,
    )


@lru_cache(maxsize=1)
def _get_reranker():
    """Load BGE cross-encoder reranker once per process — cached singleton."""
    from FlagEmbedding import FlagReranker

    logger.info("Loading BGE reranker", model=settings.RERANKER_MODEL)
    return FlagReranker(
        settings.RERANKER_MODEL,
        cache_dir=settings.MODELS_CACHE_DIR,
        use_fp16=True,
    )


@lru_cache(maxsize=1)
def _get_chroma_collection():
    import chromadb
    client = chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
    )
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ── Hybrid Retriever ──────────────────────────────────────────────────────────

class HybridRetriever:
    """
    BGE-M3 dense retrieval with cross-encoder reranking.
    Optimised for Arabic HR policy documents with English cross-lingual support.
    """

    def __init__(self) -> None:
        self._processor = ArabicTextProcessor()
        self.rrf_k = 60   # Reciprocal Rank Fusion constant (standard = 60)

    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
        domain_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the most relevant handbook chunks for a query.
        Returns chunks sorted by reranker score, highest first.

        Args:
            query:         User query in Arabic or English.
            top_k:         Number of final chunks to return after reranking.
            domain_filter: Optional ChromaDB metadata filter (e.g. "leave").
        """
        if not query or not query.strip():
            return []

        normalised = self._processor.normalize(query)
        lang       = self._processor.detect_language(query)

        # BGE-M3 handles cross-lingual natively — embed with appropriate instruction
        if lang == "ar":
            query_for_embed = f"{ARABIC_QUERY_INSTRUCTION}{normalised}"
        else:
            query_for_embed = (
                f"Represent this question for searching Arabic HR policy documents: {normalised}"
            )

        candidates = await self._dense_retrieve(
            query_for_embed,
            n_results=settings.RAG_TOP_K_RETRIEVE,
            domain_filter=domain_filter,
        )

        if not candidates:
            return []

        reranked = self._rerank(query=normalised, candidates=candidates)
        return reranked[:top_k]

    async def _dense_retrieve(
        self,
        query: str,
        n_results: int,
        domain_filter: str | None,
    ) -> list[dict[str, Any]]:
        """BGE-M3 bi-encoder retrieval via ChromaDB."""
        model = _get_embedding_model()
        embedding = model.encode(
            [query],
            batch_size=1,
            instruction=ARABIC_QUERY_INSTRUCTION,
        )[0].tolist()

        collection  = _get_chroma_collection()
        total_docs  = collection.count()
        if total_docs == 0:
            logger.warning("ChromaDB collection is empty — no RAG results possible")
            return []

        where_filter: dict | None = {"domain": {"$eq": domain_filter}} if domain_filter else None

        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, total_docs),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[dict] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(
                {
                    "text":     doc,
                    "metadata": meta or {},
                    "score":    float(1.0 - dist),   # cosine distance → similarity
                    "source":   "dense",
                }
            )
        return chunks

    def _rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        BGE cross-encoder reranker — more accurate than bi-encoder similarity.
        Scores each (query, passage) pair independently.
        """
        if not candidates:
            return []

        reranker = _get_reranker()
        pairs    = [(query, c["text"]) for c in candidates]

        try:
            scores = reranker.compute_score(pairs, normalize=True)
        except Exception as exc:
            logger.warning("Reranker failed — falling back to bi-encoder scores", error=str(exc))
            for c in candidates:
                c["rerank_score"] = c.get("score", 0.0)
            return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        for chunk, score in zip(candidates, scores):
            chunk["rerank_score"] = float(score)

        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
