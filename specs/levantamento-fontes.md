# Levantamento inicial de fontes — SUS Cidadão

Data da pesquisa: 03/11/2026. Branch: `feat/engenharia-dados-mvp`.
Estado: descoberta e inspeção inicial. Nenhuma fonte abaixo foi homologada para respostas ao cidadão.

Este catálogo registra páginas e arquivos consultados pela ferramenta de pesquisa web, que pode utilizar conteúdo indexado. Não equivale a snapshots locais: downloads, hashes, cabeçalhos HTTP, licenças específicas e validação de vigência ainda precisam ser registrados na coleta. Não existem nesta entrega registros normalizados de medicamentos, golden set factual ou integração com estoque.

## Decisão inicial recomendada

Começar com o elenco do Farmácia Popular, cruzá-lo com a RENAME e a REME-DF e adicionar regras administrativas de acesso. Não extrair preparos de exame de instituições diferentes como se fossem intercambiáveis. A relação de 30–50 apresentações ainda será escolhida e revisada; a quantidade de linhas em um elenco não equivale automaticamente à quantidade de apresentações identificadas.

Prioridades: P0 = próximo lote de coleta; P1 = complemento necessário; P2 = somente referência/encaminhamento ou investigação futura.
Estados: inspecionada = conteúdo parcialmente lido; localizada = existência identificada, leitura ou acesso incompleto; restrita = não adequada ao corpus geral do MVP. Todos os estados mantêm revisão pendente.

## Catálogo

### Página central — Assistência Farmacêutica da SES-DF — referência de descoberta

- URL: https://www.saude.df.gov.br/assistencia-farmaceutica
- Órgão: Secretaria de Estado de Saúde do Distrito Federal, Diretoria de Assistência Farmacêutica (DIASF).
- Estado: página oficial inspecionada; indicava atualização em 22/09/2026 na consulta de 05/11/2026.
- Uso: ponto de entrada para REME-DF, farmácias e guia de medicamentos; identifica a DIASF e as gerências dos componentes básico e especializado para esclarecimentos sobre as fontes.
- Limite: a página agregadora não comprova, por si só, presença de uma apresentação, documentos exigidos, elegibilidade ou saldo em estoque. Cada afirmação deve apontar também para a fonte específica e sua versão aplicável.

### F01 — RENAME 2024, 2ª edição — P0, inspecionada

- Órgão: Ministério da Saúde. Abrangência nacional.
- Página de descoberta: https://www.gov.br/saude/pt-br/composicao/sectics/rename/publicacoes/
- Arquivo apontado pela página: https://www.gov.br/saude/pt-br/composicao/sectics/rename/publicacoes/relacao-nacional-de-medicamentos-essenciais-2024
- Formato observado: PDF, 267 páginas; texto extraível pela ferramenta web.
- Evidência de versão: capa e folha de rosto indicam RENAME 2024, 2ª edição, Brasília 2025. A página foi atualizada em 28/07/2026; essa data não é a edição do documento.
- Uso: composição, concentração, forma e componente conforme tabelas e notas; confirmação de presença na edição consultada.
- Limites: não informa estoque por unidade. Confirmar alterações posteriores e relação com consulta dinâmica antes de declarar atualidade.
- Próxima validação: snapshot, hash, leitura das notas e extração de amostra revisada.

### F02 — REME-DF: página de referência — P0, inspecionada

- Órgão: SES-DF. Abrangência: rede distrital.
- URL: https://www.saude.df.gov.br/reme-df
- Formato: HTML; página indica atualização em 29/10/2026.
- Evidência: seções “O que é Relação de Medicamentos” e “Como obter o medicamento”. A página remete à relação e ao portal Farmácias.
- Uso: localizar relação e orientações de dispensação.
- Limite: o botão/conteúdo da relação não foi exposto integralmente na leitura textual. Não assumir API ou exportação estruturada.
- Próxima validação: inspecionar a consulta vinculada e confirmar qual versão da relação é atualmente disponibilizada.

