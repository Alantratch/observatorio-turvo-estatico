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

O build funciona **sem acessar fontes públicas**, usando os snapshots versionados. O navegador não consulta SIDRA diretamente.

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

## Atualizar os dados

```sh
npm run data:update
# Apenas verificar os arquivos existentes, sem rede:
python3 scripts/etl.py --offline
```

O ETL consulta SIDRA para Turvo, Guarapuava, Laranjal e Pitanga, com timeout, três tentativas e validação de município, variável, unidade e valores. Se uma consulta falhar, mantém o último snapshot válido e registra falha em `collection.failures`. A tentativa mais recente está em `collection.attemptedAt`; a coleta do valor preservado fica em `collectedAt`. Não troca uma série oficial por demonstrações.

Integrações iniciais: população residente, área territorial e densidade do Censo 2022 (tabela 4714); PIB total (tabela 5938, último período disponível). A disponibilidade efetiva está registrada no JSON. PIB em **mil reais** é multiplicado por 1.000. PIB é nominal, não deflacionado. Séries iniciais oficiais podem ter somente uma observação; não interpolamos anos inexistentes.

Dados nos demais módulos são explicitamente **fictícios**, destinados a demonstrar os componentes. Não use os valores demonstrativos para decisões ou publicações. O comparador usa apenas observações oficiais da mesma referência e unidade.

## Módulos

| Módulo | MVP | Evolução |
| --- | --- | --- |
| Visão Geral | Cards oficiais, gráficos e referências | Destaques editoriais e mapa |
| População | Página própria: Censo, estimativas, idade/sexo, cor/raça, urbano/rural, domicílios e território | Comparador regional no novo schema |
| Economia / PIB | SIDRA 5938 | PIB per capita e setores do valor adicionado |
| Trabalho e Emprego | Demo RAIS/CAGED | Importadores e saldo mensal |
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
public/data/
  indicators.json           # Snapshots de Turvo + demonstrações identificadas
  comparison.json           # Snapshots oficiais dos municípios comparados
  population.json           # Dados multidimensionais de População
  population/               # Malha municipal e respostas brutas auditáveis
scripts/etl.py              # Orquestração incremental de ETLs
scripts/common.py           # HTTP, números e escrita atômica
scripts/sources/ibge.py      # Metadados e parsing completo de agregados
scripts/modules/population.py # Coleta e validação do módulo População
tests/test_etl.py           # Conversão, integridade e comportamento em falhas
.github/workflows/          # CI, coleta semanal e deploy opcional
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

A atualização semanal executa segunda-feira às 09:17 UTC (06:17 em Brasília) e pode ser iniciada manualmente. Commits feitos com `GITHUB_TOKEN` não acionam novos workflows de push; por isso o próprio workflow de coleta compila e publica quando há secrets Cloudflare. Em integração Git, se o provedor não disparar build para commits do bot, use o modo Actions. Os agendamentos do GitHub podem atrasar e podem ser desabilitados por inatividade em repositórios públicos: consulte o histórico de Actions.

## Custo e segurança

MVP sem VPS, banco, autenticação ou backend permanente. Armazena somente pequenos agregados públicos. Pode operar nos planos gratuitos de Pages e GitHub Actions, respeitando quotas vigentes; não há garantia de gratuidade ilimitada. Domínio próprio é opcional. Não configurar serviços faturáveis é suficiente para o MVP; R2, D1 e Worker não são necessários. Fontes externas podem limitar requisições.

Não coloque tokens em `public/` ou variáveis `VITE_*`: o build publica esses valores. Secrets de deploy ficam no GitHub. Cabeçalhos básicos de segurança estão em `public/_headers`. A fonte Google Fonts é opcional, com fallback local do sistema.

## Qualidade e contribuição

`npm test` valida o ETL e os dados locais. `npm run build` verifica TypeScript e gera os arquivos estáticos. CI executa ambos e salva o artefato `dist`. [CONTRIBUTING](CONTRIBUTING.md) explica como ampliar um módulo e revisar fontes.

Licença MIT para o código. Os dados mantêm os termos e atribuições de cada órgão; a licença do código não altera a licença dos dados de terceiros.
