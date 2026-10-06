# Fontes e metodologia

Turvo/PR: código IBGE **4127965**. Em outras bases, o identificador pode ter seis dígitos: mapear explicitamente e testar antes de integrar. Não deduzir correspondência apenas pelo nome Turvo (há homônimos).

| Área | Órgão / fonte | URL | Situação |
| --- | --- | --- | --- |
| População, território | IBGE SIDRA tabela 4714 | https://sidra.ibge.gov.br/tabela/4714 | Integrada; Censo 2022 |
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
