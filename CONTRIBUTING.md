# Como contribuir

Abra uma issue com módulo, fonte e resultado esperado. Envie alterações em branches e pull requests pequenos. Use Node 22 e Python 3.10+; execute `npm ci`, `npm test` e `npm run build`.

Para adicionar um indicador, use o contrato de `src/lib/types.ts`, fonte HTTPS, órgão, período, unidade, código IBGE e coleta. Demonstração deve ter `status=mock`, data de coleta null e nota explícita. Nunca apresentar números fictícios como oficiais. Não substituir falhas ou supressões por zero.

Conectores devem validar município, variável, unidade e paginação, ter timeout e preservar último snapshot válido. Inclua teste com fixture pequena, verifique licença/atribuição da fonte e atualize `docs/fontes.md`. Não versionar microdados pessoais, credenciais ou downloads enormes.

Componentes devem funcionar em celular, teclado e com estados de carregamento/erro. Gráficos precisam de tabela equivalente. Preservar cores legíveis, foco visível e HTML semântico.

MIT licencia o código; dados de terceiros obedecem seus próprios termos. Não fazer contribuições que atribuam ao projeto caráter oficial sem autorização institucional.
