# Meio Ambiente · Turvo/PR

Módulo `environment`, código IBGE **4127965**, schemaVersion **1**. Substitui `procurement` no catálogo, rota e navegação. Removidos seu indicador fictício, condicionais de cards e textos da página Sobre. Outros módulos e suas bases são preservados. Compras públicas, se retomadas, serão uma ferramenta separada.

## Entrega e arquivos

Página carregada sob demanda: `src/modules/environment/EnvironmentPage.tsx`, gráficos em `EnvironmentCharts.tsx`, mapa em `EnvironmentMap.tsx`, estilos, tipos e loader próprios. Integração em `src/App.tsx` e `src/modules/catalog.ts`. Dados: `public/data/environment.json`, extratos auditáveis em `public/data/environment/resources/` e quatro arquivos `public/data/exports/environment-*.csv`. O catálogo geral recebe quatro classes diretamente observadas; agregações derivadas ficam no módulo.

ETL: `scripts/sources/environment.py` (fontes e geoprocessamento), `scripts/modules/environment.py` (normalização, validação, preservação e publicação), `scripts/etl.py` (CLI). Dependências: `scripts/requirements-environment.txt`. Testes: `tests/test_environment.py` e `tests/environment-data.test.mjs`. Automação: `.github/workflows/environment.yml`, com cópia em `docs/github-actions`. CI e rotinas existentes recebem dependências necessárias aos testes completos. README/fontes/roadmap/operação documentam esta entrega.

## Fontes confirmadas

