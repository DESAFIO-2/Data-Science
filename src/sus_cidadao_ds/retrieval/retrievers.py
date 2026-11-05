"""Implementação determinística de TF-IDF (ADR-003), BM25, Tabular DCB e Hybrid Retriever (RRF)."""

from __future__ import annotations

from collections import Counter
import math
import re
import unicodedata

from sus_cidadao_ds.contracts.schemas import (
    CanonicalMedication,
    NormativeChunk,
    RetrievalHit,
)

_PT_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "esta",
        "este",
        "meu",
        "minha",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "onde",
        "os",
        "ou",
        "para",
        "pela",
        "pelas",
        "pelo",
        "pelos",
        "por",
        "qual",
        "que",
        "se",
        "sem",
        "ser",
        "seu",
        "sua",
        "um",
        "uma",
    }
)


def normalize_pt_text(text: str) -> str:
    """Remove acentuação, converte para minúsculas e normaliza espaços."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-z0-9\s/]", " ", without_accents)
    return " ".join(cleaned.split())


def tokenize_with_ngrams(text: str, max_ngram: int = 2) -> list[str]:
    """Tokeniza texto normalizado removendo stopwords e gerando n-gramas (1..max_ngram)."""
    norm = normalize_pt_text(text)
    base_tokens = [
        tok for tok in norm.split() if len(tok) > 1 and tok not in _PT_STOPWORDS
    ]
    tokens = list(base_tokens)
    if max_ngram >= 2 and len(base_tokens) >= 2:
        for idx in range(len(base_tokens) - 1):
            tokens.append(f"{base_tokens[idx]}_{base_tokens[idx + 1]}")
    return tokens


class TFIDFRetriever:
    """Linha de base TF-IDF determinística compatível com ADR-003 da Engenharia de Dados."""

    def __init__(self, chunks: list[NormativeChunk], max_ngram: int = 2) -> None:
        self.chunks = chunks
        self.max_ngram = max_ngram
        self.idf: dict[str, float] = {}
        self.doc_vectors: list[dict[str, float]] = []
        self._build_index()

    def _build_index(self) -> None:
        n_docs = len(self.chunks)
        if n_docs == 0:
            return
        doc_tokens_list: list[list[str]] = []
        df_counter: Counter[str] = Counter()

        for chunk in self.chunks:
            composite_text = (
                f"{chunk.document_title} {chunk.section} {chunk.text} "
                f"{' '.join(chunk.dcb_mentions)}"
            )
            tokens = tokenize_with_ngrams(composite_text, self.max_ngram)
            doc_tokens_list.append(tokens)
            for unique_tok in set(tokens):
                df_counter[unique_tok] += 1

        self.idf = {
            term: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
            for term, df in df_counter.items()
        }

        for tokens in doc_tokens_list:
            vec = self._vectorize(tokens)
            self.doc_vectors.append(vec)

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        tf_counts = Counter(tokens)
        raw_weights: dict[str, float] = {}
        for term, count in tf_counts.items():
            if term in self.idf:
                sublinear_tf = 1.0 + math.log(count)
                raw_weights[term] = sublinear_tf * self.idf[term]
        norm = math.sqrt(sum(w * w for w in raw_weights.values()))
        if norm == 0.0:
            return {}
        return {term: weight / norm for term, weight in raw_weights.items()}

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.12,
    ) -> list[RetrievalHit]:
        """Consulta cosseno TF-IDF com abstenção controlada por `min_score`."""
        q_tokens = tokenize_with_ngrams(query, self.max_ngram)
        q_vec = self._vectorize(q_tokens)
        if not q_vec:
            return []

        scored: list[tuple[float, NormativeChunk]] = []
        for chunk, d_vec in zip(self.chunks, self.doc_vectors, strict=True):
            dot = sum(
                q_weight * d_vec.get(term, 0.0) for term, q_weight in q_vec.items()
            )
            if dot >= min_score:
                scored.append((dot, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalHit(
                chunk_id=chunk.chunk_id,
                score=round(score, 4),
                source_id=chunk.source_id,
                document_title=chunk.document_title,
                section=chunk.section,
                page_number=chunk.page_number,
                route_category=chunk.route_category,
                text=chunk.text,
                matched_dcb=None,
                retriever_name="tfidf_baseline",
            )
            for score, chunk in scored[:top_k]
        ]


class BM25Retriever:
    """Recuperador probabilístico Okapi BM25 com normalização de escore para [0, 1]."""

    def __init__(
        self,
        chunks: list[NormativeChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_freqs: list[Counter[str]] = []
        self.doc_lens: list[int] = []
        self.avgdl: float = 1.0
        self.idf: dict[str, float] = {}
        self._build_index()

    def _build_index(self) -> None:
        n_docs = len(self.chunks)
        if n_docs == 0:
            return
        df_counter: Counter[str] = Counter()
        for chunk in self.chunks:
            composite_text = (
                f"{chunk.document_title} {chunk.section} {chunk.text} "
                f"{' '.join(chunk.dcb_mentions)}"
            )
            tokens = tokenize_with_ngrams(composite_text, max_ngram=1)
            counts = Counter(tokens)
            self.doc_freqs.append(counts)
            self.doc_lens.append(len(tokens))
            for tok in counts:
                df_counter[tok] += 1

        self.avgdl = sum(self.doc_lens) / n_docs if n_docs else 1.0
        self.idf = {
            term: math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for term, df in df_counter.items()
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.15,
    ) -> list[RetrievalHit]:
        """Consulta BM25 com escore saturado em [0, 1] via $s / (s + 4)$."""
        q_tokens = tokenize_with_ngrams(query, max_ngram=1)
        if not q_tokens:
            return []

        scored: list[tuple[float, NormativeChunk]] = []
        for chunk, tf_map, doc_len in zip(
            self.chunks, self.doc_freqs, self.doc_lens, strict=True
        ):
            raw_bm25 = 0.0
            for term in set(q_tokens):
                if term not in tf_map:
                    continue
                tf = tf_map[term]
                idf = self.idf.get(term, 0.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                raw_bm25 += idf * ((tf * (self.k1 + 1.0)) / denom)

            norm_score = raw_bm25 / (raw_bm25 + 4.0) if raw_bm25 > 0 else 0.0
            if norm_score >= min_score:
                scored.append((norm_score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalHit(
                chunk_id=chunk.chunk_id,
                score=round(score, 4),
                source_id=chunk.source_id,
                document_title=chunk.document_title,
                section=chunk.section,
                page_number=chunk.page_number,
                route_category=chunk.route_category,
                text=chunk.text,
                matched_dcb=None,
                retriever_name="bm25_lexical",
            )
            for score, chunk in scored[:top_k]
        ]


class TabularDCBMatcher:
    """Busca determinística e por sobreposição de tokens no catálogo canônico Gold (DCB)."""

    _IGNORED_SALTS: frozenset[str] = frozenset(
        {
            "cloridrato",
            "maleato",
            "besilato",
            "sulfato",
            "fumarato",
            "hemifumarato",
            "potassica",
            "sodica",
            "sodico",
            "calcica",
            "hidratada",
            "di",
            "hidratado",
            "humana",
            "mg",
            "mcg",
            "ui",
            "ml",
        }
    )

    def __init__(self, medications: list[CanonicalMedication]) -> None:
        self.medications = medications

    def match_medications(self, query: str) -> list[tuple[float, CanonicalMedication]]:
        """Retorna medicamentos canônicos casados com a consulta e confiança em [0, 1]."""
        norm_query = normalize_pt_text(query)
        query_tokens = set(norm_query.split())
        matches: list[tuple[float, CanonicalMedication]] = []

        for med in self.medications:
            norm_dcb = normalize_pt_text(med.dcb_name)
            dcb_tokens = [t for t in norm_dcb.split() if len(t) > 2]
            core_tokens = [
                t for t in dcb_tokens if t not in self._IGNORED_SALTS
            ] or dcb_tokens

            if norm_dcb in norm_query:
                score = 0.95
            else:
                matched_core = [t for t in core_tokens if t in query_tokens]
                if len(matched_core) < len(core_tokens):
                    continue
                coverage = len(matched_core) / len(core_tokens)
                score = 0.70 + 0.25 * coverage

            norm_conc = normalize_pt_text(med.concentration)
            if norm_conc and norm_conc in norm_query:
                score = min(1.0, score + 0.05)

            matches.append((round(score, 4), med))

        matches.sort(key=lambda item: item[0], reverse=True)
        # Deduplica por dcb_name mantendo maior score
        seen_dcbs: set[str] = set()
        unique_matches: list[tuple[float, CanonicalMedication]] = []
        for score, med in matches:
            if med.dcb_name not in seen_dcbs:
                seen_dcbs.add(med.dcb_name)
                unique_matches.append((score, med))
        return unique_matches


class HybridRetriever:
    """Recuperador Híbrido (Busca Tabular DCB Gold + TF-IDF + BM25 com Reciprocal Rank Fusion)."""

    _SISREG_DOMAIN_TOKENS: frozenset[str] = frozenset(
        {
            "sisreg",
            "regulacao",
            "cppas",
            "ecocardiograma",
            "cardiologia",
            "endoscopia",
            "ressonancia",
            "reumatologia",
            "endocrinologia",
            "exame",
            "consulta",
        }
    )

    def __init__(
        self,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        rrf_k: int = 60,
    ) -> None:
        self.medications = medications
        self.chunks = {c.chunk_id: c for c in chunks}
        self.tabular = TabularDCBMatcher(medications)
        self.tfidf = TFIDFRetriever(chunks)
        self.bm25 = BM25Retriever(chunks)
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.18,
    ) -> list[RetrievalHit]:
        """Combina correspondência tabular DCB e recuperação normativa via RRF calibrado."""
        med_matches = self.tabular.match_medications(query)
        matched_dcbs = {med.dcb_name: score for score, med in med_matches}

        norm_query_tokens = set(normalize_pt_text(query).split())
        is_sisreg_intent = bool(
            norm_query_tokens.intersection(self._SISREG_DOMAIN_TOKENS)
        )

        tfidf_hits = self.tfidf.search(query, top_k=len(self.chunks), min_score=0.01)
        bm25_hits = self.bm25.search(query, top_k=len(self.chunks), min_score=0.01)

        tfidf_ranks = {hit.chunk_id: rank + 1 for rank, hit in enumerate(tfidf_hits)}
        tfidf_scores = {hit.chunk_id: hit.score for hit in tfidf_hits}

        bm25_ranks = {hit.chunk_id: rank + 1 for rank, hit in enumerate(bm25_hits)}
        bm25_scores = {hit.chunk_id: hit.score for hit in bm25_hits}

        combined_results: list[RetrievalHit] = []
        for chunk_id, chunk in self.chunks.items():
            t_score = tfidf_scores.get(chunk_id, 0.0)
            b_score = bm25_scores.get(chunk_id, 0.0)

            rrf_component = 0.0
            if chunk_id in tfidf_ranks:
                rrf_component += (self.rrf_k + 1.0) / (
                    self.rrf_k + tfidf_ranks[chunk_id]
                )
            if chunk_id in bm25_ranks:
                rrf_component += (self.rrf_k + 1.0) / (
                    self.rrf_k + bm25_ranks[chunk_id]
                )
            rrf_norm = rrf_component / 2.0

            lexical_score = 0.55 * t_score + 0.45 * b_score

            # Verifica se algum DCB casado na tabela Gold aparece no chunk normativo
            chunk_dcb_boost = 0.0
            best_dcb: str | None = None
            for dcb_name in chunk.dcb_mentions:
                if dcb_name in matched_dcbs:
                    if matched_dcbs[dcb_name] > chunk_dcb_boost:
                        chunk_dcb_boost = matched_dcbs[dcb_name]
                        best_dcb = dcb_name

            if chunk_dcb_boost > 0.0:
                final_score = (
                    0.50 * lexical_score + 0.35 * chunk_dcb_boost + 0.15 * rrf_norm
                )
            elif is_sisreg_intent and chunk.route_category == "SISREG_EXAME_CONSULTA":
                final_score = 0.80 * lexical_score + 0.20 * rrf_norm
            elif matched_dcbs:
                # A consulta possui DCB válido, mas este chunk não menciona o DCB
                final_score = 0.35 * lexical_score
            else:
                # Sem DCB no catálogo Gold e sem intenção SISREG -> penaliza ruído de palavras genéricas
                final_score = 0.30 * lexical_score

            if final_score >= min_score:
                combined_results.append(
                    RetrievalHit(
                        chunk_id=chunk.chunk_id,
                        score=round(final_score, 4),
                        source_id=chunk.source_id,
                        document_title=chunk.document_title,
                        section=chunk.section,
                        page_number=chunk.page_number,
                        route_category=chunk.route_category,
                        text=chunk.text,
                        matched_dcb=best_dcb,
                        retriever_name="hybrid_dcb_rrf",
                    )
                )

        combined_results.sort(key=lambda item: item.score, reverse=True)
        return combined_results[:top_k]
