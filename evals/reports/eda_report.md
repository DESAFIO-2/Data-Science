# Relatório de Análise Exploratória de Dados (EDA) — SUS Cidadão

- **Hash Consolidado do Manifesto (SHA-256):** `6aad97cb7ce99495baecca22a0218e750fa43d222e106e6b47904095ba44795d`
- **Total de Apresentações Canônicas (Gold):** `24`
- **Denominações Comuns Brasileiras (DCBs únicos):** `23`
- **Total de Chunks Normativos (Silver):** `13`

## 1. Distribuição por Componente da RENAME 2024

| Componente RENAME | Quantidade |
|---|---|
| Básico | 17 |
| Especializado | 7 |

## 2. Distribuição por Via de Acesso Cidadão

| Via de Dispensação | Quantidade | Regra Operacional |
|---|---|---|
| `ALTO_CUSTO_CEAF` | 6 | Farmácia de Alto Custo SES-DF (Processo LME + Exames PCDT + CID-10) |
| `FARMACIA_POPULAR` | 13 | Drogaria privada credenciada (100% gratuito com CPF + Receita) |
| `UBS_ATENCAO_PRIMARIA` | 5 | Farmácia da UBS da Região Administrativa (CNS + CPF + Receita) |

## 3. Indicadores de Gratuidade e Complexidade

- **Gratuidade Plena Farmácia Popular (`pfpb_free`):** 13 itens (54.2%)
- **Exigência de Processo LME / Alto Custo (`requires_lme`):** 6 itens (25.0%)
- **Cobertura de DCBs nos Chunks Normativos:** 100.0%

## 4. Perfilamento dos Chunks Normativos (Camada Silver)

- **Média de palavras por chunk:** `87.92`
- **Mediana de palavras por chunk:** `86.0`
- **Intervalo (mín–máx palavras):** `72` – `109`

| Fonte Normativa (`source_id`) | Chunks |
|---|---|
| `PFPB_2024` | 2 |
| `PRE_EXAME_SESDF_HUB` | 4 |
| `REME_DF_2024` | 2 |
| `RENAME_2024` | 3 |
| `SISREG_CPPAS_DF` | 2 |
