# SPEC-01: Sincronização com Engenharia de Dados (Silver/Gold) e Análise Exploratória (EDA)

- **Status:** Implementado
- **Fase:** Semana 2 — Base de Conhecimento e Recuperação
- **Dependências:** `SPEC-00-architecture.md`

---

## 1. Objetivo

Garantir que o repositório `Data-Science`:
1. Consuma diretamente os artefatos produzidos por `DESAFIO-2/engenharia-dados` (`data/silver/` e `data/gold/`) quando o diretório local é fornecido (`--engineering-dir`), validando os hashes SHA-256 do manifesto.
2. Materialize determinísticamente o catálogo canônico (`medicamentos_sus_canonical.json`), os chunks normativos (`normative_chunks.json`) e o manifesto criptográfico (`data/manifests/manifest.json`) a partir das regras oficiais do Ministério da Saúde e SES-DF (RENAME 2024 2ª ed., Farmácia Popular, REME-DF e SISREG III/CPPAS).
3. Produza um relatório estatístico automatizado de Análise Exploratória de Dados (EDA) em `evals/reports/eda_report.md` e JSON estruturado para rastreamento no **MLflow**.

---

## 2. Escopo das Fontes Canônicas (Silver & Gold)

| Fonte Oficial | Escopo | Via de Acesso Cidadão | Regra Chave |
|---|---|---|---|
| **PFPB 2024** | Hipertensão, Diabetes, Asma, Osteoporose, Dislipidemia, Rinite, Parkinson, Glaucoma, Anticoncepção | **Farmácia Popular** (drogaria privada credenciada) | Receita válida (180 dias ou 365 para anticoncepcionais) + Documento com CPF |
| **RENAME 2024 / REME-DF (Básico)** | Atenção Primária à Saúde | **UBS (Unidade Básica de Saúde)** da Região Administrativa (RA) | Cartão SUS (CNS), CPF, comprovante/vínculo na UBS e receita válida |
| **RENAME 2024 / REME-DF (Especializado - CEAF)** | Medicamentos de Alto Custo / Complexidade | **Farmácia de Alto Custo (CEAF-DF)** (Estação 102 Sul, Ceilândia, Gama) | Processo administrativo com **LME** (Laudo de Medicamentos Especializados), exames exigidos pelo PCDT, CID-10 elegível, CNS e CPF |
| **SISREG III / CPPAS SES-DF** | Consultas e Exames Especializados | **Regulação via UBS (Atenção Primária)** no sistema SISREG / Complexo Regulador DF | Encaminhamento clínico com justificativa, classificação de risco/prioridade (P1/P2/P3) e exames prévios obrigatórios do protocolo CPPAS |

---

## 3. Métricas Obrigatórias da EDA

O módulo `sus_cidadao_ds.eda.analyzer` deve calcular e validar:
1. **Total de medicamentos canônicos (`total_medications`)** e **total de DCBs únicos (`unique_dcbs`)**.
2. **Distribuição por Componente da RENAME** (`Básico`, `Especializado`, `Estratégico`).
3. **Matriz de Cobertura Cruzada:**
   - Quantidade e percentual de medicamentos gratuitos na **Farmácia Popular (`pfpb_free`)** vs. exclusivos de **UBS** vs. **Farmácia de Alto Custo (`requires_lme`)**.
4. **Perfilamento dos Chunks Normativos (`normative_chunks`):**
   - Número total de chunks por fonte (`RENAME_2024`, `PFPB_2024`, `REME_DF_2024`, `SISREG_CPPAS_DF`).
   - Estatísticas de comprimento (média, mediana, mínimo, máximo de tokens/palavras por chunk).
   - Taxa de cobertura DCB nos chunks normativos (`dcb_chunk_coverage_rate`).

---

## 4. Critérios de Aceite da SPEC-01
- [x] `sus_cidadao_ds.sync` gera/sincroniza `data/gold/medicamentos_sus_canonical.json`, `data/silver/normative_chunks.json` e `data/manifests/manifest.json` com hashes SHA-256 verificáveis.
- [x] `sus_cidadao_ds.eda` gera `evals/reports/eda_report.md` e registra as métricas de perfilamento no MLflow.
- [x] Testes unitários verificam a integridade de todos os schemas e hashes SHA-256.

