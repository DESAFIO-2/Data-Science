"""Motores de recuperação: TF-IDF Baseline (ADR-003), BM25, Tabular DCB e Hybrid RRF."""

from sus_cidadao_ds.retrieval.chroma_indexer import (
    ChromaIndexingSummary,
    ChromaSearchResult,
    ChromaVectorStoreManager,
)
from sus_cidadao_ds.retrieval.retrievers import (
    BM25Retriever,
    HybridRetriever,
    TabularDCBMatcher,
    TFIDFRetriever,
    normalize_pt_text,
)

__all__ = [
    "BM25Retriever",
    "ChromaIndexingSummary",
    "ChromaSearchResult",
    "ChromaVectorStoreManager",
    "HybridRetriever",
    "TFIDFRetriever",
    "TabularDCBMatcher",
    "normalize_pt_text",
]