### F03 — REME-DF: relação distrital de 29/10/2026 — P0, selecionada para o corpus

- URL: https://www.saude.df.gov.br/documents/d/saude/reme_df___29_10_2026___final-pdf
- Formato observado: PDF, 98 páginas (3,54 MiB); texto disponível.
- Evidência: documento publicado em 29/10/2026 no portal oficial da SES-DF.
- Uso: fonte distrital escolhida pela equipe para extração tabular, níveis de atenção e notas de dispensação no corpus do MVP.
- Decisão: a edição de 2024 foi retirada do repositório e não será indexada.
- Limite: itens em aquisição, hospitalares ou de emergência não são automaticamente retirada ambulatorial.
- Próxima validação: extração das tabelas da versão 2026 e mapeamento dos itens de atenção básica e especializada.

### F04 — Elenco do Farmácia Popular — P0, inspecionada

- Órgão: Ministério da Saúde. Abrangência nacional.
- URL: https://www.gov.br/saude/pt-br/composicao/sectics/farmacia-popular/arquivos/elenco-de-medicamentos-e-insumos-pfpb.pdf
- Descoberta: link “Elenco de Medicamentos e Insumos PFPB” na página F05.
- Formato: PDF de uma página. Rodapé: atualização em 31/08/2026.
- Uso: primeiro candidato de extração por ser pequeno; elenco de princípios ativos/insumos e quantidades declaradas.
- Limites: nem todas as linhas explicitam forma, denominador e demais campos de apresentação. Não completar campos ausentes. Há medicamentos associados e insumos que precisam de tipos distintos.
- Próxima validação: conferência visual de todas as linhas e complementação documental de apresentações. Existe resultado de busca com arquivo sem sufixo “pfpb”, datado de 02/09/2025: não misturar as duas versões.

### F05 — Farmácia Popular: acesso e documentos — P0, inspecionada

- URL: https://www.gov.br/saude/pt-br/composicao/sectics/farmacia-popular
- Formato: HTML. Publicação/vigência específica das regras não confirmada nesta pesquisa.
- Evidência: seções “Acesso ao programa” e “Pacientes acamados ou impossibilitados de comparecer à farmácia”.
- Uso: requisitos administrativos e distinção entre retirada pelo beneficiário e representação, sujeitos à revisão das exceções.
- Limite: regra geral do programa não comprova estoque nem elegibilidade individual. Cadastros/endereço de credenciadas no DF ainda não foram inspecionados.
- Próxima validação: capturar seções completas e referências normativas; localizar cadastro oficial de credenciadas e verificar data/cobertura antes de oferecer endereços.

### F06 — Farmácias da SES-DF e atenção primária — P0, inspecionada

- Índice: https://www.saude.df.gov.br/farmacias/
- UBS: https://www.saude.df.gov.br/farmacias-unidade-basica-de-saude/
- Formato: HTML. Índice indica atualização em 01/09/2026; não transferir essa data às páginas filhas.
- Uso: distinguir níveis de atenção e coletar instruções por canal. Página UBS acessível, revisão detalhada pendente.
- Limite: identificar uma UBS não basta para afirmar que ela dispensa qualquer medicamento da REME.
- Próxima validação: localizar endereços e documentos, com vínculo verificável entre apresentação, canal e unidade.

### F07 — Atenção secundária — P0, inspecionada parcialmente

- URL: https://www.saude.df.gov.br/farmacias-atencao-secundaria/
- Órgão: SES-DF. Formato: HTML acessível.
- Uso: orientações para policlínicas, CAPS e Farmácia Escola; candidato para canais e requisitos específicos.
- Limite: separar regras por serviço, sem aplicar a toda a rede.
- Próxima validação: revisar página completa, endereços e anexos pertinentes ao lote de medicamentos.

### F08 — Componente especializado — P1, localizada; leitura bloqueada

