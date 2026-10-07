# Operação das atualizações automáticas

Cloudflare Pages publica pela integração Git. Nenhuma rotina usa Wrangler, secrets de Cloudflare ou upload de `dist`. O build nas rotinas de dados é uma validação antes do commit; só ocorre quando os arquivos do módulo mudam. Consultas sem novidade não fazem commit nem provocam um novo build do Pages. As datas de coleta do IBGE são preservadas quando dados e metadados permanecem iguais. Falhas continuam registradas; logs do Actions documentam tentativas sem alteração.

## Calendário

| Arquivo | Fontes | Agenda UTC | Brasília |
| --- | --- | --- | --- |
| `data.yml` | IBGE: População, Economia e comparações iniciais | Segunda, 09:17 | Segunda, 06:17 |
| `employment.yml` | CAGED e tabela anual RAIS | Dia 3, 10:31 | Dia 3, 07:31 |
| `education.yml` | INEP | Dia 5, 11:19 | Dia 5, 08:19 |
| `health.yml` | CNES/DATASUS | Dia 7, 11:37 | Dia 7, 08:37 |
| `agriculture.yml` | PAM, PPM, PEVS e Censo Agropecuário | Dia 9, 11:43 | Dia 9, 08:43 |
| `social.yml` | MDS/SUAS | Dia 12, 12:17 | Dia 12, 09:17 |

Finanças e PNCP ainda são demonstrações; não há coletor automático desses módulos. `all` cobre somente o conector inicial, População e Economia. A CI valida offline todos os demais snapshots separadamente. Remuneração RAIS continua manual para evitar baixar o arquivo regional grande automaticamente. Uma nova competência CAGED reprocessa a janela de 24 meses e pode consumir tempo; o limite de execução é de 180 minutos e não representa garantia de conclusão.

## Publicação e falhas

1. Só `main` pode executar coletores, inclusive em disparos manuais. O checkout usa explicitamente `main`, buscando o estado atual ao iniciar o job.
2. Todos compartilham `data-update`, para impedir escritores simultâneos do catálogo. O GitHub mantém uma execução e uma pendente por grupo; uma terceira solicitação pode substituir a pendente. Evite disparar várias rotinas manualmente de uma vez.
3. O ETL preserva valores anteriores quando uma fonte falha. A validação offline roda mesmo sem alterações; com alterações, testes Python/JavaScript e build com verificação de privacidade precisam passar antes do commit.
4. Somente JSON, CSV, respostas municipais e metadados previstos daquele módulo são preparados para commit. Arquivos nacionais e caches temporários não são enviados nem publicados como artefatos.
5. O push normal para `main` falha se outro commit tiver avançado a branch. Nunca há force push ou rebase automático de catálogos gerados. Nesse caso, execute novamente a rotina na `main` atualizada.
6. Uma coleta parcial termina com falha no Actions, mesmo se os snapshots preservados/relatórios tiverem sido validados e versionados. Consulte o log da etapa de coleta e `collection.failures` quando persistido pelo conector. Alguns conectores transacionais preservam todos os bytes anteriores; nesses casos o relatório está somente no log.

O token automático tem `contents: write` apenas nos coletores, e a CI usa `contents: read`. Branch protection que exija PR pode impedir o commit do bot; não contorne essa proteção. As execuções de CI originadas por commits enviados com `GITHUB_TOKEN` não são disparadas novamente, evitando loops; o próprio coletor já valida antes do push. A integração externa do Cloudflare deve estar habilitada para a `main`.

## Ativação e diagnóstico

As rotinas ficam em `.github/workflows/` na `main`, com cópias de referência em `docs/github-actions/`. Ambos devem ser mantidos idênticos. Agendamentos só executam a versão presente na branch padrão. Não copie workflows antigos de deploy, inclusive o PR #13, que contém Wrangler e ficou incompatível com a decisão de usar apenas Pages pela integração Git.

Depois de ativar, abra Actions, escolha a rotina e use **Run workflow → main**. Confira coleta, validação e commit, ou ausência de mudanças. Não force a coleta pesada apenas para testar o agendamento. Agendas podem atrasar; em repositórios públicos, o GitHub pode desabilitá-las após 60 dias sem atividade. Em falha de fonte pública, repita após a fonte voltar. Em erro de dependência, validação ou duração, revise o log antes de repetir.

Referências oficiais: [local dos workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [agendamentos e branch padrão](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [concorrência](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), [eventos com GITHUB_TOKEN](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow).
