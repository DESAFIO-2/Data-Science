# SPEC-04: Avaliação Experimental Científica (Métricas IR + Framework RAGAS)

- **Status:** Implementado
- **Fase:** Semana 3 — Avaliação Experimental Científica (LLM Pura vs. RAG)
- **Dependências:** `SPEC-02-golden-dataset.md`, `SPEC-03-hybrid-retrieval.md`

---

## 1. Objetivo

Conduzir o experimento controlado da Semana 3 comparando três arquiteturas sobre o `golden_set_v1.json`:
1. **Baseline 0 — LLM Pura (Zero-Context / Sem RAG):** Geração sem acesso às portarias RENAME 2024, PFPB, REME-DF e SISREG-DF (sujeita a alucinações de elenco e omissão de requisitos regionais como LME/CEAF-DF).
2. **Baseline 1 — RAG TF-IDF (`min_score = 0.12`):** Recuperação léxica inicial (ADR-003 da Engenharia de Dados).
3. **Proposta — RAG Híbrido (`hybrid_dcb_rrf`) + Orquestrador Multiagentes:** Busca Tabular DCB + Vetorial/Léxica RRF com limiar calibrado e Guardrails.

---

## 2. Métricas Científicas Avaliadas

### 2.1 Métricas de Recuperação de Informação (IR)
- **$\text{Hit Rate}@K$:** Proporção de consultas positivas com ao menos 1 chunk relevante no Top-$K$.
- **$\text{Recall}@K$:** Fração dos chunks relevantes recuperados no Top-$K$.
- **$\text{MRR}$ (Mean Reciprocal Rank):** Média de $1 / \text{rank}_1$ do primeiro chunk relevante.

### 2.2 Métricas do Framework RAGAS
- **Faithfulness (Fidelidade ao Contexto):** Proporção de afirmações factuais da resposta que são diretamente suportadas pelos chunks recuperados (penaliza alucinações).
- **Answer Relevancy (Relevância da Resposta):** Grau de alinhamento semântico/lexical entre a resposta gerada, a pergunta do cidadão e os documentos/rotas exigidos.
- **Context Recall (Revocação de Contexto):** Cobertura das informações da resposta de referência (`reference_answer`) pelos contextos recuperados.

### 2.3 Métricas de Negócio e Segurança SUS Cidadão
- **Route Classification Accuracy:** Precisão na classificação da rota (`FARMACIA_POPULAR`, `UBS_ATENCAO_PRIMARIA`, `ALTO_CUSTO_CEAF`, `SISREG_EXAME_CONSULTA`, `ABSTENCAO_FORA_ELENCO`, `BLOQUEIO_CLINICO_ATO_MEDICO`).
- **Clinical Guardrail Pass Rate:** 100% de bloqueio em consultas que solicitam diagnóstico, ajuste de dose ou substituição de receita sem médico.

---

## 3. Critérios de Aceite da SPEC-04
- [x] Execução comparativa das arquiteturas registrada em JSON (`evals/reports/experiment_runs_registry.json`) via `ExperimentTracker`.
- [x] Geração automática de `evals/reports/ragas_benchmark_report.md` e `evals/baselines/llm_vs_rag_comparison.json`.

