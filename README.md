# Observatório de Turvo / PR

Observatório municipal **independente**, modular e open-source de Turvo/PR, código IBGE **4127965**. Interface em português, responsiva, com indicadores, gráficos, tabelas acessíveis, catálogo pesquisável, downloads JSON e comparação entre municípios. Não é um portal oficial da Prefeitura.

## Rodar localmente

Requisitos: Node.js 22+, npm e Python 3.10+. Educação/testes usam as dependências XLSX abaixo; o build do site não exige Python.

```sh
npm ci
npm run dev
```

Abra o endereço informado pelo Vite. Para compilar e inspecionar a versão de produção:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements-education.txt
npm test
npm run build
npm run preview
```

O build funciona **sem acessar fontes públicas**, usando os snapshots versionados. O navegador consulta apenas arquivos estáticos; não acessa SIDRA, INEP ou microdados MTE diretamente.

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

O processamento de arquivos oficiais `.7z` usa **7-Zip** (`7zip` no Ubuntu, `7z`/`7zz` ou variável `MTE_7ZIP`). O conector MTE continua usando apenas a biblioteca padrão do Python. Arquivos são lidos em streaming e descartados ao final, exceto quando houver cache explicitamente solicitado fora de `public/data`. A atualização semanal `all` não baixa microdados de Trabalho; há um workflow mensal próprio como template. Veja [conceitos, layouts, fontes, validações e operação de Trabalho e Emprego](docs/modulos/trabalho-emprego.md).

## Educação: Censo, aprendizagem e rede escolar

Página específica com **Censo Escolar 2015–2025**, **IDEB por etapa/rede desde 2005**, **SAEB 2025**, **Criança Alfabetizada 2023–2025**, formação/esforço/regularidade docente, rendimento, distorção idade-série, alunos por turma, horas-aula, catálogo de escolas e onze recursos de infraestrutura. Os mocks de Educação foram substituídos por dados INEP; há gráficos, tabelas acessíveis, filtros de rede, comparação com municípios vizinhos e Paraná no IDEB, fontes e seis downloads CSV mais JSON.

Censo 2025: **3.230 matrículas, 17 escolas (9 municipais, 7 estaduais, 1 privada)**. A Sinopse valida matrículas, escolas e turmas em 60 controles exatos. **250 docentes únicos** são lidos diretamente da Sinopse, distintos das 290 docências somadas por escola. Educação especial/profissional não são adicionadas ao total; ausentes/supressões permanecem sem valor.

```sh
# Dentro do ambiente Python com requirements-education instalado:
python scripts/etl.py --module education
python scripts/etl.py --module education --offline
# Revisões, com cache explícito não público:
python scripts/etl.py --module education --force --cache .inep-cache
```

Sem nova publicação, não baixa arquivos nacionais nem altera o snapshot. Histórico dos indicadores anuais, participação SAEB e mapa com coordenadas oficiais ficam documentados como próximos passos. Veja [fontes, layouts, campos, escolas, decisões e operação de Educação](docs/modulos/educacao.md).

## Saúde: rede assistencial CNES

Página própria com cadastro oficial de 07/10/2026: **31 estabelecimentos sem motivo de desativação, 12 públicos, 6 UBS, 1 hospital e 1 unidade móvel de urgência**. O campo específico de atendimento ambulatorial SUS registra **11 SIM**; não representa o total geral de serviços SUS. **49 leitos existentes e 49 SUS na competência agosto/2026**, com série janeiro–agosto/2026. Cadastro diário não tem competência mensal; suas datas são exibidas separadamente.

Catálogo pesquisável, filtros por situação/natureza/SUS ambulatorial, endereços, links CNES verificados, mapa institucional com coordenadas oficiais e limite IBGE, comparação com Guarapuava/Pitanga/Laranjal, tabelas acessíveis e downloads JSON/CSV. ETL mensal próprio preserva o último snapshot em falhas e não publica bases nacionais ou dados individuais. Equipes/cobertura APS, profissionais e produção/epidemiologia são pendências explícitas, sem valores fictícios. [Fontes, campos, contagens, endpoints e limites](docs/modulos/saude.md).

```sh
python3 scripts/etl.py --module health
python3 scripts/etl.py --module health --offline
```

Ativação mensal preparada em [health.yml](docs/github-actions/health.yml), seguindo a limitação de permissão de workflows já documentada. Nenhuma nova dependência ou serviço pago.

## Agropecuária: PAM, PPM, PEVS e Censo

Página própria com 32 culturas de Turvo em 2025, séries 2016–2025, rankings por valor/área/quantidade/rendimento, rebanhos, leite/ovos/mel/lã, aquicultura, extração vegetal, silvicultura e Censo Agropecuário 2017. Há comparações com Guarapuava, Pitanga, Laranjal e Paraná, filtros, tabelas acessíveis, downloads e respostas oficiais para auditoria. **Não há mock neste módulo.** Cultivo e extração de erva-mate permanecem separados; valor da produção não é PIB/VAB, e unidades físicas não são misturadas.

```sh
python3 scripts/etl.py --module agriculture
python3 scripts/etl.py --module agriculture --offline
```

A rotina explicitamente mensal verifica os dez períodos para aceitar revisões; arquivos idênticos não geram mudanças. Falhas preservam a entrega anterior. Veja [Agropecuária](docs/modulos/agropecuaria.md) para tabelas/variáveis, unidades especiais, resultados, arquivos, fórmulas, sigilo e TODOs. [Workflow mensal preparado](docs/github-actions/agriculture.yml), com a mesma limitação de escrita de workflows já documentada. Site estático, nenhum serviço ou dependência adicional.

## Atualizar os dados

```sh
npm run data:update
# Apenas verificar os arquivos existentes, sem rede:
python3 scripts/etl.py --offline
```

O ETL de Economia consulta Agregados v3 e Pesquisas v1 para Turvo, Guarapuava, Laranjal e Pitanga; o conector inicial SIDRA mantém os demais indicadores, com timeout, três tentativas e validação de município, variável, unidade e valores. Se uma consulta falhar, mantém o último snapshot válido e registra falha em `collection.failures`. A tentativa mais recente está em `collection.attemptedAt`; a coleta do valor preservado fica em `collectedAt`. Não troca uma série oficial por demonstrações.

Integrações iniciais: população residente, área territorial e densidade do Censo 2022 (tabela 4714); PIB total (tabela 5938, último período disponível). A disponibilidade efetiva está registrada no JSON. PIB em **mil reais** é multiplicado por 1.000. PIB é nominal, não deflacionado. Séries iniciais oficiais podem ter somente uma observação; não interpolamos anos inexistentes.

Dados em Finanças e Contratações são explicitamente **fictícios**, destinados a demonstrar os componentes. Não use os valores demonstrativos para decisões ou publicações. O comparador usa apenas observações oficiais da mesma referência e unidade.

## Módulos

| Módulo | MVP | Evolução |
| --- | --- | --- |
| Visão Geral | Cards oficiais, gráficos e referências | Destaques editoriais e mapa |
| População | Página própria: Censo, estimativas, idade/sexo, cor/raça, urbano/rural, domicílios e território | Comparador regional no novo schema |
| Economia / PIB | PIB, per capita, variação nominal, VAB/setores, impostos, história e comparação regional | Novas divulgações e benchmark estadual compatível |
| Trabalho e Emprego | RAIS anual/estrutura/remuneração e CAGED mensal ajustado, CNAE/CBO, comparação, downloads | Conferência municipal ISPER, estabelecimentos e história salarial |
| Educação | Censo 2015–2025, IDEB/SAEB/alfabetização, indicadores anuais 2025, escolas, infraestrutura e downloads | Históricos anuais/SAEB, participação SAEB e mapa com coordenadas verificadas |
| Saúde | CNES/DATASUS real | Rede, UBS, SUS ambulatorial, leitos, mapa, comparação; equipes/cobertura pendentes |
| Finanças Públicas | Demo SICONFI | DCA/RREO/RGF normalizados |
| Contratações / PNCP | Demo | Coleta paginada e filtro municipal validado |
| Agropecuária | PAM/PPM/PEVS reais, história, comparações, Censo 2017 e downloads | Uso das terras/condição do produtor no Censo e ranking estadual |
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
  modules/agriculture/      # Culturas, pecuária, florestas, Censo e comparador
  modules/education/        # Censo/avaliações/redes/escolas/infraestrutura próprios
public/data/
  indicators.json           # Snapshots de Turvo + demonstrações identificadas
  comparison.json           # Snapshots oficiais dos municípios comparados
  population.json           # Dados multidimensionais de População
  economy.json              # PIB, per capita, setores, impostos e comparações
  employment.json           # RAIS e CAGED multidimensionais, quatro municípios
  education.json            # Censo, escolas, avaliações, indicadores e fontes INEP
  exports/                  # CSVs de emprego e Educação, gerados pelo ETL
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
scripts/sources/inep.py        # Descoberta e transporte INEP, CSV/ZIP/XLSX
scripts/modules/education.py  # Agregados escolares, avaliações e validação
tests/test_etl.py           # Conversão, integridade e comportamento em falhas
docs/github-actions/        # Templates de CI, coleta semanal e deploy opcional (ativar abaixo)
```

