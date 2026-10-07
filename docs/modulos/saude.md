# Saúde — rede assistencial de Turvo/PR

Módulo estático em `#health`, município **4127965**, DATASUS **412796**, UF **41/PR**. Não depende do MCP Brasil, Worker, banco, autenticação ou chamada ao Ministério da Saúde feita pelo navegador. A origem é Ministério da Saúde / DATASUS / CNES.

## Entrega e referências verificadas em 07/10/2026

| Informação | Valor / referência |
| --- | --- |
| Exportação diária CNES | 07/10/2026; **sem competência mensal no arquivo** |
| Cadastros no município | 54 CNES distintos |
| Sem motivo de desativação (“ativos” neste painel) | 31 |
| Com motivo de desativação | 23; excluídos dos indicadores atuais |
| Natureza pública | 12, todos de natureza municipal 1244 |
| Natureza privada | 15 |
| Sem fins lucrativos | 4; sem inferência de certificação filantrópica |
| Atendimento **ambulatorial** SUS | 11 SIM (35,48% de 31), 20 NAO, 0 não informado |
| Atendimento SUS geral | **Indisponível**: a coluna ambulatorial não representa todos os serviços SUS |
| Centro de Saúde/UBS, tipo 02 | 6 |
| Gestão | 29 municipal, 1 dupla, 1 estadual; gestão não é propriedade |
| Hospital geral ativo | 1, Hospital Bom Pastor, CNES 2741962, natureza 3999, sem fins lucrativos, gestão dupla |
| Unidade de urgência | 1, Base Descentralizada SAMU Bravo Turvo, tipo 42, CNES 4206916 |
| Leitos existentes / SUS | 49 / 49, **competência 202608** |
| UTI existentes / SUS | 0 / 0 na publicação de leitos |
| Histórico real de leitos | 202601–202608; 49 existentes e 49 SUS em cada competência |
| Região de Saúde | 41005 — 5ª RS Guarapuava |
| Macrorregião de Saúde | 4107 — Macrorregional Leste |
| Coordenadas no limite municipal | 31 cadastros ativos; posição declarada no CNES, não confirmação do endereço |

O cadastro inclui unidades administrativas e estabelecimentos privados. Não equivale a 31 unidades de atendimento da Prefeitura. Ausência de motivo de desativação não comprova que a unidade esteja atendendo agora.

### Tipos encontrados nos cadastros ativos

| Código CNES | Descrição oficial | Quantidade |
| --- | --- | --- |
| 22 | Consultório isolado | 11 |
| 02 | Centro de Saúde/Unidade Básica | 6 |
| 43 | Farmácia | 5 |
| 36 | Clínica/Centro de Especialidade | 2 |
| 39 | Unidade de Apoio Diagnose e Terapia (SADT isolado) | 2 |
| 05 | Hospital Geral | 1 |
| 42 | Unidade Móvel de Nível Pré-Hospitalar na Área de Urgência | 1 |
| 68 | Central de Gestão em Saúde | 1 |
| 71 | Centro de Apoio à Saúde da Família | 1 |
| 74 | Polo Academia da Saúde | 1 |

### UBS, não equipes

- 0937355 — UBS Jardim Filadelfia.
- 2741423 — UBS Iracy Aparecida de Campos Sede.
- 2742306 — UBS Faxinal da Boa Vista.
- 2742322 — UBS Passa Quatro.
- 2743248 — UBS Cachoeira dos Turcos.
- 2743280 — UBS Saudade.

Nomes mantidos como informados pela fonte. Não inferimos ESF, eAP, Saúde Bucal ou ACS. Os postos tipo 01 estão separados; em Turvo os cadastros desse tipo estão desativados nesta exportação.

## Fontes de produção e descoberta

