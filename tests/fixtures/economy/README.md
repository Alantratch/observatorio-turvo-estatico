# Fixtures oficiais de Economia

Respostas coletadas em 06/10/2026 do IBGE para testes offline. Sem números fabricados.

- metadata.json: `/api/v3/agregados/5938/metadados`.
- periods.json: `/api/v3/agregados/5938/periodos`.
- aggregate-turvo.json: tabela 5938, N6[4127965], todos os períodos, variáveis 37, 543, 498, 513, 516, 517, 520, 6575, 6574, 525 e 528.
- capita-meta.json: `/api/v1/pesquisas/indicadores/47001`.
- capita-turvo.json: `/api/v1/pesquisas/indicadores/47001/resultados/4127965`.
- indicators38.json: `/api/v1/pesquisas/38/indicadores`, preservando o vínculo 47000 (PIB per capita) → 47001 (Série revisada).

Base: https://servicodados.ibge.gov.br. As fixtures mantêm nomes, unidades, símbolos e precisão das respostas. Consultas completas auditáveis também estão em public/data/economy/raw.