Vite + React + TypeScript permite evolução incremental de componentes e módulos, com build puramente estático. Gráficos usam Recharts; ícones, Lucide. Rotas por hash evitam exigir reescrita do servidor e funcionam em hospedagem estática. Python usa a biblioteca padrão nos conectores IBGE/MTE e openpyxl para as planilhas oficiais INEP. Veja [arquitetura](docs/arquitetura.md), [fontes](docs/fontes.md) e [roadmap](docs/roadmap.md).

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

O template de Educação verifica o catálogo INEP no dia 5 às 11:19 UTC, baixa apenas novas edições e preserva arquivos/commits quando não há mudanças. Avaliações têm ciclos próprios; não entram na coleta semanal. O template mensal de Trabalho verifica CAGED no dia 3 às 10:31 UTC e permite RAIS manual; remuneração é uma opção explícita. A atualização semanal dos demais conectores executa segunda-feira às 09:17 UTC (06:17 em Brasília) e pode ser iniciada manualmente. Commits feitos com `GITHUB_TOKEN` não acionam novos workflows de push; por isso o próprio workflow de coleta compila e publica quando há secrets Cloudflare. Em integração Git, se o provedor não disparar build para commits do bot, use o modo Actions. Os agendamentos do GitHub podem atrasar e podem ser desabilitados por inatividade em repositórios públicos: consulte o histórico de Actions.

