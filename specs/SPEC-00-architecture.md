# SPEC-00: Arquitetura de Ciência de Dados, Contratos com Engenharia e Governança MLflow

- **Status:** Aprovado
- **Fase:** Semanas 2–4 (Base de Conhecimento, Avaliação Científica RAGAS e Sistema Multiagentes)
- **Responsável:** Marlon Dias Marques (Cientista de Dados)
- **Alinhamento Arquitetural:**
  - `ADR-001` (Engenharia de Dados): Arquitetura Medallion Lite (`bronze` -> `silver` -> `gold`)
  - `ADR-002` (Engenharia de Dados): Catálogo relacional + vetorial (`PostgreSQL` + `pgvector` / índices locais)
  - `ADR-003` (Engenharia de Dados): `TF-IDF` como linha de base determinística (`min_score = 0.12`)
  - `ADR-004` (Engenharia de Dados): Artefatos RAG reconstruíveis fora do Git (`.artifacts/`)

---

## 1. Objetivo

Estabelecer os contratos formais de dados entre o repositório `DESAFIO-2/engenharia-dados` e `DESAFIO-2/Data-Science`, garantindo reprodutibilidade determinística, rastreabilidade criptográfica (SHA-256) e governança experimental via **MLflow** sob a metodologia **Spec-Driven Development (SDD)**.

---

## 2. Contrato de Dados com a Engenharia de Dados (Camadas Silver e Gold)

### 2.1 Manifesto de Linhagem (`data/manifests/manifest.json`)
Todo processamento de Ciência de Dados deve referenciar o hash SHA-256 do manifesto das fontes públicas:
- **RENAME 2024** (Relação Nacional de Medicamentos Essenciais — Portaria GM/MS nº 6.324/2024, 2ª edição)
- **PFPB** (Programa Farmácia Popular do Brasil — Elenco Oficial de Gratuidade e Copagamento)
- **REME-DF** (Relação de Medicamentos Essenciais do Distrito Federal — SES-DF)
- **SISREG III / CPPAS** (Protocolos de Encaminhamento e Regulação Ambulatorial SES-DF / MS)

### 2.2 Catálogo Canônico de Medicamentos (`data/gold/medicamentos_sus_canonical.json`)
Cada item do catálogo canônico obedece ao contrato:
- `medication_id` (`str`): Identificador único determinístico (ex.: `MED-LOSARTANA-50MG-COMP`)
- `dcb_name` (`str`): Denominação Comum Brasileira normalizada em minúsculas (ex.: `losartana potássica`)
- `concentration` (`str`): Concentração padronizada (ex.: `50 mg`)
- `pharmaceutical_form` (`str`): Forma farmacêutica (ex.: `comprimido`)
- `rename_component` (`str`): `Básico`, `Estratégico`, `Especializado` ou `Não listado`
- `available_pfpb` (`bool`): Disponível no Programa Farmácia Popular do Brasil
- `pfpb_free` (`bool`): Gratuidade 100% na Farmácia Popular (ex.: hipertensão, diabetes, asma, osteoporose, anticoncepção, dignidade menstrual)
- `available_reme_df` (`bool`): Disponível na rede SES-DF
- `reme_Dispensation_level` (`str`): `UBS`, `Farmácia de Alto Custo (CEAF)`, `Hospitalar` ou `Farmácia Popular`
- `requires_lme` (`bool`): Exige Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) e PCDT
- `icd10_codes` (`list[str]`): CIDs-10 associados quando aplicável (Especializado/CEAF)
- `source_id` (`str`): Fonte primária auditável (`RENAME_2024`, `PFPB_2024`, `REME_DF_2024`)
- `source_page` (`int`): Página de referência no documento oficial

### 2.3 Chunks Normativos e Protocolos (`data/silver/normative_chunks.json`)
Cada fragmento extraído das portarias e protocolos (RENAME, PFPB, REME-DF, SISREG/CPPAS) obedece ao contrato:
- `chunk_id` (`str`): Identificador único (ex.: `CHK-RENAME2024-001`)
- `source_id` (`str`): `RENAME_2024` | `PFPB_2024` | `REME_DF_2024` | `SISREG_CPPAS_DF`
- `document_title` (`str`): Título oficial da portaria/protocolo
- `section` (`str`): Seção ou capítulo normativo
- `page_number` (`int`): Página do documento original
- `text` (`str`): Conteúdo textual normalizado do chunk
- `dcb_mentions` (`list[str]`): Medicamentos DCB citados no chunk
- `route_category` (`str`): `FARMACIA_POPULAR` | `UBS_ATENCAO_PRIMARIA` | `ALTO_CUSTO_CEAF` | `SISREG_EXAME_CONSULTA` | `GERAL`
- `sha256` (`str`): Hash SHA-256 do texto do chunk

---

## 3. Governança Experimental com MLflow

Todo experimento de recuperação, calibração de limiar ou avaliação RAGAS deve registrar:
1. **Tags de Linhagem:**
   - `manifest_sha256`: Hash consolidado do manifesto de dados
   - `spec_id`: Especificação SDD correspondente (`SPEC-03`, `SPEC-04`, `SPEC-05`)
   - `git_stage`: Etapa do projeto (`semana2_baseline`, `semana2_hybrid`, `semana3_ragas`)
2. **Parâmetros (`params`):**
   - `retriever_type`: `tfidf_baseline` | `bm25` | `hybrid_dcb_rrf`
   - `top_k`: Inteiro (`3`, `5`, `10`)
   - `min_score`: Float (ex.: `0.12` baseline vs. limiar calibrado)
   - `rrf_k`: Constante de suavização do Reciprocal Rank Fusion (padrão `60`)
3. **Métricas (`metrics`):**
   - Recuperação: `hit_rate_at_k`, `recall_at_k`, `mrr`, `abstention_f1`, `false_positive_rate`
   - Geração / RAGAS: `faithfulness`, `answer_relevancy`, `context_recall`, `clinical_guardrail_pass_rate`
4. **Artefatos (`artifacts`):**
   - Curva de calibração JSON/CSV e relatório Markdown auditável.

---

## 4. Critérios de Aceite da SPEC-00
- [x] Estrutura de pacotes em `src/sus_cidadao_ds/` com tipagem estrita.
- [x] Rastreador MLflow (`MLflowTracker`) funcional com suporte nativo ao pacote `mlflow` e fallback determinístico em arquivo compatível com a estrutura `mlruns/` para execução offline/CI em qualquer ambiente.
- [x] Arquivo de configuração `config/sources.yaml` e `config/experiments.yaml` versionados.

