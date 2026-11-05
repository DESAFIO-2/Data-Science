# SPEC-03: Recuperação Híbrida (TF-IDF Baseline vs. BM25 vs. Hybrid RRF) e Calibração de Limiar

- **Status:** Implementado
- **Fase:** Semana 2 & Semana 3 — Base de Conhecimento, Recuperação e Calibração
- **Dependências:** `SPEC-01-eda-and-sync.md`, `SPEC-02-golden-dataset.md`

---

## 1. Objetivo

1. Reproduzir fielmente a linha de base da Engenharia de Dados (`ADR-003`: `TF-IDF` com unigramas/bigramas e limiar inicial de abstenção `min_score = 0.12`).
2. Implementar o **Hybrid Retriever (`hybrid_dcb_rrf`)** que combina:
   - **Busca Tabular Determinística DCB (`TabularDCBMatcher`)** no catálogo canônico Gold (`medicamentos_sus_canonical.json`);
   - **Busca Léxica Probabilística (`BM25Retriever`)** e **Vetorial Esparsa (`TFIDFRetriever`)** nos chunks normativos Silver (`normative_chunks.json`);
   - Fusão de rankings via **Reciprocal Rank Fusion (RRF)** ponderada:
     $$\text{Score}_{\text{Hybrid}}(q, d) = \alpha \cdot \text{Score}_{\text{DCB}}(q, d) + (1 - \alpha) \cdot \text{Score}_{\text{Lexical/RRF}}(q, d)$$
3. Calibrar cientificamente o limiar `min_score` no Golden Dataset para maximizar simultaneamente a taxa de acerto nos casos positivos e a taxa de abstenção correta nos casos fora do elenco SUS (`should_abstain = True`).

---

## 2. Critérios de Aceite da SPEC-03
- [x] `TFIDFRetriever` executa consultas como `"losartana potássica 50 mg"` com `--top-k 3 --min-score 0.12` retornando `CHK-PFPB-001` no topo.
- [x] `HybridRetriever` supera o `TFIDFRetriever` em `MRR` e `Recall@3` no Golden Dataset.
- [x] `ThresholdCalibrator` avalia a grade de limiares (`0.02` a `0.35`), seleciona o limiar ótimo e registra os resultados no **MLflow** e em `evals/reports/calibration_report.md`.

