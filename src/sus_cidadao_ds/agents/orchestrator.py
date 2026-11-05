"""Orquestrador Multiagentes do SUS Cidadão (SPEC-05).

Pipeline de 4 agentes colaborativos em Grafo de Estado:
1. Agente Extrator & Triador Multimodal (PII Masking LGPD + Guardrail Clínico + Extração de Entidades/RA)
2. Agente Auditor Farmacêutico (RAG Híbrido: RENAME 2024 + Farmácia Popular + REME-DF)
3. Agente Consultor SISREG / SES-DF (RAG: Protocolos CPPAS / Complexo Regulador DF)
4. Agente Sintetizador do Roteiro Cidadão (Roteiro auditável + Checklist + Alertas RF08 15d/7d)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sus_cidadao_ds.contracts.schemas import (
    CanonicalMedication,
    NormativeChunk,
    RetrievalHit,
)
from sus_cidadao_ds.guardrails.clinical_blocker import ClinicalBlocker
from sus_cidadao_ds.guardrails.pii_masker import PIIMasker
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager
from sus_cidadao_ds.retrieval.retrievers import (
    HybridRetriever,
    TabularDCBMatcher,
    normalize_pt_text,
)


@dataclass(frozen=True)
class MedicationAuditItem:
    """Resultado da auditoria farmacêutica para um medicamento individual."""

    dcb_name: str
    concentration: str
    rename_component: str
    dispensation_route: str
    requires_lme: bool
    validity_days: int
    where_to_collect: str
    required_documents: list[str]
    source_citation: str


@dataclass(frozen=True)
class SISREGGuidanceItem:
    """Orientação regulatória SISREG III / CPPAS para exame ou consulta especializada."""

    procedure_name: str
    regulation_channel: str
    required_documents: list[str]
    priority_rule: str
    source_citation: str


@dataclass
class OrchestratorState:
    """Estado compartilhado entre os 4 agentes do Grafo de Orquestração."""

    raw_input: str
    days_since_emission: int = 0
    sanitized_input: str = ""
    pii_redactions: int = 0
    detected_pii_types: list[str] = field(default_factory=list)
    is_clinical_blocked: bool = False
    clinical_block_message: str = ""
    detected_ra: str = "Distrito Federal (Geral)"
    detected_exams: list[str] = field(default_factory=list)
    audited_medications: list[MedicationAuditItem] = field(default_factory=list)
    sisreg_items: list[SISREGGuidanceItem] = field(default_factory=list)
    retrieved_hits: list[RetrievalHit] = field(default_factory=list)
    agent_trace: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CitizenGuidanceResponse:
    """Resposta final consolidada pelo Agente 4 (Sintetizador do Roteiro Cidadão)."""

    primary_route: str
    sanitized_query: str
    detected_ra: str
    is_clinical_block: bool
    abstained: bool
    audited_medications: list[MedicationAuditItem]
    sisreg_guidance: list[SISREGGuidanceItem]
    checklist_documents: list[str]
    validity_alerts: list[str]
    citations: list[str]
    retrieved_chunks: list[RetrievalHit]
    synthesized_guidance: str
    agent_trace: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultiAgentOrchestrator:
    """Orquestra os 4 agentes especializados do SUS Cidadão com RAG Híbrido e Guardrails."""

    _DF_RAS: tuple[tuple[str, str, str], ...] = (
        ("ceilandia", "Ceilândia - DF", "Farmácia de Alto Custo de Ceilândia (EQNN 18/20)"),
        ("samambaia", "Samambaia - DF", "Farmácia de Alto Custo de Ceilândia (EQNN 18/20 — mais próxima)"),
        ("taguatinga", "Taguatinga - DF", "Farmácia de Alto Custo de Ceilândia (EQNN 18/20 — mais próxima)"),
        ("gama", "Gama - DF", "Farmácia de Alto Custo do Gama (Praça 1, Setor Leste)"),
        ("santa maria", "Santa Maria - DF", "Farmácia de Alto Custo do Gama (Setor Leste)"),
        ("asa sul", "Plano Piloto (Asa Sul) - DF", "Farmácia de Alto Custo da Estação 102 Sul do Metrô"),
        ("plano piloto", "Plano Piloto - DF", "Farmácia de Alto Custo da Estação 102 Sul do Metrô"),
    )

    _SISREG_PROCEDURES: tuple[tuple[str, str], ...] = (
        ("ecocardiograma", "Ecocardiograma Transtorácico"),
        ("cardiologia", "Consulta em Cardiologia"),
        ("endoscopia", "Endoscopia Digestiva Alta (EDA)"),
        ("ressonancia", "Ressonância Magnética"),
        ("reumatologia", "Consulta em Reumatologia"),
        ("endocrinologia", "Consulta em Endocrinologia"),
    )

    def __init__(
        self,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        min_score: float = 0.18,
        vectorstore_manager: ChromaVectorStoreManager | None = None,
    ) -> None:
        self.medications = medications
        self.chunks = chunks
        self.min_score = min_score
        self.vectorstore_manager = vectorstore_manager
        self.pii_masker = PIIMasker()
        self.clinical_blocker = ClinicalBlocker()
        self.tabular_matcher = TabularDCBMatcher(medications)
        self.hybrid_retriever = HybridRetriever(medications, chunks)

    def run(
        self,
        user_input: str,
        days_since_emission: int = 166,
    ) -> CitizenGuidanceResponse:
        """Executa sequencialmente o grafo dos 4 agentes sobre a entrada do usuário."""
        state = OrchestratorState(
            raw_input=user_input, days_since_emission=days_since_emission
        )

        # Nó 1: Agente Extrator & Triador Multimodal + Guardrails
        self._agent_1_extractor_triage(state)
        if state.is_clinical_blocked:
            return self._agent_4_synthesize(state)

        # Nó 2: Agente Auditor Farmacêutico (RAG Híbrido: RENAME + PFPB + REME-DF)
        self._agent_2_pharmaceutical_auditor(state)

        # Nó 3: Agente Consultor SISREG / SES-DF
        self._agent_3_sisreg_consultant(state)

        # Nó 4: Agente Sintetizador do Roteiro Cidadão
        return self._agent_4_synthesize(state)

    def _agent_1_extractor_triage(self, state: OrchestratorState) -> None:
        mask_res = self.pii_masker.mask(state.raw_input)
        state.sanitized_input = mask_res.sanitized_text
        state.pii_redactions = mask_res.redaction_count
        state.detected_pii_types = mask_res.detected_pii_types

        clin_res = self.clinical_blocker.inspect(state.sanitized_input)
        if clin_res.is_blocked:
            state.is_clinical_blocked = True
            state.clinical_block_message = clin_res.safe_response
            state.agent_trace.append(
                f"[Agente 1: Extrator & Triador] BLOQUEIO ÉTICO ACIONADO ({clin_res.reason})."
            )
            return

        norm_text = normalize_pt_text(state.sanitized_input)
        for token, ra_label, _ in self._DF_RAS:
            if token in norm_text:
                state.detected_ra = ra_label
                break

        for token, proc_label in self._SISREG_PROCEDURES:
            if token in norm_text:
                state.detected_exams.append(proc_label)

        state.agent_trace.append(
            f"[Agente 1: Extrator & Triador] PII redigidos={state.pii_redactions} "
            f"| RA={state.detected_ra} | Exames/Consultas detectados={len(state.detected_exams)}"
        )

    def _resolve_ceaf_unit(self, ra_label: str) -> str:
        norm_ra = normalize_pt_text(ra_label)
        for token, _, ceaf_unit in self._DF_RAS:
            if token in norm_ra:
                return ceaf_unit
        return "Farmácia de Alto Custo (CEAF-DF: unidades Estação 102 Sul, Ceilândia ou Gama)"

    def _agent_2_pharmaceutical_auditor(self, state: OrchestratorState) -> None:
        hits = self.hybrid_retriever.search(
            state.sanitized_input, top_k=3, min_score=self.min_score
        )

        # Se houver gerenciador vetorial ChromaDB, enriquece com busca semântica sobre o corpus de PDFs
        if self.vectorstore_manager is not None:
            try:
                chroma_hits = self.vectorstore_manager.search_unified_corpus(
                    state.sanitized_input, top_k=3
                )
                for ch in chroma_hits:
                    if ch.relevance_score >= 0.22:
                        hits.append(
                            RetrievalHit(
                                chunk_id=ch.id,
                                document_title=str(ch.metadata.get("source_pdf", "PDF Oficial SUS")),
                                section=f"Pág. {ch.metadata.get('page_number', 1)} ({ch.metadata.get('category', 'normativo')})",
                                route_category=str(ch.metadata.get("category", "normativo")),
                                text=ch.document,
                                score=ch.relevance_score,
                            )
                        )
            except Exception:
                pass

        state.retrieved_hits = hits

        med_matches = self.tabular_matcher.match_medications(state.sanitized_input)
        ceaf_unit = self._resolve_ceaf_unit(state.detected_ra)

        for _, med in med_matches:
            if med.dispensation_route == "FARMACIA_POPULAR":
                where = (
                    "Programa Farmácia Popular do Brasil (qualquer drogaria privada credenciada "
                    f"'Aqui Tem Farmácia Popular' em {state.detected_ra} com 100% de gratuidade via CPF) "
                    "ou Farmácia da UBS de referência."
                )
            elif med.dispensation_route == "UBS_ATENCAO_PRIMARIA":
                where = (
                    f"Farmácia da Unidade Básica de Saúde (UBS) de referência em {state.detected_ra} "
                    "(item exclusivo da Atenção Primária — não disponível na rede privada Farmácia Popular)."
                )
            else:
                live_stock_info = ""
                if self.vectorstore_manager is not None:
                    try:
                        stock_hits = self.vectorstore_manager.search(
                            query=f"{med.dcb_name} {ceaf_unit}",
                            collection_name=self.vectorstore_manager.COLLECTION_STOCK,
                            top_k=1,
                        )
                        if stock_hits and stock_hits[0].relevance_score > 0.40:
                            live_disp = stock_hits[0].metadata.get("disp_estoque", "")
                            if live_disp:
                                live_stock_info = f" [InfoSaúde em Tempo Real: {live_disp}]"
                    except Exception:
                        pass

                where = (
                    f"{ceaf_unit} — Componente Especializado da Assistência Farmacêutica (CEAF){live_stock_info}, "
                    "mediante abertura/renovação de processo com LME."
                )

            citation = f"{med.source_id} (pág. {med.source_page})"
            state.audited_medications.append(
                MedicationAuditItem(
                    dcb_name=med.dcb_name,
                    concentration=med.concentration,
                    rename_component=med.rename_component,
                    dispensation_route=med.dispensation_route,
                    requires_lme=med.requires_lme,
                    validity_days=med.prescription_validity_days,
                    where_to_collect=where,
                    required_documents=list(med.required_documents),
                    source_citation=citation,
                )
            )

        state.agent_trace.append(
            f"[Agente 2: Auditor Farmacêutico] Medicamentos auditados={len(state.audited_medications)} "
            f"| Chunks normativos recuperados={len(state.retrieved_hits)}"
        )

    def _agent_3_sisreg_consultant(self, state: OrchestratorState) -> None:
        norm_text = normalize_pt_text(state.sanitized_input)
        is_sisreg_query = bool(state.detected_exams) or "sisreg" in norm_text

        if not is_sisreg_query:
            state.agent_trace.append(
                "[Agente 3: Consultor SISREG] Nenhum exame ou consulta especializada solicitado."
            )
            return

        procedures = state.detected_exams or ["Exame / Consulta Especializada via SISREG"]
        for proc in procedures:
            norm_proc = normalize_pt_text(proc)
            if "ecocardiograma" in norm_proc or "cardiologia" in norm_proc:
                docs = [
                    "Pedido médico fundamentado com hipótese diagnóstica (CID-10) e sinais de alarme",
                    "Eletrocardiograma (ECG) prévio anexado",
                    "Cartão Nacional de Saúde (CNS) e CPF atualizados na UBS",
                ]
                citation = "SISREG_CPPAS_DF — Cap. 4 Cardiologia (pág. 21)"
            else:
                docs = [
                    "Encaminhamento médico com justificativa clínica para classificação de prioridade (P1/P2/P3)",
                    "Resultados de exames laboratoriais prévios obrigatórios do protocolo CPPAS",
                    "Cartão Nacional de Saúde (CNS), CPF e telefone atualizado para contato de regulação",
                ]
                citation = "SISREG_CPPAS_DF — Cap. 7 Protocolos de Regulação (pág. 38)"

            state.sisreg_items.append(
                SISREGGuidanceItem(
                    procedure_name=proc,
                    regulation_channel=(
                        f"Sala de Regulação / Acolhimento da UBS de referência em {state.detected_ra} "
                        "(inserção no sistema SISREG III / Complexo Regulador DF)"
                    ),
                    required_documents=docs,
                    priority_rule="Classificação de risco regulatório: P1 (Vermelha/Urgente), P2 (Amarela), P3 (Verde)",
                    source_citation=citation,
                )
            )

        state.agent_trace.append(
            f"[Agente 3: Consultor SISREG] Procedimentos regulados auditados={len(state.sisreg_items)}"
        )

    def _agent_4_synthesize(self, state: OrchestratorState) -> CitizenGuidanceResponse:
        if state.is_clinical_blocked:
            state.agent_trace.append(
                "[Agente 4: Sintetizador] Emitindo resposta de segurança do Guardrail Clínico."
            )
            return CitizenGuidanceResponse(
                primary_route="BLOQUEIO_CLINICO_ATO_MEDICO",
                sanitized_query=state.sanitized_input,
                detected_ra=state.detected_ra,
                is_clinical_block=True,
                abstained=True,
                audited_medications=[],
                sisreg_guidance=[],
                checklist_documents=[],
                validity_alerts=[],
                citations=[],
                retrieved_chunks=[],
                synthesized_guidance=state.clinical_block_message,
                agent_trace=list(state.agent_trace),
            )

        if (
            not state.audited_medications
            and not state.sisreg_items
            and not state.retrieved_hits
        ):
            abstention_msg = (
                "ABSTENÇÃO SEGURA: Não foram encontradas evidências nas bases oficiais auditadas "
                "(RENAME 2024, Programa Farmácia Popular do Brasil, REME-DF ou Protocolos SISREG-DF) "
                "de cobertura gratuita para os itens consultados. Consulte a farmácia da sua UBS."
            )
            state.agent_trace.append(
                "[Agente 4: Sintetizador] Abstenção segura acionada (score abaixo do limiar e sem match DCB)."
            )
            return CitizenGuidanceResponse(
                primary_route="ABSTENCAO_FORA_ELENCO",
                sanitized_query=state.sanitized_input,
                detected_ra=state.detected_ra,
                is_clinical_block=False,
                abstained=True,
                audited_medications=[],
                sisreg_guidance=[],
                checklist_documents=[],
                validity_alerts=[],
                citations=[],
                retrieved_chunks=[],
                synthesized_guidance=abstention_msg,
                agent_trace=list(state.agent_trace),
            )

        # Determina rota primária
        if state.sisreg_items and not state.audited_medications:
            primary_route = "SISREG_EXAME_CONSULTA"
        elif any(m.dispensation_route == "ALTO_CUSTO_CEAF" for m in state.audited_medications):
            primary_route = (
                "ALTO_CUSTO_CEAF"
                if len({m.dispensation_route for m in state.audited_medications}) == 1
                else "ROTEIRO_MISTO_MULTICANAL"
            )
        elif any(
            m.dispensation_route == "UBS_ATENCAO_PRIMARIA"
            for m in state.audited_medications
        ):
            primary_route = (
                "UBS_ATENCAO_PRIMARIA"
                if len({m.dispensation_route for m in state.audited_medications}) == 1
                else "ROTEIRO_MISTO_MULTICANAL"
            )
        elif state.audited_medications:
            primary_route = "FARMACIA_POPULAR"
        else:
            primary_route = state.retrieved_hits[0].route_category

        # Consolida checklist documental sem duplicatas
        checklist: list[str] = []
        for med in state.audited_medications:
            for doc in med.required_documents:
                if doc not in checklist:
                    checklist.append(doc)
        for sis in state.sisreg_items:
            for doc in sis.required_documents:
                if doc not in checklist:
                    checklist.append(doc)

        # Alertas preventivos da Carteira Digital (RF08: 15 e 7 dias antes do vencimento)
        validity_alerts: list[str] = []
        for med in state.audited_medications:
            remaining = med.validity_days - state.days_since_emission
            if remaining <= 7:
                validity_alerts.append(
                    f"ALERTA CRÍTICO (<= 7 dias): A receita/LME de {med.dcb_name} ({med.concentration}) "
                    f"vence em {max(0, remaining)} dias (validade total: {med.validity_days} dias). "
                    "Agende renovação imediata!"
                )
            elif remaining <= 15:
                validity_alerts.append(
                    f"ALERTA PREVENTIVO (<= 15 dias): A receita/LME de {med.dcb_name} ({med.concentration}) "
                    f"vence em {remaining} dias (validade total: {med.validity_days} dias). "
                    "Providencie renovação da receita/LME."
                )
            else:
                validity_alerts.append(
                    f"VIGÊNCIA ATIVA: Receita de {med.dcb_name} válida por {med.validity_days} dias."
                )

        citations: list[str] = []
        for hit in state.retrieved_hits:
            cit = f"{hit.chunk_id} — {hit.document_title} (pág. {hit.page_number})"
            if cit not in citations:
                citations.append(cit)
        for med in state.audited_medications:
            if med.source_citation not in citations:
                citations.append(med.source_citation)

        # Constrói texto sintetizado claro e fiel às evidências
        parts: list[str] = []
        for med in state.audited_medications:
            parts.append(
                f"• {med.dcb_name} ({med.concentration}) [{med.rename_component}]: "
                f"Retirada em {med.where_to_collect} Documentos exigidos: {', '.join(med.required_documents)}. "
                f"Validade da receita/LME: {med.validity_days} dias ({med.source_citation})."
            )
        for sis in state.sisreg_items:
            parts.append(
                f"• {sis.procedure_name} [Regulação SISREG III]: Solicitar na {sis.regulation_channel}. "
                f"Critério: {sis.priority_rule}. Documentos exigidos: {', '.join(sis.required_documents)} "
                f"({sis.source_citation})."
            )
        if not parts and state.retrieved_hits:
            parts.append(state.retrieved_hits[0].text)

        synthesized = "\n".join(parts)
        state.agent_trace.append(
            f"[Agente 4: Sintetizador] Roteiro Cidadão gerado com rota={primary_route} e {len(citations)} citações."
        )

        return CitizenGuidanceResponse(
            primary_route=primary_route,
            sanitized_query=state.sanitized_input,
            detected_ra=state.detected_ra,
            is_clinical_block=False,
            abstained=False,
            audited_medications=list(state.audited_medications),
            sisreg_guidance=list(state.sisreg_items),
            checklist_documents=checklist,
            validity_alerts=validity_alerts,
            citations=citations,
            retrieved_chunks=list(state.retrieved_hits),
            synthesized_guidance=synthesized,
            agent_trace=list(state.agent_trace),
        )

