# Arquitetura

```mermaid
flowchart LR
  S[APIs públicas / SIDRA] --> E[Python ETL no GitHub Actions]
  E --> J[JSON normalizado e versionado]
  J --> B[Vite: build estático]
  B --> C[Cloudflare Pages]
  C --> U[Navegador: React e gráficos]
```

O site lê somente snapshots locais em `public/data`. Não exige backend, banco ou credenciais no navegador. Um indisponibilidade do IBGE não impede o site de servir o último snapshot.

## Contrato de indicador v1

Cada objeto possui `id`, `module`, `title`, `value` (número ou null), `unit`, `source`, `agency`, `reference`, `url`, `collectedAt` (ISO 8601 ou null), `municipalityCode`, `status` e `series` (`period`, `value`). `note` documenta transformação e limitações.

`real` exige fonte coletada; `mock` identifica dados fictícios; `unavailable` permite preparar indicador sem inventar valor. Ausência/supressão não equivale a zero. A interface diferencia estados e só compara dados oficiais com unidade e período iguais.

## Modularidade

O registro `src/modules/catalog.ts` centraliza navegação. Os indicadores vinculam-se ao módulo pelo campo `module`. Cards, tabelas e gráficos são reutilizáveis; `App.tsx` compõe as telas. Para módulos mais complexos, extraia telas para `src/modules/<nome>/` sem alterar o contrato de dados. Não é necessário manter doze implementações duplicadas no MVP.

## Resiliência

Timeout de 25s, até três tentativas por endpoint; gravação atômica em cada arquivo; snapshots anteriores preservados em falhas individuais. O relatório guarda falhas por município/indicador. A escrita dos dois arquivos não é transacional: leitores do site só recebem o conjunto após build/deploy concluído. CI não precisa da rede do IBGE. Os testes rejeitam unidades trocadas e códigos incorretos.

## Worker futuro (opcional)

Somente criar Worker se forem necessárias consultas dinâmicas, cache por parâmetro ou um endpoint próprio. Proposta: `GET /v1/municipios/:codigo/indicadores`, respondendo o mesmo schema e consultando snapshots com cache. TODO: implementar quando houver necessidade, com allowlist de municípios, limites de requisição e testes. O MVP não depende disso.

## Educação

[Educação](modulos/educacao.md) tem contrato próprio multidimensional e página sob demanda. Arquivos oficiais INEP são descobertos por base/ciclo; não há API REST única presumida. Censo 2025 junta quatro tabelas de agregados escolares por código INEP. A Sinopse fornece controle independente e docentes únicos; avaliações preservam etapas/redes. O JSON serve escola/município/rede sem indivíduos. CSVs de download incluem proveniência. Atualização mensal leve excluída do ETL semanal; reprocessamento pesado só em nova publicação/revisão manual. openpyxl lê XLSX; arquivos nacionais/cache ficam fora de public.