| Bloco | Catálogo oficial | Recurso utilizado |
| --- | --- | --- |
| Estabelecimentos | [CNES](https://dadosabertos.saude.gov.br/dataset/cnes-cadastro-nacional-de-estabelecimentos-de-saude) | [CSV/ZIP diário](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_csv.zip) |
| Leitos | [Hospitais e Leitos](https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos) | [CSV/ZIP 2026](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip) |
| Região | [Macrorregião de Saúde](https://dadosabertos.saude.gov.br/dataset/macrorregiao-de-saude) | [CSV/ZIP regional](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/dbgeral/macroregiao_de_saude_csv.zip) |
| Tipos | [CNES — Tipos de Estabelecimentos](https://cnes2.datasus.gov.br/Mod_Ind_Unidade.asp?VEstado=00) | Tabela pública oficial, não enumeração copiada do MCP |
| Conceitos leitos | [Dicionário oficial](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Dicion%C3%A1rio_Leito_hospitalar.pdf) | Existentes, SUS e UTI, sem somar campos potencialmente sobrepostos |
| Limite municipal | [Malha municipal IBGE](https://servicodados.ibge.gov.br/api/v3/malhas/municipios/4127965?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio) | Geometria 2022 já coletada no módulo População, reutilizada sem alterar aquele módulo |

O ETL descobre os recursos publicados a partir de `__NEXT_DATA__ → props.pageProps.resources` nas páginas atuais. A antiga rota CKAN `/api/3/action/package_show` não funciona neste portal. Mudança de formato provoca falha explícita e preservação do snapshot, não recurso adivinhado. Selecionamos a edição anual mais recente de leitos pelo ano da URL e os meses efetivamente encontrados no CSV; publicação do ZIP em setembro não vira competência setembro.

Cada fonte em `health.json` registra dataset, órgão, URL/catálogo, resourceId, referência, competência (ou null), publicação, coleta UTC, tamanho, SHA-256, conceito e transformação. Os horários de publicação permanecem exatamente como retornados pelo catálogo, sem atribuir fuso não documentado.

### APIs avaliadas, sem dependência de runtime

[Swagger atual](https://apidadosabertos.saude.gov.br/static/swagger.json) e [documentação](https://apidadosabertos.saude.gov.br/v1/):

- `/cnes/estabelecimentos?codigo_municipio=412796&status=1&limit=20&offset=0`: HTTP 503 na inspeção; não usado para totais.
- `/cnes/tipounidades`: HTTP 503 na inspeção; usamos a tabela oficial CNES.
- `/assistencia-a-saude/hospitais-e-leitos`: a tentativa de filtro municipal retornou dados de outro município; resposta rejeitada para contagem municipal.
- `/assistencia-a-saude/cnes-estabelecimentos?co_ibge=412796&nu_comp=202608&limit=1000&offset=0`: resposta vazia. Sem competência explícita retornou registros históricos; nunca tratamos uma primeira página histórica como cadastro atual.
- `/assistencia-a-saude/cnes-leitos` e `/assistencia-a-saude/cnes-servicos-especializados`, mesmos filtros 202608: respostas vazias. Sem filtro temporal a API de leitos retornou competências antigas. O ZIP oficial fornece referência atual verificável.
- `/assistencia-a-saude/cnes-profissionais?co_ibge=412796&nu_comp=202608&limit=1&offset=0`: resposta vazia. Não usamos `/cnes/profissionais`, antigo/descontinuado; nenhum registro nominal foi publicado.
- `/macrorregiao-e-regiao-de-saude/municipio?codigo_municipio=412796&limit=1000&offset=0`: resposta válida, pertencimento regional conferido com o CSV oficial. O ETL usa o CSV para auditoria uniforme.

Nos endpoints novos, `offset` é **número da página (0,1,2...)**, não quantidade de registros. Uma futura integração paginada deve verificar território, competência, repetição de páginas e completude.

As features [saude](https://github.com/Mcp-Brasil/mcp-brasil/tree/main/src/mcp_brasil/data/saude) e [opendatasus](https://github.com/Mcp-Brasil/mcp-brasil/tree/main/src/mcp_brasil/data/opendatasus) foram inspecionadas como referência técnica. Não são a fonte estatística. Sua enumeração de urgências não foi copiada: tipos 36, 39, 40 e 74 não são automaticamente urgência.

## Campos e regras

**Rede:** CSV Windows-1252 separado por `;`, nacional temporário. Filtro `CO_IBGE` com mapeamento explícito dos quatro códigos e `CO_UF=41`. `CO_CNES` restaurado para sete dígitos, inclusive zero inicial; `CO_UNIDADE` deve ser município de seis dígitos + CNES. Duplicatas idênticas são deduplicadas; divergentes rejeitam a atualização. `CO_MOTIVO_DESAB` vazio define o recorte ativo; qualquer motivo informado exclui dos totais atuais. A lista pode incluir desativados quando solicitado.

**Gestão/propriedade:** `TP_GESTAO` M/E/D/S é gestão; propriedade vem de `CO_NATUREZA_JUR`. Grupo 1 e empresa pública 2011 → pública; 1031/1244 → municipal; grupo 2 (exceto empresas públicas/economia mista) e grupo 4 → privada; grupo 3 → sem fins lucrativos; 2038 → economia mista; desconhecidos separados. `CO_ESFERA_ADMINISTRATIVA` não substitui natureza jurídica. A fonte oficial da classificação da natureza é [CONCLA/IBGE](https://concla.ibge.gov.br/classificacoes/por-tema/organizacao-juridica/natureza-juridica.html).

**SUS:** `CO_AMBULATORIAL_SUS` SIM/NAO/vazio é normalizado como true/false/null **somente para atendimento ambulatorial**. A soma dessas categorias deve igualar os cadastros ativos. Campo `sus` geral é true para confirmação positiva ambulatorial e null para os demais; **nunca false inferido**. `summary.sus.generalTotal=null`. O SAMU informa NAO no campo ambulatorial, mas isso não permite negar atendimento SUS geral. Hospital Bom Pastor informa SIM nesse campo e 49 leitos SUS na base hospitalar, com referência temporal própria.

**Serviços:** flags oficiais `ST_ATEND_AMBULATORIAL`, `ST_ATEND_HOSPITALAR`, `ST_SERVICO_APOIO`, `ST_CENTRO_CIRURGICO`, `ST_CENTRO_OBSTETRICO`, `ST_CENTRO_NEONATAL`; valores 0/1 (inclusive strings 0.0/1.0), ausentes mantidos separados. Não são agenda, oferta instantânea ou lista completa de especialidades.

**Urgência:** exclusivamente tipos 20, 21, 42, 73, 76. Não inferir pelo nome. Tipos hospitalares 05/07/62 são separados; hospital não é automaticamente pronto-socorro.

**Leitos:** arquivo nacional completo lido até EOF/CRC, meses COMP AAAAMM e UF PR. Excluir motivo de desabilitação informado. Chave município+competência+CNES. Contagens inteiras finitas ≥0; leitos SUS ≤ existentes para os mesmos campos e UTI SUS ≤ UTI existentes. UTI aparece separada, sem somar ao total. Especialidades gerais não disponíveis nesse recurso. Série de rede histórica não foi reconstruída do presente.

**Zero:** Laranjal não tem registros ativos de leitos em nenhuma das oito competências do arquivo nacional completo; mostramos zero confirmado pelo recorte. Arquivo vazio, download truncado, ausência de município esperado no CNES, resposta vazia da API ou indisponibilidade jamais vira zero. Publicação exige volumes nacionais mínimos (100 mil linhas CNES; mil linhas de leitos), além de cabeçalhos, códigos, tipos, totais e ZIP válido.

**Mapa:** reutiliza limite municipal IBGE 2022, verifica ponto em polígono com exclusão de buracos e aceita coordenadas finitas dentro do limite. Não geocodifica nem corrige posições por estimativa. Pontos coincidentes podem ser selecionados pela lista acessível. Seletores/legenda U, H, ! e • não dependem somente de cor. Coordenadas declaradas podem estar erradas mesmo dentro do polígono.

## Comparação publicada

| Município | Ativos, 07/10/2026 | UBS | SUS ambulatorial | Leitos, 202608 | Leitos SUS |
| --- | --- | --- | --- | --- | --- |
| Turvo 4127965 | 31 | 6 | 11 | 49 | 49 |
| Guarapuava 4109401 | 732 | 44 | 111 | 564 | 433 |
| Pitanga 4119608 | 109 | 1 | 32 | 95 | 82 |
| Laranjal 4113254 | 4 | 1 | 3 | 0 | 0 |

Mesmos arquivos e critérios em cada coluna. Absolutos não medem suficiência ou cobertura e dependem de porte e papel regional. Não dividimos automaticamente por Censo 2022 ou população histórica da tabela regional. TODO: estimativas IBGE compatíveis, fórmula e indicador `derived` explícito, depois região e Paraná.

## APS e outras camadas pendentes

- **Integrado APS:** seis UBS ativas, catálogo institucional, tipo, endereço, gestão e natureza. Não é integração de equipes ou cobertura.
- **Equipes e cobertura:** [e-Gestor APS](https://egestoraps.saude.gov.br/) avaliado; acesso atual por aplicação/login. A documentação da API expõe recursos do Previne Brasil, cadastro vinculado e desempenho, que não foram confundidos com cobertura atual ou série de equipes. Não usar scraping autenticado/frágil nem equipes × população-padrão. TODO: exportação pública validada, competência, tipo de equipe e metodologia vigente.
- **Profissionais:** validar endpoint atual/arquivo CNES, competência, CBO e conceito de vínculo; nenhuma listagem nominal. Somar vínculos não produz pessoas únicas.
- **SIA/SIH:** escolher território de atendimento ou residência; procedimentos não são pessoas e internação em outro município pode representar residente de Turvo.
- **SINASC/SIM/SINAN, dengue, SRAG e vacinação:** camada futura com agregados oficiais, períodos, território e política documentada para células pequenas; não introduzimos uma supressão arbitrária. Sem integração clínica nesta entrega, nenhuma célula clínica pequena é publicada.
- **História CNES:** conservar snapshots futuros e integrar competências históricas oficiais; não inferir abertura/fechamento pelo snapshot atual.

Não conectamos PEC/e-SUS local, prontuários, pacientes, CPF, CNS, CNPJ, telefone ou e-mail pessoal. A lista contém nomes de estabelecimentos do cadastro institucional; não nomes de profissionais como lista de pessoas. Finanças de saúde permanecem em Finanças Públicas.

## Schema, arquivos e execução

`public/data/health.json`, schemaVersion 1: município, summary, network, primaryCare, beds, region, professionals, production, epidemiology, comparison, map, sources, collection. Dados da rede e leitos são `real`; blocos não integrados são `unavailable` com motivo/URL/valor null. Sem mock. Agregações são contagens transparentes das linhas oficiais; percentuais informam seu universo. Nenhuma taxa per capita é apresentada como oficial.

- `scripts/sources/datasus.py`: catálogo atual, HTTP/timeout/retry/User-Agent, limite de bytes, ZIP/CSV e tabela de tipos.
- `scripts/sources/cnes.py`: normalização/validação institucional e leitos.
- `scripts/modules/health.py`: schema, ETL, fontes, mapa, comparação, downloads, publicação com rollback, catálogo.
- `src/modules/health/`: página, componentes, tipos, validação e estilos; carregamento sob demanda.
- `public/data/exports/health-{establishments,beds,primary-care}.csv`: exportações institucionais. A terceira lista **UBS, não equipes**.
- `tests/test_health.py`, `tests/health-data.test.mjs`, `tests/fixtures/health/`: recortes reais, validação, filtros, falhas, rollback, mapa, datas e privacidade.

```sh
python3 scripts/etl.py --module health
python3 scripts/etl.py --module health --offline
# Reprocessar publicações já conhecidas, inclusive revisões:
python3 scripts/etl.py --module health --force
npm test
npm run build
```

Python stdlib, sem dependência adicional. `all` semanal continua excluindo downloads nacionais pesados. ZIPs nacionais (aproximadamente 56 MB CNES e 4 MB leitos nesta coleta) são temporários e removidos ao fim; não versionamos bases nacionais completas. Snapshot público cerca de 110 KB, mais CSVs pequenos e geometria reutilizada. O custo de hospedagem estática não muda.

Recursos com id/URL/data de publicação idênticos são ignorados para evitar download e commit só de horário. Cache manual opcional `--cache DIRETORIO` só é aceito com `health-manifest.json` contendo, por chave cnes/beds/region, id/url/last_modified/sha256 correspondentes; cache não validado não substitui download. Não é cache público.

Todos os arquivos são gerados em staging; publicação local usa substituição atômica por arquivo e rollback em caso de erro. Qualquer falha de coleta preserva a última entrega inteira e referências/coletas originais, altera somente `collection.failures/attemptedAt` e sinaliza saída 1. Primeira falha sem snapshot não gera dados artificiais. `--offline` valida o último snapshot sem rede.

Atualização mensal instalada em [health.yml](../../.github/workflows/health.yml), com validação offline, testes/build antes do commit, arquivos restritos a Saúde/catálogo e concorrência compartilhada. Nenhum deploy ou secret Cloudflare no workflow; a publicação usa a integração Git do Pages. Veja [operação das Actions](../operacao-actions.md).
