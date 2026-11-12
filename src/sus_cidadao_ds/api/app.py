"""API FastAPI para conectar o Orquestrador RAG + Memória + Modo Voz ao aplicativo SUS Cidadão."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sus_cidadao_ds.agents.langgraph_orchestrator import LangGraphMultiAgentOrchestrator
from sus_cidadao_ds.core.config import ProjectPaths
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager
from sus_cidadao_ds.retrieval.embeddings import PortugueseClinicalEmbeddingFunction
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


def _load_default_orchestrator(paths: ProjectPaths) -> LangGraphMultiAgentOrchestrator:
    """Inicializa sincronizador Gold + ChromaDB PT-BR + Orquestrador LangGraph."""
    paths.ensure_dirs()
    sync = DataSynchronizer(paths)
    try:
        medications = sync.load_medications()
        chunks = sync.load_chunks()
    except FileNotFoundError:
        sync.sync()
        medications = sync.load_medications()
        chunks = sync.load_chunks()

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

    return application


app = create_app()
