# SPEC-08: Pipeline Unificado de Ingestão de PDFs, Conversão JSON->PDF, Indexação ChromaDB e Reavaliação RAGAS

- **Status**: Aprovado / Em Implementação
- **Data**: 05/11/2026
- **Autores**: Marlon Dias Marques (Cientista de Dados), Esquadrão SUS Cidadão (Residência em IA Eldorado / UnB / Softex)
- **Componentes**: `src/sus_cidadao_ds/ingestion/pdf_pipeline.py`, `src/sus_cidadao_ds/retrieval/chroma_indexer.py`, `src/sus_cidadao_ds/evaluation/ragas_benchmark.py`

---

## 1. Contexto e Motivação

No ecossistema do **SUS Cidadão (NavegaSUS)**, a verdade factual sobre a gratuidade e dispensação de medicamentos provém de duas naturezas de dados:
1. **Fontes Oficiais Normativas Estáticas (PDFs)**: RENAME 2024 (F01), REME-DF 2026 (F03), Elenco do Farmácia Popular (F04) e Carta de Serviços do HUB-UnB (F12), conforme levantamento catalogado em `specs/levantamento-fontes.md`.
2. **Fontes Oficiais Dinâmicas de Estoque e Geolocalização (JSON da API InfoSaúde/Power BI)**: Dados extraídos em tempo real via DAX/DSR dos painéis públicos da SES-DF (`ceaf_live_stock.json` e `df_pharmacies_geolocated.json`), documentados na `SPEC-06`.

Para garantir homogeneidade documental na arquitetura RAG e permitir auditoria transparente, estabelece-se um **Pipeline Unificado de Ingestão Documental**:
- Converte os dados estruturados de estoque e geolocalização recebidos da API em **documentos PDF oficiais padronizados** com cabeçalho institucional, carimbo de data/hora e tabelas consolidadas;
- Unifica todos os documentos em um repositório canônico de PDFs (`data/raw/pdfs/`);
- Extrai texto e gera chunks enriquecidos com metadados estruturados utilizando `pypdf`;
- Indexa o corpus unificado de chunks na base vetorial ChromaDB (`sus_unified_pdf_corpus`);
- Reexecuta toda a bateria científica de testes (IR metrics e RAGAS) consumindo exclusivamente da base vetorial ChromaDB, comparando com as linhas de base anteriores.

---

## 2. Arquitetura do Pipeline Unificado

```
┌────────────────────────────────────────────────────────┐
│               FONTES EXTERNAS / LINKS                  │
│  - F01: RENAME 2024 (gov.br)                           │
│  - F03: REME-DF 2026 (saude.df.gov.br)                 │
│  - F04: Farmácia Popular PFPB (gov.br)                 │
│  - F12: Carta HUB-UnB (hubrasil.gov.br)                │
└──────────────────────────┬─────────────────────────────┘
                           │ Download com fallback seguro
                           ▼
┌────────────────────────────────────────────────────────┐  ┌─────────────────────────────────────┐
│                 DOWNLOADER DE PDFs                     │  │    JSON DA API POWER BI (SPEC-06)   │
│       (data/raw/pdfs/<fonte_oficial>.pdf)              │  │  - ceaf_live_stock.json             │
└──────────────────────────┬─────────────────────────────┘  │  - df_pharmacies_geolocated.json    │
                           │                                └──────────────────┬──────────────────┘
                           │                                                   │ Conversor JSON->PDF
                           │                                                   ▼
                           │                                ┌─────────────────────────────────────┐
                           │                                │       GERADOR DE PDFs OFICIAIS      │
                           │                                │  - RELATORIO_ESTOQUE_CEAF.pdf       │
                           │                                │  - GUIA_FARMACIAS_UBS_GEO_DF.pdf    │
                           │                                └──────────────────┬──────────────────┘
                           │                                                   │
                           └───────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                           ┌────────────────────────────────────────────────┐
                           │          EXTRATOR DE TEXTO & CHUNKING          │
                           │         (pypdf + enriquecimento metadata)      │
                           │     --> data/silver/unified_pdf_chunks.json    │
                           └───────────────────────┬────────────────────────┘
                                                   │
                                                   ▼
                           ┌────────────────────────────────────────────────┐
                           │          INDEXADOR CHROMADB VETORIAL           │
                           │       Coleção: `sus_unified_pdf_corpus`        │
                           │     (all-MiniLM-L6-v2, persistente SQLite)     │
                           └───────────────────────┬────────────────────────┘
                                                   │
                                                   ▼
                           ┌────────────────────────────────────────────────┐
                           │     SISTEMA MULTIAGENTES & BENCHMARK RAGAS     │
                           │     - Recuperação semântica ChromaDB           │
                           │     - Métricas IR (Hit@K, Recall@K, MRR)       │
                           │     - RAGAS (Faithfulness, Relevancy, Context) │
                           │     - Registro de Runs no MLflow               │
                           └────────────────────────────────────────────────┘
```

