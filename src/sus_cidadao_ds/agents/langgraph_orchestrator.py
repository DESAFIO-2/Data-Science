"""Orquestrador Multiagentes baseado em LangGraph (StateGraph) para o SUS Cidadão.

Implementa formalmente o Grafo de Estado Colaborativo entre os 4 agentes:
1. `node_extractor_triage`: Agente 1 (Extrator & Triador Multimodal + PII Masking LGPD + Bloqueio Clínico CFM)
2. `node_pharmaceutical_auditor`: Agente 2 (Auditor Farmacêutico via RAG Híbrido: CSV Tabular + Chunks Geográficos no ChromaDB)
3. `node_sisreg_consultant`: Agente 3 (Consultor SISREG III / CPPAS da SES-DF)
4. `node_citizen_synthesizer`: Agente 4 (Sintetizador do Roteiro Cidadão + Checklist + Alertas RF08)
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from sus_cidadao_ds.agents.orchestrator import (
    CitizenGuidanceResponse,
    MedicationAuditItem,
    MultiAgentOrchestrator,
    OrchestratorState,
    SISREGGuidanceItem,
)
from sus_cidadao_ds.contracts.schemas import CanonicalMedication, NormativeChunk, RetrievalHit
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager


class MultiAgentGraphState(TypedDict, total=False):
    """Estado do grafo LangGraph compartilhado entre os agentes."""

    raw_input: str
    days_since_emission: int
    sanitized_input: str
    pii_redactions: int
    detected_pii_types: list[str]
    is_clinical_blocked: bool
    clinical_block_message: str
    detected_ra: str
    detected_exams: list[str]
    audited_medications: list[dict[str, Any]]
    sisreg_items: list[dict[str, Any]]
    retrieved_hits: list[dict[str, Any]]
    agent_trace: list[str]
    final_response: dict[str, Any]


class LangGraphMultiAgentOrchestrator:
    """Implementação do Orquestrador Multiagentes com grafo de execução LangGraph."""

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

        # Reutiliza os motores analíticos encapsulados do orquestrador canônico
        self._core = MultiAgentOrchestrator(
            medications=medications,
            chunks=chunks,
            min_score=min_score,
            vectorstore_manager=vectorstore_manager,
        )
        self.app = self._build_graph()

    def _build_graph(self) -> Any:
        """Constrói e compila o StateGraph do LangGraph."""
        workflow = StateGraph(MultiAgentGraphState)

        # Adiciona os 4 nós correspondentes aos 4 agentes
        workflow.add_node("extractor_triage", self._node_extractor_triage)
        workflow.add_node("pharmaceutical_auditor", self._node_pharmaceutical_auditor)
        workflow.add_node("sisreg_consultant", self._node_sisreg_consultant)
        workflow.add_node("citizen_synthesizer", self._node_citizen_synthesizer)

        # Arestas e roteamento condicional (Guardrail de Bloqueio Clínico)
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

        return workflow.compile()

    def _node_extractor_triage(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 1: Extrator & Triador Multimodal com PII Masking e Guardrail Clínico."""
        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
        )
        self._core._agent_1_extractor_triage(orch_state)

        return {
            "sanitized_input": orch_state.sanitized_input,
            "pii_redactions": orch_state.pii_redactions,
            "detected_pii_types": orch_state.detected_pii_types,
            "is_clinical_blocked": orch_state.is_clinical_blocked,
            "clinical_block_message": orch_state.clinical_block_message,
            "detected_ra": orch_state.detected_ra,
            "detected_exams": orch_state.detected_exams,
            "agent_trace": [
                f"[LangGraph: Node 1] Triagem concluída (PII={orch_state.pii_redactions}, RA={orch_state.detected_ra})"
            ],
        }

    def _node_pharmaceutical_auditor(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 2: Auditor Farmacêutico via RAG Híbrido e consulta ao ChromaDB."""
        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
            sanitized_input=state["sanitized_input"],
            detected_ra=state["detected_ra"],
        )
        self._core._agent_2_pharmaceutical_auditor(orch_state)

        trace = list(state.get("agent_trace", []))
        trace.append(
            f"[LangGraph: Node 2] Auditoria Farmacêutica (Meds={len(orch_state.audited_medications)}, "
            f"Hits={len(orch_state.retrieved_hits)})"
        )

        return {
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
        """Nó do Agente 3: Consultor SISREG / SES-DF para exames e consultas especializadas."""
        orch_state = OrchestratorState(
            raw_input=state["raw_input"],
            days_since_emission=state.get("days_since_emission", 166),
            sanitized_input=state["sanitized_input"],
            detected_ra=state["detected_ra"],
            detected_exams=state.get("detected_exams", []),
        )
        self._core._agent_3_sisreg_consultant(orch_state)

        trace = list(state.get("agent_trace", []))
        trace.append(f"[LangGraph: Node 3] Consultor SISREG (Procedimentos={len(orch_state.sisreg_items)})")

        return {
            "sisreg_items": [
                {
                    "procedure_name": it.procedure_name,
                    "regulation_channel": it.regulation_channel,
                    "required_documents": it.required_documents,
                    "priority_rule": it.priority_rule,
                    "source_citation": it.source_citation,
                }
                for it in orch_state.sisreg_items
            ],
            "agent_trace": trace,
        }

    def _node_citizen_synthesizer(self, state: MultiAgentGraphState) -> MultiAgentGraphState:
        """Nó do Agente 4: Sintetizador do Roteiro Cidadão e montagem da resposta final."""
        # Reconstrói estado tipado para sintetização final
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
        return {"final_response": resp.to_dict()}

    def run(self, user_input: str, days_since_emission: int = 166) -> CitizenGuidanceResponse:
        """Executa o grafo compilado do LangGraph ponta a ponta."""
        initial_state: MultiAgentGraphState = {
            "raw_input": user_input,
            "days_since_emission": days_since_emission,
        }
        output_state = self.app.invoke(initial_state)
        final_dict = output_state["final_response"]

        # Converte de volta para CitizenGuidanceResponse
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
        )
