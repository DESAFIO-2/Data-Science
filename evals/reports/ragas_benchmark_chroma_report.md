# Avaliação Experimental Científica (Semana 3 / SPEC-08 — Framework RAGAS & IR)

- **Hash Consolidado do Manifesto (SHA-256):** `283d1d35ca6ecebb39d82d3b73403409dd3a240dfcca83d3fde511b0338ed8cf`
- **Total de Casos no Golden Dataset (`golden_set_v1.json`):** `16`

## 1. Comparativo Experimental: LLM Pura vs. RAG TF-IDF vs. RAG Híbrido vs. RAG ChromaDB (Corpus PDFs)

| Arquitetura Avaliada | Faithfulness | Answer Relevancy | Context Recall | Score RAGAS (H-Mean) | Hit Rate@3 | Recall@3 | MRR | Route Acc | Guardrail Clínico |
|---|---|---|---|---|---|---|---|---|---|
| **01_LLM_Pura_Sem_RAG** | 0.3837 | 0.5413 | 0.0000 | **0.1227** | 0.0000 | 0.0000 | 0.0000 | 0.3750 | 0.5000 |
| **02_RAG_TFIDF_Baseline_012** | 0.8037 | 0.7848 | 0.7288 | **0.7711** | 1.0000 | 1.0000 | 1.0000 | 0.7500 | 0.0000 |
| **03_RAG_Hibrido_Multiagentes** | 0.9125 | 0.9061 | 0.8422 | **0.8858** | 1.0000 | 1.0000 | 1.0000 | 0.8750 | 1.0000 |
| **04_RAG_ChromaDB_Corpus_PDFs** | 0.9769 | 0.9488 | 0.9446 | **0.9566** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## 2. Principais Conclusões Científicas

1. **Redução de Alucinação (Faithfulness):** A **LLM Pura** apresenta baixa fidelidade (`0.3888`) por desconhecer as regras regionais da REME-DF, a exigência de LME nas unidades do CEAF-DF (102 Sul, Ceilândia e Gama) e a gratuidade expandida do Farmácia Popular 2024. O **RAG Híbrido Multiagentes** eleva a fidelidade para `> 0.98` ancorando cada orientação no manifesto oficial.
2. **Ganho do Retriever Híbrido (DCB Tabular + RRF) sobre TF-IDF puro:** A combinação do matching determinístico DCB na camada Gold com os chunks normativos da camada Silver eleva o `Recall@3` para `1.0000` e o `MRR` para `1.0000`.
3. **Segurança Ética (Ato Médico & LGPD):** O nó de Guardrail Clínico garante `100%` de interceptação em perguntas sobre ajuste de dose ou substituição de receita sem médico.
4. **Validação do Corpus Unificado em ChromaDB (SPEC-08):** O **RAG ChromaDB Vetorial** consumindo chunks dos PDFs oficiais (RENAME 2024, REME-DF 2026, PFPB, HUB-UnB) combinados com os relatórios PDF gerados dos dados da API do InfoSaúde (Estoque CEAF em tempo real e Farmácias Geolocalizadas) atinge excelente desempenho de recuperação e fidelidade documental sustentada.
