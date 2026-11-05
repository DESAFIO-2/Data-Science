# SPEC-02: Construção e Validação do Golden Dataset (Personas Helena, Lucas e Casos Limítrofes)

- **Status:** Implementado
- **Fase:** Semana 2 & Semana 3 — Calibração de Limiar e Benchmark RAGAS
- **Dependências:** `SPEC-00-architecture.md`, `SPEC-01-eda-and-sync.md`

---

## 1. Objetivo

Definir e validar um **Golden Dataset** auditável (`evals/datasets/golden_set_v1.json`) para:
1. Calibrar o parâmetro de abstenção `min_score` do `TF-IDF` (baseline `0.12` da Engenharia de Dados) e do `Hybrid Retriever`.
2. Medir `Hit Rate@K`, `Recall@K`, `MRR` e `Abstention F1`.
3. Executar a avaliação científica da Semana 3 (**LLM Pura vs. RAG Baseline vs. RAG Híbrido**) com as métricas **RAGAS** (`Faithfulness`, `Answer Relevancy`, `Context Recall`).

---

## 2. Estratificação do Golden Dataset (16 Casos Auditados)

| Estrato | Quantidade | Exemplos | Objetivo de Teste |
|---|---|---|---|
| **Persona Dona Helena — Farmácia Popular (PFPB)** | 4 | `losartana potássica 50 mg`, `metformina 500 mg`, `sinvastatina 20 mg`, `salbutamol 100 mcg` | Precisão na classificação `FARMACIA_POPULAR` (100% gratuito com CPF) |
| **Persona Dona Helena — UBS / Atenção Primária** | 3 | `omeprazol 20 mg`, `levotiroxina sódica 50 mcg`, `fluoxetina 20 mg (Portaria 344)` | Diferenciação de itens exclusivos de `UBS_ATENCAO_PRIMARIA` e validade de receita |
| **Persona Lucas — Farmácia de Alto Custo (CEAF / LME)** | 3 | `adalimumabe 40 mg`, `sacubitril valsartana 97/103 mg`, `insulina glargina 100 UI/mL` | Exigência de `LME`, CID-10, exames PCDT e unidades CEAF-DF (102 Sul, Ceilândia, Gama) |
| **Persona Lucas — Regulação SISREG III / CPPAS** | 2 | `Ecocardiograma Transtorácico`, `Endoscopia Digestiva Alta e Reumatologia` | Orientação de fila regulada via UBS, classificação de prioridade e exames prévios |
| **Casos Negativos / Abstenção (`should_abstain=True`)** | 2 | `semaglutida estética`, `minoxidil 5% capilar` | Calibração do limiar `min_score` para evitar falso positivo / alucinação de cobertura SUS |
| **Casos Adversariais / Guardrail Clínico (`is_clinical_block=True`)** | 2 | Troca de medicamento por conta própria; ajuste de dose em crise hipertensiva | Garantir 100% de bloqueio de prescrição/diagnóstico (Preservação do Ato Médico) |

---

## 3. Critérios de Aceite da SPEC-02
- [x] Todos os `relevant_chunk_ids` referenciados nos casos positivos existem em `data/silver/normative_chunks.json`.
- [x] Todos os `expected_dcb` existem em `data/gold/medicamentos_sus_canonical.json`.
- [x] Casos com `should_abstain=True` possuem `relevant_chunk_ids=[]`.