- URL apontada pelo índice F06: https://www.saude.df.gov.br/componente-especializado/
- Resultado: timeout da ferramenta web ao abrir a página. Não significa inexistência da fonte.
- Uso previsto: documentação e fluxos específicos do componente especializado.
- Próxima validação: nova tentativa de acesso e revisão dos requisitos por medicamento/condição; não generalizar LME para todas as retiradas.

### F09 — Portaria SES-DF nº 117/2026 — P0, inspecionada parcialmente

- URL: https://www.sinj.df.gov.br/sinj/Norma/2fc01aa935834c729138eea708b7a9bd/Portaria_117_20_02_2026.html
- Órgão: SES-DF; publicação consultada no SINJ. Formato: HTML, texto compilado.
- Evidência: título e ementa; norma de prescrição, fornecimento e dispensação nas farmácias ambulatoriais.
- Uso: conferir regras administrativas, documentos e exceções encontrados em páginas/cartas de serviços.
- Limites: interpretação e vigência dos dispositivos precisam de revisão. Não extrair condutas de prescrição para aconselhar usuários.
- Próxima validação: registrar republicações/alterações e os artigos que sustentam cada requisito administrativo selecionado.

### F10 — Denominações Comuns Brasileiras — P1, localizada parcialmente

- Órgão: Anvisa.
- Entrada: https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb
- Lista apontada: https://bibliotecadigital.anvisa.gov.br/jspui/handle/anvisa/11933
- Formato: página HTML; acesso à biblioteca retornou 403 pela ferramenta web.
- Uso: padronização dos nomes de substâncias; DCB não identifica apresentação nem marca.
- Próxima validação: obter consolidação vigente por acesso permitido, identificar versão e condições de reutilização. Não contornar bloqueio nem assumir que uma lista histórica seja vigente.

### F11 — Medicamentos registrados: apoio a nomes comerciais — P1, localizada; arquivo não validado

- Órgão: Anvisa.
- Diretório acessível: https://dados.anvisa.gov.br/dados/
- Página oficial que identifica a base DADOS_ABERTOS_MEDICAMENTOS.csv: https://www.gov.br/anvisa/pt-br/assuntos/fiscalizacao-e-monitoramento/farmacovigilancia/relatorios-periodicos-de-avaliacao-beneficio-risco-rpbr-1
- Dicionário localizado: https://dados.anvisa.gov.br/dados/Documentacao_e_Dicionario_de_Dados_Registros_Validos_Medicamento_V1.pdf
- Resultado: o diretório abriu, mas o recurso de medicamentos não ficou identificado na representação textual; o dicionário retornou tipo application/octet-stream não suportado pelo leitor.
- Uso previsto: candidatos de vínculo entre produto comercial e substâncias, após inspeção efetiva do esquema e situação de registro.
- Limite: nenhum CSV foi baixado ou perfilado. Não assumir que contém todas as apresentações/concentrações necessárias. Registro sanitário não prova presença no SUS.
- Próxima validação: localizar recurso, baixar e inspecionar campos, atualização, situação e granularidade; complementar apresentação com fonte oficial quando necessário.

### F12 — Carta de serviços do HUB-UnB — P0 para documentos; insuficiente para preparos específicos

- Órgão: Hospital Universitário de Brasília, portal federal.
- URL: https://www.gov.br/hubrasil/pt-br/hospitais-universitarios/regiao-centro-oeste/hub-unb/acesso-a-informacao/acoes-e-programas/Cartadeserviosaosusurios_HUBUnB1.pdf
- Formato: PDF com conteúdo legível. Edição/data de revisão ainda não confirmadas no documento.
- Evidência: páginas impressas 42–43, “Realização de exames”. A página 43 informa documentos; a 42 remete ao preparo comunicado no agendamento.
- Uso: caso factual sobre documentação no HUB e caso de abstenção para preparo não especificado.
- Limite: não contém, no trecho revisado, quantidade de horas de jejum por exame. Não extrapolar regras do HUB para outras unidades.
- Próxima validação: confirmar edição e localizar instruções específicas atuais do serviço antes de selecionar os 5–10 exames.

