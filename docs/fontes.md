# Fontes e metodologia

Turvo/PR: código IBGE **4127965**. Em outras bases, o identificador pode ter seis dígitos: mapear explicitamente e testar antes de integrar. Não deduzir correspondência apenas pelo nome Turvo (há homônimos).

| Área | Órgão / fonte | URL | Situação |
| --- | --- | --- | --- |
| População, território | IBGE SIDRA, Pesquisas, Localidades e Malhas | https://servicodados.ibge.gov.br/api/docs | Integradas; veja documentação de População |
| Economia | IBGE SIDRA tabela 5938 | https://sidra.ibge.gov.br/tabela/5938 | Integrada; série histórica disponível |
| Trabalho | MTE RAIS e Novo CAGED | https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho | TODO; demonstração |
| Educação | INEP Censo Escolar / IDEB | https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos | TODO; demonstração |
| Saúde | DATASUS / CNES | https://datasus.saude.gov.br/ e https://cnes.datasus.gov.br/ | TODO; demonstração |
| Finanças | Tesouro / SICONFI | https://siconfi.tesouro.gov.br/ | TODO; demonstração |
| Contratações | MGI / PNCP | https://pncp.gov.br/ | TODO; demonstração |
| Agropecuária | IBGE PAM / PPM | https://sidra.ibge.gov.br/tabela/5457 | TODO; demonstração |

## Consultas SIDRA

Padrão: `https://apisidra.ibge.gov.br/values/t/{tabela}/n6/{codigo}/v/{variavel}/p/{periodo}`. A primeira linha é o cabeçalho, não observação. Validamos D1C (município), D2C (variável), D3C (ano) e MN (unidade).

- Tabela 4714: variáveis 93 (pessoas), 6318 (km²), 614 (hab/km²), período 2022.
- Tabela 5938: variável 37 (mil reais → reais), série disponível.
- Documentação da API: https://apisidra.ibge.gov.br/

`collectedAt` registra a coleta do snapshot numérico. Se os números não mudam, preservamos essa data; `collection.attemptedAt` indica a verificação mais recente. `reference` é o período publicado. Revisões do órgão podem alterar valores de anos anteriores. Os snapshots no Git permitem rastrear alterações.

## Integrações futuras

RAIS/CAGED: distinguir estoque anual de vínculos e fluxos mensais de admissões/desligamentos; verificar mudanças metodológicas e código territorial. Não baixar microdados massivos no navegador.

INEP: distinguir município da escola e residência, rede administrativa e etapa; não expor registros pessoais. DATASUS: definir competência e cobertura; CNES conta estabelecimentos, não população atendida. SICONFI: validar conta contábil, anexo, exercício e estágio da receita/despesa. PNCP: ler documentação de filtros, paginação e unidade compradora; não confundir total contratado com quantidade de editais. PAM/PPM: selecionar produtos e unidades compatíveis antes de somar.

Valores fictícios têm `status=mock`, referência “Exemplo fictício”, sem data de coleta. Estão no catálogo para desenvolvimento e nunca no comparador de valores oficiais. TODO: substituir por `unavailable` em uma edição institucional antes de divulgação oficial.

## População aprofundada

[Documentação do módulo](modulos/populacao.md) registra tabelas 4714, 6579, 202, 4709, 9606, 9756, 9923 e 9922, API Pesquisas/29167, Localidades e Malhas. Consultas reais e metadados verificados para 4127965 geram `population.json`, com respostas brutas auditáveis. Os novos IDs são `population-census`, `population-estimate`, `territorial-area` e `population-density`. A área anual vem da API Pesquisas, sem alterar a densidade oficial censitária.

A comparação 2010–2022 usa a variação absoluta da tabela 4709 e base 2010 compatibilizada; não a publicação original 2010 da tabela 202. Símbolo SIDRA `-` significa zero absoluto e tem conversão explícita; `X`, `..` e `...` nunca viram zero.

MCP Brasil pode ser usado para descoberta e consulta assistida. Foram analisados os clientes de agregados, municípios, pesquisas e malhas em [Mcp-Brasil/mcp-brasil](https://github.com/Mcp-Brasil/mcp-brasil/tree/2efb258370b125bbf190884283ae10f209b9d335/src/mcp_brasil/data/ibge), licença MIT. Nenhum código foi copiado e o site/ETL não dependem de servidor MCP. A fonte autoritativa de todos os valores publicados permanece o IBGE.
