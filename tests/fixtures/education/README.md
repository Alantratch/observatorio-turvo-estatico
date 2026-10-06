# Fixtures reais INEP

Projeções dos arquivos oficiais INEP 2025, coletados em 06/10/2026. Os XLSX foram reduzidos a cabeçalho técnico e linhas dos quatro municípios usados pelo observatório, incluindo Turvo/SC quando presente para testar o homônimo. O arquivo de escolas contém todas as 17 escolas de Turvo/PR e uma escola por comparador, com somente campos institucionais/contagens necessários aos testes. Não contém registros de pessoas.

As quatro tabelas CSV 2025 são reconstruídas em um ZIP temporário pelos testes a partir desses campos reais, para validar a junção por CO_ENTIDADE, codificação cp1252 e delimitador semicolon. Não são o ZIP nacional original. Fonte, URL e referência dos indicadores estão em cada fixture. Ver `docs/modulos/educacao.md` para os arquivos/dicionário e decisões metodológicas.
