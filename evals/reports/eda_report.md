# Relatório de Análise Exploratória de Dados (EDA) — SUS Cidadão

- **Hash Consolidado do Manifesto (SHA-256):** `6cdf0a15b12bd78da37c7d38d2975c677d6fdc5dea77a521762c86b9f90bd511`
- **Total de Apresentações Canônicas (Gold):** `1775`
- **Denominações Comuns Brasileiras (DCBs únicos):** `960`
- **Total de Chunks Normativos (Silver):** `24`

## 1. Distribuição por Componente da RENAME 2024

| Componente RENAME | Quantidade |
|---|---|
| Básico | 749 |
| Especializado | 488 |
| Estratégico | 220 |
| Hospitalar | 318 |

## 2. Distribuição por Via de Acesso Cidadão

| Via de Dispensação | Quantidade | Regra Operacional |
|---|---|---|
| `ALTO_CUSTO_CEAF` | 487 | Farmácia de Alto Custo SES-DF (Processo LME + Exames PCDT + CID-10) |
| `FARMACIA_POPULAR` | 51 | Drogaria privada credenciada (100% gratuito com CPF + Receita) |
| `HOSPITALAR` | 318 | - |
| `UBS_ATENCAO_PRIMARIA` | 919 | Farmácia da UBS da Região Administrativa (CNS + CPF + Receita) |

## 3. Indicadores de Gratuidade e Complexidade

- **Gratuidade Plena Farmácia Popular (`pfpb_free`):** 51 itens (2.9%)
- **Exigência de Processo LME / Alto Custo (`requires_lme`):** 487 itens (27.4%)
- **Cobertura de DCBs nos Chunks Normativos:** 3.4%

## 4. Perfilamento dos Chunks Normativos (Camada Silver)

- **Média de palavras por chunk:** `93.08`
- **Mediana de palavras por chunk:** `88.0`
- **Intervalo (mín–máx palavras):** `72` – `142`

| Fonte Normativa (`source_id`) | Chunks |
|---|---|
| `ANVISA_PORTARIA_344` | 1 |
| `INFOSAUDE_DF_C06_C07` | 1 |
| `MS_CEAF_C09_C10` | 1 |
| `MS_CESAF_C14` | 1 |
| `PFPB_2024` | 3 |
| `PFPB_C01_2026` | 1 |
| `PNAB_SES_DF` | 1 |
| `PRE_EXAME_SESDF_HUB` | 4 |
| `REME_DF_2024` | 3 |
| `RENAME_2024` | 3 |
| `SES_DF_C02_2026` | 1 |
| `SES_DF_C03_2026` | 1 |
| `SES_DF_C04_2026` | 1 |
| `SISREG_CPPAS_DF` | 2 |