| Bloco | Órgão / conjunto | Acesso e referência |
| --- | --- | --- |
| Cobertura | Rede MapBiomas, Coleção **11**, versão **11**, Landsat 30 m | [Catálogo oficial de estatísticas](https://brasil.mapbiomas.org/downloads/estatisticas/), linha Biomas, Estados e Municípios / Cobertura 30m. ZIP público com XLSX, abas COVERAGE_11 e LEGEND_CODE; **1985–2025**. CC BY 4.0, atribuição Rede MapBiomas. |
| Fogo | INPE Programa Queimadas | [Dados abertos](https://data.inpe.br/queimadas/pages/secao_downloads/dados-abertos/) / [servidor oficial CSV](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/). Arquivos PR de referência 2020–2024, Brasil referência 2025, exportações mensais 2026 filtradas AQUA_M-T. Descoberta de anuais para próximos anos; fallback mensal. |
| Estações | ANA/SNIRH | [FeatureServer oficial](https://portal1.snirh.gov.br/server/rest/services/Esta%C3%A7%C3%B5es_Hidrometeorol%C3%B3gicas_SNIRH/FeatureServer/0). Consulta espacial, UF Paraná, coordenadas e campos cadastrais oficiais. Referência por atualização de cada estação. |
| Limite/área | IBGE | Malha municipal **2022**, reaproveitada de `population/turvo.geojson`; [indicador territorial 29167](https://servicodados.ibge.gov.br/api/v1/pesquisas/indicadores/29167/resultados/4127965): **936,038 km² / 2025**. |
| UCs | MMA/CNUC, distribuição IBAMA | [Poligonais sincronizadas](https://pamgia.ibama.gov.br/server/rest/services/BasesSincronizadas/lim_unidades_conserva%C3%A7%C3%A3o_mma_a/FeatureServer/0), sincronização **2026-08-11**. [Cadastro MMA](https://dados.mma.gov.br/dataset/unidadesdeconservacao) conferido independentemente na edição julho/2026. |
| Bioma | IBGE, distribuição IBAMA | [Biomas 1:250.000](https://pamgia.ibama.gov.br/server/rest/services/BasesSincronizadas/lim_biomas_ibge_250_a/FeatureServer/0): interseção confirma **Mata Atlântica**. Serviço não informa edição; não atribuímos um ano inventado. |

Coleta MapBiomas desta entrega: **2026-10-07T18:19:30.573244+00:00**. Cada recurso registra órgão, dataset, URL exata, referência, coleta, unidade, transformação e municípios. Downloads binários incluem SHA-256 e validadores HTTP. `reference` é período, `collectedAt` é coleta, `dt_sync` é sincronização técnica e não criação da UC. Os CSVs incluem fonte, referência e coleta em cada linha; inventário mantém também responsável pela estação. Metadados sem edição conhecida explicitam essa limitação.

## Resultados de cobertura · 2025

Valores abaixo em notação técnica (ponto decimal; vírgula de milhar). A interface usa português brasileiro.

| Código | Nome oficial da legenda | ha | % área IBGE |
| --- | --- | ---: | ---: |
| 3 | 1.1 Formação Florestal | 41,678.623 | 44.5266% |
| 9 | 3.3. Silvicultura | 8,014.226 | 8.5619% |
| 11 | 2.3. Campo Alagado e Área Pantanosa | 635.428 | 0.6788% |
| 15 | 3.1. Pastagem | 11,671.791 | 12.4694% |
| 21 | 3.4. Mosaico de Usos | 12,877.074 | 13.7570% |
| 24 | 4.2. Área Urbanizada | 362.809 | 0.3876% |
| 25 | 4.6. Outras Áreas não Vegetadas | 46.854 | 0.0501% |
| 33 | 5.1 Rio, Lago e Oceano | 232.562 | 0.2485% |
| 39 | 3.2.1.1. Soja | 17,876.605 | 19.0982% |
| 41 | 3.2.1.5. Outras Lavouras Temporárias | 502.629 | 0.5370% |
| 46 | 3.2.2.1. Café | 20.299 | 0.0217% |
| 48 | 3.2.1.4. Outras Lavouras Perenes | 0.000 | 0.0000% |

Classes terminais, sem somar os grupos pais. Soma **93.918,900 ha**, diferença **+0,3366%** frente a **93.603,8 ha** IBGE. Tolerância de validação **2%** para diferenças entre raster/limites/referências; não corrigimos as classes artificialmente para forçar 100%. A mesma área territorial publicada em 2025 é denominador explícito da série toda; percentuais históricos não representam limites territoriais históricos reconstituídos.

A legenda portuguesa oficial é preservada, incluindo hierarquia, código, nível, coleção e ano. A nomenclatura hierárquica da classe 48 no arquivo tem prefixo 3.2.1.4, embora diga Outras Lavouras Perenes; mantemos o texto original. Série 1985–2025 usa apenas uma coleção; nova coleção pode reclassificar anos passados. Comparações entre coleções distintas não são feitas.

## Vegetação e transformações

Vegetação nativa é **derivada**: soma dos códigos 3,4,5,6,7,49,11,12,77,84,50. Exclui silvicultura (9), agropecuária, apicum e afloramento rochoso. Em Turvo: **42.314,051 ha / 45,2055%**, incluindo Formação Florestal e Campo Alagado/Área Pantanosa. Florestas nativas (grupo 1) **41.678,623 ha / 44,5266%**; silvicultura **8.014,226 ha / 8,5619%**. Área urbanizada **362,809 ha**, água **232,562 ha**.

Grupo oficial Agropecuária inclui Silvicultura: **50.962,625 ha**. Card derivado **Agropecuária, exceto silvicultura**: **42.948,399 ha / 45,8832%**. Sua subtração é declarada para evitar dupla contagem. Produção, área colhida e rendimento continuam no módulo Agropecuária; cobertura não substitui PAM/PEVS.

Gráficos de cinco agregados evitam dezenas de curvas. Controles De/Até e classe geram diferença determinística de hectares. Não inferem causa, população urbana, ilegalidade, biodiversidade ou disponibilidade hídrica.

## Focos de calor

**AQUA_M-T / MODIS**, satélite de referência. Séries 2020–2025 completas: **12, 35, 18, 7, 21, 14** focos respectivamente. **2026: 4 focos até 2026-10-06**, parcial, dez exportações mensais disponíveis; meses futuros são `null`, não zero. Arquivo mensal revisado é reprocessado. IDs oficiais repetidos contam uma vez; IDs diferentes no mesmo ponto continuam distintos. Conflitos de ID, datas ou coordenadas invalidam a fonte. Filtro anual nome+UF protege o homônimo Turvo/SC; mensal exige código/nome+UF corretos. Datas são UTC.

A taxa **focos / km² IBGE × 1.000** é derivada; não é taxa de incêndios nem risco. Ano parcial não é comparado por variação percentual com ano completo. Os pontos publicados abrangem somente os dois anos mais recentes; mapa mostra o ano atual. Sem dados nacionais no navegador.

[Foco é detecção térmica](https://data.inpe.br/queimadas/pages/secao_informacoes/faq/index.html), não incêndio confirmado ou hectare queimado. Há [aviso INPE de falta de imageamento em 12/08/2026](https://terrabrasilis.dpi.inpe.br/queimadas/portal/pages/secao_informacoes/avisos/). Ausência de detecção não comprova ausência de fogo. Área queimada e desmatamento usam blocos distintos, indisponíveis até validar produto municipal adequado. Não aplicamos PRODES/DETER Amazônia Legal automaticamente à Mata Atlântica.

## Água e estações

**17 estações dentro da malha de Turvo** e **10 referências regionais fora dela**, as dez mais próximas entre as recuperadas pelo envelope espacial expandido em 0,15°. Não é busca exaustiva de todas as estações num raio de 50 km. Limite adicional: 50 km ao **centroide municipal**, não distância à divisa. Estação dentro = malha cobre seu ponto; o município textual do cadastro aparece separadamente e não é alterado para concordar artificialmente.

Tabela guarda código ANA, nome, latitude/longitude, pluviométrica ou fluviométrica, telemetria declarada, operação declarada, responsável, rio/bacia/sub-bacia e data cadastral. `MunicipioCodigo` é código interno ANA (ex. 22280700), não IBGE 4127965. Operando/telemetria não comprovam medição disponível ou recente. Rios e bacias listados são atributos das estações; não catálogo completo da hidrografia municipal.

Chuva, nível e vazão estão **unavailable**, sem números estimados: endpoint Hidroweb histórico consultado exige autenticação (401). O módulo não usa credenciais privadas, não interpreta vazão como risco, não extrapola chuva regional para todo município. O inventário público pode oscilar/sofrer timeout; falha mantém entrega anterior e sinaliza erro no job.

## UCs e bioma

Recorte real de polígonos com limite IBGE; cálculo em **SIRGAS 2000 / UTM 22S (EPSG:31982)**. Interseções:

- APA Estadual Serra da Esperança: **3,697 ha**, cadastro não menciona Turvo.
- Parque Estadual Serra da Esperança: **95,078 ha**, cadastro menciona Turvo. A área total de toda a UC não é atribuída a Turvo.

**União: 98,631 ha / 0,10537%**, já descontada a sobreposição. São **duas geometrias intersectantes**, **uma menção cadastral** a Turvo. A discrepância e pequenas faixas na divisa ficam visíveis. Isso é estimativa cartográfica com malha simplificada, não demarcação legal. Apenas geometrias recortadas simplificadas chegam ao navegador. Polígonos fora da malha são descartados. UC, APP, Reserva Legal e CAR não são somados; nenhum imóvel rural individual é publicado. Inventário CNUC inclui esferas federal/estadual/municipal; não ter interseção neste recorte não substitui auditoria jurídica de todas as UCs.

## Comparação e mapa

Turvo, Pitanga, Laranjal e Guarapuava: mesma coleção/ano/classes, área IBGE de cada município, percentuais e focos por 1.000 km². Área protegida dos pares permanece pendente, sem inventar zeros. Não há nota ambiental.

Mapa vetorial leve usa malha IBGE, focos do ano, estações internas e UCs recortadas, com camadas selecionáveis; tabelas fornecem alternativa acessível. **Não é mapa raster de uso do solo**. Esse mapa permanece TODO até produzir recorte municipal pequeno com método/licença confirmados, sem rasters nacionais ou credenciais GEE no build.

## Coleta reproduzível e custo

Requer Python 3.11+ para o ETL/testes geográficos; Actions usa Python 3.12.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements-environment.txt
python scripts/etl.py --module environment --offline
python scripts/etl.py --module environment --environment-source all
# Opcional: cache fora de public/data para consultas locais repetidas
python scripts/etl.py --module environment --environment-source fire --cache /tmp/turvo-environment-cache
npm test
npm run build
```

Escopos independentes `land/fire/water/protection`; `--force` rebaixa arquivos mesmo com HTTP sem revisão. MapBiomas usa tabulação municipal, sem rasterio/geopandas. Shapely e Pyproj são justificados por pontos/limites e área/união de UCs; não chegam ao frontend e não são exigidos pelo build. XLSX usa a dependência já existente de Educação. Downloads limitados a **160 MB por arquivo**, extração limitada, arquivos nacionais apenas temporários fora de `public/data`. O primeiro INPE atual baixa exportações mensais nacionais; consultas futuras verificam validadores e reaproveitam extratos municipais versionados. Cache bruto não é artefato nem Git. Se uma fonte futura exceder o limite, a coleta falha preservando o último dado; adaptar acesso em vez de remover limite sem critério.

Atualização semanal INPE (quinta 09:23 UTC); mensal dia 14 12:23 UTC todas as fontes para detectar nova coleção, revisar cadastro ANA e UCs. Sem telemetria contínua nesta entrega, não há consulta ANA diária. Dispatch manual seleciona fonte. Toda mudança passa por validação offline, testes e build antes de commit normal em main; escritores serializados com demais módulos. Arquivo INPE faltante preserva todo o bloco Fogo. Outras fontes podem publicar independentemente entregas válidas; qualquer falha termina o job em erro, com log explícito. Não se registra timestamp de tentativa sem alteração. Publicação transacional preserva arquivos em falha de escrita. Cloudflare Pages faz único deploy pela integração Git; Actions não usa Wrangler nem upload de build.

## MCP Brasil e endpoints antigos

Analisados `inpe/constants.py`, `inpe/client.py`, `ana/constants.py` e `ana/client.py` no [MCP Brasil](https://github.com/Mcp-Brasil/mcp-brasil/tree/main/src/mcp_brasil/data). API INPE histórica `terrabrasilis.dpi.inpe.br/queimadas/bdqueimadas-data-service/focos` respondeu **404**; não usada. ANA `www.snirh.gov.br/hidroweb/rest/api/estacao/telemetrica` respondeu **401**; não tratada como fonte pública de medições. Substituições são downloads oficiais INPE e inventário cartográfico ANA. MCP serve de referência técnica, sem dependência runtime ou código copiado.

## Validação e pendências

Testes exercitam município/UF e homônimo, legenda/unidade/coleção/hierarquia/séries, área/tolerância/percentuais, agregações históricas, nativa vs plantada, datas/IDs/satélite/coordenadas/futuro e meses ausentes, geometria ANA, UC recortada/união sem dupla contagem, resposta truncada, preservação integral em falha, CSVs com metadados e loader/narrativa. Fixtures são pequenas; nenhuma rede ou raster nacional em testes. `schemaVersion` e contratos TypeScript/Python são validados antes de publicação; JSON Schema está em `docs/schemas/environment.schema.json`.

Validação desta entrega: **297 testes Python + 88 JavaScript, todos aprovados**; JSON Schema aprovado; build TypeScript/Vite aprovado; workflows aprovados por actionlint; interface conferida em desktop e 375 px, filtro municipal retorna 17 estações e sem erros de console. Reconsulta ANA real manteve todos os bytes, sem timestamp novo. Falha total de fontes foi simulada e preservou integralmente os arquivos.

TODO: recorte raster municipal; MapBiomas Fogo/área queimada; produto específico de desmatamento Mata Atlântica; telemetria e histórico público por estação; hidrografia/bacias municipais completas; qualidade da água IAT/ANA; UCs nos pares; saneamento/resíduos SINISA; clima INMET; eventos S2ID. Sem contagem inventada de nascentes, risco, biodiversidade ou imóveis. Dados indisponíveis possuem `status=unavailable` e `value=null`.
