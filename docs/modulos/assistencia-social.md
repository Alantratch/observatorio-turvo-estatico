# Assistência Social — Turvo/PR

Módulo `social`, rota `#social`, município **4127965**, UF **PR**. Substitui o Comparador Municipal como página independente. As comparações temáticas existentes foram preservadas; `comparison.json` não foi excluído. A aplicação continua estática, com carregamento sob demanda e sem servidor/API própria obrigatória.

## Quatro universos

1. **Cadastro e vulnerabilidade:** Cadastro Único; famílias e pessoas separadas, renda e qualidade cadastral. Não é uma pesquisa de pobreza de todos os habitantes.
2. **Benefícios:** Bolsa Família e BPC separados, sem soma entre programas ou com o Cadastro Único. Podem existir sobreposições.
3. **Rede:** CadSUAS por data de extração e Censo SUAS por edição anual; cadastro de equipamento não comprova operação atual, nem ausência de resposta comprova inexistência.
4. **Atendimento:** RMA CRAS/PAIF, base municipal tratada. Famílias cadastradas não são famílias acompanhadas; acompanhamentos mensais não representam famílias únicas no ano.

## Fontes confirmadas e descoberta

Fonte estatística: **MDS/SAGICAD/SNAS**; IBGE apenas para denominadores populacionais. Não há consulta a sistemas municipais internos, login do Cadastro Único ou dados identificados.

