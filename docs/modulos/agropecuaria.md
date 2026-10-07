# Agropecuária de Turvo/PR

Módulo estático, carregado sob demanda em `#agriculture`. Código IBGE **4127965**; homônimo de Santa Catarina é rejeitado. Comparações com Guarapuava **4109401**, Pitanga **4119608**, Laranjal **4113254** e Paraná **41**. Fonte estatística: **IBGE**, não MCP Brasil.

## Fontes verificadas e recortes

Tabelas, conceitos, IDs de variáveis, unidades, categorias e níveis territoriais foram conferidos na API de Agregados v3 em **07/10/2026**. Dados anuais mais recentes: **2025**; dez períodos **2016–2025** para Turvo. Censo Agropecuário: **2017**, com recorte estrutural independente. A próxima coleta descobre os períodos publicados, sem fixar 2025 no código.

| Pesquisa / tabela SIDRA | Variáveis confirmadas | Classificações usadas |
| --- | --- | --- |
| [PAM 5457](https://sidra.ibge.gov.br/tabela/5457) | 214 quantidade; 8331 área plantada/destinada; 216 área colhida; 112 rendimento; 215 valor | 782, todos os produtos divulgados |
| [PPM 3939](https://sidra.ibge.gov.br/tabela/3939) | 105 efetivos, cabeças | 79, tipos de rebanho |
| [PPM 74](https://sidra.ibge.gov.br/tabela/74) | 106 produção de origem animal; 215 valor | 80, produtos animais |
| [PPM 94](https://sidra.ibge.gov.br/tabela/94) | 107 vacas ordenhadas, cabeças | Sem classificação adicional |
| [PPM 3940](https://sidra.ibge.gov.br/tabela/3940) | 4146 produção da aquicultura; 215 valor | 654, tipos de produtos |
| [PEVS 289](https://sidra.ibge.gov.br/tabela/289) | 144 quantidade extraída; 145 valor | 193, produtos da extração vegetal |
| [PEVS 291](https://sidra.ibge.gov.br/tabela/291) | 142 quantidade da silvicultura; 143 valor | 194, produtos da silvicultura |
| [Censo 6754](https://sidra.ibge.gov.br/tabela/6754) | 183 estabelecimentos; 184 área | 829 Total/Familiar/Não familiar; totais 221/12517/220 |
| [Censo 6884](https://sidra.ibge.gov.br/tabela/6884) | 185 pessoas ocupadas | 829 Total/Familiar/Não familiar; totais 2/223/218/12517 |

A classificação de lavouras temporárias/permanentes é obtida dos metadados das tabelas [1612](https://servicodados.ibge.gov.br/api/v3/agregados/1612/metadados) e [1613](https://servicodados.ibge.gov.br/api/v3/agregados/1613/metadados), por nome de produto confirmado, não por lista manual das culturas de Turvo.

Descoberta: `https://servicodados.ibge.gov.br/api/v3/agregados`. Para cada tabela: `/{tabela}/metadados`, `/{tabela}/periodos`; números: `/{tabela}/periodos/{anos}/variaveis/{variáveis}?localidades=...&classificacao=...`. As **URLs completas efetivamente consultadas**, categorias, metadados e respostas estão em `agriculture.json` e `agriculture/raw/*.json`. Não é necessário copiar manualmente consultas com centenas de categorias.

## Resultados disponíveis

PAM 2025: **32 culturas com valores/produção divulgados**, valor total oficial **R$ 224.465.000**. O valor não é PIB, receita dos produtores, lucro ou VAB. Área colhida total publicada **24.366 ha** não equivale a território agrícola único: culturas sucessivas podem usar o mesmo solo no mesmo ano.

| Cultura de maior valor | Quantidade | Área colhida | Rendimento oficial | Valor nominal |
| --- | --- | --- | --- | --- |
| Soja (em grão) | 70.297 t | 16.870 ha | 4.167 kg/ha | R$ 139.258.000 |
| Erva-mate (folha verde), cultivada | 25.100 t | 852 ha | 29.460 kg/ha | R$ 31.701.000 |
| Milho (em grão) | 21.801 t | 2.160 ha | 10.093 kg/ha | R$ 20.471.000 |

Mandioca ilustra a diferença entre áreas: 133 ha plantados e 130 ha colhidos. Tomate tem o maior rendimento no recorte de culturas em kg/ha: 59.000, sem inferir qualidade ou eficiência econômica.

Culturas atuais: abacate; abóbora; alface; alho; amendoim (em casca); arroz (em casca); aveia (em grão); banana (cacho); batata-doce; batata-inglesa; cana-de-açúcar; cebola; cenoura; cevada (em grão); erva-mate (folha verde); feijão (em grão); laranja; limão; mandioca; maracujá; melancia; milho (em grão); milho verde; morango; pêssego; repolho; soja (em grão); tangerina; tomate; trigo (em grão); triticale (em grão); uva. Centeio e fumo também permanecem no explorador histórico, embora o último ano não tenha produção positiva. Novos produtos são descobertos nos metadados.

PPM 2025: bovinos **36.000**, bubalinos **80**, equinos **1.260**, suínos total **3.100** (matrizes **450**, incluídas no total), caprinos **450**, ovinos **5.760**, galináceos total **56.000** (galinhas **16.800**, incluídas no total). Não somar totais com seus subgrupos.

Produtos animais: leite **26.500 mil litros**, ovos de galinha **71 mil dúzias**, mel **102.200 kg**, lã **2.200 kg**. Valor total de origem animal publicado **R$ 73.834.000**. Vacas ordenhadas **5.980**; indicador derivado **4.431,4 litros/vaca/ano**, fórmula leite em mil litros × 1.000 ÷ vacas, mesma referência. Não é produção por vaca/dia.

Aquicultura: carpa **5.100 kg**, pacu e patinga **130 kg**, tambacu/tambatinga **180 kg**, tilápia **12.300 kg**, outros peixes **390 kg**. Total oficial de valor **R$ 279.000**. A soma dos valores das espécies resulta R$ 280.000 por arredondamento; preservamos o total publicado, sem exigir igualdade artificial.

PEVS 2025: extração de pinhão **311 t**, madeira em tora **3.300 m³**, nó de pinho **340 m³**. Árvores abatidas **1 mil árvores**, informação física separada. Extração de erva-mate: **zero divulgado**, diferente das 25.100 t cultivadas PAM. Total de valor da extração **R$ 5.439.000**. Na silvicultura: lenha **65.000 m³**, madeira em tora **302.000 m³**, incluindo papel/celulose **14.000 m³** e outras finalidades **288.000 m³**; pinus/eucalipto aparecem como subcategorias. Total nominal silvicultura **R$ 50.652.000**. Não somar PEVS com PAM ou VAB para obter um “PIB agro”.

Censo 2017: **1.219 estabelecimentos**, **52.113 ha**, **2.804 pessoas ocupadas**. Agricultura familiar conforme classificação 829 do Censo: **859 estabelecimentos**, **11.634 ha**, **1.829 pessoas**; não familiar: **360**, **40.479 ha**, **975**. Participação familiar derivada **70,47%** dos estabelecimentos. Censo é universo diferente de RAIS, não mede vínculos formais.

## Unidades, estados e cálculos

- Valor original em **Mil Reais**, convertido uma única vez para **R$ nominal**, preservando unidade original e transformação. Intervalos históricos de moeda são validados; não usar cruzeiros como reais. Nenhuma deflação aplicada.
- PAM: quantidade em toneladas e rendimento kg/ha, com exceções oficiais. **Abacaxi e coco-da-baía: mil frutos e frutos/ha**, conforme [nota 6 oficial PAM](https://sidra.ibge.gov.br/pesquisa/pam/tabelas/). O campo genérico da API v3 declara toneladas/kg-ha para esses produtos: o ETL corrige a unidade efetiva conforme a nota, preserva a declaração original e registra a transformação, sem converter a quantidade. Esses produtos não têm série positiva de Turvo neste recorte, mas são necessários nas comparações.
- PPM/PEVS usam a unidade de cada categoria nos metadados: mil litros, mil dúzias, quilogramas, toneladas, milheiros, m³, mil árvores. Quantidades físicas e rendimentos só entram juntos em um gráfico/ranking quando a unidade coincide.
- `-` → **0/real**; `X` → **null/suppressed**; `..` → **null/notApplicable**; `...` → **null/unavailable**. Nenhum oculto é estimado. **Não há X nas respostas oficiais efetivamente coletadas neste recorte**; o parser e a interface têm tratamento e testes explícitos de supressão. Há zeros, não aplicabilidade e indisponibilidade reais, incluindo culturas adicionadas à PAM em 2025.
- Categorias totais são armazenadas separadamente dos produtos. Café arábica/canephora são subdivisões do café total e não entram com ele no ranking geral. PEVS guarda IDs, nomes e níveis; madeira total e finalidades/espécies não são adicionadas. Pinheiro brasileiro suplementar não é somado novamente à madeira.
- Variação anual derivada = `(atual/anterior − 1) × 100`, anos consecutivos, mesma variável/unidade, anterior positivo. Base zero, ausência, sigilo ou lacuna → null, nunca infinito. Variação monetária é explicitamente **nominal**.
- Participação de cultura usa **o total PAM publicado**, não soma de subcategorias nem PIB. Participação estadual usa o mesmo produto/ano/unidade, Turvo ÷ Paraná × 100. Comparações não inventam ranking de todos os municípios do estado.
- Rendimento oficial é preservado. Conferência aproximada `quantidade × 1000 / área colhida`, tolerância max(1 unidade, 3%) para arredondamento, apenas unidades aplicáveis. Divergências geram aviso, não substituição dos números oficiais. Nenhum aviso neste snapshot.

## Arquitetura, arquivos e atualização

`src/modules/agriculture/`: página React própria, carregamento/validação, contrato TypeScript, componentes de tabelas/fontes/comparação e gráficos Recharts. Cada gráfico oferece título, unidade, referência e tabela alternativa. Textos são determinísticos, sem gerar explicações causais.

`scripts/sources/ibge.py`: extensão `AgriculturalIBGE` do conector IBGE existente, sem duplicar cliente e sem alterar os contratos de População/Economia. Validação de pesquisa, variável, unidade, dimensão, município/UF/nível, ano e completude do cubo. `scripts/sources/agriculture-tables.json`: configuração auditada. `scripts/modules/agriculture.py`: transformação, cálculos, qualidade, CSVs e publicação com rollback usando o mecanismo transacional já existente no projeto.

```sh
python3 scripts/etl.py --module agriculture
python3 scripts/etl.py --module agriculture --offline
npm test
npm run build
```

O módulo roda **explicitamente**; não foi adicionado à rotina semanal `--module all`, para respeitar a periodicidade mensal e preservar outros módulos. Coleta metadados/periodicidade e os dez anos novamente, mesmo sem mudar o último ano, aceitando revisões retroativas. Uma resposta idêntica mantém `collectedAt` e não gera commit de timestamp. O cadastro de classificações mantém a mesma entrega quando nada muda.

Falha em qualquer uma das bases impede publicação parcial: último snapshot completo, CSVs, raws e catálogo preservados; somente relatório `collection.failures/attemptedAt` muda. CLI encerra com erro para sinalizar a coleta. Sem snapshot anterior, falha sem criar números. Download/validação ocorrem antes da troca; erro de publicação restaura arquivos anteriores.

Entregas:

- `public/data/agriculture.json`: schemaVersion 1, Turvo histórico, pares/Paraná no último ano, nove fontes e cálculos. Aproximadamente **2,9 MB JSON legível / 85 KB gzip** nesta edição.
- `public/data/agriculture/raw/*.json`: nove respostas brutas com metadados, URL, períodos, coleta; somente cinco territórios, sem arquivos nacionais ou registros individuais.
- `public/data/agriculture/classifications.json`: classificações temporária/permanente oficiais.
- `public/data/exports/agriculture-{crops,livestock,forestry,census}.csv`: séries de Turvo com referência, código, unidade, variável, produto/categoria, estado e fonte. Comparações e metadados completos no JSON.
- `public/data/indicators.json`: seis destaques oficiais; mock `soy` removido. Indicadores dos outros módulos preservados.
- Testes `tests/test_agriculture.py`, `tests/agriculture-data.test.mjs`, fixture PAM com células oficiais selecionadas; corrupção intencional somente nos testes.

A rotina mensal está preparada em [agriculture.yml](../github-actions/agriculture.yml), inclui coleta, validação offline, testes, build e deploy Cloudflare opcional. **Template ainda não ativado**: a credencial GitHub desta sessão não tem permissão de escrita de workflows, limitação já existente. Com essa permissão, copiar para `.github/workflows/agriculture.yml`. Deploy pela integração Git do Cloudflare Pages usa build `npm run build`, saída `dist`, sem Worker, banco ou serviço pago obrigatório. Nenhuma nova dependência npm/Python foi adicionada.

## Referência MCP Brasil e próximos passos

Inspecionados catálogo, constantes, cliente e ferramentas da feature [`ibge` de MCP Brasil](https://github.com/Mcp-Brasil/mcp-brasil/tree/2efb258370b125bbf190884283ae10f209b9d335/src/mcp_brasil/data/ibge). O cliente técnico consultado achata dimensões para localidade/valor; não o copiamos porque este módulo precisa preservar período, categoria, unidade e símbolos. MCP não é uma fonte estatística nem dependência de execução.

TODOs explícitos: condição do produtor e detalhamento do uso das terras/irrigação no Censo, máquinas, ranking estadual completo, comparações estruturais censitárias na interface, extensões LSPA com conceitos e referências próprios. Não classificar solo por área colhida PAM nem inferir tecnologia, emprego ou causas a partir desses números. Novas tabelas só entram após conferir metadados, universos, unidades e proteção do sigilo.

## Verificação desta entrega

**268 testes aprovados** (203 Python e 65 JavaScript), incluindo 47 novos testes do módulo, fixture do cubo PAM, normalização das nove respostas oficiais, símbolos, unidades, moeda, duplicatas/lacunas, município/UF, revisão retroativa, publicação sem ruído e preservação em falhas. `npm run build` concluído; validação offline aprovada. Revisão no navegador em desktop e celular 390 × 844: filtros, comparação de culturas/leite, gráficos visíveis, tabela censitária correta, downloads estáticos HTTP 200, sem erros de console e sem overflow horizontal da página. Indicadores dos outros módulos conferidos contra `origin/main`, sem alterações.