---

## 3. Especificação dos Módulos

### 3.1 `PDFDownloader`
- **Função**: Baixar os PDFs originais a partir das URLs fornecidas em `specs/levantamento-fontes.md`.
- **Resiliência e Fallback**: Como portais governamentais frequentemente sofrem instabilidades, restrições de rede ou timeouts, o downloader:
  - Tenta o download via `httpx` com timeout configurável (15s) e headers de navegador (`User-Agent`);
  - Se houver falha de rede ou timeout, verifica se o arquivo já existe no cache local (`data/raw/pdfs/`);
  - Caso não exista e o download falhe, sintetiza um documento canônico auditado correspondente ao extrato daquela portaria oficial, registrando no log que foi gerado via fallback canônico.
- **Mapeamento de Fontes**:
  - `F01_RENAME_2024.pdf`: Relação Nacional de Medicamentos Essenciais.
  - `F03_REME_DF_2026.pdf`: Relação de Medicamentos do Distrito Federal.
  - `F04_ELENCO_PFPB.pdf`: Elenco oficial do Programa Farmácia Popular do Brasil.
  - `F12_CARTA_SERVICOS_HUB.pdf`: Carta de Serviços ao Usuário do HUB-UnB.

### 3.2 `JSONToPDFConverter`
- **Função**: Converter estruturas JSON provenientes da API Power BI / Gold em PDFs auditáveis utilizando `reportlab`.
- **Documentos Gerados**:
  1. `RELATORIO_ESTOQUE_CEAF_INFOSAUDE.pdf`:
     - Cabeçalho: Governo do Distrito Federal / SES-DF / InfoSaúde.
     - Metadados: Data de extração, total de itens auditados, unidades CEAF (Gama, Ceilândia, Plano Piloto).
     - Conteúdo: Tabela com Código do Produto, Nome do Medicamento, Unidade Dispensadora, Origem de Abastecimento, Saldo Físico e Status de Disponibilidade.
  2. `GUIA_FARMACIAS_UBS_GEO_DF.pdf`:
     - Cabeçalho: Secretaria de Estado de Saúde do DF — Rede de Assistência Farmacêutica e Atenção Primária.
     - Metadados: Quantidade de estabelecimentos, Regiões de Saúde cobertas.
     - Conteúdo: Estabelecimento, Tipo de Unidade, Região Administrativa (RA), Endereço, Coordenadas (Latitude/Longitude), Horário de Funcionamento e Telefone.

