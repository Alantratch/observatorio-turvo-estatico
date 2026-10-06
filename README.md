# Observatório de Turvo / PR

Observatório municipal **independente**, modular e open-source de Turvo/PR, código IBGE **4127965**. Interface em português, responsiva, com indicadores, gráficos, tabelas acessíveis, catálogo pesquisável, downloads JSON e comparação entre municípios. Não é um portal oficial da Prefeitura.

## Rodar localmente

Requisitos: Node.js 22+, npm e Python 3.10+ (sem bibliotecas Python externas).

```sh
npm ci
npm run dev
```

Abra o endereço informado pelo Vite. Para compilar e inspecionar a versão de produção:

```sh
npm test
npm run build
npm run preview
```

O build funciona **sem acessar fontes públicas**, usando os snapshots versionados. O navegador consulta apenas arquivos estáticos; não acessa SIDRA ou microdados MTE diretamente.

## População: módulo completo

A página População tem retrato atual, evolução censitária, estimativas separadas, pirâmide etária, perfil demográfico, cor ou raça, urbano/rural, domicílios e mapa municipal oficial. Todos os números são coletados do IBGE e têm fonte, pesquisa, tabela/indicador, referência, coleta e metodologia. Nenhum mock é usado em População.

O novo `public/data/population.json` preserva dimensões e universos próprios. Há downloads JSON, CSV e GeoJSON, tabelas acessíveis e respostas brutas para auditoria. O ETL está dividido em `scripts/common.py`, `scripts/sources/ibge.py` e `scripts/modules/population.py`. A página é carregada sob demanda.

```sh
# Atualizar somente População; não consultar os outros módulos:
python3 scripts/etl.py --module population
# Validar sem rede:
python3 scripts/etl.py --module population --offline
```

A comparação oficial 2010–2022 usa população 2010 territorialmente compatibilizada, diferente do Censo 2010 original. Densidade censitária 2022 não é recalculada com área 2025. Veja [documentação completa de População](docs/modulos/populacao.md) para fontes, IDs, fórmulas e limites.

## Economia: PIB e estrutura municipal

Página própria com PIB e variação nominal (2002–2023), PIB per capita oficial (2010–2023), VAB e participações setoriais (2002–2021), impostos separados e comparação com Guarapuava, Pitanga e Laranjal. Há gráficos, tabelas acessíveis, narrativas determinísticas, referências independentes, fontes e downloads JSON/CSV. **Setores 2021 não são apresentados como composição do PIB 2023.**

A tabela 5938 é coletada pela API de Agregados v3. A variável 543 é impostos em mil reais; PIB per capita vem da pesquisa 38/indicador 47001 da API Pesquisas, sem divisão por população de outro módulo. O dataset multidimensional economy.json e respostas brutas mantêm todos os metadados e precisão oficial. Veja [documentação de Economia](docs/modulos/economia.md).

```sh
# Atualizar somente Economia, sem consultar População ou outros módulos:
python3 scripts/etl.py --module economy
# Validar os snapshots de Economia sem rede:
python3 scripts/etl.py --module economy --offline
```

## Trabalho e Emprego: RAIS e Novo CAGED

Página própria com **RAIS 2023–2025**, estoque e estrutura setorial, remuneração nominal de dezembro/2025, **Novo CAGED setembro/2024–agosto/2026** com ajustes, acumulado no ano, janela móvel de 12 meses, setores, CNAE, CBO, salários das admissões e comparação regional. Dados oficiais substituem os mocks `formal-jobs` e `caged-balance`. RAIS mede estoque anual; Novo CAGED mede eventos mensais. Vínculos e movimentos não são pessoas únicas; saldo não é estoque e não permite calcular desemprego municipal.

Há tabelas acessíveis, narrativas determinadas pelos dados, gráficos, metadados, proteção de pequenas contagens e downloads JSON/CSV. Estoque/5 setores da RAIS foram conferidos com a tabela oficial nos quatro municípios; o Novo CAGED agosto/2026 reproduziu exatamente o total nacional do MTE. **Conferência independente municipal CAGED no ISPER/Perfil permanece pendente**, assim como RAIS Estabelecimento e evolução da remuneração anual. A média RAIS informa a amostra e as remunerações ausentes/zero.

```sh
# Descobrir novos períodos; fontes independentes, sem baixar a mesma divulgação:
python3 scripts/etl.py --module employment --source caged
python3 scripts/etl.py --module employment --source rais
# Remuneração RAIS é opcional/manual: arquivo regional grande e layout validado.
python3 scripts/etl.py --module employment --source rais --rais-remuneration --cache .mte-cache
# Incorporar revisão na mesma divulgação, com cache não público:
python3 scripts/etl.py --module employment --source caged --force --cache .mte-cache
python3 scripts/etl.py --module employment --offline
```