## Custo e segurança

MVP sem VPS, banco, autenticação ou backend permanente. Armazena somente pequenos agregados públicos. Pode operar nos planos gratuitos de Pages e GitHub Actions, respeitando quotas vigentes; não há garantia de gratuidade ilimitada. Domínio próprio é opcional. Não configurar serviços faturáveis é suficiente para o MVP; R2, D1 e Worker não são necessários. Fontes externas podem limitar requisições.

Não coloque tokens em `public/` ou variáveis `VITE_*`: o build publica esses valores. Secrets de deploy ficam no GitHub. Cabeçalhos básicos de segurança estão em `public/_headers`. A fonte Google Fonts é opcional, com fallback local do sistema.

## Qualidade e contribuição

`npm test` valida o ETL e os dados locais. `npm run build` verifica TypeScript e gera os arquivos estáticos. CI executa ambos e salva o artefato `dist`. [CONTRIBUTING](CONTRIBUTING.md) explica como ampliar um módulo e revisar fontes.

Licença MIT para o código. Os dados mantêm os termos e atribuições de cada órgão; a licença do código não altera a licença dos dados de terceiros.

A logo municipal utilizada no menu é o [arquivo disponibilizado pelo Município de Turvo](https://drive.turvo.pr.gov.br/Logos/Vertical%20Cores%20.png), armazenado sem alteração em `public/branding/turvo-logo.png`.
