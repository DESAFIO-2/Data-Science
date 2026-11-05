"""Schemas formais de dados do SUS Cidadão (Camadas Silver, Gold, Golden Dataset e Retrieval)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from typing import Any


def compute_sha256(text: str) -> str:
    """Calcula o hash SHA-256 determinístico em hexadecimal."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CanonicalMedication:
    """Contrato do catálogo canônico de medicamentos (Gold Layer)."""

    medication_id: str
    dcb_name: str
    concentration: str
    pharmaceutical_form: str
    rename_component: str  # "Básico", "Estratégico", "Especializado"
    available_pfpb: bool
    pfpb_free: bool
    available_reme_df: bool
    dispensation_route: str  # "FARMACIA_POPULAR", "UBS_ATENCAO_PRIMARIA", "ALTO_CUSTO_CEAF"
    requires_lme: bool
    icd10_codes: list[str] = field(default_factory=list)
    required_documents: list[str] = field(default_factory=list)
    prescription_validity_days: int = 180
    source_id: str = "RENAME_2024"
    source_page: int = 1
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalMedication:
        return cls(
            medication_id=str(data["medication_id"]),
            dcb_name=str(data["dcb_name"]).strip().lower(),
            concentration=str(data["concentration"]).strip(),
            pharmaceutical_form=str(data["pharmaceutical_form"]).strip().lower(),
            rename_component=str(data["rename_component"]),
            available_pfpb=bool(data["available_pfpb"]),
            pfpb_free=bool(data["pfpb_free"]),
            available_reme_df=bool(data["available_reme_df"]),
            dispensation_route=str(data["dispensation_route"]),
            requires_lme=bool(data["requires_lme"]),
            icd10_codes=[str(x) for x in data.get("icd10_codes", [])],
            required_documents=[str(x) for x in data.get("required_documents", [])],
            prescription_validity_days=int(data.get("prescription_validity_days", 180)),
            source_id=str(data.get("source_id", "RENAME_2024")),
            source_page=int(data.get("source_page", 1)),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class NormativeChunk:
    """Contrato de chunk normativo de portarias e protocolos (Silver Layer)."""

    chunk_id: str
    source_id: str
    document_title: str
    section: str
    page_number: int
    text: str
    dcb_mentions: list[str]
    route_category: str
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        chunk_id: str,
        source_id: str,
        document_title: str,
        section: str,
        page_number: int,
        text: str,
        dcb_mentions: list[str],
        route_category: str,
    ) -> NormativeChunk:
        clean_text = " ".join(text.strip().split())
        return cls(
            chunk_id=chunk_id,
            source_id=source_id,
            document_title=document_title,
            section=section,
            page_number=page_number,
            text=clean_text,
            dcb_mentions=[m.lower() for m in dcb_mentions],
            route_category=route_category,
            sha256=compute_sha256(clean_text),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormativeChunk:
        return cls(
            chunk_id=str(data["chunk_id"]),
            source_id=str(data["source_id"]),
            document_title=str(data["document_title"]),
            section=str(data["section"]),
            page_number=int(data["page_number"]),
            text=str(data["text"]),
            dcb_mentions=[str(x).lower() for x in data.get("dcb_mentions", [])],
            route_category=str(data["route_category"]),
            sha256=str(data.get("sha256") or compute_sha256(str(data["text"]))),
        )


@dataclass(frozen=True)
class DataManifest:
    """Contrato de manifesto de linhagem e integridade SHA-256."""

    manifest_version: str
    generated_at_utc: str
    engineering_source: str
    canonical_medications_sha256: str
    normative_chunks_sha256: str
    combined_sha256: str
    record_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalHit:
    """Resultado individual de recuperação com rastreabilidade de fonte."""

    chunk_id: str
    score: float
    source_id: str
    document_title: str
    section: str
    page_number: int
    route_category: str
    text: str
    matched_dcb: str | None = None
    retriever_name: str = "tfidf_baseline"


@dataclass(frozen=True)
class GoldenCase:
    """Caso de teste padrão-ouro (Golden Dataset) para calibração e benchmark."""

    case_id: str
    persona: str
    query: str
    expected_dcb: list[str]
    expected_route: str
    relevant_chunk_ids: list[str]
    expected_documents: list[str]
    should_abstain: bool
    is_clinical_block: bool
    reference_answer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldenCase:
        return cls(
            case_id=str(data["case_id"]),
            persona=str(data["persona"]),
            query=str(data["query"]),
            expected_dcb=[str(x).lower() for x in data.get("expected_dcb", [])],
            expected_route=str(data["expected_route"]),
            relevant_chunk_ids=[str(x) for x in data.get("relevant_chunk_ids", [])],
            expected_documents=[str(x) for x in data.get("expected_documents", [])],
            should_abstain=bool(data.get("should_abstain", False)),
            is_clinical_block=bool(data.get("is_clinical_block", False)),
            reference_answer=str(data.get("reference_answer", "")),
        )

