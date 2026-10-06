# Fixtures públicas MTE/PDET

Coleta de 06/10/2026. `mov.csv`: primeiras 11 movimentações de Turvo/PR e uma de Turvo/SC extraídas de `CAGEDMOV202608.7z`. `for.csv`: duas movimentações de Turvo declaradas em agosto, competência julho de 2026. `exc.csv`: seis exclusões de Guarapuava, declaradas em agosto de 2026; Turvo não tinha exclusões nesse arquivo. `exc-origin.json` identifica o arquivo.

Origem: `ftp://ftp.mtps.gov.br/pdet/microdados/NOVO%20CAGED/2026/202608/`. Todos são registros públicos não identificados. Mantivemos os valores originais dos campos estatísticos utilizados no ETL. Os campos de características individuais não utilizados (idade, sexo, raça, escolaridade etc.) foram esvaziados: esta é uma projeção de teste, não microdados completos. Não há CPF/CNPJ. Fixtures ficam fora de `public/`.

`rais-table4.json` é um recorte das quatro linhas oficiais da Tabela 4 da divulgação RAIS 2025 (anos 2023–2025), incluindo cabeçalhos e hash do XLSX de origem. O arquivo público `metadata/employment/rais-table4.json` permite auditoria independente dos números de estoque.

Cenários controlados nos testes reutilizam linhas reais e modificam competência/UF/flags somente em memória para verificar períodos, exclusões, erros e privacidade. Eles não são snapshots publicados nem substituem a fonte.

`rais-2025.csv`: projeção dos primeiros registros territoriais de Turvo/PR no arquivo regional `RAIS_VINC_PUB_SUL.COMT`, incluindo um vínculo abandonado e um inativo. Encoding original cp1252, vírgula, 62 cabeçalhos originais. Somente município, ativo, abandonado, classe CNAE e remuneração nominal de dezembro foram mantidos; demais campos estão vazios. O parser rejeita um layout não cadastrado e não aplica o formato legado (TXT com `;`) à RAIS 2025.
