# SPEC-07: Indexação Automatizada Multi-Coleção no ChromaDB a partir de Fontes JSON para RAG

- **Status:** Em Implementação
- **Fase:** Base Vetorial e Recuperação Semântica (ChromaDB + Metadata Filtering)
- **Dependências:** `SPEC-01-eda-and-sync.md`, `SPEC-03-hybrid-retrieval.md`, `SPEC-06-infosaude-live-api.md`

---

## 1. Objetivo

Implementar a ingestão e indexação vetorial automatizada e determinística no **ChromaDB** a partir dos artefatos JSON das camadas Silver e Gold do projeto SUS Cidadão, viabilizando busca híbrida (semântica via embeddings + filtros exatos por metadados) para os agentes do RAG.

---

## 2. Estrutura das Coleções no ChromaDB

O banco vetorial é persistido localmente em `data/vectorstore/` (ignorado no Git conforme `ADR-004`). São criadas 3 coleções especializadas:

### 2.1 Coleção `ceaf_live_stock` (Fonte: `data/gold/ceaf_live_stock.json`)
- **Objetivo:** Responder a dúvidas de disponibilidade em tempo real nas farmácias de alto custo.
- **ID do Documento:** `ESTOQUE_{UNIDADE}_{COD_PRODUTO}` (ex.: `ESTOQUE_CEILANDIA_19578`).
- **Documento Semântico:**
  ```text
  Medicamento de Alto Custo: {desc_produto} (Código: {cod_produto}).
  Unidade de Dispensação: Farmácia de Alto Custo de {unidade} (CEAF-DF).
  Disponibilidade em Estoque: {disp_estoque}.
  Origem do Abastecimento: {origem_abastecimento}.
  Classificação: {psicotropico}.
  Última atualização registrada no InfoSaúde-DF: {ultima_atualizacao}.
  ```
- **Metadados:**
  - `cod_produto`: `str`
  - `unidade`: `str` (`Asa Sul`, `Ceilândia`, `Gama`)
  - `disp_estoque`: `str` (`COM ESTOQUE`, `SEM ESTOQUE`, etc.)
  - `tem_estoque`: `bool` (`True` se contiver "COM ESTOQUE")
  - `origem`: `str` (`SES-DF` ou `Ministério da Saúde`)

### 2.2 Coleção `df_pharmacies` (Fonte: `data/gold/df_pharmacies_geolocated.json`)
- **Objetivo:** Resolver localização, proximidade, rota e dados de contato de farmácias de UBS, Hospitais e CEAF.
- **ID do Documento:** `FARMACIA_{CNES}` (ex.: `FARMACIA_0010987`).
- **Documento Semântico:**
  ```text
  Estabelecimento de Saúde: {name} (CNES: {cnes}).
  Tipo de Farmácia: {pharmacy_type}.
  Endereço: {address}, {neighborhood_or_ra} - Distrito Federal.
  Coordenadas Geográficas: Latitude {latitude}, Longitude {longitude}.
  Link para Navegação no Google Maps: {google_maps_url}.
  Regiões Administrativas com Cobertura Direta: {covered_ras}.
  E-mail de Contato/Cadastro: {contact_email}.
  ```
- **Metadados:**
  - `cnes`: `str`
  - `bairro_ou_ra`: `str`
  - `tipo_farmacia`: `str`
  - `tem_coordenadas`: `bool`
  - `latitude`: `float` (ou 0.0)
  - `longitude`: `float` (ou 0.0)

### 2.3 Coleção `sus_normative_protocols` (Fontes: `normative_chunks.json` + `medicamentos_sus_canonical.json`)
- **Objetivo:** Recuperação de regras normativas, prazos de receita, documentação PCDT/LME e regulamentação SISREG.
- **ID do Documento:** `CHUNK_{chunk_id}` ou `CANONICAL_{medication_id}`.
- **Documento Semântico:** Conteúdo normativo com metadados de fonte, página, seção e DCBs associados.

---

## 3. Critérios de Aceite da SPEC-07
- [ ] Classe `ChromaVectorStoreManager` implementada em `src/sus_cidadao_ds/retrieval/chroma_indexer.py`.
- [ ] Suporte a `upsert` em lote evitando duplicatas e permitindo atualizações diárias de estoque.
- [ ] Método `search(query, collection_name, where_filter, top_k)` retornando texto semântico, metadados e score de similaridade (cosseno).
- [ ] Integração com a CLI (`index-chroma` e `search-chroma`).
- [ ] Teste automatizado validando a persistência e busca das 3 coleções.

