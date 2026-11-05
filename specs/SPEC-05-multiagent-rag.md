# SPEC-05: Guardrails (LGPD & Ato Médico) e Orquestrador Multiagentes

- **Status:** Implementado
- **Fase:** Semana 4 — Sistema Multiagentes Colaborativo & Guardrails
- **Dependências:** `SPEC-03-hybrid-retrieval.md`, `SPEC-04-evaluation-mlflow.md`

---

## 1. Objetivo

Implementar o pipeline multiagentes colaborativo do **SUS Cidadão (NavegaSUS)** com:
1. **Guardrail de Privacidade (LGPD — PII Masking):** Desidentificação automática de CPF, Cartão Nacional de Saúde (CNS), telefone, e-mail e nomes próprios em receitas antes do processamento pelos agentes.
2. **Guardrail Ético Inegociável (Preservação do Ato Médico):** Bloqueio determinístico de solicitações de diagnóstico, mudança de posologia/dose ou substituição de medicamentos.
3. **Orquestrador de 4 Agentes Especializados (Grafo de Estado):**
   - **Agente 1 — Extrator & Triador Multimodal:** Extrai itens prescritos, exames/consultas, Região Administrativa (RA) do DF e data de emissão da receita.
   - **Agente 2 — Auditor Farmacêutico (RAG Híbrido):** Audita cada medicamento contra RENAME 2024, Farmácia Popular e REME-DF, diferenciando `FARMACIA_POPULAR`, `UBS_ATENCAO_PRIMARIA` e `ALTO_CUSTO_CEAF` (processo LME).
   - **Agente 3 — Consultor SISREG / SES-DF:** Audita pedidos de exames e consultas especializadas contra os protocolos CPPAS/SISREG III.
   - **Agente 4 — Sintetizador do Roteiro Cidadão:** Consolida o roteiro passo a passo, checklist documental, alertas de vencimento da Carteira Digital (15 e 7 dias antes do vencimento) e citações auditáveis (portaria + página).

---

## 2. Critérios de Aceite da SPEC-05
- [x] `PIIMasker` mascara CPF (`***.***.***-**`), CNS (`700************`), telefone e nome de paciente preservando intactos os nomes de medicamentos, dosagens e Regiões Administrativas.
- [x] `ClinicalBlocker` intercepta 100% dos casos de intervenção clínica indevida e emite alerta de segurança / orientação de urgência (UPA / SAMU 192 / UBS).
- [x] `MultiAgentOrchestrator` processa prescrições complexas (múltiplos medicamentos de diferentes componentes + exames SISREG) gerando estado estruturado e auditável.

