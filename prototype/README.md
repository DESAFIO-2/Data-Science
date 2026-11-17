# SUS Digital — Protótipo Mobile Integrado aos Multiagentes RAG & Voz (Zelo)

Aplicativo **Expo / React Native (Web, Android e iOS)** mobile-first adaptado de `DESAFIO-2/Front-End-` e integrado em tempo real à API FastAPI dos Multiagentes SUS Cidadão (`src/sus_cidadao_ds/api/app.py`).

## Funcionalidades Integradas ao Backend v9

- **Zelo Voz (`(tabs)/zelo.tsx`)**:
  - Conversa por voz em Português (Web Speech API `pt-BR` + captura `MediaRecorder` -> `POST /v1/voice-turn`) e síntese de áudio PT-BR (`tts_audio_base64` / `speechSynthesis`).
  - Memória persistente por sessão LGPD (`session_id` SQLite no LangGraph).
  - Cards estruturados: rota oficial (`FARMACIA_POPULAR`, `UBS_ATENCAO_PRIMARIA`, `ALTO_CUSTO_CEAF`, `PRE_EXAME_PREPARO`, `SISREG_EXAME_CONSULTA`), preparo pré-exame, checklist de documentos, alerta de validade RF08, fontes oficiais + rastreio dos 4 agentes, e bloqueio ético do Ato Médico (Lei nº 12.842/2013) com atalhos SAMU 192 / Disque 136 / UPA.
- **Carteira Digital & Receitas (`(tabs)/receitas.tsx`)**:
  - Cadastro de novas receitas/exames com autocomplete nos **1.775 itens** do catálogo canônico v9 (`GET /api/v1/medications/autocomplete`).
  - Auditoria ao vivo via `POST /api/v1/prescriptions/audit` com contagem de validade (180d PFPB, 90d CEAF/SISREG, 30d/10d) e alertas proativos de 15 e 7 dias na aba de Notificações.
  - Anexo fotográfico estritamente local no dispositivo (sem OCR de caligrafia na nuvem, conforme ADR-0002).
- **Farmácias & InfoSaúde DF (`(tabs)/farmacias.tsx`)**:
  - Busca nas **231 unidades geolocalizadas do DF** (`GET /v1/pharmacies/nearby`) por Região Administrativa ou coordenadas GPS.
  - Consulta em tempo real ao estoque CEAF Alto Custo (`GET /v1/ceaf-stock` — 857 registros).
- **Acessibilidade (`perfil.tsx`)**:
  - Escala de fonte (`Letras maiores +16%`) aplicada globalmente, seleção de Região Administrativa DF, configuração dinâmica da URL da API FastAPI e teste de conexão.

## Como Executar Localmente

### 1. Iniciar a API Multiagentes + Voz (Terminal 1)

```bash
cd /Users/aluno2/Data-Science
make serve
# Escuta em http://127.0.0.1:8000 (Swagger em /docs)
```

### 2. Iniciar o Protótipo Mobile (Terminal 2)

```bash
cd /Users/aluno2/Data-Science/prototype
npm ci              # apenas na primeira vez
npx expo start --web
```

Para testar no celular físico via **Expo Go**, defina o IP da sua máquina na rede local no campo **Motor Multiagentes RAG & Voz -> URL da API FastAPI** dentro da tela **Meu Perfil** do próprio app (ou via `EXPO_PUBLIC_API_URL=http://SEU_IP_LAN:8000`).

## Validação Estática

```bash
cd /Users/aluno2/Data-Science/prototype
npx tsc --noEmit
npm run lint
```
