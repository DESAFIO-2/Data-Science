"""Motores de Recuperação (SPEC-03 / SPEC-09 / Corpus Consolidado v9).

Replica integralmente a arquitetura RAG híbrida oficial de `DESAFIO-2/development`:
- `TabularDCBMatcher`: matching determinístico de DCB, equivalências escopadas de dose
  (ex.: Sacubitril/Valsartana 97/103 mg <-> 200 mg, Salbutamol 100 mcg <-> 100 mcg/dose)
  e remoção segura de separadores de milhar brasileiros.
- `TFIDFRetriever` + `BM25Retriever`: ranqueadores lexicais determinísticos.
- `HybridRetriever`: fusão tripla `Tabular DCB + TF-IDF + BM25` via `Reciprocal Rank Fusion (RRF)`,
  enriquecida para intenções regulatórias (`CHK-REGRA-*`, `CHK-COMP-*`), `SISREG` e `PRE_EXAME_PREPARO`.
- `EvidenceV2Retriever`: resolução 1:1 das 2.114 evidências literais (`evidence_chunks_v2.json`)
  por `occurrence_ids` para proveniência auditável nos multiagentes.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from sus_cidadao_ds.contracts.schemas import (
    CanonicalMedication,
    EvidenceChunkV2,
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

    _DOSE_PART = (
        r"\b\d+(?:[.,]\d+)*(?:/\d+(?:[.,]\d+)*)*\s*"
        r"(?:mcg|mg|g|ui|ml|%)(?!\w)"
        r"(?:\s*/\s*(?:\d+(?:[.,]\d+)*\s*)?(?:ml|g|dose)\b)?"
    )
    _DOSE = re.compile(_DOSE_PART + r"(?:\s*\+\s*" + _DOSE_PART + r")*", re.IGNORECASE)

    _EQUIVALENCIAS_CONCENTRACAO_SCOPED: dict[str, tuple[frozenset[str], ...]] = {
        "sacubitril valsartana sodica hidratada": (
            frozenset({"97mg+103mg", "200mg"}),
            frozenset({"49mg+51mg", "100mg"}),
            frozenset({"24mg+26mg", "50mg"}),
        ),
        "sulfato de salbutamol": (frozenset({"100mcg", "100mcg/dose"}),),
    }

    @staticmethod
    def normalizar_concentracao(concentracao: str) -> str:
        """Normaliza concentração removendo separador de milhar BR e preservando decimais."""
        sem_milhar = re.sub(
            r"(?<![\d.,])([1-9]\d{0,2}(?:\.\d{3})+)(?![\d.,])",
            lambda m: m.group(1).replace(".", ""),
            concentracao,
        )
        valor = re.sub(r"\s+", "", sem_milhar.lower().replace(",", "."))
        composto = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)(mcg|mg|g|ui)", valor)
        if composto:
            primeiro, segundo, unidade = composto.groups()
            return f"{primeiro}{unidade}+{segundo}{unidade}"
        return valor

    @classmethod
    def _doses_equivalentes(cls, norm_dcb: str, dose_consulta: str, dose_catalogo: str) -> bool:
        if not dose_consulta or dose_consulta == dose_catalogo:
            return True
        pares = cls._EQUIVALENCIAS_CONCENTRACAO_SCOPED.get(norm_dcb, ())
        return any(dose_consulta in par and dose_catalogo in par for par in pares)

    @classmethod
    def doses_no_texto(cls, texto: str) -> set[str]:
        return {cls.normalizar_concentracao(dose) for dose in cls._DOSE.findall(texto)}

    @classmethod
    def tem_numero_nao_interpretado(cls, texto: str) -> bool:
        """Número sem unidade reconhecida exige confirmação da apresentação."""
        residual = cls._DOSE.sub("", texto)
        residual = re.sub(r"\bdiabetes\s+tipo\s+[12]\b", "", residual, flags=re.IGNORECASE)
        residual = re.sub(
            r"\b\d+\s*(?:comprimidos|capsulas|cápsulas|ampolas|unidades)\b",
            "",
            residual,
            flags=re.IGNORECASE,
        )
        return bool(re.search(r"\d", residual))

    def __init__(self, medications: list[CanonicalMedication]) -> None:
        self.medications = medications

    def match_medications(
        self,
        query: str,
        *,
        concentracao: str = "",
        forma: str = "",
        deduplicar: bool = True,
    ) -> list[tuple[float, CanonicalMedication]]:
        """Retorna medicamentos canônicos casados com a consulta e score em [0, 1]."""
        norm_query = normalize_pt_text(query)
        query_tokens = set(norm_query.split())
        doses_na_consulta = self.doses_no_texto(query)
        matches: list[tuple[float, CanonicalMedication]] = []

        dose = self.normalizar_concentracao(concentracao)
        forma_norm = normalize_pt_text(forma)

        for med in self.medications:
            norm_dcb = normalize_pt_text(med.dcb_name)
            norm_med_conc = self.normalizar_concentracao(med.concentration)
            if not self._doses_equivalentes(norm_dcb, dose, norm_med_conc):
                continue
            if forma_norm and normalize_pt_text(med.pharmaceutical_form) != forma_norm:
                continue

            dcb_tokens = [t for t in norm_dcb.split() if len(t) > 2]
            core_tokens = [
                t for t in dcb_tokens if t not in self._IGNORED_SALTS
            ] or dcb_tokens
            if not core_tokens:
                continue

            if f" {norm_dcb} " in f" {norm_query} ":
                score = 0.95
            else:
                matched_core = [t for t in core_tokens if t in query_tokens]
                if len(matched_core) < len(core_tokens):
                    continue
                coverage = len(matched_core) / len(core_tokens)
                score = 0.70 + 0.25 * coverage

            norm_conc = normalize_pt_text(med.concentration)
            if (norm_conc and norm_conc in norm_query) or any(
                self._doses_equivalentes(norm_dcb, d_q, norm_med_conc)
                for d_q in doses_na_consulta
            ):
                score = min(1.0, score + 0.05)

            form_tokens = [
                t
                for t in normalize_pt_text(med.pharmaceutical_form).split()
                if len(t) >= 4 and t not in {"forma", "informada", "uso"}
            ]
            if form_tokens and any(ft in query_tokens for ft in form_tokens):
                score = min(1.0, score + 0.02)

            matches.append((round(score, 4), med))

        asks_ubs_channel = (
            any(tok in norm_query for tok in ("sala da ubs", "na ubs", "policlinica", "cedin", "cesaf"))
            and "farmacia popular" not in norm_query
        )
        route_priority = (
            {
                "UBS_ATENCAO_PRIMARIA": 4,
                "FARMACIA_POPULAR": 3,
                "ALTO_CUSTO_CEAF": 2,
                "HOSPITALAR": 1,
            }
            if asks_ubs_channel
            else {
                "FARMACIA_POPULAR": 4,
                "UBS_ATENCAO_PRIMARIA": 3,
                "ALTO_CUSTO_CEAF": 2,
                "HOSPITALAR": 1,
            }
        )
        matches.sort(
            key=lambda item: (
                item[0],
                1 if f" {normalize_pt_text(item[1].dcb_name)} " in f" {norm_query} " else 0,
                route_priority.get(item[1].dispensation_route, 0),
            ),
            reverse=True,
        )
        if not deduplicar:
            return matches

        # 1. Remove variantes de sal que conflitam quando a forma exata do sal já apareceu na consulta
        # (ex.: "benzilpenicilina potássica" quando usuário pediu "benzilpenicilina benzatina")
        exact_core_matched_lengths: dict[str, int] = {}
        for _, med in matches:
            norm_dcb = normalize_pt_text(med.dcb_name)
            dcb_toks = [t for t in norm_dcb.split() if len(t) > 2]
            core = [t for t in dcb_toks if t not in self._IGNORED_SALTS] or dcb_toks
            base_tok = core[0]
            if f" {norm_dcb} " in f" {norm_query} ":
                exact_core_matched_lengths[base_tok] = max(
                    exact_core_matched_lengths.get(base_tok, 0), len(dcb_toks)
                )

        filtered: list[tuple[float, CanonicalMedication]] = []
        for score, med in matches:
            norm_dcb = normalize_pt_text(med.dcb_name)
            dcb_toks = [t for t in norm_dcb.split() if len(t) > 2]
            core = [t for t in dcb_toks if t not in self._IGNORED_SALTS] or dcb_toks
            base_tok = core[0]
            if (
                base_tok in exact_core_matched_lengths
                and exact_core_matched_lengths[base_tok] > len(core)
                and f" {norm_dcb} " not in f" {norm_query} "
            ):
                continue
            filtered.append((score, med))

        # 2. Deduplica por núcleo ativo normalizado (colapsa acentos/formatos tipo "losartana potássica" vs "losartana potassica")
        # e suprime subconjunto estrito quando forma mais específica aparece literalmente (ex.: "insulina humana" sob "insulina humana nph")
        seen_cores: set[tuple[str, ...]] = set()
        unique_matches: list[tuple[float, CanonicalMedication]] = []
        for score, med in filtered:
            norm_dcb = normalize_pt_text(med.dcb_name)
            dcb_toks = [t for t in norm_dcb.split() if len(t) > 2]
            core_key = tuple(
                sorted(t for t in dcb_toks if t not in self._IGNORED_SALTS) or dcb_toks
            )
            if core_key not in seen_cores:
                seen_cores.add(core_key)
                unique_matches.append((score, med))

        if len(unique_matches) > 1:
            core_sets = [
                set(
                    [
                        t
                        for t in normalize_pt_text(m.dcb_name).split()
                        if len(t) > 2 and t not in self._IGNORED_SALTS
                    ]
                    or [t for t in normalize_pt_text(m.dcb_name).split() if len(t) > 2]
                )
                for _, m in unique_matches
            ]
            non_subsumed: list[tuple[float, CanonicalMedication]] = []
            for idx, (score, med) in enumerate(unique_matches):
                cur_set = core_sets[idx]
                is_subsumed = any(
                    j != idx
                    and cur_set
                    and cur_set < other_set
                    and f" {normalize_pt_text(unique_matches[j][1].dcb_name)} "
                    in f" {norm_query} "
                    for j, other_set in enumerate(core_sets)
                )
                if not is_subsumed:
                    non_subsumed.append((score, med))
            unique_matches = non_subsumed

        # 3. Se usuário listou monoterapias separadas sem '+', evita duplicar combinação fixa redundante
        if "+" not in query:
            standalone_cores = {
                tuple(sorted(
                    [t for t in normalize_pt_text(m.dcb_name).split() if len(t) > 2 and t not in self._IGNORED_SALTS]
                ))
                for _, m in unique_matches
                if "+" not in m.dcb_name
            }
            deduped_final: list[tuple[float, CanonicalMedication]] = []
            for score, med in unique_matches:
                if "+" in med.dcb_name:
                    parts = [
                        tuple(sorted(
                            [t for t in normalize_pt_text(p).split() if len(t) > 2 and t not in self._IGNORED_SALTS]
                        ))
                        for p in med.dcb_name.split("+")
                    ]
                    if parts and all(part in standalone_cores for part in parts):
                        continue
                deduped_final.append((score, med))
            return deduped_final

        return unique_matches

    casar = match_medications


class EvidenceV2Retriever:
    """Índice de proveniência 1:1 para os 2.114 chunks literais do corpus consolidado v9."""

    def __init__(self, evidences: list[EvidenceChunkV2]) -> None:
        self.evidences = evidences
        self.by_occurrence: dict[str, EvidenceChunkV2] = {
            ev.occurrence_id: ev for ev in evidences
        }

    def lookup_for_medication(
        self,
        med: CanonicalMedication,
        limit: int = 2,
    ) -> list[RetrievalHit]:
        """Recupera evidências literais F01/F03/F04 vinculadas ao item canônico."""
        hits: list[RetrievalHit] = []
        for occ_id in med.occurrence_ids:
            ev = self.by_occurrence.get(occ_id)
            if ev is None:
                continue
            src = ev.source or {}
            src_id = str(src.get("source_id", med.source_id))
            src_ver = str(src.get("version", ev.release_version))
            page_num = int(src.get("page") or med.source_page or 1)
            hits.append(
                RetrievalHit(
                    chunk_id=ev.chunk_id,
                    score=0.98,
                    source_id=src_id,
                    document_title=f"{src_id} — {src_ver} ({ev.release_version})",
                    section=f"Evidência literal ({ev.item_type})",
                    page_number=page_num,
                    route_category=med.dispensation_route,
                    text=f"{ev.text} [{ev.literal_text}]" if ev.literal_text else ev.text,
                    matched_dcb=med.dcb_name,
                    retriever_name="evidence_v2_provenance",
                )
            )
            if len(hits) >= limit:
                break
        return hits


class HybridRetriever:
    """Recuperador Híbrido: Casamento Tabular DCB, TF-IDF e BM25 com Reciprocal Rank Fusion (RRF)."""

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
    _PRE_EXAM_DOMAIN_TOKENS: frozenset[str] = frozenset(
        {
            "preparo",
            "preparar",
            "jejum",
            "ultrassom",
            "ultrassonografia",
            "abdome",
            "barriga",
            "bexiga",
            "endoscopia",
            "ressonancia",
            "tomografia",
            "contraste",
            "creatinina",
            "ecocardiograma",
            "coleta",
            "glicemia",
            "colesterol",
            "acompanhante",
        }
    )
    _REGULATORY_RULE_TOKENS: frozenset[str] = frozenset(
        {
            "procuracao",
            "procurador",
            "terceiro",
            "terceiros",
            "idoso",
            "idosa",
            "acamado",
            "bairro",
            "polo",
            "polos",
            "adscricao",
            "territorio",
            "territorial",
            "cadastrada",
            "lme",
            "pcdt",
            "infosaude",
            "estoque",
            "declaracao",
            "autorizadora",
            "policlinica",
            "cedin",
            "dignidade",
            "menstrual",
            "cesaf",
            "tuberculose",
            "hanseniase",
        }
    )

    def __init__(
        self,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        rrf_k: int = 60,
        tabular_matcher: TabularDCBMatcher | None = None,
    ) -> None:
        self.medications = medications
        self.chunks = {c.chunk_id: c for c in chunks}
        self.tabular = tabular_matcher or TabularDCBMatcher(medications)
        self.tfidf = TFIDFRetriever(chunks)
        self.bm25 = BM25Retriever(chunks)
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.18,
    ) -> list[RetrievalHit]:
        """Executa busca híbrida ponderada (Tabular DCB + TF-IDF + BM25 + RRF)."""
        med_matches = self.tabular.match_medications(query)
        matched_dcbs = {med.dcb_name: score for score, med in med_matches}

        norm_query_tokens = set(normalize_pt_text(query).split())
        is_sisreg_intent = bool(norm_query_tokens.intersection(self._SISREG_DOMAIN_TOKENS))
        is_pre_exam_intent = bool(norm_query_tokens.intersection(self._PRE_EXAM_DOMAIN_TOKENS))
        is_rule_intent = bool(norm_query_tokens.intersection(self._REGULATORY_RULE_TOKENS))

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

            rrf_comp = 0.0
            if chunk_id in tfidf_ranks:
                rrf_comp += (self.rrf_k + 1.0) / (self.rrf_k + tfidf_ranks[chunk_id])
            if chunk_id in bm25_ranks:
                rrf_comp += (self.rrf_k + 1.0) / (self.rrf_k + bm25_ranks[chunk_id])
            rrf_norm = rrf_comp / 2.0

            lexical_score = 0.55 * t_score + 0.45 * b_score

            chunk_dcb_boost = 0.0
            best_dcb: str | None = None
            for dcb_name in chunk.dcb_mentions:
                if dcb_name in matched_dcbs:
                    if matched_dcbs[dcb_name] > chunk_dcb_boost:
                        chunk_dcb_boost = matched_dcbs[dcb_name]
                        best_dcb = dcb_name

            if chunk_dcb_boost > 0.0:
                final_score = 0.50 * lexical_score + 0.35 * chunk_dcb_boost + 0.15 * rrf_norm
            elif is_pre_exam_intent and chunk.route_category == "PRE_EXAME_PREPARO" and b_score >= 0.15:
                final_score = 0.80 * lexical_score + 0.20 * rrf_norm
            elif is_sisreg_intent and chunk.route_category == "SISREG_EXAME_CONSULTA":
                final_score = 0.80 * lexical_score + 0.20 * rrf_norm
            elif is_rule_intent and chunk.chunk_id.startswith(("CHK-REGRA-", "CHK-COMP-")):
                final_score = 0.70 * lexical_score + 0.30 * rrf_norm
            elif matched_dcbs:
                final_score = 0.35 * lexical_score
            else:
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
