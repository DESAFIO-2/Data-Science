"""Orquestrador Multiagentes baseado em LangGraph (StateGraph) com Memória Persistente por Sessão.

Implementa formalmente o Grafo de Estado Colaborativo entre os 4 agentes:
1. `node_extractor_triage`: Agente 1 (Extrator & Triador Multimodal + PII Masking LGPD + Bloqueio Clínico CFM + Herança de RA)
2. `node_pharmaceutical_auditor`: Agente 2 (Auditor Farmacêutico via RAG Híbrido: CSV Tabular + Chunks Geográficos no ChromaDB)
3. `node_sisreg_consultant`: Agente 3 (Consultor SISREG III / CPPAS da SES-DF)
4. `node_citizen_synthesizer`: Agente 4 (Sintetizador do Roteiro Cidadão + Persistência SQLite LGPD + Alertas RF08)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from sus_cidadao_ds.agents.orchestrator import (
    CitizenGuidanceResponse,
    MedicationAuditItem,
    MultiAgentOrchestrator,
    OrchestratorState,
    SISREGGuidanceItem,
)
from sus_cidadao_ds.agents.session_memory import SessionContext, SQLiteSessionStore
from sus_cidadao_ds.contracts.schemas import CanonicalMedication, NormativeChunk, RetrievalHit
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager
from sus_cidadao_ds.retrieval.retrievers import normalize_pt_text


class MultiAgentGraphState(TypedDict, total=False):
    """Estado do grafo LangGraph compartilhado entre os agentes e persistido por `thread_id`."""

    raw_input: str
    days_since_emission: int
    session_id: str
    turn_count: int
    sanitized_input: str
    pii_redactions: int
    detected_pii_types: list[str]
    is_clinical_blocked: bool
    clinical_block_message: str
    detected_ra: str
    prior_ra: str
    detected_exams: list[str]
    known_medications: list[str]
    known_exams: list[str]
    sanitized_history: list[str]
    audited_medications: list[dict[str, Any]]
    sisreg_items: list[dict[str, Any]]
    retrieved_hits: list[dict[str, Any]]
    agent_trace: list[str]
    final_response: dict[str, Any]


class LangGraphMultiAgentOrchestrator:
    """Implementação do Orquestrador Multiagentes com StateGraph, Checkpointer e Memória em SQLite."""

    _FOLLOWUP_CUES: tuple[str, ...] = (
        "documento",
        "documentos",
        "onde pego",
        "onde retiro",
        "onde retirar",
        "onde buscar",
        "endereco",
        "validade",
        "vencimento",
        "estoque",
        "disponivel",
        "disso",
        "desse",
        "dessa",
        "deles",
        "delas",
        "lme",
        "levar",
        "agendar",
        "marcar",
        "preparo",
        "preparar",
        "jejum",
        "sem comer",
        "beber agua",
        "tomar agua",
        "bexiga",
        "metal",
        "joia",
        "acompanhante",
        "dirigir",
        "contraste",
        "creatinina",
        "exame",
    )

    def __init__(
        self,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        min_score: float = 0.18,
        vectorstore_manager: ChromaVectorStoreManager | None = None,
        session_db_path: Path | None = None,
    ) -> None:
        self.medications = medications
        self.chunks = chunks
        self.min_score = min_score
        self.vectorstore_manager = vectorstore_manager

        self._core = MultiAgentOrchestrator(
            medications=medications,
            chunks=chunks,
            min_score=min_score,
            vectorstore_manager=vectorstore_manager,
        )
        self.checkpointer = MemorySaver()
        self.session_store = SQLiteSessionStore(db_path=session_db_path)
        self.app = self._build_graph()

    def _build_graph(self) -> Any:
        """Constrói e compila o StateGraph do LangGraph com MemorySaver."""
        workflow = StateGraph(MultiAgentGraphState)

        workflow.add_node("extractor_triage", self._node_extractor_triage)
        workflow.add_node("pharmaceutical_auditor", self._node_pharmaceutical_auditor)
        workflow.add_node("sisreg_consultant", self._node_sisreg_consultant)
        workflow.add_node("citizen_synthesizer", self._node_citizen_synthesizer)

        workflow.add_edge(START, "extractor_triage")

        def route_after_triage(state: MultiAgentGraphState) -> str:
            if state.get("is_clinical_blocked", False):
                return "citizen_synthesizer"
            return "pharmaceutical_auditor"

        workflow.add_conditional_edges(
            "extractor_triage",
            route_after_triage,
            {
                "citizen_synthesizer": "citizen_synthesizer",
                "pharmaceutical_auditor": "pharmaceutical_auditor",
            },
        )

        workflow.add_edge("pharmaceutical_auditor", "sisreg_consultant")
        workflow.add_edge("sisreg_consultant", "citizen_synthesizer")
        workflow.add_edge("citizen_synthesizer", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _is_followup_query(self, sanitized_input: str) -> bool:
        """Identifica perguntas de continuação de conversa sem menção explícita de novo fármaco."""
        norm = normalize_pt_text(sanitized_input)
        return any(cue in norm for cue in self._FOLLOWUP_CUES)

    def _node_extractor_triage(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 1: Extrator & Triador com PII Masking, Bloqueio Clínico e Herança de RA."""
        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
        )
        self._core._agent_1_extractor_triage(orch_state)

        prior_ra = state.get("prior_ra", "Distrito Federal (Geral)")
        inherited_ra = False
        if (
            orch_state.detected_ra == "Distrito Federal (Geral)"
            and prior_ra != "Distrito Federal (Geral)"
        ):
            orch_state.detected_ra = prior_ra
            inherited_ra = True

        prior_exams = list(state.get("known_exams", []))
        merged_exams = list(prior_exams)
        for exam in orch_state.detected_exams:
            if exam not in merged_exams:
                merged_exams.append(exam)

        turn_count = int(state.get("turn_count", 0)) + 1
        history = list(state.get("sanitized_history", []))
        history.append(f"Turno {turn_count}: {orch_state.sanitized_input}")

        ra_note = f"{orch_state.detected_ra} [herdado da sessão]" if inherited_ra else orch_state.detected_ra
        return {
            "sanitized_input": orch_state.sanitized_input,
            "pii_redactions": orch_state.pii_redactions,
            "detected_pii_types": orch_state.detected_pii_types,
            "is_clinical_blocked": orch_state.is_clinical_blocked,
            "clinical_block_message": orch_state.clinical_block_message,
            "detected_ra": orch_state.detected_ra,
            "detected_exams": orch_state.detected_exams,
            "known_exams": merged_exams,
            "sanitized_history": history,
            "turn_count": turn_count,
            "agent_trace": [
                f"[LangGraph: Node 1] Turno {turn_count} triado (PII={orch_state.pii_redactions}, RA={ra_note})"
            ],
        }

    def _node_pharmaceutical_auditor(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 2: Auditor Farmacêutico com RAG Híbrido + Memória de Medicamentos da Sessão."""
        sanitized_query = state["sanitized_input"]
        prior_meds = list(state.get("known_medications", []))
        prior_exams = list(state.get("known_exams", []))
        current_exams = list(state.get("detected_exams", []))
        direct_matches = self._core.tabular_matcher.match_medications(sanitized_query)

        effective_query = sanitized_query
        inherited_context = False
        if not direct_matches and self._is_followup_query(sanitized_query):
            if prior_meds and not current_exams:
                effective_query = f"{sanitized_query} {' '.join(prior_meds)}"
                inherited_context = True
            elif prior_exams and not current_exams:
                effective_query = f"{sanitized_query} {' '.join(prior_exams)}"
                inherited_context = True

        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
            sanitized_input=effective_query,
            detected_ra=state["detected_ra"],
        )
        self._core._agent_2_pharmaceutical_auditor(orch_state)

        merged_meds = list(prior_meds)
        for med in orch_state.audited_medications:
            if med.dcb_name not in merged_meds:
                merged_meds.append(med.dcb_name)

        trace = list(state.get("agent_trace", []))
        mem_note = " | contexto herdado da sessão" if inherited_context else ""
        trace.append(
            f"[LangGraph: Node 2] Auditoria Farmacêutica (Meds={len(orch_state.audited_medications)}, "
            f"Hits={len(orch_state.retrieved_hits)}{mem_note})"
        )

        return {
            "known_medications": merged_meds,
            "audited_medications": [
                {
                    "dcb_name": m.dcb_name,
                    "concentration": m.concentration,
                    "rename_component": m.rename_component,
                    "dispensation_route": m.dispensation_route,
                    "requires_lme": m.requires_lme,
                    "validity_days": m.validity_days,
                    "where_to_collect": m.where_to_collect,
                    "required_documents": m.required_documents,
                    "source_citation": m.source_citation,
                }
                for m in orch_state.audited_medications
            ],
            "retrieved_hits": [
                {
                    "chunk_id": h.chunk_id,
                    "score": h.score,
                    "source_id": h.source_id,
                    "document_title": h.document_title,
                    "section": h.section,
                    "page_number": h.page_number,
                    "route_category": h.route_category,
                    "text": h.text,
                    "retriever_name": h.retriever_name,
                }
                for h in orch_state.retrieved_hits
            ],
            "agent_trace": trace,
        }

    def _node_sisreg_consultant(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 3: Consultor SISREG / SES-DF com reaproveitamento de exames na sessão."""
        current_exams = list(state.get("detected_exams", []))
        prior_exams = list(state.get("known_exams", []))
        has_new_meds = bool(state.get("audited_medications", []))

        effective_exams = current_exams
        if (
            not current_exams
            and not has_new_meds
            and prior_exams
            and self._is_followup_query(state.get("sanitized_input", ""))
        ):
            effective_exams = prior_exams

        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
            sanitized_input=state["sanitized_input"],
            detected_ra=state["detected_ra"],
            detected_exams=effective_exams,
        )
        self._core._agent_3_sisreg_consultant(orch_state)

        trace = list(state.get("agent_trace", []))
        trace.append(
            f"[LangGraph: Node 3] Consultor SISREG (Procedimentos={len(orch_state.sisreg_items)})"
        )

        return {
            "sisreg_items": [
                {
                    "procedure_name": it.procedure_name,
                    "regulation_channel": it.regulation_channel,
                    "required_documents": it.required_documents,
                    "priority_rule": it.priority_rule,
                    "source_citation": it.source_citation,
                    "preparation_tips": it.preparation_tips,
                }
                for it in orch_state.sisreg_items
            ],
            "agent_trace": trace,
        }

    def _node_citizen_synthesizer(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 4: Sintetizador do Roteiro Cidadão e persistência da sessão."""
        meds = [
            MedicationAuditItem(
                dcb_name=m["dcb_name"],
                concentration=m["concentration"],
                rename_component=m["rename_component"],
                dispensation_route=m["dispensation_route"],
                requires_lme=m["requires_lme"],
                validity_days=m["validity_days"],
                where_to_collect=m["where_to_collect"],
                required_documents=m["required_documents"],
                source_citation=m["source_citation"],
            )
            for m in state.get("audited_medications", [])
        ]
        sisreg = [
            SISREGGuidanceItem(
                procedure_name=it["procedure_name"],
                regulation_channel=it["regulation_channel"],
                required_documents=it["required_documents"],
                priority_rule=it["priority_rule"],
                source_citation=it["source_citation"],
                preparation_tips=list(it.get("preparation_tips", [])),
            )
            for it in state.get("sisreg_items", [])
        ]
        hits = [
            RetrievalHit(
                chunk_id=h["chunk_id"],
                score=h["score"],
                source_id=h["source_id"],
                document_title=h["document_title"],
                section=h["section"],
                page_number=h["page_number"],
                route_category=h["route_category"],
                text=h["text"],
                retriever_name=h.get("retriever_name", "langgraph_retriever"),
            )
            for h in state.get("retrieved_hits", [])
        ]

        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
            sanitized_input=state.get("sanitized_input", state["raw_input"]),
            pii_redactions=state.get("pii_redactions", 0),
            detected_pii_types=state.get("detected_pii_types", []),
            is_clinical_blocked=state.get("is_clinical_blocked", False),
            clinical_block_message=state.get("clinical_block_message", ""),
            detected_ra=state.get("detected_ra", "Distrito Federal (Geral)"),
            detected_exams=state.get("detected_exams", []),
            audited_medications=meds,
            sisreg_items=sisreg,
            retrieved_hits=hits,
            agent_trace=list(state.get("agent_trace", [])),
        )

        resp = self._core._agent_4_synthesize(orch_state)
        resp_dict = resp.to_dict()
        resp_dict["session_id"] = state.get("session_id") or None
        resp_dict["turn_count"] = int(state.get("turn_count", 1))
        resp_dict["remembered_history"] = list(state.get("sanitized_history", []))
        return {"final_response": resp_dict}

    def clear_session(self, session_id: str) -> None:
        """Apaga o histórico persistido de uma sessão."""
        self.session_store.clear_session(session_id)

    def run(
        self,
        user_input: str,
        days_since_emission: int = 166,
        session_id: str | None = None,
    ) -> CitizenGuidanceResponse:
        """Executa o grafo LangGraph com memória persistente opcional por `session_id`."""
        is_persistent_session = bool(session_id)
        effective_thread_id = session_id or f"ephemeral-{uuid.uuid4().hex}"

        prior_ctx = (
            self.session_store.load_session(session_id)
            if session_id
            else SessionContext(session_id=effective_thread_id)
        )

        initial_state: MultiAgentGraphState = {
            "raw_input": user_input,
            "days_since_emission": days_since_emission,
            "session_id": session_id or "",
            "turn_count": prior_ctx.turn_count,
            "prior_ra": prior_ctx.detected_ra,
            "known_medications": list(prior_ctx.known_medications),
            "known_exams": list(prior_ctx.known_exams),
            "sanitized_history": list(prior_ctx.sanitized_history),
            "audited_medications": [],
            "sisreg_items": [],
            "retrieved_hits": [],
        }

        output_state = self.app.invoke(
            initial_state,
            config={"configurable": {"thread_id": effective_thread_id}},
        )

        if is_persistent_session and session_id:
            updated_ctx = SessionContext(
                session_id=session_id,
                detected_ra=output_state.get("detected_ra", prior_ctx.detected_ra),
                known_medications=list(
                    output_state.get("known_medications", prior_ctx.known_medications)
                ),
                known_exams=list(output_state.get("known_exams", prior_ctx.known_exams)),
                sanitized_history=list(
                    output_state.get("sanitized_history", prior_ctx.sanitized_history)
                ),
                turn_count=int(output_state.get("turn_count", prior_ctx.turn_count + 1)),
            )
            self.session_store.save_session(updated_ctx)

        final_dict = output_state["final_response"]

        audited_meds = [
            MedicationAuditItem(
                dcb_name=m["dcb_name"],
                concentration=m["concentration"],
                rename_component=m["rename_component"],
                dispensation_route=m["dispensation_route"],
                requires_lme=m["requires_lme"],
                validity_days=m["validity_days"],
                where_to_collect=m["where_to_collect"],
                required_documents=m["required_documents"],
                source_citation=m["source_citation"],
            )
            for m in final_dict["audited_medications"]
        ]
        sisreg_items = [
            SISREGGuidanceItem(
                procedure_name=it["procedure_name"],
                regulation_channel=it["regulation_channel"],
                required_documents=it["required_documents"],
                priority_rule=it["priority_rule"],
                source_citation=it["source_citation"],
                preparation_tips=list(it.get("preparation_tips", [])),
            )
            for it in final_dict["sisreg_guidance"]
        ]
        retrieved_hits = [
            RetrievalHit(
                chunk_id=h["chunk_id"],
                score=h["score"],
                source_id=h["source_id"],
                document_title=h["document_title"],
                section=h["section"],
                page_number=h["page_number"],
                route_category=h["route_category"],
                text=h["text"],
                retriever_name=h.get("retriever_name", "langgraph_retriever"),
            )
            for h in final_dict["retrieved_chunks"]
        ]

        return CitizenGuidanceResponse(
            primary_route=final_dict["primary_route"],
            sanitized_query=final_dict["sanitized_query"],
            detected_ra=final_dict["detected_ra"],
            is_clinical_block=final_dict["is_clinical_block"],
            abstained=final_dict["abstained"],
            audited_medications=audited_meds,
            sisreg_guidance=sisreg_items,
            checklist_documents=final_dict["checklist_documents"],
            validity_alerts=final_dict["validity_alerts"],
            citations=final_dict["citations"],
            retrieved_chunks=retrieved_hits,
            synthesized_guidance=final_dict["synthesized_guidance"],
            agent_trace=final_dict["agent_trace"],
            session_id=final_dict.get("session_id"),
            turn_count=int(final_dict.get("turn_count", 1)),
            remembered_history=list(final_dict.get("remembered_history", [])),
            spoken_guidance=str(final_dict.get("spoken_guidance", "")),
            follow_up_suggestions=list(final_dict.get("follow_up_suggestions", [])),
        )