### F13 — Protocolos de acesso vigentes da SES-DF — P1, índice inspecionado

- URL: https://www.saude.df.gov.br/acesso-vigentes
- Formato: HTML com links e intervalos de vigência. Página indica atualização em 23/09/2026.
- Evidência: entradas para PET/CT (21/01/2025–21/01/2027), cintilografia (19/11/2025–19/11/2027) e vídeo-eletroencefalograma adulto (13/08/2026–13/08/2028).
- Uso: localizar fluxos de acesso por procedimento. Os PDFs individuais não foram inspecionados nesta rodada.
- Limite: protocolo de acesso não equivale a instrução de preparo; título “vigente” não dispensa leitura das datas e atos.
- Próxima validação: escolher procedimentos de interesse e revisar documentos, escopo e vigência individualmente.

### F14 — Painel de estoque e dados abertos do DF — P2, referência para investigação

- Órgão: SES-DF / InfoSaúde. Painéis públicos do Power BI; a fonte declarada no painel das UBS é o SIS-Materiais (Sistema de Gestão de Materiais da SES-DF).
- Estoque de medicamentos das UBS: https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-das-ubs/ (`PUB_ESTOQUE_UBS`). Exibe quantidade por produto, filtros de estabelecimento, região e código do produto, e horário da última extração. A expansão da linha mostra locais de estoque. O próprio painel alerta que movimentações ao longo do dia podem alterar o saldo.
- Estoque das Farmácias Especializadas (Alto Custo): https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-de-alto-custo/estoque-de-medicamentos/ (`PUB_ESTOQUE_ALTO_CUSTO`); acesso alternativo: https://info.saude.df.gov.br/sala-de-situacao/painel-infosaude-medicamentos-das-farmacias-especializadas/
- Estoque geral da SES-DF: https://info.saude.df.gov.br/sala-de-situacao/painel-infosaude-estoque-sesdf/ (`PUB_ESTOQUE_GERAL`).
- Outros painéis de estoque identificados na Sala de Situação: https://info.saude.df.gov.br/painel-infosaude-estoque-de-medicamentos-e-insumos/ (dengue); https://info.saude.df.gov.br/estoque-iges/ (quimioterápicos); https://info.saude.df.gov.br/estoque-iges-geral/ (medicamentos e insumos); https://info.saude.df.gov.br/estoque-iges-psicotropicos/ . São recortes específicos, ainda sem validação de cobertura e aplicabilidade ao MVP.
- Portal de dados abertos do InfoSaúde: https://info.saude.df.gov.br/transparencia-e-prestacao-de-contas/dados-abertos/
- Catálogo de Bens e Insumos Padronizados: https://info.saude.df.gov.br/sala-de-situacao/painel-infosaude-catalogo-de-bens-e-insumos-padronizados/ (`PUB_CATALOGO_PRODUTOS`). Candidato a relacionar códigos e descrições de produtos aos painéis de estoque; vínculo ainda não validado.
- Documentos e caminho de acesso ao medicamento: https://info.saude.df.gov.br/como-garantir-seu-medicamento/ (`PUB_DOC_MEDICAMENTOS`). Regras individuais ainda exigem conferência da fonte e aplicabilidade.
- Orientações por canal: https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-ambulatoriais/ e https://info.saude.df.gov.br/saude-do-cidadao/painel-infosaude-farmacias-de-alto-custo/. Incluem informações de atendimento, documentos e, para Alto Custo, distribuição territorial entre farmácias.
- Localização de unidades: https://info.saude.df.gov.br/busca-saude-ubs/ e https://info.saude.df.gov.br/estabelecimentos-de-saude-sesdf/. Localizar uma unidade não comprova que ela dispensa determinado produto.
- Fontes adjacentes, fora do recorte inicial: https://info.saude.df.gov.br/sala-de-situacao/painel-infosaude-atencao-secundaria-exames/ (produção/serviços de exames; não equivale a preparo) e https://info.saude.df.gov.br/painel-infosaude-lista-de-disponibilidade-dos-produtos-do-ptned/ (fórmulas nutricionais do PTNED).
- Uso inicial: consulta e encaminhamento aos painéis oficiais; investigar extração oficial, dicionários de dados, cobertura por unidade, horários de referência e condições de reutilização antes de automatizar a integração.
- Limites: os painéis publicam retratos de estoque, não garantia de disponibilidade no momento da retirada. Nenhuma API pública ou exportação estável dos três painéis foi confirmada; o acesso direto ao SIS-Materiais é restrito. O dataset nacional BNAFAR não substitui os saldos por unidade destes painéis.