O processamento de arquivos oficiais `.7z` usa **7-Zip** (`7zip` no Ubuntu, `7z`/`7zz` ou variável `MTE_7ZIP`). Python continua sem bibliotecas externas. Arquivos são lidos em streaming e descartados ao final, exceto quando houver cache explicitamente solicitado fora de `public/data`. A atualização semanal `all` não baixa microdados de Trabalho; há um workflow mensal próprio como template. Veja [conceitos, layouts, fontes, validações e operação de Trabalho e Emprego](docs/modulos/trabalho-emprego.md).

## Atualizar os dados

```sh
npm run data:update
# Apenas verificar os arquivos existentes, sem rede:
python3 scripts/etl.py --offline
```

O ETL de Economia consulta Agregados v3 e Pesquisas v1 para Turvo, Guarapuava, Laranjal e Pitanga; o conector inicial SIDRA mantém os demais indicadores, com timeout, três tentativas e validação de município, variável, unidade e valores. Se uma consulta falhar, mantém o último snapshot válido e registra falha em `collection.failures`. A tentativa mais recente está em `collection.attemptedAt`; a coleta do valor preservado fica em `collectedAt`. Não troca uma série oficial por demonstrações.

Integrações iniciais: população residente, área territorial e densidade do Censo 2022 (tabela 4714); PIB total (tabela 5938, último período disponível). A disponibilidade efetiva está registrada no JSON. PIB em **mil reais** é multiplicado por 1.000. PIB é nominal, não deflacionado. Séries iniciais oficiais podem ter somente uma observação; não interpolamos anos inexistentes.

Dados em Educação, Saúde, Finanças, Contratações e Agropecuária são explicitamente **fictícios**, destinados a demonstrar os componentes. Não use os valores demonstrativos para decisões ou publicações. O comparador usa apenas observações oficiais da mesma referência e unidade.

## Módulos

| Módulo | MVP | Evolução |
| --- | --- | --- |
| Visão Geral | Cards oficiais, gráficos e referências | Destaques editoriais e mapa |
| População | Página própria: Censo, estimativas, idade/sexo, cor/raça, urbano/rural, domicílios e território | Comparador regional no novo schema |
| Economia / PIB | PIB, per capita, variação nominal, VAB/setores, impostos, história e comparação regional | Novas divulgações e benchmark estadual compatível |
| Trabalho e Emprego | RAIS anual/estrutura/remuneração e CAGED mensal ajustado, CNAE/CBO, comparação, downloads | Conferência municipal ISPER, estabelecimentos e história salarial |
| Educação | Demo Censo Escolar | Matrículas, IDEB e rede escolar |
| Saúde | Demo CNES | Estabelecimentos, cobertura e indicadores |
| Finanças Públicas | Demo SICONFI | DCA/RREO/RGF normalizados |
| Contratações / PNCP | Demo | Coleta paginada e filtro municipal validado |
| Agropecuária | Demo PAM | PAM/PPM, produtos e unidades |
| Comparador Municipal | Comparação SIDRA de três municípios | Seleção ampliada, taxas comparáveis |
| Catálogo de Dados | Busca, metadados, download JSON | CSV, dicionário e séries por fonte |
| Sobre / Metodologia | Conceitos, atualização e limites | Registro de revisões metodológicas |

## Estrutura

```text
src/
  components/Indicators.tsx  # Cards, gráficos e tabela reutilizáveis
  modules/catalog.ts        # Registro central dos módulos e navegação
  lib/types.ts              # Contrato normalizado de dados
  lib/data.ts               # Carregamento e formatação
  App.tsx                   # Composição das páginas e estados
  modules/population/       # Página, gráficos, metadados e schema de População
  modules/economy/          # Página e gráficos próprios, comparação e metodologia
  modules/employment/       # RAIS/CAGED separados, gráficos, tabelas e metodologia
public/data/
  indicators.json           # Snapshots de Turvo + demonstrações identificadas
  comparison.json           # Snapshots oficiais dos municípios comparados
  population.json           # Dados multidimensionais de População
  economy.json              # PIB, per capita, setores, impostos e comparações
  employment.json           # RAIS e CAGED multidimensionais, quatro municípios
  exports/                  # CSVs de emprego, gerados pelo ETL
  metadata/employment/      # Controles oficiais municipais RAIS
  economy/                  # Respostas oficiais auditáveis
  gdp*.csv                  # PIB e per capita, gerados pelo ETL
  economy-sectors.csv        # VAB e participações setoriais
  population/               # Malha municipal e respostas brutas auditáveis
scripts/etl.py              # Orquestração incremental de ETLs
scripts/common.py           # HTTP, números e escrita atômica
scripts/sources/ibge.py      # Metadados e parsing completo de agregados
scripts/modules/population.py # Coleta e validação do módulo População
scripts/modules/economy.py    # Coleta e validação do módulo Economia
scripts/sources/mte.py         # Transporte, descoberta, layouts e streaming MTE
scripts/modules/employment.py # RAIS, CAGED, ajustes, privacidade e exportação
tests/test_etl.py           # Conversão, integridade e comportamento em falhas
docs/github-actions/        # Templates de CI, coleta semanal e deploy opcional (ativar abaixo)
```

