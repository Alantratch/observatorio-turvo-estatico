import { useState, type ReactNode } from "react";
import { Download, ExternalLink } from "lucide-react";
import type { AgricultureData, ProductBlock, Product } from "./types";
import {
  dataUrl,
  cellText,
  shortName,
  metricLabels,
  format,
  localScope,
  comparable,
  stateShare,
  rankProducts,
} from "./data";
import { AgricultureChart } from "./AgricultureCharts";
export function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="panel agri-section">
      <span className="eyebrow">AGROPECUÁRIA · TURVO / PR</span>
      <h2>{title}</h2>
      {description && <p className="agri-muted">{description}</p>}
      {children}
    </section>
  );
}
export function SourceNote({
  data,
  id,
}: {
  data: AgricultureData;
  id: string;
}) {
  const s = data.sources.find((s) => s.id === id);
  if (!s) return null;
  return (
    <p className="source agri-source">
      <a href={s.officialUrl} target="_blank" rel="noreferrer">
        IBGE · {s.research} · tabela {s.table} <ExternalLink size={11} />
      </a>
      <span>
        Referência: {s.reference} · Coleta:{" "}
        {new Date(s.collectedAt).toLocaleDateString("pt-BR")}
      </span>
    </p>
  );
}
export function ProductTable({
  block,
  products = block.products,
  columns = ["production", "productionValue"],
  caption,
}: {
  block: ProductBlock;
  products?: Product[];
  columns?: string[];
  caption: string;
}) {
  return (
    <div className="table-wrap">
      <table>
        <caption>
          {caption} · {block.reference} · unidades por variável/produto
        </caption>
        <thead>
          <tr>
            <th>Produto / classificação</th>
            {columns.map((c) => (
              <th key={c}>{metricLabels[c] ?? c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <tr key={p.id}>
              <th scope="row">
                {shortName(p.name)}
                <small>
                  {p.kind
                    ? `Lavoura ${p.kind.toLocaleLowerCase("pt-BR")} · `
                    : ""}
                  Categoria {p.categoryId}
                  {p.categoryLevel > 0 && !p.kind
                    ? ` · nível ${p.categoryLevel}`
                    : ""}
                  {p.rankNote && ` · ${p.rankNote}`}
                </small>
              </th>
              {columns.map((c) => (
                <td key={c}>{cellText(p.latest.metrics[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Comparison({ data }: { data: AgricultureData }) {
  const [sector, setSector] = useState("crops"),
    [id, setId] = useState(
      data.summary.leadingCropId ?? data.crops.products[0]?.id ?? "",
    ),
    [metric, setMetric] = useState("production");
  const scopes = [localScope(data), ...data.comparisons];
  const getBlock = (s: (typeof scopes)[number]) =>
    sector === "crops"
      ? s.crops
      : sector === "herds"
        ? s.livestock.herds
        : sector === "animal"
          ? s.livestock.products
          : sector === "aquaculture"
            ? s.livestock.aquaculture
            : sector === "extraction"
              ? s.forestry.extraction
              : s.forestry.silviculture;
  const block = getBlock(scopes[0]),
    products = block.products.filter(
      (p) =>
        p.presentInLatest ||
        (sector === "extraction" && p.categoryId === "3406"),
    ),
    selected = products.find((p) => p.id === id) ?? products[0],
    metricKeys = selected ? Object.keys(selected.latest.metrics) : [],
    metricKey = metricKeys.includes(metric) ? metric : metricKeys[0],
    own = selected?.latest.metrics[metricKey];
  const rows = scopes.map((scope) => {
    const peerBlock = getBlock(scope),
      product = peerBlock.products.find((p) => p.id === selected?.id),
      c = comparable(
        own,
        product?.latest.metrics[metricKey],
        block.reference,
        peerBlock.reference,
      );
    return {
      label: scope.name,
      value: c?.value ?? null,
      c,
      code: scope.municipalityCode,
    };
  });
  const state = rows.find((r) => r.code === "41");
  return (
    <Section
      id="agri-comparison"
      title="Turvo em perspectiva"
      description="Compare o mesmo produto, variável, unidade e ano. Quantidade absoluta e rendimento são dimensões distintas."
    >
      <div className="agri-filters">
        <label>
          Base
          <select value={sector} onChange={(e) => setSector(e.target.value)}>
            {[
              ["crops", "Culturas · PAM"],
              ["herds", "Rebanhos · PPM"],
              ["animal", "Produtos animais · PPM"],
              ["aquaculture", "Aquicultura · PPM"],
              ["silviculture", "Silvicultura · PEVS"],
              ["extraction", "Extração vegetal · PEVS"],
            ].map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Produto comparado
          <select
            value={selected?.id ?? ""}
            onChange={(e) => setId(e.target.value)}
          >
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {shortName(p.name)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Métrica comparada
          <select
            value={metricKey ?? ""}
            onChange={(e) => setMetric(e.target.value)}
          >
            {metricKeys.map((k) => (
              <option key={k} value={k}>
                {metricLabels[k]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {selected && own && (
        <>
          <h3>
            {shortName(selected.name)} · {metricLabels[metricKey]}
          </h3>
          <AgricultureChart
            bars
            rows={rows.filter((r) => r.code !== "41")}
            title={metricLabels[metricKey]}
            unit={own.unit}
            reference={block.reference}
          />
          <div className="table-wrap">
            <table>
              <caption>
                {shortName(selected.name)} · {metricLabels[metricKey]} ·{" "}
                {block.reference} · {own.unit}
              </caption>
              <thead>
                <tr>
                  <th>Território</th>
                  <th>Valor</th>
                  <th>Referência</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    className={r.code === "4127965" ? "agri-highlight" : ""}
                    key={r.code}
                  >
                    <th scope="row">
                      {r.label}
                      <small>{r.code}</small>
                    </th>
                    <td>{cellText(r.c)}</td>
                    <td>{block.reference}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {state?.c &&
            ["production", "productionValue"].includes(metricKey) && (
              <p className="agri-callout" data-status="derived">
                Participação calculada de Turvo no total estadual deste produto:{" "}
                <strong>
                  {format(
                    stateShare(own, state.c, block.reference, block.reference),
                    "%",
                  )}
                </strong>
                . Indicador derivado: valor de Turvo ÷ valor do Paraná × 100.
                Não é participação no PIB.
              </p>
            )}
          <SourceNote data={data} id={block.sourceId} />
        </>
      )}
      <p>
        Os municípios têm dimensões territoriais e estruturas produtivas
        diferentes. Maior quantidade não significa maior rendimento. Não
        calculamos posição estadual sem consultar todos os municípios; os
        gráficos comparam apenas os territórios selecionados.
      </p>
    </Section>
  );
}
export function ProductHistory({
  product,
  metric,
  title,
}: {
  product: Product;
  metric: string;
  title?: string;
}) {
  const unit = product.latest.metrics[metric]?.unit ?? "";
  return (
    <>
      <h3>
        {title ?? shortName(product.name)} · {metricLabels[metric]}
      </h3>
      <p className="agri-muted">
        {product.series[0]?.reference}–{product.latest.reference} · {unit}.
        Lacunas e supressões permanecem sem linha.
      </p>
      <AgricultureChart
        rows={product.series.map((p) => ({
          label: p.reference,
          value: p.metrics[metric]?.value ?? null,
        }))}
        title={metricLabels[metric]}
        unit={unit}
        reference={`${product.series[0]?.reference}–${product.latest.reference}`}
      />
      <details>
        <summary>Ver histórico em tabela acessível</summary>
        <div className="table-wrap">
          <table>
            <caption>
              {shortName(product.name)} · {metricLabels[metric]} · {unit}
            </caption>
            <thead>
              <tr>
                <th>Ano</th>
                <th>Valor</th>
                <th>Variação anual calculada</th>
              </tr>
            </thead>
            <tbody>
              {product.series.map((p) => (
                <tr key={p.reference}>
                  <th scope="row">{p.reference}</th>
                  <td>{cellText(p.metrics[metric])}</td>
                  <td>{format(p.annualChanges[metric], "%")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          Variação = (atual/anterior − 1) × 100; apenas anos consecutivos, mesma
          unidade e base anterior positiva. Valores monetários representam
          variação nominal.
        </p>
      </details>
    </>
  );
}
export function ForestryBlock({
  data,
  block,
  title,
}: {
  data: AgricultureData;
  block: ProductBlock;
  title: string;
}) {
  const products = block.products.filter((p) => p.presentInLatest),
    chartProducts =
      block.sourceId === "silviculture"
        ? products.filter((p) => p.categoryLevel === 1)
        : products.filter(
            (p) =>
              (p.latest.metrics.productionValue.value ?? 0) > 0 &&
              !products.some(
                (q) =>
                  q.id !== p.id &&
                  q.name.startsWith(p.name.split(" - ")[0] + "."),
              ),
          );
  const sorted = [...chartProducts].sort(
    (a, b) =>
      (b.latest.metrics.productionValue.value ?? -1) -
      (a.latest.metrics.productionValue.value ?? -1),
  );
  return (
    <article>
      <h3>
        {title} · {block.reference}
      </h3>
      <p>
        Total de valor publicado na base:{" "}
        <strong>{cellText(block.totals.productionValue)}</strong>. Categorias e
        subcategorias podem se sobrepor; não somamos suas quantidades ou seus
        valores.
      </p>
      {sorted.length > 0 && (
        <>
          <h4>Valor da produção nominal · categorias selecionadas</h4>
          <AgricultureChart
            bars
            title={`Valor · ${title}`}
            rows={sorted.map((p) => ({
              label: shortName(p.name),
              value: p.latest.metrics.productionValue.value,
            }))}
            unit="R$"
            reference={block.reference}
          />
          <details>
            <summary>Ver valores do gráfico em tabela acessível</summary>
            <ProductTable
              block={block}
              products={sorted}
              caption={`Valor da produção · ${title}`}
              columns={["productionValue"]}
            />
          </details>
        </>
      )}
      <ProductTable block={block} products={products} caption={title} />
      {!products.length && (
        <p>Nenhuma produção positiva divulgada neste recorte.</p>
      )}
      <SourceNote data={data} id={block.sourceId} />
    </article>
  );
}
export function Methodology({ data }: { data: AgricultureData }) {
  return (
    <Section
      id="agri-sources"
      title="Fontes e metodologia"
      description="Valores oficiais e cálculos do Observatório permanecem identificados, com referências independentes."
    >
      <div className="agri-downloads">
        {[
          ["agriculture.json", "Snapshot completo"],
          ["exports/agriculture-crops.csv", "Culturas · CSV"],
          ["exports/agriculture-livestock.csv", "Pecuária · CSV"],
          ["exports/agriculture-forestry.csv", "PEVS · CSV"],
          ["exports/agriculture-census.csv", "Censo · CSV"],
        ].map(([file, label]) => (
          <a key={file} href={dataUrl(file)} download>
            <Download size={14} />
            {label}
          </a>
        ))}
      </div>
      <div className="agri-two">
        <article>
          <h3>Unidades, sigilo e revisões</h3>
          <p>
            “−” é zero absoluto; X é valor inibido; “..” não se aplica; “...”
            não está disponível. Valores ocultos não são estimados. Mil reais
            são convertidos para R$ nominal. Abacaxi e coco-da-baía usam mil
            frutos e frutos/ha conforme notas oficiais PAM; ovos permanecem em
            mil dúzias e leite em mil litros.
          </p>
          <p>
            O IBGE pode revisar anos anteriores. A coleta mensal verifica toda a
            janela histórica, preservando a data de coleta de fontes idênticas.
            Falhas mantêm a última entrega válida.
          </p>
        </article>
        <article>
          <h3>Conceitos que permanecem distintos</h3>
          <p>
            Valor da produção não é PIB nem VAB. Área plantada/destinada e área
            colhida são diferentes; uma área pode ter culturas sucessivas no
            mesmo ano, portanto hectares colhidos não são área territorial
            única. O ano PAM é o ano informado pelo IBGE, sem renomear para
            safra.
          </p>
          <p>
            Erva-mate cultivada e extraída não são somadas. Rebanho não é
            produção animal; subgrupos não são adicionados ao total. Censo
            Agropecuário estrutural não é uma pesquisa anual nem RAIS.
          </p>
        </article>
      </div>
      {data.sources.map((s) => (
        <details key={s.id} className="agri-source-detail">
          <summary>
            {s.research} · tabela {s.table} · referência {s.reference}
          </summary>
          <p>{s.title}</p>
          <dl>
            {Object.entries({
              Órgão: s.agency,
              Referência: s.reference,
              "Histórico coletado": s.periods.join(", "),
              Coleta: s.collectedAt,
              Territórios:
                "Turvo 4127965, Guarapuava 4109401, Pitanga 4119608, Laranjal 4113254 e Paraná 41",
              Transformações: s.transformations.join(" "),
            }).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          <p>
            Variáveis:{" "}
            {s.variables
              .map((v) => `${v.id} — ${v.nome} (${v.unidade})`)
              .join("; ")}
            .
          </p>
          <p>
            Classificações:{" "}
            {s.classifications.map((c) => c.id).join(", ") ||
              "sem classificação adicional"}
            ; produto/categoria preservados nos dados.
          </p>
          <a href={s.officialUrl} target="_blank" rel="noreferrer">
            Tabela SIDRA
          </a>{" "}
          ·{" "}
          <a href={s.metadataUrl} target="_blank" rel="noreferrer">
            Metadados
          </a>{" "}
          ·{" "}
          <a href={s.url} target="_blank" rel="noreferrer">
            Consulta utilizada
          </a>{" "}
          ·{" "}
          <a href={dataUrl(`agriculture/raw/${s.id}.json`)} download>
            Resposta para auditoria
          </a>
        </details>
      ))}
      <details>
        <summary>Qualidade e limites da integração</summary>
        <p>{data.quality.yieldCheck}</p>
        {data.quality.warnings.length ? (
          data.quality.warnings.map((r, i) => (
            <p key={i}>
              {r.product} · {r.reference}: {r.message}
            </p>
          ))
        ) : (
          <p>
            Nenhuma divergência acima da tolerância encontrada nas séries de
            rendimento coletadas de Turvo.
          </p>
        )}
        <p>
          Próximas etapas: condição do produtor, uso das terras, irrigação e
          máquinas no Censo; ranking estadual com todos os municípios e
          acompanhamento conjuntural LSPA claramente separado da PAM
          consolidada. Não atribuímos causas a variações nem avaliamos a
          qualidade da produção.
        </p>
      </details>
      <p>
        MCP Brasil foi referência de descoberta técnica. A fonte estatística é o
        IBGE; o navegador consulta apenas arquivos estáticos do projeto.
      </p>
    </Section>
  );
}