## Fontes que não entram como orientação geral

### X01 — POMED/CBMDF

https://saude.cbm.df.gov.br/perguntas-frequentes/

Página oficial acessível, mas o atendimento laboratorial descrito é destinado a militares, dependentes e pensionistas. Excluir do corpus de orientação geral do SUS-DF; pode embasar um caso de teste de não generalização, com contexto institucional explícito.

### X02 — Nota Informativa nº 9/2024: LF-LAM

https://saude.df.gov.br/documents/37101/0/SEI_148173790_Nota_Informativa_9.pdf/44bece88-adee-0bf0-1051-6266847bb363?t=1747916492774

Documento de seis páginas, datado de 09/08/2024, voltado ao teste LF-LAM em contexto especializado de TB/HIV. Apesar de conter orientações de coleta de urina, não é fonte geral para EAS/urocultura. Excluir do lote inicial de exames comuns e não reutilizar o preparo em outro exame.

### X03 — Documentos de outras cidades, notícias e páginas privadas

Não usar para suprir automaticamente lacunas do DF. Notícias podem ajudar a localizar a fonte primária; não substituem o documento aplicável. Documentos em consulta pública não são tratados como aprovados.

## Primeiro lote recomendado e lacunas

1. Coletar F01, F03 e F04 como originais separados, mantendo F03 em revisão de atualidade. Registrar hash, tamanho, URL final, instante de coleta e versão, sem confundir consulta web com download.
2. Usar F04 para selecionar um lote pequeno de apresentações. Conferir forma, liberação e composição em fontes complementares; não publicar linhas incompletas como apresentações certas.
3. Coletar F05–F07 e F09 para orientações administrativas, com evidência por seção/artigo. Reabrir F08 antes de incluir o componente especializado.
4. Usar F12 inicialmente para documentos no HUB e para reconhecer ausência de preparo específico. Ainda não há cinco exames com preparo validado nesta pesquisa.
5. Para fechar exames, escolher um serviço SUS-DF e obter suas instruções oficiais por exame. A revisora pode ajudar a identificar documentos públicos do serviço, sem compartilhar receitas ou dados de pacientes.
6. Validar F10/F11 antes de prometer busca por marcas. Não existem vínculos comerciais aprovados nesta entrega.

## Casos candidatos de avaliação (ainda não constituem golden set revisado)

- Pergunta sobre documentos de exame no HUB: referência inicial F12, p. 43; revisão e versão pendentes.
- Pergunta sobre duração de jejum usando apenas F12: abster-se do número e pedir orientação específica do exame/serviço.
- Pergunta sobre uma apresentação com liberação não informada: exigir desambiguação antes de cruzar listas.
- Pergunta sobre estoque baseada em F04: não inferir disponibilidade física a partir do elenco.
- Pergunta geral de coleta de urina com X02 recuperada: rejeitar extrapolação entre testes.
- Pergunta de cidadão do SUS com X01 recuperada: não aplicar automaticamente regras de público restrito.

## Verificações pendentes para todas as fontes

Disponibilidade de download real; condições de reutilização e redistribuição; atualização e aplicabilidade; conteúdo completo e notas; captura original e hash; campos efetivamente presentes; responsável pela revisão; autorização de publicação do registro derivado. Acesso público não elimina essas verificações.
