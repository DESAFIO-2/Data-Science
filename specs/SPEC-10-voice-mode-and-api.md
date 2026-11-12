# SPEC-10: Modo Voz Interativo, API FastAPI (`/v1/chat`, `/v1/voice-turn`) e Protótipo Conversacional

- **Status:** Implementado
- **Fase:** Semana 5/6 — Integração com o Aplicativo & Assistente de Voz Acessível
- **Dependências:** `SPEC-09-pre-exam-guardrails-rag.md`, Memória Persistente LangGraph (`SQLiteSessionStore`)

---

## 1. Objetivo

Conectar o cérebro científico (`LangGraphMultiAgentOrchestrator` + `ChromaVectorStoreManager` + `SQLiteSessionStore`) diretamente ao aplicativo e habilitar interação por **voz natural** em Português do Brasil voltada à acessibilidade (Persona Dona Helena):

1. **Modo Voz no Orquestrador (`spoken_guidance` + `follow_up_suggestions`):**
   - Além do roteiro estruturado em tela (`synthesized_guidance`), o Agente 4 gera `spoken_guidance`: texto curto, empático, sem colchetes/códigos normativos pesados, otimizado para síntese de fala (TTS), com convite natural para o próximo turno da conversa.
2. **Motor de Áudio Modular (`src/sus_cidadao_ds/voice/audio_engine.py`):**
   - **STT:** Transcrição via Gemini / OpenAI Whisper quando configurado via variáveis de ambiente, além de integração nativa com Web Speech API no navegador.
   - **TTS:** Síntese neural PT-BR via `edge-tts` (`pt-BR-FranciscaNeural`) com fallback para `/usr/bin/say -v Luciana` (macOS) ou Web Speech Synthesis.
3. **API FastAPI Pronta para o Aplicativo (`src/sus_cidadao_ds/api/app.py`):**
   - `GET /health` — Saúde do serviço e estatísticas da base vetorial.
   - `POST /v1/chat` — Turno textual com `session_id` persistente.
   - `POST /v1/voice-turn` — Turno de voz completo (recebe áudio ou transcrição + `session_id`, executa LangGraph RAG + guardrails, gera `spoken_guidance` + áudio MP3 Base64).
   - `GET /v1/sessions/{session_id}` e `DELETE /v1/sessions/{session_id}` — Gestão segura de sessão LGPD.
   - `GET /voice-demo` — Interface Web interativa com microfone para testar conversa falada em tempo real no navegador.

---

## 2. Critérios de Aceite
- [x] `CitizenGuidanceResponse` expõe `spoken_guidance` natural e `follow_up_suggestions`.
- [x] Endpoints `/health`, `/v1/chat`, `/v1/voice-turn` e `/voice-demo` respondem com contratos Pydantic validados via `TestClient`.
- [x] Fluxo multi-turno por voz preserva RA, medicamentos e exames em sessão persistente sem vazar PII (CPF/CNS/Nome).

