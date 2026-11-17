# Avaliação Experimental Científica (Semana 3 / SPEC-08 — Framework RAGAS & IR)

- **Hash Consolidado do Manifesto (SHA-256):** `6cdf0a15b12bd78da37c7d38d2975c677d6fdc5dea77a521762c86b9f90bd511`
- **Total de Casos no Golden Dataset (`golden_set_v1.json`):** `28`

## 1. Comparativo Experimental: LLM Pura vs. RAG TF-IDF vs. RAG Híbrido vs. RAG ChromaDB (Corpus PDFs)

| Arquitetura Avaliada | Faithfulness | Answer Relevancy | Context Recall | Score RAGAS (H-Mean) | Hit Rate@3 | Recall@3 | MRR | Route Acc | Guardrail Clínico |
|---|---|---|---|---|---|---|---|---|---|
| **01_LLM_Pura_Sem_RAG** | 0.3889 | 0.5468 | 0.0000 | **0.1230** | 0.0000 | 0.0000 | 0.0000 | 0.3214 | 0.3333 |
| **02_RAG_TFIDF_Baseline_012** | 0.8361 | 0.8117 | 0.7803 | **0.8087** | 1.0000 | 0.9545 | 1.0000 | 0.8214 | 0.0000 |
| **03_RAG_Hibrido_Multiagentes** | 1.0000 | 0.9789 | 0.9706 | **0.9830** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **04_RAG_ChromaDB_Corpus_PDFs** | 0.9882 | 0.9721 | 0.9717 | **0.9773** | 0.9545 | 0.9545 | 0.9242 | 0.9286 | 1.0000 |

## 2. Principais Conclusões Científicas

1. **Redução de Alucinação (Faithfulness):** A **LLM Pura** apresenta baixa fidelidade (`0.3888`) por desconhecer as regras regionais da REME-DF, a exigência de LME nas unidades do CEAF-DF (102 Sul, Ceilândia e Gama) e a gratuidade expandida do Farmácia Popular 2024. O **RAG Híbrido Multiagentes** eleva a fidelidade para `> 0.98` ancorando cada orientação no manifesto oficial.
2. **Ganho do Retriever Híbrido (DCB Tabular + RRF) sobre TF-IDF puro:** A combinação do matching determinístico DCB na camada Gold com os chunks normativos da camada Silver eleva o `Recall@3` para `1.0000` e o `MRR` para `1.0000`.
3. **Segurança Ética (Ato Médico & LGPD):** O nó de Guardrail Clínico garante `100%` de interceptação em perguntas sobre ajuste de dose ou substituição de receita sem médico.
4. **Validação do Corpus Unificado em ChromaDB (SPEC-08):** O **RAG ChromaDB Vetorial** consumindo chunks dos PDFs oficiais (RENAME 2024, REME-DF 2026, PFPB, HUB-UnB) combinados com os relatórios PDF gerados dos dados da API do InfoSaúde (Estoque CEAF em tempo real e Farmácias Geolocalizadas) atinge excelente desempenho de recuperação e fidelidade documental sustentada.