Vite + React + TypeScript permite evolução incremental de componentes e módulos, com build puramente estático. Gráficos usam Recharts; ícones, Lucide. Rotas por hash evitam exigir reescrita do servidor e funcionam em hospedagem estática. Python usa apenas a biblioteca padrão. Veja [arquitetura](docs/arquitetura.md), [fontes](docs/fontes.md) e [roadmap](docs/roadmap.md).

## Ativar as automações no GitHub

Os workflows estão prontos em `docs/github-actions/`. A autenticação usada na criação do repositório não tinha o escopo `workflow`, e o GitHub recusou o envio para `.github/workflows/`. Por isso **as automações ainda não estão ativas no repositório remoto**.

Para ativá-las numa cópia atualizada do repositório:

```sh
gh auth refresh -h github.com -s workflow
mkdir -p .github/workflows
cp docs/github-actions/*.yml .github/workflows/
git add .github/workflows
git commit -m "ci: ativar build, atualização e deploy"
git push
```

Depois confira a aba Actions. O envio exige uma credencial com permissão para workflows. Até ativar, execute a atualização manualmente pelo comando local. O workflow de coleta publica o snapshot preservado e o relatório de falha antes de sinalizar erro ao GitHub.

## Deploy no Cloudflare Pages

Opção recomendada: conecte este repositório no painel **Workers & Pages → Create → Pages → Connect to Git**.

- Branch de produção: `main`.
- Comando: `npm run build`.
- Diretório de saída: `dist`.
- Node.js: 22 (variável `NODE_VERSION=22` se necessário).
- Diretório raiz: raiz do repositório.
- Nenhum segredo ou Worker necessário ao site.

Configuração oficial: https://developers.cloudflare.com/pages/framework-guides/deploy-a-react-site/

Alternativa por GitHub Actions: crie um projeto Pages de upload direto chamado `observatorio-turvo-estatico` e configure os secrets `CLOUDFLARE_API_TOKEN` (escopo limitado a Pages) e `CLOUDFLARE_ACCOUNT_ID`. O workflow de deploy compila e publica com Wrangler. Sem secrets, compila e informa que a publicação foi pulada. **Escolha um único modo de deploy** para evitar publicações duplicadas. O provisionamento da conta Cloudflare não é feito pelo repositório.

O template mensal de Trabalho verifica CAGED no dia 3 às 10:31 UTC e permite RAIS manual; remuneração é uma opção explícita. A atualização semanal dos demais conectores executa segunda-feira às 09:17 UTC (06:17 em Brasília) e pode ser iniciada manualmente. Commits feitos com `GITHUB_TOKEN` não acionam novos workflows de push; por isso o próprio workflow de coleta compila e publica quando há secrets Cloudflare. Em integração Git, se o provedor não disparar build para commits do bot, use o modo Actions. Os agendamentos do GitHub podem atrasar e podem ser desabilitados por inatividade em repositórios públicos: consulte o histórico de Actions.

## Custo e segurança

MVP sem VPS, banco, autenticação ou backend permanente. Armazena somente pequenos agregados públicos. Pode operar nos planos gratuitos de Pages e GitHub Actions, respeitando quotas vigentes; não há garantia de gratuidade ilimitada. Domínio próprio é opcional. Não configurar serviços faturáveis é suficiente para o MVP; R2, D1 e Worker não são necessários. Fontes externas podem limitar requisições.

Não coloque tokens em `public/` ou variáveis `VITE_*`: o build publica esses valores. Secrets de deploy ficam no GitHub. Cabeçalhos básicos de segurança estão em `public/_headers`. A fonte Google Fonts é opcional, com fallback local do sistema.

## Qualidade e contribuição

`npm test` valida o ETL e os dados locais. `npm run build` verifica TypeScript e gera os arquivos estáticos. CI executa ambos e salva o artefato `dist`. [CONTRIBUTING](CONTRIBUTING.md) explica como ampliar um módulo e revisar fontes.

Licença MIT para o código. Os dados mantêm os termos e atribuições de cada órgão; a licença do código não altera a licença dos dados de terceiros.
