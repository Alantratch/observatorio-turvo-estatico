import { useEffect, useState } from "react";
import type { AgricultureData, ProductBlock } from "./types";
import {
  loadAgriculture,
  rankProducts,
  cellText,
  format,
  narrative,
  share,
  shortName,
  variationText,
  metricLabels,
} from "./data";
import {
  Comparison,
  Section,
  SourceNote,
  ProductTable,
  ProductHistory,
  ForestryBlock,
  Methodology,
} from "./AgricultureComponents";
import { AgricultureChart } from "./AgricultureCharts";
import "./agriculture.css";
function HistoryExplorer({
  block,
  label,
}: {
  block: ProductBlock;
  label: string;
}) {
  const [id, setId] = useState(
      [...block.products].sort(
        (a, b) =>
          (b.latest.metrics.productionValue?.value ??
            b.latest.metrics.herd?.value ??
            -1) -
          (a.latest.metrics.productionValue?.value ??
            a.latest.metrics.herd?.value ??
            -1),
      )[0]?.id,
    ),
    [metric, setMetric] = useState(
      Object.keys(block.products[0]?.latest.metrics ?? {})[0],
    );
  const p = block.products.find((p) => p.id === id) ?? block.products[0];
  const keys = Object.keys(p?.latest.metrics ?? {}),
    key = keys.includes(metric) ? metric : keys[0];
  return p ? (
    <>
      <div className="agri-filters">
        <label>
          {label}
          <select value={p.id} onChange={(e) => setId(e.target.value)}>
            {block.products.map((p) => (
              <option key={p.id} value={p.id}>
                {shortName(p.name)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Variável do histórico
          <select value={key} onChange={(e) => setMetric(e.target.value)}>
            {keys.map((k) => (
              <option key={k} value={k}>
                {metricLabels[k]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ProductHistory product={p} metric={key} />
      <p className="agri-callout">{variationText(p, key)}</p>
    </>
  ) : null;
}
function Crops({ data }: { data: AgricultureData }) {
  const [metric, setMetric] = useState("productionValue"),
    [kind, setKind] = useState("all"),
    [unit, setUnit] = useState("Toneladas");
  const available = [
    ...new Set(
      data.crops.products
        .filter((p) => p.presentInLatest)
        .map((p) => p.latest.metrics[metric]?.unit)
        .filter(Boolean),
    ),
  ];
  const selectedUnit = available.includes(unit) ? unit : available[0];
  const ranking = rankProducts(data.crops, metric, kind, selectedUnit),
    lead = ranking.find((p) => p.latest.metrics[metric].value !== null);
  return (
    <>
      <Section
        id="agri-crops"
        title="Culturas agrícolas"
        description={`${data.summary.cropCount} culturas com produção ou valor divulgado em ${data.crops.reference}. Ranking por variável, sem misturar unidades físicas.`}
      >
        <div className="agri-filters">
          <label>
            Ordenar culturas por
            <select value={metric} onChange={(e) => setMetric(e.target.value)}>
              {[
                "productionValue",
                "harvestedArea",
                "production",
                "yield",
                "plantedOrIntendedArea",
              ].map((k) => (
                <option value={k} key={k}>
                  {metricLabels[k]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tipo de lavoura
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="all">Todas</option>
              <option value="Temporária">Temporária</option>
              <option value="Permanente">Permanente</option>
            </select>
          </label>
          <label>
            Unidade do ranking
            <select
              value={selectedUnit}
              onChange={(e) => setUnit(e.target.value)}
            >
              {available.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
          </label>
        </div>
        {lead ? (
          <>
            <h3>{metricLabels[metric]} · dez maiores culturas</h3>
            <AgricultureChart
              bars
              rows={ranking
                .slice(0, 10)
                .map((p) => ({
                  label: shortName(p.name),
                  value: p.latest.metrics[metric].value,
                }))}
              title={metricLabels[metric]}
              unit={selectedUnit}
              reference={data.crops.reference}
            />
            <p className="agri-callout">
              <strong>{shortName(lead.name)}</strong> lidera este recorte:{" "}
              {cellText(lead.latest.metrics[metric])}.
              {metric === "productionValue" && (
                <>
                  {" "}
                  Participação calculada (indicador derivado) no valor agrícola
                  publicado:{" "}
                  {format(
                    share(
                      lead.latest.metrics.productionValue,
                      data.crops.totals.productionValue,
                    ),
                    "%",
                  )}{" "}
                  (valor da cultura ÷ total PAM × 100).
                </>
              )}
            </p>
            <ProductTable
              block={data.crops}
              products={ranking}
              columns={[metric]}
              caption="Ranking completo do recorte"
            />
          </>
        ) : (
          <p>
            Nenhum valor numérico disponível para ordenar neste filtro; consulte
            os estados na tabela completa.
          </p>
        )}
        <details>
          <summary>
            Áreas, produção, rendimento e valor de todas as culturas
          </summary>
          <ProductTable
            block={data.crops}
            products={data.crops.products.filter((p) => p.presentInLatest)}
            columns={[
              "plantedOrIntendedArea",
              "harvestedArea",
              "production",
              "yield",
              "productionValue",
            ]}
            caption="Culturas de Turvo"
          />
        </details>
        <p>
          Área plantada (temporárias) e destinada à colheita (permanentes)
          seguem a variável oficial. Área colhida pode ser diferente. Rendimento
          é o publicado pelo IBGE; não representa qualidade do produto.
          Categorias de café que detalham um total são identificadas e excluídas
          do ranking conjunto.
        </p>
        <SourceNote data={data} id="pam" />
      </Section>
      <Section
        id="agri-history"
        title="Uma década de produção agrícola"
        description="Explore as séries disponíveis. Culturas introduzidas recentemente na pesquisa não recebem valores inventados para anos anteriores."
      >
        <HistoryExplorer block={data.crops} label="Cultura do histórico" />
        <SourceNote data={data} id="pam" />
      </Section>
    </>
  );
}
function Content({ data }: { data: AgricultureData }) {
  const value = rankProducts(data.crops, "productionValue").find(
      (p) => p.latest.metrics.productionValue.value !== null,
    ),
    area = rankProducts(data.crops, "harvestedArea").find(
      (p) => p.latest.metrics.harvestedArea.value !== null,
    ),
    production = rankProducts(
      data.crops,
      "production",
      "all",
      "Toneladas",
    ).find((p) => p.latest.metrics.production.value !== null);
  const herd = rankProducts(data.livestock.herds, "herd").find(
    (p) => p.categoryLevel === 0,
  );
  const mate = data.crops.products.find(
      (p) => p.name === "Erva-mate (folha verde)",
    ),
    extract = data.forestry.extraction.products.find(
      (p) => p.categoryId === "3406",
    );
  const census = data.agriculturalCensus;
  return (
    <div className="agriculture-page">
      {data.collection.failures.length > 0 && (
        <div className="notice" role="status">
          A última coleta teve falhas. Esta página preserva o último snapshot
          validado; consulte o relatório no JSON.
        </div>
      )}
      <section className="agri-intro">
        <span className="eyebrow">DO CAMPO AO TERRITÓRIO</span>
        <h2>A produção rural de Turvo</h2>
        <p>{narrative(data)}</p>
        <div className="agri-badges">
          <span>PAM · {data.crops.reference}</span>
          <span>PPM · {data.livestock.herds.reference}</span>
          <span>PEVS · {data.forestry.extraction.reference}</span>
          <span>Censo · {census.reference}</span>
        </div>
      </section>
      <div className="agri-cards">
        {[
          [
            "Valor agrícola · PAM",
            cellText(data.summary.productionValue, true),
            `${data.crops.reference} · Total oficial, nominal; não é PIB`,
          ],
          [
            "Maior valor por cultura",
            value ? shortName(value.name) : "Indisponível",
            value
              ? `${cellText(value.latest.metrics.productionValue, true)} · ${data.crops.reference}`
              : "Sem dado",
          ],
          [
            "Maior área colhida",
            area ? shortName(area.name) : "Indisponível",
            area
              ? `${cellText(area.latest.metrics.harvestedArea)} · ${data.crops.reference}`
              : "Sem dado",
          ],
          [
            "Maior quantidade em toneladas",
            production ? shortName(production.name) : "Indisponível",
            production
              ? `${cellText(production.latest.metrics.production)} · ${data.crops.reference}`
              : "Sem dado",
          ],
          [
            "Maior efetivo de rebanho",
            herd ? shortName(herd.name) : "Indisponível",
            herd
              ? `${cellText(herd.latest.metrics.herd)} · ${data.livestock.herds.reference}`
              : "Sem dado",
          ],
          [
            "Estabelecimentos rurais",
            cellText(census.values.establishments),
            `${census.reference} · Censo, referência estrutural`,
          ],
        ].map(([title, number, note]) => (
          <article key={title}>
            <span>{title}</span>
            <strong>{number}</strong>
            <small>{note}</small>
          </article>
        ))}
      </div>
      <nav className="agri-jump" aria-label="Seções da Agropecuária">
        {[
          ["agri-crops", "Culturas"],
          ["agri-history", "Histórico"],
          ["agri-mate", "Erva-mate"],
          ["agri-livestock", "Pecuária"],
          ["agri-forestry", "Florestas"],
          ["agri-census", "Censo"],
          ["agri-comparison", "Comparação"],
          ["agri-sources", "Fontes"],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() =>
              document
                .getElementById(id)
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            {label}
          </button>
        ))}
      </nav>
      <Crops data={data} />
      <Section
        id="agri-mate"
        title="Erva-mate: cultivo e extração"
        description="São duas pesquisas e formas de produção diferentes. Mantemos os resultados separados."
      >
        <div className="agri-two">
          {[
            [mate, data.crops, "Cultivada · PAM"],
            [extract, data.forestry.extraction, "Extraída · PEVS"],
          ].map(([p, b, label]) => {
            const product = p as typeof mate,
              block = b as ProductBlock;
            return (
              <article key={String(label)}>
                <h3>
                  {String(label)} · {block.reference}
                </h3>
                <p className="agri-big">
                  {cellText(product?.latest.metrics.production)}
                </p>
                <p>
                  Valor nominal:{" "}
                  {cellText(product?.latest.metrics.productionValue)}
                </p>
                {product && (
                  <ProductHistory
                    product={product}
                    metric="production"
                    title={String(label)}
                  />
                )}
                <SourceNote data={data} id={block.sourceId} />
              </article>
            );
          })}
        </div>
        <p>
          Zero divulgado pelo IBGE permanece zero; não substituímos ausência ou
          sigilo por zero. Não somamos cultivo e extração.
        </p>
      </Section>
      <Section
        id="agri-livestock"
        title="Pecuária e produção animal"
        description="Efetivos são contagens de animais, não volumes de produção. Galinhas e matrizes suínas são subgrupos de seus respectivos totais."
      >
        <h3>Rebanhos · {data.livestock.herds.reference}</h3>
        <ProductTable
          block={data.livestock.herds}
          products={data.livestock.herds.products.filter(
            (p) => p.presentInLatest,
          )}
          columns={["herd"]}
          caption="Efetivos dos rebanhos"
        />
        <HistoryExplorer
          block={data.livestock.herds}
          label="Rebanho do histórico"
        />
        <SourceNote data={data} id="herds" />
        <h3>Produtos de origem animal · {data.livestock.products.reference}</h3>
        <p>
          Total de valor publicado:{" "}
          <strong>
            {cellText(data.livestock.products.totals.productionValue)}
          </strong>
          .
        </p>
        <ProductTable
          block={data.livestock.products}
          products={data.livestock.products.products.filter(
            (p) => p.presentInLatest,
          )}
          caption="Produção de origem animal"
        />
        <div className="agri-callout">
          Vacas ordenhadas:{" "}
          <strong>{cellText(data.livestock.milkedCows.latest.metric)}</strong> ·{" "}
          {data.livestock.milkedCows.reference}. Produção anual por vaca
          ordenhada: <strong>{cellText(data.livestock.milkPerCow)}</strong>.
          Indicador derivado: leite em mil litros × 1.000 ÷ vacas ordenhadas, no
          mesmo ano; não equivale à produtividade diária nem a avaliação
          individual dos animais.
        </div>
        <HistoryExplorer
          block={data.livestock.products}
          label="Produto animal do histórico"
        />
        <SourceNote data={data} id="animal" />
        <SourceNote data={data} id="milkedCows" />
        <h3>Aquicultura · {data.livestock.aquaculture.reference}</h3>
        <p>
          Total de valor publicado:{" "}
          <strong>
            {cellText(data.livestock.aquaculture.totals.productionValue)}
          </strong>
          . Totais e espécies não são somados entre si.
        </p>
        <ProductTable
          block={data.livestock.aquaculture}
          products={data.livestock.aquaculture.products.filter(
            (p) => p.presentInLatest,
          )}
          caption="Produtos da aquicultura"
        />
        <HistoryExplorer
          block={data.livestock.aquaculture}
          label="Produto da aquicultura do histórico"
        />
        <SourceNote data={data} id="aquaculture" />
      </Section>
      <Section
        id="agri-forestry"
        title="Silvicultura e extração vegetal"
        description="Madeira de florestas plantadas e produtos da extração vegetal permanecem separados. Unidades variam por produto, inclusive m³, toneladas e mil árvores."
      >
        <div className="agri-two">
          <ForestryBlock
            data={data}
            block={data.forestry.silviculture}
            title="Silvicultura"
          />
          <ForestryBlock
            data={data}
            block={data.forestry.extraction}
            title="Extração vegetal"
          />
        </div>
        <h3>Histórico da silvicultura</h3>
        <HistoryExplorer
          block={data.forestry.silviculture}
          label="Produto da silvicultura do histórico"
        />
        <h3>Histórico da extração vegetal</h3>
        <HistoryExplorer
          block={data.forestry.extraction}
          label="Produto da extração do histórico"
        />
      </Section>
      <Section
        id="agri-census"
        title="Estrutura dos estabelecimentos rurais"
        description={`Censo Agropecuário ${census.reference}: retrato estrutural, separado das pesquisas anuais. Esta é a referência disponível nestas tabelas.`}
      >
        <div className="table-wrap">
          <table>
            <caption>Censo Agropecuário · Turvo · {census.reference}</caption>
            <thead>
              <tr>
                <th>Tipologia</th>
                <th>Estabelecimentos</th>
                <th>Área dos estabelecimentos</th>
                <th>Pessoas ocupadas</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Total", ""],
                ["Agricultura familiar", "family"],
                ["Não familiar", "nonFamily"],
              ].map(([label, prefix]) => (
                <tr key={label}>
                  <th scope="row">{label}</th>
                  {["establishments", "area", "people"].map((k) => (
                    <td key={k}>
                      {cellText(
                        census.values[
                          prefix ? prefix + k[0].toUpperCase() + k.slice(1) : k
                        ],
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="agri-callout">
          Agricultura familiar:{" "}
          <strong>{cellText(census.values.familyShare)}</strong> dos
          estabelecimentos. Cálculo: estabelecimentos familiares ÷ total × 100.
          Tipologia conforme classificação do Censo.
        </p>
        <p>
          {census.note} Pessoas ocupadas no Censo não equivalem a empregos
          formais da RAIS ou admissões do CAGED. Consulte também{" "}
          <a href="#employment">Trabalho e Emprego</a>. Valor da produção anual
          não equivale a VAB; consulte <a href="#economy">Economia/PIB</a>.
        </p>
        {census.sourceIds.map((id) => (
          <SourceNote key={id} data={data} id={id} />
        ))}
      </Section>
      <Comparison data={data} />
      <Methodology data={data} />
    </div>
  );
}
export default function AgriculturePage({
  comparisonOnly = false,
}: {
  comparisonOnly?: boolean;
}) {
  const [data, setData] = useState<AgricultureData>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    setError("");
    setData(undefined);
    loadAgriculture(c.signal)
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => c.abort();
  }, [retry]);
  if (error)
    return (
      <section className="panel" role="alert">
        <h2>Agropecuária não carregou</h2>
        <p>{error}</p>
        <button onClick={() => setRetry((n) => n + 1)}>Tentar novamente</button>
      </section>
    );
  if (!data)
    return (
      <div className="loading" role="status">
        Carregando Agropecuária…
        <div className="skeleton" />
      </div>
    );
  return comparisonOnly ? (
    <div className="agriculture-page">
      <Comparison data={data} />
    </div>
  ) : (
    <Content data={data} />
  );
}
