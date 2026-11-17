"""Portas (Clean Architecture), Adaptadores Locais e Telemetria dos Agentes (Semana 4)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from sus_cidadao_ds.contracts.schemas import (
    CanonicalMedication,
    EvidenceChunkV2,
    NormativeChunk,
    RetrievalHit,
)
from sus_cidadao_ds.core.config import ProjectPaths
from sus_cidadao_ds.guardrails.clinical_blocker import ClinicalBlocker, ClinicalCheckResult
from sus_cidadao_ds.guardrails.pii_masker import PIIMasker, PIIMaskingResult
from sus_cidadao_ds.ingestion.infosaude_client import haversine_km
from sus_cidadao_ds.retrieval.retrievers import (
    EvidenceV2Retriever,
    HybridRetriever,
    TabularDCBMatcher,
    normalize_pt_text,
)


@dataclass
class OperationTrace:
    """Registro de latência e status de um agente ou ferramenta."""

    operation: str
    elapsed_ms: float = 0.0


@contextmanager
def trace_operation(operation: str) -> Iterator[OperationTrace]:
    """Instrumenta o tempo de execução de cada nó/agente em milissegundos."""
    record = OperationTrace(operation=operation)
    start = time.perf_counter()
    try:
        yield record
    finally:
        record.elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)


@runtime_checkable
class GuardrailPort(Protocol):
    """Porta de proteção LGPD + bloqueio clínico + anti-injection."""

    def mask(self, raw_text: str) -> PIIMaskingResult: ...
    def inspect(self, text: str) -> ClinicalCheckResult: ...


@runtime_checkable
class MedicationRepositoryPort(Protocol):
    """Porta determinística para casamento de DCB no catálogo canônico v9."""

    def match_medications(
        self,
        text: str,
        *,
        concentracao: str = "",
        forma: str = "",
        deduplicar: bool = True,
    ) -> list[tuple[float, CanonicalMedication]]: ...


@runtime_checkable
class EvidenceRepositoryPort(Protocol):
    """Porta para proveniência literal 1:1 dos chunks v2 (F01/F03/F04)."""

    def lookup_for_medication(
        self, med: CanonicalMedication, limit: int = 2
    ) -> list[RetrievalHit]: ...


@runtime_checkable
class RetrieverPort(Protocol):
    """Porta de recuperação híbrida lexical (TF-IDF + BM25 + Tabular RRF)."""

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.18
    ) -> list[RetrievalHit]: ...


@runtime_checkable
class InfoSaudeStockPort(Protocol):
    """Porta local determinística para estoque CEAF-DF em tempo real."""

    def lookup_stock(self, dcb_name: str, ceaf_unit_hint: str = "") -> str: ...


@runtime_checkable
class GeneratorPort(Protocol):
    """Porta de geração humanizada opcional no Agente 4 (Sintetizador Cidadão)."""

    def generate(self, user_query: str, grounded_facts: str) -> str: ...


@runtime_checkable
class PharmacyRepositoryPort(Protocol):
    """Porta determinística para estabelecimentos geolocalizados (CEAF / Policlínicas / UBS DF)."""

    def find_nearby(
        self,
        *,
        ra: str = "",
        q: str = "",
        lat: float | None = None,
        lng: float | None = None,
        limit: int = 8,
    ) -> tuple[int, list[dict[str, Any]]]: ...

    def hint_for_ra(self, detected_ra: str, *, route: str = "") -> str: ...


class LocalGuardrailAdapter:
    """Adaptador padrão usando PIIMasker LGPD + ClinicalBlocker + anti-injection."""

    def __init__(
        self,
        masker: PIIMasker | None = None,
        blocker: ClinicalBlocker | None = None,
    ) -> None:
        self.masker = masker or PIIMasker()
        self.blocker = blocker or ClinicalBlocker()

    def mask(self, raw_text: str) -> PIIMaskingResult:
        return self.masker.mask(raw_text)

    def inspect(self, text: str) -> ClinicalCheckResult:
        return self.blocker.inspect(text)


class TabularMedicationAdapter:
    """Adaptador tabular determinístico sobre `medicamentos_sus_canonical.json`."""

    def __init__(self, medications: list[CanonicalMedication]) -> None:
        self.matcher = TabularDCBMatcher(medications)

    def match_medications(
        self,
        text: str,
        *,
        concentracao: str = "",
        forma: str = "",
        deduplicar: bool = True,
    ) -> list[tuple[float, CanonicalMedication]]:
        return self.matcher.match_medications(
            text, concentracao=concentracao, forma=forma, deduplicar=deduplicar
        )


class EvidenceV2Adapter:
    """Adaptador de proveniência sobre os 2.114 chunks literais de F01/F03/F04."""

    def __init__(self, evidences_v2: list[EvidenceChunkV2] | None = None) -> None:
        self.retriever = EvidenceV2Retriever(evidences_v2 or [])

    def lookup_for_medication(
        self, med: CanonicalMedication, limit: int = 2
    ) -> list[RetrievalHit]:
        return self.retriever.lookup_for_medication(med, limit=limit)


class HybridRetrieverAdapter:
    """Adaptador lexical híbrido (Tabular + TF-IDF + BM25 via RRF k=60)."""

    def __init__(
        self,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        tabular_matcher: TabularDCBMatcher | None = None,
    ) -> None:
        self.retriever = HybridRetriever(
            medications=medications,
            chunks=chunks,
            tabular_matcher=tabular_matcher,
        )

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.18
    ) -> list[RetrievalHit]:
        return self.retriever.search(query=query, top_k=top_k, min_score=min_score)


class LocalCEAFStockRepository:
    """Consulta determinística sobre `data/gold/ceaf_live_stock.json` sem ChromaDB em runtime."""

    _UNIT_TOKENS: tuple[tuple[str, str], ...] = (
        ("ceilandia", "ceilandia"),
        ("taguatinga", "ceilandia"),
        ("samambaia", "ceilandia"),
        ("gama", "gama"),
        ("santa maria", "gama"),
        ("asa sul", "asa sul"),
        ("102 sul", "asa sul"),
        ("plano piloto", "asa sul"),
    )

    def __init__(self, stock_path: Path | None = None) -> None:
        resolved = stock_path or (ProjectPaths.from_root().gold_dir / "ceaf_live_stock.json")
        self.stock_path = resolved
        self._items: list[dict[str, str]] | None = None

    def _load(self) -> list[dict[str, str]]:
        if self._items is not None:
            return self._items
        if not self.stock_path.exists():
            self._items = []
            return self._items
        raw = json.loads(self.stock_path.read_text(encoding="utf-8"))
        rows = raw.get("items", [])
        parsed: list[dict[str, str]] = []
        for row in rows:
            parsed.append(
                {
                    "desc_norm": normalize_pt_text(
                        str(row.get("desc_produto") or row.get("medicamento") or "")
                    ),
                    "unidade": str(row.get("unidade") or ""),
                    "unidade_norm": normalize_pt_text(str(row.get("unidade") or "")),
                    "disp_estoque": str(row.get("disp_estoque") or "").strip(),
                }
            )
        self._items = parsed
        return self._items

    def lookup_stock(self, dcb_name: str, ceaf_unit_hint: str = "") -> str:
        items = self._load()
        if not items:
            return ""
        dcb_norm = normalize_pt_text(dcb_name)
        core_tokens = [tok for tok in dcb_norm.split() if len(tok) >= 4]
        if not core_tokens:
            return ""

        hint_norm = normalize_pt_text(ceaf_unit_hint)
        target_unit = ""
        for token, unit_key in self._UNIT_TOKENS:
            if token in hint_norm:
                target_unit = unit_key
                break

        matches = [
            row for row in items if all(tok in row["desc_norm"] for tok in core_tokens[:2])
        ]
        if not matches:
            return ""

        if target_unit:
            unit_matches = [row for row in matches if target_unit in row["unidade_norm"]]
            if unit_matches:
                best = unit_matches[0]
                disp = best["disp_estoque"] or "consultar unidade"
                return f" [InfoSaúde em Tempo Real — {best['unidade']}: {disp}]"

        summary = ", ".join(
            f"{m['unidade']}: {m['disp_estoque'] or 'consultar'}" for m in matches[:3]
        )
        return f" [InfoSaúde em Tempo Real: {summary}]"


class DeterministicCitizenGenerator:
    """Gerador determinístico zero-custo quando nenhuma LLM externa está ativa."""

    def generate(self, user_query: str, grounded_facts: str) -> str:
        _ = user_query
        return grounded_facts.strip()


class GeminiGeneratorAdapter:
    """Adaptador REST oficial Gemini para humanização estrita de `grounded_facts` (Semana 4)."""

    PROMPT_VERSION = "semana4-v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, user_query: str, grounded_facts: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY não configurada para GeminiGeneratorAdapter.")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        prompt = (
            "Você é a assistente administrativa acolhedora do SUS Cidadão DF. "
            "Responda em português brasileiro claro e empático usando EXCLUSIVAMENTE "
            "os fatos auditados abaixo. NÃO dê doses, NÃO altere medicamentos, "
            "NÃO prescreva e mantenha exatamente os identificadores de fonte recebidos.\n\n"
            f"<consulta_nao_confiavel>\n{user_query}\n</consulta_nao_confiavel>\n\n"
            f"<fatos_auditados>\n{grounded_facts}\n</fatos_auditados>"
        )
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 450},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"Falha ao consultar Gemini REST: {exc}") from exc

        text = str(
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        ).strip()
        if not text:
            raise RuntimeError("Resposta vazia retornada pelo Gemini REST.")
        return text


class LocalPharmacyRepository:
    """Repositório determinístico sobre `data/gold/df_pharmacies_geolocated.json` (231 unidades)."""

    def __init__(self, pharmacies_path: Path | None = None) -> None:
        resolved = pharmacies_path or (
            ProjectPaths.from_root().gold_dir / "df_pharmacies_geolocated.json"
        )
        self.pharmacies_path = resolved
        self._rows: list[dict[str, Any]] | None = None

    def _load(self) -> list[dict[str, Any]]:
        if self._rows is not None:
            return self._rows
        if not self.pharmacies_path.exists():
            self._rows = []
            return self._rows
        raw = json.loads(self.pharmacies_path.read_text(encoding="utf-8"))
        self._rows = list(raw.get("pharmacies", []))
        return self._rows

    def find_nearby(
        self,
        *,
        ra: str = "",
        q: str = "",
        lat: float | None = None,
        lng: float | None = None,
        limit: int = 8,
    ) -> tuple[int, list[dict[str, Any]]]:
        rows = self._load()
        if not rows:
            return 0, []

        norm_ra = normalize_pt_text(ra.replace(" - DF", ""))
        norm_q = normalize_pt_text(q)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            hay = normalize_pt_text(
                " ".join(
                    [
                        str(row.get("name", "")),
                        str(row.get("address", "")),
                        str(row.get("neighborhood_or_ra", "")),
                        str(row.get("pharmacy_type") or ""),
                        " ".join(str(x) for x in (row.get("covered_ras") or [])),
                    ]
                )
            )
            match_score = 0.0
            if norm_ra and norm_ra in hay:
                match_score += 5.0
            if norm_q and norm_q in hay:
                match_score += 4.0
            if "alto custo" in str(row.get("pharmacy_type", "")).lower():
                match_score += 1.0

            dist_km: float | None = None
            if lat is not None and lng is not None and row.get("latitude") and row.get("longitude"):
                dist_km = round(
                    haversine_km(lat, lng, float(row["latitude"]), float(row["longitude"])),
                    2,
                )
                match_score += max(0.0, 4.0 - dist_km * 0.1)

            item_copy = dict(row)
            if dist_km is not None:
                item_copy["distance_km"] = dist_km
            if (norm_ra or norm_q) and match_score == 0.0:
                continue
            scored.append((match_score, item_copy))

        if not scored:
            scored = [(0.0, dict(r)) for r in rows[:limit]]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return len(scored), [item for _, item in scored[:limit]]

    def hint_for_ra(self, detected_ra: str, *, route: str = "") -> str:
        clean_ra = detected_ra.replace(" - DF", "").strip()
        if not clean_ra or "geral" in clean_ra.lower():
            return ""
        q = "alto custo" if route == "ALTO_CUSTO_CEAF" else "ubs"
        total, items = self.find_nearby(ra=clean_ra, q=q, limit=1)
        if total == 0 or not items:
            total, items = self.find_nearby(ra=clean_ra, limit=1)
        if total == 0 or not items:
            return ""
        top = items[0]
        name = str(top.get("name", "")).strip()
        addr = str(top.get("address", "")).strip()
        if name and addr:
            return f" [Unidade mapeada na RA: {name} — {addr}]"
        return f" [Unidade mapeada na RA: {name}]" if name else ""


@dataclass(frozen=True)
class ServiceContainer:
    """Contêiner de dependências da Arquitetura Limpa injetado nos 4 agentes LangGraph."""

    guardrail: GuardrailPort
    medication_repo: MedicationRepositoryPort
    evidence_repo: EvidenceRepositoryPort
    retriever: RetrieverPort
    stock_repo: InfoSaudeStockPort
    pharmacy_repo: PharmacyRepositoryPort
    generator: GeneratorPort
    strict_generator: bool = False

    @classmethod
    def build(
        cls,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        *,
        evidences_v2: list[EvidenceChunkV2] | None = None,
        guardrail_port: GuardrailPort | None = None,
        medication_repo: MedicationRepositoryPort | None = None,
        evidence_repo: EvidenceRepositoryPort | None = None,
        retriever_port: RetrieverPort | None = None,
        stock_repository: InfoSaudeStockPort | None = None,
        pharmacy_repository: PharmacyRepositoryPort | None = None,
        generator_port: GeneratorPort | None = None,
        strict_generator: bool = False,
        gold_dir: Path | None = None,
    ) -> ServiceContainer:
        med_adapter = TabularMedicationAdapter(medications)
        hybrid_adapter = HybridRetrieverAdapter(
            medications=medications,
            chunks=chunks,
            tabular_matcher=med_adapter.matcher,
        )
        stock_file = (gold_dir / "ceaf_live_stock.json") if gold_dir else None
        pharm_file = (gold_dir / "df_pharmacies_geolocated.json") if gold_dir else None
        return cls(
            guardrail=guardrail_port or LocalGuardrailAdapter(),
            medication_repo=medication_repo or med_adapter,
            evidence_repo=evidence_repo or EvidenceV2Adapter(evidences_v2 or []),
            retriever=retriever_port or hybrid_adapter,
            stock_repo=stock_repository or LocalCEAFStockRepository(stock_path=stock_file),
            pharmacy_repo=pharmacy_repository or LocalPharmacyRepository(pharmacies_path=pharm_file),
            generator=generator_port or DeterministicCitizenGenerator(),
            strict_generator=strict_generator,
        )

