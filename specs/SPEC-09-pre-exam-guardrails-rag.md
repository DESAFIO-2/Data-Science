# SPEC-09: Corpus Validado de Pré-Exames, Guardrail Clínico Expandido e RAG Híbrido de Produção

- **Status:** Implementado
- **Fase:** Semana 5 — Evolução de Produção (Retrieval Limpo + Pré-Exames + Segurança CFM)
- **Dependências:** `SPEC-03-hybrid-retrieval.md`, `SPEC-05-multiagent-rag.md`, `SPEC-07-chromadb-vectorstore.md`, `SPEC-08-unified-pdf-pipeline.md`

---

## 1. Objetivo

1. **Separar Baseline Experimental de Motor de Produção:**
   - Isolar o `TFIDFRetriever` exclusivamente para uso em benchmarks e calibração histórica (`ADR-003` em `calibration/` e `evaluation/`).
   - Consolidar o motor oficial de produção usando **3 camadas complementares**:
     1. `TabularDCBMatcher` (correspondência determinística em medicamentos canônicos Gold);
     2. `BM25Retriever` + `RRF` (precisão lexical em siglas e nomes brasileiros sem dependência do `TF-IDF`);
     3. `ChromaVectorStoreManager` com função de embedding **consciente de Português/SUS** (`PortugueseClinicalEmbeddingFunction`) — suportando provedores multilíngues (`gemini`, `openai`) e modo local `pt_br_hybrid_onnx` com projeção semântica clínica PT-BR.

2. **Corpus Validado de Orientações de Pré-Exame (`GUIA_PRE_EXAMES_SUS_DF.pdf` + Silver Chunks):**
   - Indexar protocolos de preparo administrativo/logístico para exames frequentes no SUS-DF (Endoscopia Digestiva Alta, Ultrassonografia Abdominal/Pélvica, Ressonância Magnética/Tomografia, Coleta Laboratorial e Ecocardiograma Transtorácico).
   - **Restrição obrigatória (`levantamento-fontes.md`):** Não extrapolar preparos entre instituições distintas como se fossem universais. Toda orientação deve informar a unidade/fonte de referência e instruir o cidadão a confirmar o horário exato no comprovante do agendamento.

3. **Expansão do `ClinicalBlocker` (Pré-Exames):**
   - Interceptar pedidos de suspensão ou alteração de medicamentos contínuos antes de exames (ex.: insulina, anti-hipertensivos, anticoagulantes/AAS antes de endoscopia ou jejum), bloqueando decisão terapêutica sem orientação médica.

4. **Expansão do Golden Dataset (`golden_set_v1.json`) e Avaliação Honesta:**
   - Expandir o conjunto de avaliação com casos de pré-exames (incluindo linguagem coloquial típica de voz), abstenção para procedimentos sem protocolo validado e bloqueio clínico pré-exame.
   - Garantir que `_evaluate_rag_chromadb` infira `pred_route` exclusivamente dos hits retornados pelo ChromaDB.

---

## 2. Critérios de Aceite
- [x] `HybridRetriever` de produção opera sem `TFIDFRetriever` (`BM25 + Tabular DCB + RRF`), preservando `Combined F1 = 1.0`.
- [x] `ChromaVectorStoreManager` usa `PortugueseClinicalEmbeddingFunction` com persistência e busca semântica em linguagem natural PT-BR (ex.: *"ficar sem comer antes do exame da barriga"* $\rightarrow$ preparo de ultrassonografia abdominal).
- [x] `ClinicalBlocker` bloqueia 100% das perguntas sobre suspensão/troca de remédios antes de exames.
- [x] `golden_set_v1.json` expandido para 22 casos com cobertura de pré-exames e 100% de integridade referencial.

