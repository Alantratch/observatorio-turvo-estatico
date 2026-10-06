# Roadmap por módulos

Cada etapa deve incluir conector, metadados, teste de normalização e revisão da metodologia antes de marcar um dado como oficial.

1. **População:** implementados Censos publicados, estimativas anuais separadas, crescimento compatibilizado, pirâmide etária, sexo, cor ou raça, índices demográficos, urbano/rural, domicílios, malha municipal e downloads. Próximos passos: comparação regional no novo schema e história em geografia compatível para Censos anteriores. Veja [módulo População](modulos/populacao.md).
2. **Economia:** TODO PIB histórico, valor adicionado por setor, deflator documentado e cautela com mudanças metodológicas.
3. **Trabalho:** TODO importadores agregados RAIS/CAGED, estoque anual e saldo mensal em telas distintas.
4. **Educação:** TODO agregação do Censo Escolar e IDEB por etapa/rede; supressão de células sensíveis.
5. **Saúde:** TODO CNES por competência, séries de estabelecimentos, definição de indicadores de cobertura.
6. **Finanças:** TODO conector SICONFI com anexos DCA/RREO/RGF, valores realizados e comparações per capita.
7. **PNCP:** TODO coleta paginada, identificação territorial da unidade compradora, filtros e links dos contratos.
8. **Agropecuária:** TODO séries PAM/PPM por produto, valor, quantidade e área; distinguir unidades.
9. **Comparador:** TODO selecionar municípios do Paraná, construir benchmarks e gráficos comparáveis.
10. **Catálogo:** TODO exportar CSV, dicionário por campo, schema JSON formal e relatório de qualidade.
11. **Metodologia:** TODO changelog de revisões, autoria da curadoria e processo público de correção.
12. **Visão Geral:** TODO destaque dos módulos prontos, mapa, tendência apenas com séries verificadas.

Transversal: separar páginas temáticas quando crescerem, testes de interface, auditoria WCAG, revisão de dependências, execução de testes periódicos contra fixtures reais, limites de tamanho de dados e armazenamento externo somente se necessário.
