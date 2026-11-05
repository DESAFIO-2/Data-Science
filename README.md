# SUS Cidadão (NavegaSUS) — Ciência de Dados & Experimentação RAG/Multiagentes

Repositório da Frente de **Ciência de Dados** do projeto **SUS Cidadão (NavegaSUS)** (*Desafio 2: Qualidade de Vida e Tomada de Decisão com IA — Instituto Eldorado | Residência em IA UnB/Softex*).

Desenvolvido sob a metodologia **Spec-Driven Development (SDD)** a partir da fundação construída pela Frente de Engenharia de Dados (`DESAFIO-2/engenharia-dados`), cobrindo:
1. **Consumo e Sincronização Medallion (Silver & Gold)** com verificação de linhagem SHA-256 (`SPEC-01`);
2. **Análise Exploratória de Dados (EDA)** das bases oficiais (`RENAME 2024`, `Farmácia Popular`, `REME-DF` e `SISREG III / CPPAS`);
3. **Construção do Golden Dataset (`golden_set_v1.json`)** estratificado pelas personas **Dona Helena** e **Lucas**, incluindo casos fora de elenco (abstenção) e bloqueio clínico (`SPEC-02`);
4. **Recuperação Híbrida (`Tabular DCB + TF-IDF + BM25 via RRF`) e Calibração Científica do Limiar `min_score`** superando o baseline inicial `0.12` (`SPEC-03`);
5. **Avaliação Experimental Científica (Semana 3 — Framework RAGAS + IR)** comparando **LLM Pura vs. RAG TF-IDF vs. RAG Híbrido Multiagentes** com rastreamento completo no **MLflow** (`SPEC-04`);
6. **Orquestrador Multiagentes (4 Agentes) + Guardrails LGPD e Ato Médico** (`SPEC-05`).

---

## Esquadrão

| Papel | Responsável |
|---|---|
| **Cientista de Dados** | **Marlon Dias Marques** |
| **Engenheira de Dados** | Jhiovana Silva Ribeiro |
| **Engenheiro de IA** | Samuel de Souza Rodrigues |
| **Arquiteto de Software** | Mickeias Charles de Oliveira Paiva |
| **MLOps / LLMOps** | Tayrine Hevellin Zitkoski |

---

## Arquitetura SDD (Spec-Driven Development)

Todas as especificações formais encontram-se em [`specs/`](specs/):
- [`SPEC-00-architecture.md`](specs/SPEC-00-architecture.md): Contratos Silver/Gold com Engenharia de Dados (`ADR-001` a `ADR-004`) e governança **MLflow**.
- [`SPEC-01-eda-and-sync.md`](specs/SPEC-01-eda-and-sync.md): Sincronização criptográfica SHA-256 e Análise Exploratória (RENAME 2024, PFPB, REME-DF, SISREG).
- [`SPEC-02-golden-dataset.md`](specs/SPEC-02-golden-dataset.md): Conjunto Padrão-Ouro (16 casos auditados: Dona Helena, Lucas, Abstenção e Guardrail Clínico).
- [`SPEC-03-hybrid-retrieval.md`](specs/SPEC-03-hybrid-retrieval.md): Baseline `TF-IDF (0.12)` vs. `BM25` vs. `Hybrid Retriever (DCB + RRF)` e calibração de limiar.
- [`SPEC-04-evaluation-mlflow.md`](specs/SPEC-04-evaluation-mlflow.md): Benchmark **RAGAS** (`Faithfulness`, `Answer Relevancy`, `Context Recall`) + `Hit Rate@3`, `Recall@3`, `MRR` no **MLflow**.
- [`SPEC-05-multiagent-rag.md`](specs/SPEC-05-multiagent-rag.md): Orquestrador dos 4 Agentes + `PIIMasker` (LGPD) + `ClinicalBlocker` (Preservação do Ato Médico).

---

## Resultados Experimentais Consolidados (Semana 2 & Semana 3)

### 1. Calibração do Limiar de Abstenção (`min_score` — `SPEC-03`)
| Recuperador | `min_score` | Hit Rate@3 | Recall@3 | MRR | Abstention Acc | Combined F1 |
|---|---|---|---|---|---|---|
| **TF-IDF Baseline (ADR-003)** | `0.12` | `1.0000` | `1.0000` | `1.0000` | `0.0000` | `0.0000` |
| **TF-IDF Calibrado (Ótimo)** | `0.18` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | **`1.0000`** |
| **Hybrid Retriever (DCB Gold + RRF)** | `0.12`–`0.25` | **`1.0000`** | **`1.0000`** | **`1.0000`** | **`1.0000`** | **`1.0000`** |

### 2. Benchmark Científico RAGAS (`LLM Pura vs. RAG` — `SPEC-04`)
| Arquitetura Avaliada | Faithfulness | Answer Relevancy | Context Recall | Score RAGAS (H-Mean) | Hit Rate@3 | MRR | Route Acc | Guardrail Clínico |
|---|---|---|---|---|---|---|---|---|
| **01. LLM Pura (Sem RAG)** | `0.3837` | `0.5413` | `0.0000` | `0.1227` | `0.0000` | `0.0000` | `0.3750` | `0.5000` |
| **02. RAG TF-IDF Baseline (`0.12`)** | `0.8037` | `0.7848` | `0.7288` | `0.7711` | `1.0000` | `1.0000` | `0.7500` | `0.0000` |
| **03. RAG Híbrido + Multiagentes** | **`1.0000`** | **`0.9751`** | **`0.9651`** | **`0.9798`** | **`1.0000`** | **`1.0000`** | **`1.0000`** | **`1.0000`** |

Relatórios completos gerados automaticamente em:
- [`evals/reports/eda_report.md`](evals/reports/eda_report.md)
- [`evals/reports/calibration_report.md`](evals/reports/calibration_report.md)
- [`evals/reports/ragas_benchmark_report.md`](evals/reports/ragas_benchmark_report.md)
- [`evals/reports/mlflow_runs_registry.json`](evals/reports/mlflow_runs_registry.json)

---

## Comandos Rápidos

```bash
# 1. Sincronizar camadas Silver/Gold (ou importar de --engineering-dir)
make sync-data

# 2. Executar Análise Exploratória de Dados (EDA) + registro MLflow
make eda

# 3. Calibrar limiar de abstenção min_score (TF-IDF vs Hybrid RRF) + MLflow
make calibrate

# 4. Executar Benchmark Científico RAGAS (LLM Pura vs RAG) + MLflow
make benchmark

# 5. Executar Orquestrador Multiagentes em uma prescrição completa
make run-agents

# 6. Executar suíte de testes SDD (SPEC-00 a SPEC-05)
make test
```

### Consultas via CLI (Compatível com Engenharia de Dados)

```bash
# Consulta com Hybrid Retriever (DCB + Portarias RRF)
PYTHONPATH=src python3 -m sus_cidadao_ds.cli search "losartana potássica 50 mg" --retriever hybrid --top-k 3 --min-score 0.12

# Auditoria completa pelo Orquestrador de 4 Agentes + Guardrails LGPD/CFM
PYTHONPATH=src python3 -m sus_cidadao_ds.cli audit "Paciente: Maria Silva, CPF 123.456.789-00. Receita: Losartana potássica 50 mg, Adalimumabe 40 mg e Ecocardiograma Transtorácico. Moro em Ceilândia - DF." --days-emitted 170
```
