"""Orquestrador Multiagentes do SUS Cidadão (SPEC-05).

Pipeline de 4 agentes colaborativos em Grafo de Estado:
1. Agente Extrator & Triador Multimodal (PII Masking LGPD + Guardrail Clínico + Extração de Entidades/RA)
2. Agente Auditor Farmacêutico (RAG Híbrido: RENAME 2024 + Farmácia Popular + REME-DF)
3. Agente Consultor SISREG / SES-DF (RAG: Protocolos CPPAS / Complexo Regulador DF)
4. Agente Sintetizador do Roteiro Cidadão (Roteiro auditável + Checklist + Alertas RF08 15d/7d)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
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
    """Orientação regulatória SISREG III / CPPAS e preparo pré-exame."""

    procedure_name: str
    regulation_channel: str
    required_documents: list[str]
    priority_rule: str
    source_citation: str
    preparation_tips: list[str] = field(default_factory=list)


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
    session_id: str | None = None
    turn_count: int = 1
    remembered_history: list[str] = field(default_factory=list)
    spoken_guidance: str = ""
    follow_up_suggestions: list[str] = field(default_factory=list)

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
        ("exame do coracao", "Ecocardiograma Transtorácico"),
        ("cardiologia", "Consulta em Cardiologia"),
        ("endoscopia", "Endoscopia Digestiva Alta (EDA)"),
        ("ressonancia", "Ressonância Magnética"),
        ("tomografia", "Tomografia Computadorizada"),
        ("ultrassom", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("ultrassonografia", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("ecografia", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("exame da barriga", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("abdome", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("abdomen", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("pelvica", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("vias urinarias", "Ultrassonografia (Abdome / Pélvica / Vias Urinárias)"),
        ("exame de sangue", "Coleta Laboratorial (Exame de Sangue)"),
        ("coleta de sangue", "Coleta Laboratorial (Exame de Sangue)"),
        ("glicemia", "Coleta Laboratorial (Exame de Sangue)"),
        ("colesterol", "Coleta Laboratorial (Exame de Sangue)"),
        ("hemograma", "Coleta Laboratorial (Exame de Sangue)"),
        ("reumatologia", "Consulta em Reumatologia"),
        ("endocrinologia", "Consulta em Endocrinologia"),
    )

    _PRE_EXAM_INTENT_CUES: tuple[str, ...] = (
        "preparo",
        "preparar",
        "preparacao",
        "jejum",
        "sem comer",
        "tomar agua",
        "beber agua",
        "bexiga cheia",
        "antes do exame",
        "antes de fazer",
        "acompanhante",
        "sedacao",
        "contraste",
        "metal",
        "joia",
        "joias",
        "piercing",
        "brinco",
        "marcapasso",
        "creatinina",
        "alcool",
        "exame da barriga",
        "exame do coracao",
        "roupa",
    )

    _SISREG_SCHEDULING_CUES: tuple[str, ...] = (
        "sisreg",
        "agendar",
        "agendamento",
        "marcar",
        "regulacao",
        "encaminhamento",
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
            if token in norm_text and proc_label not in state.detected_exams:
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

    _GENERIC_QUERY_TOKENS: frozenset[str] = frozenset(
        {
            "comprimido",
            "capsula",
            "solucao",
            "injetavel",
            "spray",
            "gotas",
            "tratamento",
            "medicamento",
            "remedio",
            "preciso",
            "precisa",
            "quero",
            "posso",
            "tomar",
            "quais",
            "sobre",
            "funciona",
            "levar",
            "retirar",
            "pegar",
            "buscar",
            "preparo",
            "preparar",
            "preparacao",
            "exame",
            "exames",
            "fazer",
            "antes",
            "depois",
            "tenho",
            "como",
            "onde",
            "comer",
            "beber",
            "horas",
            "favor",
            "gostaria",
            "saber",
            "documento",
            "documentos",
            "jejum",
            "amanha",
        }
    )

    def _agent_2_pharmaceutical_auditor(self, state: OrchestratorState) -> None:
        med_matches = self.tabular_matcher.match_medications(state.sanitized_input)
        hits = self.hybrid_retriever.search(
            state.sanitized_input, top_k=3, min_score=self.min_score
        )

        # Se houver gerenciador vetorial ChromaDB, enriquece com busca semântica fundamentada
        if self.vectorstore_manager is not None:
            try:
                chroma_hits = self.vectorstore_manager.search_unified_corpus(
                    state.sanitized_input, top_k=3
                )
                norm_q = normalize_pt_text(state.sanitized_input)
                sig_tokens = [
                    tok
                    for tok in norm_q.split()
                    if len(tok) >= 5
                    and not tok.isdigit()
                    and tok not in self._GENERIC_QUERY_TOKENS
                ]
                has_prior_grounding = bool(med_matches or hits)

                for ch in chroma_hits:
                    norm_doc = normalize_pt_text(ch.document)
                    if has_prior_grounding:
                        is_grounded = ch.relevance_score >= 0.25
                    elif sig_tokens:
                        matched = sum(1 for tok in sig_tokens if tok in norm_doc)
                        needed = max(1, (len(sig_tokens) + 1) // 2)
                        is_grounded = ch.relevance_score >= 0.35 and matched >= needed
                    else:
                        is_grounded = False

                    if is_grounded:
                        hits.append(
                            RetrievalHit(
                                chunk_id=ch.id,
                                score=ch.relevance_score,
                                source_id="CHROMA_PDF_CORPUS",
                                document_title=str(ch.metadata.get("source_pdf", "PDF Oficial SUS")),
                                section=f"Pág. {ch.metadata.get('page_number', 1)} ({ch.metadata.get('category', 'normativo')})",
                                page_number=int(ch.metadata.get("page_number", 1)),
                                route_category=str(ch.metadata.get("category", "normativo")),
                                text=ch.document,
                                retriever_name="chroma_dense",
                            )
                        )
            except Exception:
                pass

        state.retrieved_hits = hits

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

    @staticmethod
    def _resolve_procedure_guidance(
        proc_label: str,
    ) -> tuple[list[str], str, list[str]]:
        """Retorna (documentos, citacao, dicas_de_preparo) para o procedimento detectado."""
        norm_proc = normalize_pt_text(proc_label)
        if "ecocardiograma" in norm_proc:
            return (
                [
                    "Pedido médico fundamentado com hipótese diagnóstica (CID-10) e sinais de alarme",
                    "Eletrocardiograma (ECG) prévio anexado",
                    "Cartão Nacional de Saúde (CNS) e CPF atualizados na UBS",
                ],
                "SISREG_CPPAS_DF — Cap. 4 Cardiologia (pág. 21)",
                [
                    "Não há necessidade de jejum para o Ecocardiograma Transtorácico padrão.",
                    "Vista roupa confortável de duas peças para facilitar o exame e leve ECG prévio.",
                    "Confirme as orientações específicas no comprovante da unidade executante e não suspenda remédios contínuos sem aval médico.",
                ],
            )
        if "cardiologia" in norm_proc:
            return (
                [
                    "Pedido médico fundamentado com hipótese diagnóstica (CID-10) e sinais de alarme",
                    "Eletrocardiograma (ECG) prévio anexado",
                    "Cartão Nacional de Saúde (CNS) e CPF atualizados na UBS",
                ],
                "SISREG_CPPAS_DF — Cap. 4 Cardiologia (pág. 21)",
                [
                    "Leve eletrocardiograma (ECG), exames recentes e a lista dos medicamentos de uso contínuo.",
                    "Não altere ou suspenda medicações antes da consulta sem orientação médica.",
                ],
            )
        if "endoscopia" in norm_proc:
            return (
                [
                    "Encaminhamento médico com justificativa clínica (P1/P2/P3) e comprovante de agendamento",
                    "Presença obrigatória de acompanhante maior de 18 anos no dia do exame",
                    "Documento oficial com foto, CPF e Cartão Nacional de Saúde (CNS)",
                ],
                "PRE_EXAME_SESDF_HUB — Endoscopia (pág. 1)",
                [
                    "Jejum alimentar padrão de referência em torno de 8 horas antes do horário marcado (conforme orientação da unidade).",
                    "Compareça obrigatoriamente com acompanhante adulto devido à sedação e não dirija após o procedimento.",
                    "Confirme o tempo exato de líquidos claros no comprovante da unidade executante e nunca suspenda remédios contínuos sem aval médico.",
                ],
            )
        if "ultrassonografia" in norm_proc:
            return (
                [
                    "Pedido médico e comprovante do agendamento da unidade executante",
                    "Exames de imagem ou laboratoriais prévios (se houver)",
                    "Documento oficial com foto, CPF e Cartão Nacional de Saúde (CNS)",
                ],
                "PRE_EXAME_SESDF_HUB — Ultrassonografia (pág. 2)",
                [
                    "Para Ultrassonografia de Abdome Total (exame da barriga): jejum alimentar padrão de referência entre 6 e 8 horas antes do horário marcado.",
                    "Para Ultrassonografia Pélvica, Próstata ou Vias Urinárias: comparecer com bexiga cheia (tomar água cerca de 1 hora antes e não urinar até o exame).",
                    "Confirme as instruções específicas impressas no comprovante da unidade executante e não suspenda remédios contínuos sem aval médico.",
                ],
            )
        if "ressonancia" in norm_proc or "tomografia" in norm_proc:
            return (
                [
                    "Pedido médico com justificativa clínica e comprovante de agendamento",
                    "Exame recente de creatinina (quando houver indicação de contraste)",
                    "Documento oficial com foto, CPF, Cartão Nacional de Saúde (CNS) e exames prévios",
                ],
                "PRE_EXAME_SESDF_HUB — Ressonância/Tomografia (pág. 3)",
                [
                    "Retire todos os objetos metálicos (brincos, alianças, piercings, relógio, celular, fivelas e cartões magnéticos) antes de entrar na sala.",
                    "Avise obrigatoriamente a equipe no agendamento e na recepção caso possua marcapasso, implantes metálicos, clipes ou claustrofobia.",
                    "Confirme necessidade de jejum e exame de creatinina para contraste no papel do agendamento da unidade e não suspenda medicamentos contínuos sem aval médico.",
                ],
            )
        if "coleta laboratorial" in norm_proc or "sangue" in norm_proc:
            return (
                [
                    "Pedido médico dos exames laboratoriais e comprovante de agendamento",
                    "Documento oficial com foto, CPF e Cartão Nacional de Saúde (CNS)",
                ],
                "PRE_EXAME_SESDF_HUB — Coleta Laboratorial (pág. 4)",
                [
                    "Evite bebida alcoólica nas 72 horas anteriores e exercícios físicos intensos na véspera da coleta de sangue.",
                    "Confirme diretamente no laboratório ou UBS se o exame solicitado exige jejum (ex.: 8 a 12h) ou se o jejum é dispensado.",
                    "Não suspenda medicações de uso contínuo sem autorização do médico solicitante.",
                ],
            )
        return (
            [
                "Encaminhamento médico com justificativa clínica para classificação de prioridade (P1/P2/P3)",
                "Resultados de exames laboratoriais prévios obrigatórios do protocolo CPPAS",
                "Cartão Nacional de Saúde (CNS), CPF e telefone atualizado para contato de regulação",
            ],
            "SISREG_CPPAS_DF — Cap. 7 Protocolos de Regulação (pág. 38)",
            [
                "Confirme eventuais exigências de preparo no comprovante da unidade executante ou na recepção da sua UBS.",
            ],
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
            docs, citation, prep_tips = self._resolve_procedure_guidance(proc)

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
                    preparation_tips=prep_tips,
                )
            )

        state.agent_trace.append(
            f"[Agente 3: Consultor SISREG] Procedimentos regulados auditados={len(state.sisreg_items)}"
        )

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Remove marcações visuais/citações acadêmicas para leitura fluida em voz PT-BR."""
        cleaned = re.sub(r"\[[^\]]*\]", "", text)
        cleaned = re.sub(r"\([^)]*pág\.[^)]*\)", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*•\s*", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _maybe_polish_voice_with_gemini(
        self, fallback_speech: str, grounded_facts: str
    ) -> str:
        """Opcionalmente humaniza spoken_guidance via Gemini Flash sem inventar fatos."""
        if os.environ.get("SUS_CIDADAO_VOICE_LLM", "0") != "1":
            return fallback_speech
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return fallback_speech
        model = os.environ.get("SUS_CIDADAO_VOICE_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        prompt = (
            "Você é a voz acolhedora do aplicativo SUS Cidadão (Distrito Federal). "
            "Reescreva em até 4 frases curtas e naturais em português brasileiro falado "
            "EXCLUSIVAMENTE com base nos fatos abaixo, sem colchetes, sem citações de páginas e "
            "sem inventar doses ou orientações médicas. Termine com uma pergunta gentil de acompanhamento.\n\n"
            f"FATOS AUDITADOS:\n{grounded_facts}\n\n"
            f"RASCUNHO:\n{fallback_speech}"
        )
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 260},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            return self._clean_for_speech(text) if text else fallback_speech
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError):
            return fallback_speech

    def _build_spoken_and_followups(
        self,
        state: OrchestratorState,
        primary_route: str,
        checklist: list[str],
        validity_alerts: list[str],
        synthesized_text: str,
    ) -> tuple[str, list[str]]:
        """Constrói spoken_guidance conversacional e sugestões de próximo turno de voz."""
        ra_note = (
            ""
            if state.detected_ra.startswith("Distrito Federal")
            else f" em {state.detected_ra}"
        )
        spoken_segments: list[str] = []
        follow_ups: list[str] = []

        if state.audited_medications:
            for med in state.audited_medications:
                clean_where = self._clean_for_speech(med.where_to_collect).rstrip(".")
                spoken_segments.append(
                    f"Sobre {med.dcb_name} {med.concentration}{ra_note}: "
                    f"a retirada gratuita ocorre via {clean_where}, "
                    f"com validade da receita de {med.validity_days} dias."
                )
            if checklist:
                spoken_segments.append(
                    f"Não esqueça de levar: {', '.join(checklist[:3])}."
                )
            if any("ALERTA CRÍTICO" in a or "ALERTA PREVENTIVO" in a for a in validity_alerts):
                spoken_segments.append(
                    "Fique atento ao prazo da sua receita ou LME para pedir a renovação antes do vencimento."
                )
            follow_ups.extend(
                [
                    "Quais documentos exatos preciso levar?",
                    "Onde fica a Farmácia de Alto Custo ou UBS mais próxima?",
                ]
            )

        if state.sisreg_items:
            for sis in state.sisreg_items:
                if primary_route == "PRE_EXAME_PREPARO" and sis.preparation_tips:
                    tips_joined = " ".join(sis.preparation_tips[:3])
                    spoken_segments.append(
                        f"Sobre o preparo para {sis.procedure_name}{ra_note}: {tips_joined}"
                    )
                    if checklist:
                        spoken_segments.append(
                            f"No dia do exame, leve {', '.join(checklist[:3])}."
                        )
                    follow_ups.extend(
                        [
                            f"Quais documentos preciso levar no dia da {sis.procedure_name}?",
                            "Preciso levar acompanhante ou posso ir sozinho?",
                        ]
                    )
                else:
                    spoken_segments.append(
                        f"Para {sis.procedure_name}{ra_note}, o pedido deve ser inserido no SISREG "
                        "pelo acolhimento ou sala de regulação da sua UBS de referência."
                    )
                    if sis.preparation_tips:
                        spoken_segments.append(sis.preparation_tips[0])
                    follow_ups.extend(
                        [
                            f"Qual o preparo necessário antes de fazer {sis.procedure_name}?",
                            "Quais documentos levo para o agendamento na UBS?",
                        ]
                    )

        if not spoken_segments and state.retrieved_hits:
            spoken_segments.append(self._clean_for_speech(state.retrieved_hits[0].text))
            follow_ups.append("Quer que eu explique os documentos necessários?")

        if spoken_segments:
            spoken_segments.append(
                "Quer que eu detalhe algum documento ou tire outra dúvida sobre o preparo?"
            )

        fallback_speech = self._clean_for_speech(" ".join(spoken_segments))
        final_speech = self._maybe_polish_voice_with_gemini(fallback_speech, synthesized_text)
        unique_followups = list(dict.fromkeys(follow_ups))[:3]
        return final_speech, unique_followups

    def _agent_4_synthesize(self, state: OrchestratorState) -> CitizenGuidanceResponse:
        if state.is_clinical_blocked:
            state.agent_trace.append(
                "[Agente 4: Sintetizador] Emitindo resposta de segurança do Guardrail Clínico."
            )
            block_spoken = self._clean_for_speech(state.clinical_block_message)
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
                spoken_guidance=block_spoken,
                follow_up_suggestions=[
                    "Quais documentos levo para falar com meu médico na UBS?",
                    "Como agendar consulta de retorno pelo SISREG?",
                ],
            )

        if (
            not state.audited_medications
            and not state.sisreg_items
            and not state.retrieved_hits
        ):
            abstention_msg = (
                "ABSTENÇÃO SEGURA: Não foram encontradas evidências nas bases oficiais auditadas "
                "(RENAME 2024, Programa Farmácia Popular do Brasil, REME-DF, Protocolos SISREG-DF ou Guia de Pré-Exames SUS-DF) "
                "de cobertura gratuita ou protocolo validado para os itens consultados. Consulte a farmácia ou o acolhimento da sua UBS."
            )
            state.agent_trace.append(
                "[Agente 4: Sintetizador] Abstenção segura acionada (score abaixo do limiar e sem match DCB)."
            )
            abstention_spoken = (
                "Não encontrei esse medicamento ou procedimento nas bases oficiais do SUS que consultei. "
                "Para sua segurança, confirme diretamente na farmácia ou no acolhimento da sua UBS se há protocolo ou cobertura específica na sua região."
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
                spoken_guidance=abstention_spoken,
                follow_up_suggestions=[
                    "Posso consultar outro exame ou medicamento?",
                    "Quais documentos levar para atendimento na UBS?",
                ],
            )

        norm_q = normalize_pt_text(state.sanitized_input)
        has_pre_exam_intent = any(cue in norm_q for cue in self._PRE_EXAM_INTENT_CUES)
        has_sisreg_scheduling = any(
            cue in norm_q for cue in self._SISREG_SCHEDULING_CUES
        )
        top_hit_is_pre_exam = bool(
            state.retrieved_hits
            and state.retrieved_hits[0].route_category
            in ("PRE_EXAME_PREPARO", "preparo_pre_exames")
        )

        # Determina rota primária preservando compatibilidade SISREG vs Pré-Exames
        if state.sisreg_items and not state.audited_medications:
            if has_pre_exam_intent or (
                top_hit_is_pre_exam and not has_sisreg_scheduling
            ):
                primary_route = "PRE_EXAME_PREPARO"
            else:
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
        elif top_hit_is_pre_exam:
            primary_route = "PRE_EXAME_PREPARO"
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
        for sis in state.sisreg_items:
            if sis.source_citation not in citations:
                citations.append(sis.source_citation)

        # Constrói texto sintetizado claro e fiel às evidências
        parts: list[str] = []
        for med in state.audited_medications:
            parts.append(
                f"• {med.dcb_name} ({med.concentration}) [{med.rename_component}]: "
                f"Retirada em {med.where_to_collect} Documentos exigidos: {', '.join(med.required_documents)}. "
                f"Validade da receita/LME: {med.validity_days} dias ({med.source_citation})."
            )
        for sis in state.sisreg_items:
            if primary_route == "PRE_EXAME_PREPARO" and sis.preparation_tips:
                parts.append(
                    f"• {sis.procedure_name} [Preparo Pré-Exame SUS-DF]: "
                    f"{' '.join(sis.preparation_tips)} "
                    f"Documentos para levar: {', '.join(sis.required_documents)} ({sis.source_citation})."
                )
            else:
                parts.append(
                    f"• {sis.procedure_name} [Regulação SISREG III]: Solicitar na {sis.regulation_channel}. "
                    f"Critério: {sis.priority_rule}. Documentos exigidos: {', '.join(sis.required_documents)} "
                    f"({sis.source_citation})."
                )
        if not parts and state.retrieved_hits:
            parts.append(state.retrieved_hits[0].text)

        synthesized = "\n".join(parts)
        spoken_guidance, follow_ups = self._build_spoken_and_followups(
            state=state,
            primary_route=primary_route,
            checklist=checklist,
            validity_alerts=validity_alerts,
            synthesized_text=synthesized,
        )
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
            spoken_guidance=spoken_guidance,
            follow_up_suggestions=follow_ups,
        )