| Recurso | Uso e referência |
| --- | --- |
| [Ferramentas oficiais do Cadastro Único](https://www.gov.br/mds/pt-br/orgaos/SAGICAD/dados-e-ferramentas-informacionais/dados-e-ferramentas-do-cadastro-unico) | Descoberta de RI, CECAD 2.0, Observatório do Cadastro Único, VIS DATA, Mapa Social e IVCAD; não há dependência dessas interfaces no navegador |
| [Serviço público municipal MDS](https://aplicacoes.mds.gov.br/sagi/servicos/misocial?q=*:*&fq=tipo_s:mes_mu&fq=codigo_ibge:412796&wt=json&rows=1&sort=anomes_s%20desc) | Agregados mensais consumidos pelo RI/VIS DATA; consulta restrita aos quatro municípios e campos explicitamente autorizados |
| [RI Cadastro Único de Turvo](https://aplicacoes.cidadania.gov.br/ri/ri/relatorios/cidadania/cadastro-unico.php?codigo=412796&p_ibge=412796&ibge=412796) | Conferência independente dos indicadores de setembro/2026 |
| [RI Bolsa Família de Turvo](https://aplicacoes.cidadania.gov.br/ri/ri/relatorios/cidadania/bolsa-familia.php?codigo=412796&p_ibge=412796&ibge=412796) | Conferência de famílias, pessoas, valor e média oficial; setembro/2026 |
| [RI Benefícios de Turvo](https://aplicacoes.cidadania.gov.br/ri/ri/relatorios/cidadania/beneficios.php?codigo=412796&p_ibge=412796&ibge=412796) | BPC pela Fonte Pagadora; agosto/2026, competência independente |
| [Catálogo Censo SUAS/RMA](https://aplicacoes.mds.gov.br/sagi/snas/vigilancia/index2) | Descoberta dos links XLSX/ZIP efetivamente publicados; Censo 2025 e RMA CRAS 2025 |
| [RMA CRAS tratado 2025](https://aplicacoes.mds.gov.br/sagi/dicivip_datain/ckfinder/userfiles/files/RMA_CRAS_Criterios_2025_divulgacao_150526.xlsx) | A1, A2, C1 da planilha `Base tratada`; sem recortes de violência/sexo/idade/bairro |
| [IBGE tabela 6579](https://sidra.ibge.gov.br/tabela/6579) | Variável 9324, estimativa populacional 2026, reutilizando o conector IBGE já existente |

O identificador municipal do MDS tem seis dígitos: **412796 ↔ 4127965**, **411960 ↔ 4119608**, **411325 ↔ 4113254**, **410940 ↔ 4109401**. Nome, código, UF e nível mensal são conferidos; Turvo/SC é rejeitado. O parâmetro `q=*:*` é necessário. A resposta não é uma API com contrato formal estável: schema mudado, duplicidade ou truncamento interrompe publicação e preserva snapshot anterior.

HTML é usado **somente como último recurso para descobrir links do catálogo Censo/RMA**, porque não foi confirmado catálogo estruturado equivalente; números vêm do serviço agregado e arquivos estruturados. Os links têm host/caminho/ano validados. Não há scraping numérico das páginas RI no ETL.

## Campos municipais utilizados

O código-fonte `scripts/sources/mds.py` mantém o dicionário explícito e a lista `fl` da consulta; campos não previstos nunca são copiados para dados públicos.

- CadÚnico: `cadun_qtd_familias_cadastradas_i`, `cadun_qtd_pessoas_cadastradas_i`, famílias/pessoas `pobreza_pbf`, `baixa_renda`, `rfpc_acima_meio_sm`, `cadun_qtd_familias_atualizadas_i`, `cadun_taxa_atualizacao_cadastral_d`.
- Bolsa Família: `qtd_familias_beneficiarias_bolsa_familia`, `qtd_pessoas_beneficiarias_bolsa_familia_i`, `valor_repassado_bolsa_familia`, `pbf_vlr_medio_benef_f`. **Não usamos** `pbf_vlr_repassado_d`: nessa resposta, contém a competência, não o valor transferido.
- BPC pela Fonte Pagadora: `bpc_ben_i`, `bpc_idoso_ben_i`, `bpc_pcd_ben_i`, `bpc_idoso_val_s`, `bpc_pcd_val_s`, `bpc_val_s`. Campos monetários string-decimal preservam centavos; aliases float divergem. **Não usamos** `bpc_residencia_*`, universo distinto. Setembro contém zeros genéricos e não os campos completos: é tratado como não publicado, não como ausência de BPC.
- CadSUAS: `cadsuas_data_extracao_s`, contagens confirmadas de CRAS, CREAS, convivência, acolhimento, Centro Dia/similares; Centro POP sem campo confirmado é `unavailable`, não zero presumido. Ausência de campo não equivale a inexistência.
- Censo: apenas `Dados_Gerais`, código/UF/identificador, `q0_1` (nome da instituição), `q0_2/3/4/6` (endereço institucional), atividades PAIF `q12_13` e PAEFI `q12_3` da edição **2025**. Não presumir esses códigos para outra edição. Nenhum arquivo RH é aberto. Centro Dia não tem CSV, portanto usa XLSX; planilhas adicionais só são aceitas quando vazias. A UF de Centro Dia 2025 está em `q0_9`, conforme dicionário da edição, não em `q0_10` (contato, excluído).
- RMA: `IBGE`, `IBGE7`, `UF_A`, `ano`, `mes`, identificador institucional somente para deduplicação interna, `a1`, `a2`, `c1`. Apenas os totais municipais saem no JSON/CSV.

Cada indicador normalizado inclui órgão, base, indicador, referência, unidade, código, fonte/URL, coleta, transformação e nota. `sourceId` liga a fonte ao hash de conteúdo; fontes anuais incluem SHA-256 do arquivo original. Não publicamos respostas amplas/raws sociais.

## Renda e qualidade cadastral

As três categorias de renda são mutuamente exclusivas e verificadas contra os totais de famílias e pessoas. Não somamos a faixa “até meio salário mínimo” às suas subcategorias, nem reciclamos definições antigas de extrema pobreza.

[Definição oficial consultada, atualizada em 04/06/2026](https://www.gov.br/mds/pt-br/noticias-e-conteudos/desenvolvimento-social/noticias-desenvolvimento-social/desde-2023-mais-de-14-milhoes-de-pessoas-sairam-da-pobreza): pobreza até R$ 218 por pessoa/mês; baixa renda acima desse limite até meio salário mínimo; demais acima de meio salário mínimo. Essa explicação está vinculada à edição/referência do snapshot; **não é algoritmo permanente de elegibilidade**, não reclassifica históricos, e deve ser revista para novas divulgações.

O percentual atualizado é oficial, conferido contra numerador/denominador com tolerância de arredondamento de 0,02 ponto percentual. “Diferença entre total e atualizados” tem status `derived`, fórmula explícita; não mede fluxo recente. Histórico do total cadastrado marca março/2025 como transição administrativa do novo sistema; o gráfico interrompe a linha, mantendo o ponto em tabela.

## Bolsa Família e BPC

Bolsa Família usa janela de 24 meses dentro do programa iniciado em março/2023; não conecta Auxílio Brasil. Famílias, pessoas, repasse nominal e média têm unidades próprias. O RI informa que valor transferido e benefício médio desconsideram famílias suspensas na folha; a média oficial **não é substituída por divisão pelo total de famílias**. Transferências federais aos beneficiários não são despesa da Prefeitura ou receita municipal.

BPC pela Fonte Pagadora tem pessoas idosas e com deficiência separados, contagens/valores/competência próprios. Valida soma das duas categorias e dos centavos publicados, sem inferir públicos únicos entre programas. Apenas competência com todos os campos necessários publicados pode ser apresentada; meses incompletos viram lacunas na série.

## Rede SUAS e oferta

Arquivos da edição 2025 descobertos no catálogo: `1_CRAS.zip`, `2_CREAS.zip`, `3_CENTRO_POP.zip`, `4_UNIDADE_DE_ACOLHIMENTO.zip`, `5_CENTRO_DE_CONVIV%c3%8aNCIA.zip`, `6_CENTRO_DIA.zip`, `8_POSTO_DE_CADASTRAMENTO.zip` em `https://aplicacoes.mds.gov.br/snas/defeso/censosuas/2025/`.

Identificação oficial das instituições, endereço institucional, tipo, referência, status de respondente e fonte são públicos. Deduplicação por identificador/município; atributos conflitantes bloqueiam coleta. Responder ao Censo não significa situação operacional atual. A rede CadSUAS traz contagens na extração de setembro/2026; diferenças entre bases são exibidas, nunca reconciliadas artificialmente.

As coordenadas exportadas não tiveram validade/precisão confirmada (incluem valores fora de faixa). Não há geocodificação inventada ou reescala especulativa: `coordinates=null`, mapa institucional pendente. **Nenhum mapa de famílias/beneficiários.** Os serviços PAIF/PAEFI são identificados pelas ações declaradas no Censo, sem inferir atendimentos recentes pela simples presença de uma unidade.

Alguns XLSX nacionais têm caracteres de controle proibidos em XML 1.0; somente esses bytes são retirados do XML de leitura. Células, texto válido e hash do arquivo original permanecem intactos. Outros erros de formato bloqueiam atualização.

## RMA e cobertura

A base tratada do MDS remove formulários inteiramente zerados e valores discrepantes conforme critérios descritos no próprio XLSX. Não reutilizamos `Base Original`, colunas `_original`, nem imputamos valores retirados. Se alguma unidade informante tiver célula ausente, o total daquela variável no mês fica ausente. Meses sem formulários ficam `null`, não zero. A quantidade de formulários válidos acompanha cada mês; não se infere cobertura integral dos serviços municipais.

A1 é famílias em acompanhamento PAIF no mês; A2 é novas famílias; C1 é atendimentos particularizados. A1 não pode ser somada nos doze meses e apresentada como famílias únicas. RMA de 2025 e oferta do Censo 2025 não são apresentados como atendimento de 2026. Agregados PAEFI permanecem pendentes até validar a exportação RMA CREAS e a proteção das células.

## Comparação interna

Turvo, Pitanga, Laranjal e Guarapuava, em ordem fixa. Cadastro com a **mesma competência**; números absolutos e proporção em seletores separados, unidades CRAS somente como resposta censitária na mesma edição.

`pessoas CadÚnico / população IBGE estimada × 100`: status `derived`, guarda numerador/denominador, URLs e referências. CadÚnico mensal e estimativa IBGE de 1º de julho no mesmo ano têm datas distintas, portanto é **proporção administrativa aproximada**, não cobertura oficial nem percentual de pobres. Em falha temporária da consulta IBGE, a última estimativa verificada do mesmo ano é preservada com sua coleta original. Sem estimativa compatível, proporção indisponível. Não usa famílias divididas por habitantes como cobertura familiar. Não há ranking de pobreza ou inferência causal.

## Privacidade e proteção de dados

Somente estatísticas municipais agregadas e equipamentos. **Nunca** nome de pessoa/família, CPF, NIS, telefone, nascimento, prontuário, endereço residencial ou benefício individual. Nenhum cruzamento por deficiência/violência/bairro/idade/sexo, GPTE ou composição familiar no MVP; não acessamos sistemas identificados. Dados nacionais são temporários/cache não público, não entram no Git nem em `public/data`; membros RH não são lidos.

Contagens **1–4** de famílias/pessoas/benefícios/atendimentos são publicadas com `status=suppressed`, `value=null`, sem valor original e sem exportação da célula. No BPC, total/categorias/valores recebem **supressão complementar** quando uma categoria é pequena. Faixas de renda recebem supressão complementar. Não criamos recortes sensíveis; equipamentos podem ter contagem 1 porque não identificam beneficiários.

A validação usa lista explícita de campos permitidos e bloqueia campos desconhecidos, não apenas palavras proibidas. `name` é permitido **somente no objeto municipality**; `institutionName` e `institutionalAddress` **somente nas unidades SUAS**. CSVs devem respeitar cabeçalhos exatos e corresponder ao snapshot validado. Arquivos sociais extras/raws são bloqueados. **`npm run build` falha** se snapshot/CSV contiver campos pessoais, contagens pequenas não protegidas ou divergência. Testes cobrem injeções de campos e os caminhos de supressão.

Isso é uma política conservadora do Observatório, não garantia absoluta contra todo risco de reidentificação. Novos recortes exigem análise de finalidade, universo e reconstrução por totais antes da implementação.

## Operação e arquivos

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements-education.txt
python scripts/etl.py --module social --cache .mds-cache
python scripts/etl.py --module social --offline
# Revalidar também arquivos anuais no mesmo URL:
python scripts/etl.py --module social --force --cache .mds-cache
python scripts/check_social_privacy.py
npm test
npm run build
```

- `scripts/sources/mds.py`: descoberta, filtro municipal/colunas, formatos, cache, parse.
- `scripts/modules/social.py`: conceitos, normalização, integridade, supressão, CSV, catálogo e publicação transacional.
- `scripts/check_social_privacy.py`: barreira do build e conferência dos exports.
- `src/modules/social/`: página, seções, gráficos/componentes, tipos, estados e estilos.
- `public/data/social.json`: schema v1 sem mocks; `real`, `derived`, `unavailable`, `suppressed`.
- `public/data/exports/social-{cadunico,bolsa-familia,bpc,suas,services}.csv`: só agregados/equipamentos.
- `docs/github-actions/social.yml`: template mensal de coleta/validação/testes/build/commit opcional/deploy.

Reutilizamos HTTP JSON/retries (`scripts/common.py`), download limitado (`sources/datasus.py`), IBGE (`sources/ibge.py`), escrita atômica e publicação com rollback (`modules/health.py`). Arquivos anuais usam cache com ETag/Last-Modified/tamanho e SHA-256; sem validadores, novo download. Arquivos e conteúdo idênticos preservam timestamps; mudanças históricas/revisões são detectadas. Falhas não sobrescrevem snapshots, CSVs ou catálogo; saída não zero sinaliza falha da atualização.

**GitHub Actions ainda não ativo:** a credencial disponível não tem permissão de escrita de workflows, como nas etapas anteriores. O template está pronto para instalação em `.github/workflows/social.yml` por credencial autorizada. Cloudflare Pages continua publicando pela integração Git, sem Worker ou serviço pago novo. Não chamar automação preparada de automação executada.

## Pendências explícitas

- IDCRAS/IDCREAS/IDConselho: [ferramenta oficial](https://www.gov.br/mds/pt-br/orgaos/SAGICAD/dados-e-ferramentas-informacionais/IDCRAS-IDCREAS-e-IDConselho/cras); ferramenta legada de downloads apresentou loop de redirecionamento. Validar edição/componentes/exportação estruturada, sem “nota” ou ranking moral.
- IVCAD: [MDS](https://www.gov.br/mds/pt-br/orgaos/SAGICAD/dados-e-ferramentas-informacionais/ivcad); ferramenta de análise familiar não será acessada na área identificada. Confirmar exportação municipal segura antes de reproduzir índice.
- Conselho Municipal: arquivo Censo foi encontrado, mas não tem o mesmo contrato de identificador das unidades; implementar schema próprio agregado, sem nomes de conselheiros.
- Famílias unipessoais, fluxos recentes e GPTE: campos atuais com definição/competência confirmada e proteção contra células pequenas.
- RMA CREAS/PAEFI e histórico RMA anterior a 2025: nova validação de schema e cobertura; sem cruzamentos sensíveis.
- Mapas: coordenadas oficiais válidas só para instituições; nenhuma família.
- Definições de renda e dicionários Censo: revisar por edição; não aplicar automaticamente campos de 2025 a novos questionários.
