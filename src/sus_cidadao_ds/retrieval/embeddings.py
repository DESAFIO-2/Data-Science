"""Provedor de Embeddings Consciente de Português Clínico e SUS-DF para o ChromaDB (SPEC-09).

Suporta:
1. `pt_br_hybrid_onnx` (padrão offline/local sem custo): combina embeddings densos locais
   ONNX (`all-MiniLM-L6-v2`, 384d) com subespaço semântico clínico PT-BR + n-gramas (128d),
   permitindo que perguntas coloquiais faladas (ex.: "exame da barriga sem comer") casem com
   protocolos oficiais ("Ultrassonografia Abdominal / Jejum").
2. `gemini`: API Gemini (`text-embedding-004`) quando `GEMINI_API_KEY` estiver configurada.
3. `openai`: API OpenAI (`text-embedding-3-small`) quando `OPENAI_API_KEY` estiver configurada.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from typing import Any

import httpx
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.utils.embedding_functions import (
    DefaultEmbeddingFunction,
    register_embedding_function,
)

# Grupos conceituais bilíngues/coloquiais do SUS e pré-exames (cada tupla projeta em 1 dimensão)
_PT_CLINICAL_CONCEPT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("jejum", "sem comer", "agua", "alimento", "alimentacao", "fome", "cafe", "comer", "beber"),
    ("bexiga", "bexiga cheia", "urinar", "urina", "xixi", "pelvica", "vias urinarias", "prostata", "copos"),
    ("abdome", "abdominal", "barriga", "estomago", "figado", "vesicula", "ultrassom", "ultrassonografia"),
    ("endoscopia", "eda", "digestiva", "acompanhante", "sedacao", "garganta", "estomago"),
    ("ressonancia", "tomografia", "metal", "metalico", "brinco", "alianca", "piercing", "marcapasso", "protese", "claustrofobia", "contraste", "creatinina"),
    ("ecocardiograma", "coracao", "cardiologia", "ecg", "eletrocardiograma", "peito", "roupa confortavel"),
    ("sangue", "coleta", "laboratorio", "laboratorial", "colesterol", "glicemia", "lipidico", "alcool", "exercicio"),
    ("preparo", "pre exame", "pre-exame", "antes do exame", "cuidados", "instrucoes"),
    ("alto custo", "ceaf", "lme", "especializado", "pcdt", "cid", "processo", "laudo"),
    ("farmacia popular", "pfpb", "gratuito", "drogaria", "credenciada", "aqui tem", "cpf"),
    ("ubs", "unidade basica", "posto de saude", "atencao primaria", "cns", "cartao sus"),
    ("validade", "vencer", "vencimento", "renovacao", "180 dias", "90 dias", "30 dias", "10 dias"),
    ("estoque", "disponivel", "falta", "asa sul", "ceilandia", "gama", "infosaude"),
    ("sisreg", "regulacao", "encaminhamento", "prioridade", "agendamento", "consulta"),
)


def _normalize_for_pt_concept(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    no_acc = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-z0-9\s/-]", " ", no_acc)
    return " ".join(cleaned.split())


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return vec
    return [v / norm for v in vec]


def _encode_pt_clinical_subspace(text: str, total_dims: int = 128) -> list[float]:
    """Codifica conceitos clínicos coloquiais do SUS e n-gramas PT-BR em vetor denso."""
    norm_text = _normalize_for_pt_concept(text)
    vec = [0.0] * total_dims
    concept_count = len(_PT_CLINICAL_CONCEPT_GROUPS)

    # 1. Dimensões semânticas explícitas de conceitos clínicos e pré-exames do SUS
    for idx, keywords in enumerate(_PT_CLINICAL_CONCEPT_GROUPS):
        hits = sum(1 for kw in keywords if kw in norm_text)
        if hits > 0:
            vec[idx] = 1.0 + math.log(1.0 + hits)

    # 2. Projeção lexical (subpalavras + termos PT-BR) nas dimensões restantes
    lexical_dims = total_dims - concept_count
    words = [w for w in norm_text.split() if len(w) >= 2]
    features: list[str] = list(words)
    for word in words:
        if len(word) >= 4:
            for i in range(len(word) - 2):
                features.append(word[i : i + 3])

    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        bucket = concept_count + (int.from_bytes(digest[:4], "big") % lexical_dims)
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[bucket] += sign * (1.5 if len(feat) > 3 else 0.7)

    return _l2_normalize(vec)


@register_embedding_function
class PortugueseClinicalEmbeddingFunction(EmbeddingFunction[Documents]):
    """EmbeddingFunction do ChromaDB otimizada para consultas clínicas/administrativas em PT-BR."""

    def __init__(self, provider: str = "auto") -> None:
        self.provider = provider
        self._onnx_ef: Any | None = None

    def _resolve_provider(self) -> str:
        env_provider = os.environ.get("SUS_CIDADAO_EMBEDDING_PROVIDER", "").strip().lower()
        effective = env_provider or self.provider
        if effective == "auto":
            if os.environ.get("GEMINI_API_KEY") and env_provider == "gemini":
                return "gemini"
            if os.environ.get("OPENAI_API_KEY") and env_provider == "openai":
                return "openai"
            return "pt_br_hybrid_onnx"
        return effective

    def _get_onnx_ef(self) -> Any:
        if self._onnx_ef is None:
            self._onnx_ef = DefaultEmbeddingFunction()
        return self._onnx_ef

    def _embed_local_hybrid(self, texts: Documents) -> list[list[float]]:
        onnx_vecs: list[list[float]] | None = None
        try:
            raw_vecs = self._get_onnx_ef()(list(texts))
            onnx_vecs = [[float(x) for x in row] for row in raw_vecs]
        except Exception:
            onnx_vecs = None

        output: list[list[float]] = []
        for idx, text in enumerate(texts):
            pt_vec = _encode_pt_clinical_subspace(text, total_dims=128)
            if onnx_vecs is not None and idx < len(onnx_vecs):
                onnx_norm = _l2_normalize(onnx_vecs[idx])
                combined = [0.55 * v for v in onnx_norm] + [0.45 * v for v in pt_vec]
                output.append(_l2_normalize(combined))
            else:
                padded = pt_vec + [0.0] * 384
                output.append(_l2_normalize(padded))
        return output

    def _embed_gemini(self, texts: Documents) -> list[list[float]]:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            return self._embed_local_hybrid(texts)
        vectors: list[list[float]] = []
        with httpx.Client(timeout=15.0) as client:
            for text in texts:
                resp = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}",
                    json={"content": {"parts": [{"text": text}]}},
                )
                resp.raise_for_status()
                vals = [float(x) for x in resp.json()["embedding"]["values"]]
                vectors.append(_l2_normalize(vals))
        return vectors

    def _embed_openai(self, texts: Documents) -> list[list[float]]:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return self._embed_local_hybrid(texts)
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": list(texts)},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            return [_l2_normalize([float(x) for x in item["embedding"]]) for item in data]

    def __call__(self, input: Documents) -> Embeddings:
        provider = self._resolve_provider()
        if provider == "gemini":
            try:
                return self._embed_gemini(input)  # type: ignore[return-value]
            except Exception:
                return self._embed_local_hybrid(input)  # type: ignore[return-value]
        if provider == "openai":
            try:
                return self._embed_openai(input)  # type: ignore[return-value]
            except Exception:
                return self._embed_local_hybrid(input)  # type: ignore[return-value]
        return self._embed_local_hybrid(input)  # type: ignore[return-value]

    @staticmethod
    def name() -> str:
        return "sus_cidadao_pt_br_clinical_v1"

    def get_config(self) -> dict[str, Any]:
        return {"provider": self.provider}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> PortugueseClinicalEmbeddingFunction:
        return PortugueseClinicalEmbeddingFunction(provider=str(config.get("provider", "auto")))

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        return

