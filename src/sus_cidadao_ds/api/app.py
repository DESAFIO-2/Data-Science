"""API FastAPI para conectar o Orquestrador RAG + Memória + Modo Voz ao aplicativo SUS Cidadão."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sus_cidadao_ds.agents.langgraph_orchestrator import LangGraphMultiAgentOrchestrator
from sus_cidadao_ds.core.config import ProjectPaths
from sus_cidadao_ds.ingestion.infosaude_client import haversine_km
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager
from sus_cidadao_ds.retrieval.embeddings import PortugueseClinicalEmbeddingFunction
from sus_cidadao_ds.retrieval.retrievers import TabularDCBMatcher, normalize_pt_text
from sus_cidadao_ds.sync.data_sync import DataSynchronizer
from sus_cidadao_ds.voice.audio_engine import VoiceEngine


class ChatRequest(BaseModel):
    """Payload JSON para turno conversacional no aplicativo."""

    text: str = Field(..., min_length=1, description="Pergunta ou solicitação do cidadão.")
    session_id: str | None = Field(
        default=None,
        description="Identificador persistente da sessão. Gerado automaticamente se omitido.",
    )
    days_since_emission: int = Field(
        default=166,
        ge=0,
        le=3650,
        description="Dias decorridos desde a emissão da receita/LME (para alertas RF08).",
    )
    include_audio: bool = Field(
        default=False,
        description="Quando True, sintetiza também o áudio PT-BR de `spoken_guidance`.",
    )


class ConversationTurnResponse(BaseModel):
    """Contrato estruturado retornado ao aplicativo web/mobile."""

    session_id: str
    turn_count: int
    transcript: str
    stt_provider: str
    primary_route: str
    sanitized_query: str
    detected_ra: str
    is_clinical_block: bool
    abstained: bool
    synthesized_guidance: str
    spoken_guidance: str
    follow_up_suggestions: list[str]
    preparation_tips: list[str]
    checklist_documents: list[str]
    validity_alerts: list[str]
    citations: list[str]
    audited_medications: list[dict[str, Any]]
    sisreg_guidance: list[dict[str, Any]]
    retrieved_chunks: list[dict[str, Any]]
    remembered_history: list[str]
    agent_trace: list[str]
    tts_audio_base64: str | None = None
    tts_mime_type: str = "text/plain"
    tts_provider: str = "none"
    tts_voice: str = VoiceEngine.DEFAULT_TTS_VOICE
    tts_fallback_reason: str | None = None


class SessionStateResponse(BaseModel):
    """Resumo seguro LGPD da memória persistida de uma sessão."""

    session_id: str
    detected_ra: str
    known_medications: list[str]
    known_exams: list[str]
    sanitized_history: list[str]
    turn_count: int


class PrescriptionItemInput(BaseModel):
    """Item estruturado enviado pelo app para auditoria normativa de receita."""

    nome_digitado: str = Field(..., min_length=1, max_length=240)
    principio_ativo_dcb: str | None = None
    concentracao: str | None = None
    forma_farmaceutica: str | None = None
    posologia: str | None = None
    quantidade_prescrita: str | None = None


class PrescriptionAuditRequestDTO(BaseModel):
    """Contrato `/api/v1/prescriptions/audit` compatível com DESAFIO-2/development e App Mobile."""

    itens: list[PrescriptionItemInput] = Field(..., min_length=1)
    data_emissao: date | None = None
    regiao_administrativa: str = "Distrito Federal (Geral)"
    tipo_prescritor: str = "SUS"
    pergunta_adicional: str | None = None


class ItemRoteiroDTO(BaseModel):
    """Item individual auditado retornado para a Carteira Digital do app."""

    medicamento: str
    principio_ativo_dcb: str
    via_retirada: str
    local_sugerido: str
    o_que_levar: list[str]
    dias_validade_receita: int | None = None
    data_limite_validade: date | None = None
    dias_restantes: int | None = None
    alerta_vencimento_proximo: bool = False
    citacao_normativa: str


class PrescriptionAuditResponseDTO(BaseModel):
    """Resposta estruturada de auditoria de receita médica."""

    sucesso: bool
    regiao_administrativa: str
    itens: list[ItemRoteiroDTO]
    resumo_acolhedor: str
    aviso_preservacao_ato_medico: str
    solicitou_automedicacao: bool = False


def _load_default_orchestrator(paths: ProjectPaths) -> LangGraphMultiAgentOrchestrator:
    """Inicializa sincronizador Gold v9 + ChromaDB PT-BR + Orquestrador LangGraph."""
    paths.ensure_dirs()
    sync = DataSynchronizer(paths)
    try:
        medications = sync.load_medications()
        chunks = sync.load_chunks()
    except FileNotFoundError:
        sync.sync()
        medications = sync.load_medications()
        chunks = sync.load_chunks()
    evidences_v2 = sync.load_evidence_chunks_v2()

    vsm: ChromaVectorStoreManager | None = None
    try:
        vsm = ChromaVectorStoreManager(vectorstore_dir=paths.data_dir / "vectorstore")
    except Exception:
        vsm = None

    return LangGraphMultiAgentOrchestrator(
        medications=medications,
        chunks=chunks,
        min_score=0.18,
        vectorstore_manager=vsm,
        evidences_v2=evidences_v2,
    )


def create_app(
    paths: ProjectPaths | None = None,
    orchestrator: LangGraphMultiAgentOrchestrator | None = None,
    voice_engine: VoiceEngine | None = None,
) -> FastAPI:
    """Constrói a aplicação FastAPI pronta para produção e prototipagem por voz."""
    resolved_paths = paths or ProjectPaths.from_root()
    orch = orchestrator or _load_default_orchestrator(resolved_paths)
    voice = voice_engine or VoiceEngine()
    ui_html_path = Path(__file__).resolve().parent / "voice_ui.html"

    application = FastAPI(
        title="SUS Cidadão (NavegaSUS) API",
        version="0.2.0",
        description=(
            "Orquestrador Multiagentes RAG + Memória Persistente LGPD + Modo Voz (STT/TTS PT-BR) "
            "e Preparo Pré-Exame SUS-DF."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def _execute_turn(
        user_text: str,
        session_id: str | None,
        days_since_emission: int,
        stt_provider: str,
        synthesize_audio: bool,
    ) -> ConversationTurnResponse:
        effective_session = (session_id or "").strip() or f"sess-{uuid.uuid4().hex[:10]}"
        result = orch.run(
            user_input=user_text,
            days_since_emission=days_since_emission,
            session_id=effective_session,
        )

        prep_tips: list[str] = []
        for sis in result.sisreg_guidance:
            for tip in sis.preparation_tips:
                if tip not in prep_tips:
                    prep_tips.append(tip)

        tts_audio_b64: str | None = None
        tts_mime = "text/plain"
        tts_provider = "disabled"
        tts_voice = voice.tts_voice
        tts_reason: str | None = None
        if synthesize_audio:
            spoken_text = result.spoken_guidance or result.synthesized_guidance
            tts_res = await voice.async_synthesize_speech(spoken_text)
            tts_audio_b64 = tts_res.audio_base64
            tts_mime = tts_res.mime_type
            tts_provider = tts_res.provider
            tts_voice = tts_res.voice
            tts_reason = tts_res.fallback_reason

        return ConversationTurnResponse(
            session_id=result.session_id or effective_session,
            turn_count=result.turn_count,
            transcript=user_text,
            stt_provider=stt_provider,
            primary_route=result.primary_route,
            sanitized_query=result.sanitized_query,
            detected_ra=result.detected_ra,
            is_clinical_block=result.is_clinical_block,
            abstained=result.abstained,
            synthesized_guidance=result.synthesized_guidance,
            spoken_guidance=result.spoken_guidance or result.synthesized_guidance,
            follow_up_suggestions=result.follow_up_suggestions,
            preparation_tips=prep_tips,
            checklist_documents=result.checklist_documents,
            validity_alerts=result.validity_alerts,
            citations=result.citations,
            audited_medications=[asdict(m) for m in result.audited_medications],
            sisreg_guidance=[asdict(s) for s in result.sisreg_guidance],
            retrieved_chunks=[asdict(h) for h in result.retrieved_chunks],
            remembered_history=result.remembered_history,
            agent_trace=result.agent_trace,
            tts_audio_base64=tts_audio_b64,
            tts_mime_type=tts_mime,
            tts_provider=tts_provider,
            tts_voice=tts_voice,
            tts_fallback_reason=tts_reason,
        )

    @application.get("/health")
    def health() -> dict[str, Any]:
        """Verifica disponibilidade da API, sessões SQLite, embeddings e voz."""
        chroma_stats: dict[str, Any] = {}
        vsm = orch._core.vectorstore_manager
        if vsm is not None:
            try:
                chroma_stats = {
                    col.name: col.count() for col in vsm.client.list_collections()
                }
            except Exception:
                chroma_stats = {"status": "unavailable"}

        return {
            "status": "ok",
            "service": "sus-cidadao-navegasus-api",
            "embedding_profile": PortugueseClinicalEmbeddingFunction().get_config(),
            "chroma_collections": chroma_stats,
            "stt_provider_configured": voice.stt_provider_configured(),
            "tts_voice": voice.tts_voice,
        }

    @application.get("/", response_class=HTMLResponse)
    @application.get("/voice-demo", response_class=HTMLResponse)
    def voice_demo() -> HTMLResponse:
        """Serve o protótipo Web interativo com microfone PT-BR em tempo real."""
        if not ui_html_path.exists():
            raise HTTPException(status_code=404, detail="Interface voice_ui.html não encontrada.")
        return HTMLResponse(content=ui_html_path.read_text(encoding="utf-8"))

    @application.post("/v1/chat", response_model=ConversationTurnResponse)
    async def chat_turn(payload: ChatRequest) -> ConversationTurnResponse:
        """Executa um turno conversacional textual com memória de sessão."""
        clean_text = payload.text.strip()
        if not clean_text:
            raise HTTPException(status_code=422, detail="O campo `text` não pode estar vazio.")
        return await _execute_turn(
            user_text=clean_text,
            session_id=payload.session_id,
            days_since_emission=payload.days_since_emission,
            stt_provider="text_input",
            synthesize_audio=payload.include_audio,
        )

    @application.post("/v1/voice-turn", response_model=ConversationTurnResponse)
    async def voice_turn(
        text: Annotated[str | None, Form()] = None,
        audio: Annotated[UploadFile | None, File()] = None,
        session_id: Annotated[str | None, Form()] = None,
        days_since_emission: Annotated[int, Form()] = 166,
        synthesize_audio: Annotated[bool, Form()] = True,
    ) -> ConversationTurnResponse:
        """Executa um turno de voz completo (áudio/texto -> LangGraph -> TTS PT-BR)."""
        clean_text = (text or "").strip()
        stt_provider = "client_transcript"

        if not clean_text:
            if audio is None:
                raise HTTPException(
                    status_code=422,
                    detail="Envie `text` (transcrição) ou arquivo `audio` para iniciar o turno de voz.",
                )
            raw_bytes = await audio.read()
            stt_res = voice.transcribe_audio(
                audio_bytes=raw_bytes,
                filename=audio.filename or "voice.webm",
                mime_type=audio.content_type or "audio/webm",
            )
            if stt_res.error or not stt_res.text:
                raise HTTPException(
                    status_code=400,
                    detail=stt_res.error or "Não foi possível transcrever o áudio enviado.",
                )
            clean_text = stt_res.text
            stt_provider = stt_res.provider

        return await _execute_turn(
            user_text=clean_text,
            session_id=session_id,
            days_since_emission=days_since_emission,
            stt_provider=stt_provider,
            synthesize_audio=synthesize_audio,
        )

    @application.get("/v1/sessions/{session_id}", response_model=SessionStateResponse)
    def get_session(session_id: str) -> SessionStateResponse:
        """Inspeciona o contexto sanitizado salvo na memória persistente da sessão."""
        ctx = orch.session_store.load_session(session_id)
        return SessionStateResponse(
            session_id=ctx.session_id,
            detected_ra=ctx.detected_ra,
            known_medications=ctx.known_medications,
            known_exams=ctx.known_exams,
            sanitized_history=ctx.sanitized_history,
            turn_count=ctx.turn_count,
        )

    @application.delete("/v1/sessions/{session_id}")
    def delete_session(session_id: str) -> dict[str, Any]:
        """Remove o histórico persistido de uma sessão."""
        orch.clear_session(session_id)
        return {"status": "deleted", "session_id": session_id}

    @application.get("/api/v1/medications/autocomplete")
    def autocomplete_medications(
        q: Annotated[str, Query(min_length=1, max_length=200)],
        limite: Annotated[int, Query(ge=1, le=50)] = 10,
    ) -> dict[str, Any]:
        """Sugestão assistida de medicamentos/insumos padronizados (1.775 itens do corpus v9)."""
        norm = normalize_pt_text(q)
        ranked: list[tuple[int, Any]] = []
        for med in orch.medications:
            dcb_norm = normalize_pt_text(med.dcb_name)
            if dcb_norm.startswith(norm):
                ranked.append((0, med))
            elif norm in dcb_norm:
                ranked.append((1, med))
        ranked.sort(key=lambda item: (item[0], item[1].dcb_name, item[1].concentration))

        seen: set[tuple[str, str, str]] = set()
        results: list[dict[str, Any]] = []
        for _, med in ranked:
            key = (med.dcb_name, med.concentration, med.pharmaceutical_form)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "medication_id": med.medication_id,
                    "dcb_principio_ativo": med.dcb_name.upper(),
                    "concentracao": med.concentration,
                    "forma_farmaceutica": med.pharmaceutical_form.upper(),
                    "via_retirada": med.dispensation_route,
                    "dispensacao_gratuita_prevista": med.available_pfpb or med.available_reme_df,
                    "exige_lme": med.requires_lme,
                    "texto_exibicao": (
                        f"{med.dcb_name.title()} {med.concentration} - {med.pharmaceutical_form.title()}"
                    ),
                }
            )
            if len(results) >= limite:
                break

        return {
            "consulta": q,
            "total_encontrados": len(results),
            "resultados": results,
        }

    @application.post("/api/v1/prescriptions/audit", response_model=PrescriptionAuditResponseDTO)
    def audit_prescription(payload: PrescriptionAuditRequestDTO) -> PrescriptionAuditResponseDTO:
        """Audita receita estruturada via RAG híbrido v9 + Guardrail clínico + Validade RF08."""
        core = orch._core
        masker = core.pii_masker
        blocker = core.clinical_blocker
        matcher = core.tabular_matcher
        retriever = core.hybrid_retriever

        regiao = masker.mask(payload.regiao_administrativa).sanitized_text
        raw_fields = [
            v
            for item in payload.itens
            for v in (
                item.nome_digitado,
                item.principio_ativo_dcb,
                item.concentracao,
                item.forma_farmaceutica,
                item.posologia,
                item.quantidade_prescrita,
            )
            if v
        ] + [payload.pergunta_adicional or "", payload.regiao_administrativa]

        blocks = [res for field_val in raw_fields if (res := blocker.inspect(field_val)).is_blocked]
        if blocks:
            chosen = next((b for b in blocks if b.has_red_flag_emergency), blocks[0])
            return PrescriptionAuditResponseDTO(
                sucesso=False,
                regiao_administrativa=regiao,
                itens=[],
                resumo_acolhedor=chosen.safe_response,
                aviso_preservacao_ato_medico=(
                    "Preservação estrita do Ato Médico (Lei nº 12.842/2013): atuação limitada à navegação."
                ),
                solicitou_automedicacao=chosen.reason != "PROMPT_INJECTION",
            )

        today = date.today()
        base_date = payload.data_emissao or today
        ceaf_unit = core._resolve_ceaf_unit(regiao)
        audited_items: list[ItemRoteiroDTO] = []

        for item in payload.itens:
            nome = masker.mask(item.nome_digitado).sanitized_text
            dcb = masker.mask(item.principio_ativo_dcb or "").sanitized_text
            forma = masker.mask(item.forma_farmaceutica or "").sanitized_text
            doses = matcher.doses_no_texto(nome)
            dose = item.concentracao or (next(iter(doses)) if len(doses) == 1 else "")
            dose_ambigua = (
                TabularDCBMatcher.tem_numero_nao_interpretado(nome)
                or len(doses) > 1
                or bool(
                    item.concentracao
                    and doses
                    and doses != {TabularDCBMatcher.normalizar_concentracao(item.concentracao)}
                )
            )
            consulta = dcb or nome
            matches = (
                matcher.match_medications(
                    consulta,
                    concentracao=dose,
                    forma=forma,
                    deduplicar=False,
                )
                if not dose_ambigua
                else []
            )
            if dcb:
                dcb_norm = normalize_pt_text(dcb)
                matches = [
                    (sc, med)
                    for sc, med in matches
                    if normalize_pt_text(med.dcb_name) == dcb_norm
                ]

            if matches:
                _, med = matches[0]
                local, docs = core._resolve_medication_channel(
                    med=med, detected_ra=regiao, ceaf_unit=ceaf_unit
                )
                val_days = None if med.item_type == "supply" else med.prescription_validity_days
                dt_limit = base_date + timedelta(days=val_days) if val_days is not None else None
                days_left = max(0, (dt_limit - today).days) if dt_limit else None
                audited_items.append(
                    ItemRoteiroDTO(
                        medicamento=nome,
                        principio_ativo_dcb=med.dcb_name.upper(),
                        via_retirada=med.dispensation_route,
                        local_sugerido=local,
                        o_que_levar=docs,
                        dias_validade_receita=val_days,
                        data_limite_validade=dt_limit,
                        dias_restantes=days_left,
                        alerta_vencimento_proximo=(days_left is not None and days_left <= 15),
                        citacao_normativa=f"{med.source_id} (p. {med.source_page})",
                    )
                )
            else:
                hits = (
                    retriever.search(nome, top_k=1)
                    if not (dcb or forma or dose_ambigua)
                    else []
                )
                if dose:
                    hits = [h for h in hits if h.route_category in ("SISREG_EXAME_CONSULTA", "PRE_EXAME_PREPARO")]
                if hits and hits[0].route_category in {
                    "SISREG_EXAME_CONSULTA",
                    "PRE_EXAME_PREPARO",
                    "ALTO_CUSTO_CEAF",
                    "FARMACIA_POPULAR",
                    "UBS_ATENCAO_PRIMARIA",
                }:
                    hit = hits[0]
                    val_days = 90 if hit.route_category in {"SISREG_EXAME_CONSULTA", "ALTO_CUSTO_CEAF"} else 180
                    dt_limit = base_date + timedelta(days=val_days)
                    days_left = max(0, (dt_limit - today).days)
                    audited_items.append(
                        ItemRoteiroDTO(
                            medicamento=nome,
                            principio_ativo_dcb=hit.matched_dcb.upper() if hit.matched_dcb else "PROTOCOLO_SUS",
                            via_retirada=hit.route_category,
                            local_sugerido=f"Unidade de referência em {regiao} ({hit.section}).",
                            o_que_levar=[
                                "Pedido/receita médica válida",
                                "Documento oficial com foto e CPF",
                                "Cartão Nacional de Saúde (CNS)",
                            ],
                            dias_validade_receita=val_days,
                            data_limite_validade=dt_limit,
                            dias_restantes=days_left,
                            alerta_vencimento_proximo=(days_left <= 15),
                            citacao_normativa=f"{hit.chunk_id} — {hit.document_title} (p. {hit.page_number})",
                        )
                    )
                else:
                    audited_items.append(
                        ItemRoteiroDTO(
                            medicamento=nome,
                            principio_ativo_dcb="NAO_IDENTIFICADO",
                            via_retirada="NAO_PADRONIZADO",
                            local_sugerido="Apresentação ou cobertura não confirmada no catálogo v9 consultado.",
                            o_que_levar=[],
                            dias_validade_receita=None,
                            data_limite_validade=None,
                            dias_restantes=None,
                            alerta_vencimento_proximo=False,
                            citacao_normativa="Sem cobertura de gratuidade localizada nas relações públicas.",
                        )
                    )

        total_pfpb = sum(1 for it in audited_items if it.via_retirada == "FARMACIA_POPULAR")
        total_ubs = sum(1 for it in audited_items if it.via_retirada == "UBS_ATENCAO_PRIMARIA")
        total_ceaf = sum(1 for it in audited_items if it.via_retirada == "ALTO_CUSTO_CEAF")
        summary_parts = [f"Auditamos {len(audited_items)} item(ns) para a região de {regiao}."]
        if total_pfpb:
            summary_parts.append(f"{total_pfpb} item(ns) no elenco do Farmácia Popular.")
        if total_ubs:
            summary_parts.append(f"{total_ubs} item(ns) na rede pública DF (UBS/REME-DF).")
        if total_ceaf:
            summary_parts.append(f"{total_ceaf} item(ns) no Alto Custo (CEAF) com exigência de LME.")

        return PrescriptionAuditResponseDTO(
            sucesso=True,
            regiao_administrativa=regiao,
            itens=audited_items,
            resumo_acolhedor=" ".join(summary_parts),
            aviso_preservacao_ato_medico=(
                "Aviso Importante: Orientação exclusivamente administrativa e documental no SUS. "
                "Não substitui consulta ou prescrição médica."
            ),
            solicitou_automedicacao=False,
        )

    @application.get("/v1/pharmacies/nearby")
    def nearby_pharmacies(
        ra: str = "",
        q: str = "",
        lat: float | None = None,
        lng: float | None = None,
        limite: Annotated[int, Query(ge=1, le=25)] = 8,
    ) -> dict[str, Any]:
        """Lista farmácias CEAF, Policlínicas e UBSs geolocalizadas do InfoSaúde-DF."""
        pharm_path = resolved_paths.gold_dir / "df_pharmacies_geolocated.json"
        if not pharm_path.exists():
            return {"ra": ra, "total": 0, "items": []}
        raw = json.loads(pharm_path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = list(raw.get("pharmacies", []))

        norm_ra = normalize_pt_text(ra)
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

        if not scored and rows:
            scored = [(0.0, dict(r)) for r in rows[:limite]]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return {
            "ra": ra or "Distrito Federal",
            "total": len(scored),
            "items": [item for _, item in scored[:limite]],
        }

    @application.get("/v1/ceaf-stock")
    def ceaf_stock(
        q: str = "",
        unidade: str = "",
        limite: Annotated[int, Query(ge=1, le=50)] = 15,
    ) -> dict[str, Any]:
        """Consulta em tempo real os estoques CEAF-DF (Asa Sul, Ceilândia, Gama) no snapshot InfoSaúde."""
        stock_path = resolved_paths.gold_dir / "ceaf_live_stock.json"
        if not stock_path.exists():
            return {"query": q, "total": 0, "items": []}
        raw = json.loads(stock_path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = list(raw.get("items", []))
        norm_q = normalize_pt_text(q)
        norm_u = normalize_pt_text(unidade)

        matched: list[dict[str, Any]] = []
        for row in rows:
            name_norm = normalize_pt_text(
                str(row.get("desc_produto", row.get("medicamento", row.get("nome_medicamento", ""))))
            )
            unit_norm = normalize_pt_text(str(row.get("unidade", row.get("farmacia", ""))))
            if norm_q and norm_q not in name_norm:
                continue
            if norm_u and norm_u not in unit_norm:
                continue
            matched.append(row)
            if len(matched) >= limite:
                break

        return {
            "query": q,
            "unidade": unidade or "Todas",
            "updated_at": raw.get("panel_updated_at_utc"),
            "total": len(matched),
            "items": matched,
        }

    return application


app = create_app()
