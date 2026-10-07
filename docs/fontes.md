# Fontes e metodologia

Turvo/PR: código IBGE **4127965**. Em outras bases, o identificador pode ter seis dígitos: mapear explicitamente e testar antes de integrar. Não deduzir correspondência apenas pelo nome Turvo (há homônimos).

| Área | Órgão / fonte | URL | Situação |
| --- | --- | --- | --- |
| População, território | IBGE SIDRA, Pesquisas, Localidades e Malhas | https://servicodados.ibge.gov.br/api/docs | Integradas; veja documentação de População |
| Economia | IBGE Agregados 5938 e Pesquisas 38/47001 | https://servicodados.ibge.gov.br/api/docs | PIB, per capita, VAB/setores, impostos e comparações integrados |
| Trabalho | MTE/PDET · RAIS e Novo CAGED | https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/estatisticas-trabalho | Integrado: RAIS 2023–2025 e CAGED set/2024–ago/2026; metadados próprios |
| Educação | INEP Censo Escolar, Sinopse, IDEB, SAEB, alfabetização e indicadores anuais | [INEP dados abertos](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos) | Integrado; [arquivos, campos, períodos e limites](modulos/educacao.md) |
| Saúde | Ministério da Saúde / DATASUS / CNES | [Catálogo CNES](https://dadosabertos.saude.gov.br/dataset/cnes-cadastro-nacional-de-estabelecimentos-de-saude) | Rede diária, leitos mensais, regionalização e comparação integrados; [metodologia, campos e fontes](modulos/saude.md) |
| Assistência Social | MDS/SAGICAD/SNAS · serviço municipal RI/VIS DATA, CadSUAS, Censo SUAS e RMA | [Fontes e endpoints](modulos/assistencia-social.md) | Integrado; referências próprias, somente agregados seguros |
| Finanças | Tesouro / SICONFI | https://siconfi.tesouro.gov.br/ | TODO; demonstração |
| Meio Ambiente | MapBiomas, INPE, ANA, IBGE e MMA/CNUC | [Fontes e endpoints](modulos/meio-ambiente.md) | Cobertura, fogo, estações, bioma e interseções de UCs integrados |
| Agropecuária | IBGE PAM / PPM / PEVS e Censo | [Fontes](modulos/agropecuaria.md) | Integrado |

## Consultas SIDRA

Padrão: `https://apisidra.ibge.gov.br/values/t/{tabela}/n6/{codigo}/v/{variavel}/p/{periodo}`. A primeira linha é o cabeçalho, não observação. Validamos D1C (município), D2C (variável), D3C (ano) e MN (unidade).

- Tabela 4714: variáveis 93 (pessoas), 6318 (km²), 614 (hab/km²), período 2022.
- Tabela 5938: variável 37 (mil reais → reais), série disponível.
- Documentação da API: https://apisidra.ibge.gov.br/

`collectedAt` registra a coleta do snapshot numérico. Se os números não mudam, preservamos essa data; `collection.attemptedAt` indica a verificação mais recente. `reference` é o período publicado. Revisões do órgão podem alterar valores de anos anteriores. Os snapshots no Git permitem rastrear alterações.

## Integrações futuras

RAIS/CAGED: distinguir estoque anual de vínculos e fluxos mensais de admissões/desligamentos; verificar mudanças metodológicas e código territorial. Não baixar microdados massivos no navegador.

INEP: distinguir município da escola e residência, rede administrativa e etapa; não expor registros pessoais. DATASUS: definir competência e cobertura; CNES conta estabelecimentos, não população atendida. SICONFI: validar conta contábil, anexo, exercício e estágio da receita/despesa. PAM/PPM: selecionar produtos e unidades compatíveis antes de somar.

Valores fictícios têm `status=mock`, referência “Exemplo fictício”, sem data de coleta. Estão no catálogo para desenvolvimento e nunca nas comparações temáticas de valores oficiais. TODO: substituir por `unavailable` em uma edição institucional antes de divulgação oficial.

## População aprofundada

[Documentação do módulo](modulos/populacao.md) registra tabelas 4714, 6579, 202, 4709, 9606, 9756, 9923 e 9922, API Pesquisas/29167, Localidades e Malhas. Consultas reais e metadados verificados para 4127965 geram `population.json`, com respostas brutas auditáveis. Os novos IDs são `population-census`, `population-estimate`, `territorial-area` e `population-density`. A área anual vem da API Pesquisas, sem alterar a densidade oficial censitária.

A comparação 2010–2022 usa a variação absoluta da tabela 4709 e base 2010 compatibilizada; não a publicação original 2010 da tabela 202. Símbolo SIDRA `-` significa zero absoluto e tem conversão explícita; `X`, `..` e `...` nunca viram zero.

MCP Brasil pode ser usado para descoberta e consulta assistida. Foram analisados os clientes de agregados, municípios, pesquisas e malhas em [Mcp-Brasil/mcp-brasil](https://github.com/Mcp-Brasil/mcp-brasil/tree/2efb258370b125bbf190884283ae10f209b9d335/src/mcp_brasil/data/ibge), licença MIT. Nenhum código foi copiado e o site/ETL não dependem de servidor MCP. A fonte autoritativa dos indicadores de População/Economia permanece o IBGE; Trabalho usa MTE/PDET.

## Economia aprofundada

[Documentação do módulo](modulos/economia.md): tabela 5938, variáveis 37, 498, 513/516, 517/520, 6575/6574, 525/528 e 543. **543 é impostos, em Mil Reais; não PIB per capita.** Este vem de Pesquisas 38, pai 47000/folha 47001, unidade R$, série revisada. PIB 2002–2023, per capita 2010–2023, abertura setorial/VAB total/impostos 2002–2021. Os quatro municípios são coletados pelas mesmas APIs oficiais.

Participações setoriais oficiais têm denominador VAB total; impostos/PIB é cálculo derivado separado. Variação do PIB é nominal, sem correção inflacionária. A falta de abertura em 2022/2023 é característica da divulgação do IBGE. Metadados, símbolos brutos e referências independentes estão em economy.json e economy/raw. JSON e CSVs são produzidos pelo ETL.

Foram inspecionadas ferramentas IBGE, IPEADATA e BACEN do MCP Brasil e catálogo oficial IPEADATA. As séries regionais de preços de 2010 não foram misturadas com os valores correntes do IBGE; indicadores nacionais BACEN não foram atribuídos ao município. MCP é referência de descoberta; IBGE é a fonte autoritativa dos indicadores publicados.

## Trabalho e Emprego · MTE/PDET

[Documentação completa](modulos/trabalho-emprego.md) lista URLs de origem, layouts e filtros. RAIS tabela 4: estoque e cinco setores 2023–2025, conferidos com microdados 2025 (ativos em 31/12, abandonados excluídos). Remuneração nominal de dezembro/2025 calcula média somente com valores positivos, mostrando cobertura. Novo CAGED: 24 competências até agosto/2026, MOV + FOR − EXC por competência original, admissões/desligamentos/saldo, janelas completas, CNAE/CBO com proteção de contagens 1–4 e salário das admissões não intermitentes nos limites metodológicos MTE.

O total nacional de agosto/2026 coincide exatamente com o sumário oficial; a conferência independente municipal CAGED no ISPER/Perfil permanece pendente. Não publicamos estoque CAGED reconstruído nem taxas municipais de emprego/desemprego. SHA256, tamanho, coleta, referência, layouts e revisões estão em `employment.json`.

O MCP Brasil foi inspecionado no commit `2efb258370b125bbf190884283ae10f209b9d335`: não há conector municipal RAIS/CAGED. O catálogo BACEN contém SGS 28561 (saldo CAGED nacional), PNAD e rendimento macro. Não foram atribuídos a Turvo. Oportunidade futura upstream `mte_trabalho`, documentada no módulo, sem servidor MCP obrigatório no site.

## Saúde / CNES

Exportação diária CNES, arquivo anual Hospitais e Leitos com competências mensais, regionalização oficial e tabela oficial de tipos. Publicação do arquivo não substitui competência; coleta é outra data. SUS disponível no cadastro é **ambulatorial**, sem extrapolação para atendimento geral. Gestão não é propriedade. [Documentação completa](modulos/saude.md) contém URLs, SHA-256 no snapshot, mapeamento de campos, consultas rejeitadas, comparação, critérios de situação, zeros confirmados e pendências APS. Fonte estatística: Ministério da Saúde/DATASUS/CNES; MCP Brasil apenas referência técnica.

## Agropecuária / IBGE

[Documentação completa](modulos/agropecuaria.md): PAM 5457 (214/8331/216/112/215), PPM 3939 (105), 74 (106/215), 94 (107), 3940 (4146/215), PEVS 289 (144/145), 291 (142/143), Censo Agropecuário 6754 (183/184) e 6884 (185). Metadados/variáveis/categorias e consultas oficiais Agregados v3 estão no snapshot e nos raws. Referências anuais 2016–2025; estrutura censitária 2017. Tipologia temporária/permanente: metadados 1612/1613. Mil reais viram reais nominais; unidades físicas seguem categorias e notas oficiais PAM (abacaxi/coco em mil frutos). Totais e subcategorias não são somados, cultivo e extração permanecem separados, sigilo nunca é inferido. Não há X neste recorte coletado, mas estados suppressed/notApplicable/unavailable/zero são distintos e testados. MCP Brasil é referência técnica, IBGE é a fonte estatística.

## Assistência Social / MDS

[Documentação completa](modulos/assistencia-social.md): serviço público municipal com filtros `mes_mu`, código MDS de seis dígitos e campos explícitos; dados conferidos nos relatórios RI. Cadastro Único e Bolsa Família setembro/2026; BPC Fonte Pagadora agosto/2026, sem mistura com residência. CadSUAS por data de extração, Censo SUAS 2025 por edição anual, RMA CRAS 2025 somente Base tratada. IBGE 6579/9324 fornece denominadores 2026 para proporção aproximada administrativa (não pobreza/cobertura oficial). Não acessa bases identificadas, RH ou sistemas internos. JSON/CSV somente agregados; supressão 1–4 e complementar, schema permitido e verificação obrigatória no build. Indicadores SUAS/IVCAD e PAEFI permanecem pendentes.

## Meio Ambiente

[Documentação completa](modulos/meio-ambiente.md): MapBiomas Coleção 11/estatísticas municipais, INPE Programa Queimadas AQUA_M-T, inventário ANA/SNIRH, malha/área/bioma IBGE e poligonais MMA/CNUC distribuídas pelo IBAMA. Quantidades derivadas identificadas; indisponibilidade não vira zero. Analisados clientes INPE/ANA do MCP Brasil; API histórica INPE respondeu 404 e telemetria Hidroweb 401. O ETL usa arquivos públicos atuais e serviços cartográficos oficiais, sem dependência do MCP.