### 3.3 `PDFChunkExtractor`
- **Função**: Processar todos os PDFs em `data/raw/pdfs/` através da biblioteca `pypdf`.
- **Estratégia de Chunking**:
  - Extração página a página mantendo a rastreabilidade exata (`page_number`, `source_pdf`).
  - Limpeza de quebras de linha espúrias e normalização de espaços.
  - Chunk size alvo: ~800 a 1200 caracteres, com overlap contextual quando necessário.
  - Metadados anexados a cada chunk:
    - `chunk_id`: Hash ou identificador único legível (ex: `F03_REME_DF_2026_p12_c1`).
    - `source_pdf`: Nome do arquivo PDF de origem.
    - `source_id`: Identificador da fonte (`F01`, `F03`, `F04`, `F12`, `JSON_ESTOQUE`, `JSON_GEO`).
    - `category`: Categoria temática (`normativo`, `estoque_tempo_real`, `geolocalizacao`, `regulacao`).
    - `title`: Título do documento.
    - `content`: Texto textual do chunk.
- **Saída**: `data/silver/unified_pdf_chunks.json`.

### 3.4 `ChromaVectorStoreManager` (Extensão Unificada)
- **Função**: Ingerir `unified_pdf_chunks.json` na coleção `sus_unified_pdf_corpus`.
- **Configurações**:
  - Modelo de Embeddings: `all-MiniLM-L6-v2` (ONNX / sentence-transformers).
  - Métrica de Distância: Cosseno (`hnsw:space = cosine`).
  - IDs Determinísticos baseados no `chunk_id`.

---

## 4. Reavaliação RAGAS & Benchmarking Científico

Para comprovar experimentalmente o impacto da base vetorial unificada, reexecuta-se o benchmark comparativo sobre o **Golden Dataset (Helena e Lucas)**:

1. **Modelos em Comparação**:
   - `LLM Pura (Zero-Shot)`: Sem contexto recuperado, sujeita a alucinações e desatualização.
   - `RAG TF-IDF (Baseline)`: Recuperação lexical esparsa sem embeddings.
   - `RAG Híbrido (SPEC-03)`: RRF com TF-IDF + Busca Tabular DCB.
   - `RAG ChromaDB Vetorial (SPEC-08)`: Recuperação semântica densa sobre o corpus unificado de PDFs (RENAME + REME-DF + PFPB + HUB + Estoque InfoSaúde em PDF + Farmácias em PDF).

2. **Métricas Computadas**:
   - **Métricas de Recuperação (IR)**:
     - `Hit Rate@K` (K=1, 3, 5)
     - `Recall@K` (K=3, 5)
     - `Mean Reciprocal Rank (MRR)`
     - `Abstention Accuracy` (precisão em casos fora do escopo ou sem evidência)
   - **Métricas RAGAS (LLM-as-a-Judge)**:
     - `Faithfulness`: Proporção de afirmações sustentadas pelo contexto do PDF.
     - `Answer Relevancy`: Pertinência da resposta à dúvida do cidadão.
     - `Context Recall`: Proporção de evidências do gabarito factual recuperadas.

3. **Rastreabilidade e MLflow**:
   - Cada execução registra run no MLflow com tags: `run_type="chroma_rag_benchmark"`, `corpus="unified_pdf_corpus"`, `chunk_count=N`.
   - Relatório consolidado gerado em `evals/reports/ragas_benchmark_chroma_report.md`.

---

## 5. Critérios de Aceite
1. Todos os PDFs oficiais mapeados (F01, F03, F04, F12) devem ser baixados ou cacheados em `data/raw/pdfs/`.
2. Os JSONs da API Power BI devem ser convertidos em PDFs válidos (`RELATORIO_ESTOQUE_CEAF_INFOSAUDE.pdf` e `GUIA_FARMACIAS_UBS_GEO_DF.pdf`).
3. `pypdf` deve extrair 100% dos textos dos PDFs sem erros de decodificação.
4. `ChromaDB` deve indexar todos os chunks gerados na coleção `sus_unified_pdf_corpus`.
5. O runner de benchmark deve executar contra a base ChromaDB e registrar métricas no MLflow e relatório markdown.
6. Todos os testes automatizados em `tests/test_sdd_specs.py` devem passar.
7. Código e documentação devem ser comitados e enviados para `origin/main` no repositório `DESAFIO-2/Data-Science`.

