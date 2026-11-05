# SPEC-06: Ingestão Periódica da API Pública oculta do InfoSaúde-DF (Estoque em Tempo Real & Mapas/Geolocalização)

- **Status:** Implementado e Validado com Dados Reais da SES-DF
- **Fase:** Integração em Tempo Real (Estoque Farmácias de Alto Custo, UBS e Geolocalização de Unidades)
- **Dependências:** `SPEC-00-architecture.md`, `SPEC-01-eda-and-sync.md`

---

## 1. Descoberta Técnica (Inspeção de Rede & Engenharia Reversa dos Painéis)

A página oficial [`https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-de-alto-custo/estoque-de-medicamentos/`](https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-de-alto-custo/estoque-de-medicamentos/) é servida em WordPress (`page_id=2583`) e embute painéis **Microsoft Power BI Publish-to-Web** hospedados no cluster governamental sul-americano da Microsoft (`https://wabi-brazil-south-api.analysis.windows.net`).

Embora não exista um botão de download CSV público na página, o cliente Web do Power BI consome uma **API REST Pública (Semantic Query API)** autenticada exclusivamente pelo cabeçalho público `X-PowerBI-ResourceKey` de cada painel.

### 1.1 Mapeamento Completo das 3 APIs Descobertas no InfoSaúde-DF

| Painel InfoSaúde | ResourceKey (`X-PowerBI-ResourceKey`) | Model ID | Dataset ID (`dbName`) | Tabelas Principais Descobertas |
|---|---|---|---|---|
| **1. `PUB_ESTOQUE_ALTO_CUSTO`** *(Estoque CEAF + Mapas CEAF)* | `a665320c-1f2b-43cd-8380-6d39f535daf9` | `10730466` | `424ade14-3f72-4830-a4dc-ab612ad877ee` | `estoque_geral_ceaf` (857 linhas / 294 medicamentos), `Data_atualização`, `Localização Asa Sul`, `Localização Ceilândia`, `Localização Gama`, `end_web` |
| **2. `PUB_DOC_MEDICAMENTOS`** *(Mapas/Lat-Lng de 228 Farmácias/UBS + Protocolos/CID-10)* | `d77b9ba0-317a-4041-88a0-3241c35384ac` | `10722913` | `c021e607-7580-407e-bbab-4312c5c14cd9` | `Estabelecimentos` (228 unidades com CNES, endereço, `latitude`, `longitude`), `gabarito_localiz_ubs`, `tb_diasf_componente_especializado`, `tb_diasf_farmacia_ubs`, `Dt_att` |
| **3. `PUB_ESTOQUE_UBS`** *(Estoque Farmácias das UBS)* | `5ccba871-5230-4333-86f6-7fc3a29b5d5b` | `10723062` | `ceb0186a-2546-4bfd-814e-5dad49b318cc` | `st_stage_trak tab_sismateriais_epi` (`i_cod_produto`, `i_desc_produto`, `i_qtd_rede`, `cnes`, `i_desc_radf`, `status disponivel rede`, `data_extracao`) |

---

## 2. Frequência e Janela de Atualização Identificadas nos Dados

Através da consulta direta às tabelas `Data_atualização`, `estoque_geral_ceaf.ultima_atualizacao` e `Dt_att`:

1. **Estoque de Medicamentos (`PUB_ESTOQUE_ALTO_CUSTO` — `estoque_geral_ceaf`):**
   - **Frequência:** **Diária (2x ao dia em dias úteis)**.
   - **Janelas observadas nos registros:**
     - **Carga da meia-noite (`00:00:00-03`):** consolidação diária do sistema de materiais (`SISMATERIAIS / TRAK`).
     - **Carga intradiária (`13:45` – `14:37 BRT`):** atualização vespertina do painel (`Data de Atualização = 14:37:46`).
2. **Catálogo de Medicamentos, Documentos Exigidos e Geolocalização das UBS (`PUB_DOC_MEDICAMENTOS`):**
   - **Frequência:** **Semanal (Segundas-feiras às `00:19 BRT`)**.

---

## 3. Endpoints REST para Consumo Direto

- **Schema Conceitual (GET):**
  `GET https://wabi-brazil-south-api.analysis.windows.net/public/reports/{ResourceKey}/conceptualschema`
  Header: `X-PowerBI-ResourceKey: {ResourceKey}`
- **Consulta de Dados (POST):**
  `POST https://wabi-brazil-south-api.analysis.windows.net/public/reports/querydata?synchronous=true`
  Headers:
  - `Content-Type: application/json`
  - `X-PowerBI-ResourceKey: {ResourceKey}`

### Algoritmo de Descompressão DSR (Data Shape Result)
O Power BI retorna os dados comprimidos no formato `dsr.DS[0].PH[0].DM0` com dicionários `ValueDicts`:
- Cada linha contém um array `C` (valores das colunas alteradas), uma máscara de bits `R` (*Repeat Bitmask*: se o bit $i$ é `1`, repete o valor da linha anterior na coluna $i$) e uma máscara de bits `Ø` (*Null Bitmask*: se o bit $i$ é `1`, a coluna $i$ é `None`).
- Os 100 primeiros valores distintos de colunas texto ficam indexados em `ValueDicts["D0"]`, `ValueDicts["D1"]`, etc., enquanto valores subsequentes vêm inline como string em `C`.

---

## 4. Critérios de Aceite da SPEC-06
- [x] Cliente `InfoSaudeLiveClient` implementado em `src/sus_cidadao_ds/ingestion/infosaude_client.py` com decodificador DSR completo.
- [x] Extração e persistência dos **857 registros de estoque real** (294 medicamentos nas unidades Asa Sul, Ceilândia e Gama) em `data/gold/ceaf_live_stock.json`.
- [x] Extração das **3 unidades CEAF com Google Maps Embed + coordenadas exatas** e das **171 farmácias/UBS geolocalizadas do DF** em `data/gold/df_pharmacies_geolocated.json`.
- [x] Workflow agendado GitHub Actions (`.github/workflows/infosaude-stock-sync.yml`) para sincronização automática diária (06h e 15h BRT) e semanal.

