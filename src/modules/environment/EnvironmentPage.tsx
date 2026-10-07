import { useEffect, useState } from "react";
import { Download, Leaf, ExternalLink } from "lucide-react";
import type { EnvironmentData, Missing, HistoryRow } from "./types";
import { loadEnvironment, number, labels, changes, dataUrl } from "./data";
import EnvironmentMap from "./EnvironmentMap";
import { Bars, History } from "./EnvironmentCharts";
import "./environment.css";
const keys = [
  "native",
  "farmingWithoutPlantation",
  "plantation",
  "urban",
  "water",
] as const;
function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel env-section" id={id}>
      <span className="eyebrow">MEIO AMBIENTE</span>
      <h2>{title}</h2>
      {description && <p className="env-description">{description}</p>}
      {children}
    </section>
  );
}
function Pending({ item }: { item: Missing }) {
  return (
    <div className="env-pending">
      <strong>Não disponível</strong>
      <p>{item.reason}</p>
      <a href={item.url} target="_blank" rel="noreferrer">
        Consultar a fonte <ExternalLink size={12} />
      </a>
    </div>
  );
}
function Source({ data, id }: { data: EnvironmentData; id: string }) {
  const source = data.sources.find((s) => s.id === id);
  return source ? (
    <p className="env-source">
      {source.agency} · {source.dataset}
      {source.collection ? ` · Coleção ${source.collection}` : ""} ·{" "}
      {source.reference}
      <br />
      Coleta:{" "}
      {new Date(source.collectedAt).toLocaleDateString("pt-BR", {
        timeZone: "America/Sao_Paulo",
      })}{" "}
      ·{" "}
      <a href={source.url} target="_blank" rel="noreferrer">
        Dados de origem <ExternalLink size={11} />
      </a>
    </p>
  ) : null;
}
export default function EnvironmentPage() {
  const [data, setData] = useState<EnvironmentData>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0),
    [start, setStart] = useState("2015"),
    [end, setEnd] = useState("2025"),
    [metric, setMetric] = useState<keyof Omit<HistoryRow, "year">>("forest"),
    [fireYear, setFireYear] = useState("2026"),
    [stationFilter, setStationFilter] = useState("all");
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setData(undefined);
    loadEnvironment(controller.signal)
      .then((d) => {
        setData(d);
        if (d.landCover.status === "real") setEnd(d.landCover.reference);
        if (d.fire.status === "real") setFireYear(d.fire.reference.slice(0, 4));
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [retry]);
  if (error)
    return (
      <section className="panel" role="alert">
        <h2>Os dados de Meio Ambiente não carregaram</h2>
        <p>{error}</p>
        <button onClick={() => setRetry((r) => r + 1)}>Tentar novamente</button>
      </section>
    );
  if (!data)
    return (
      <div role="status" className="loading">
        Carregando Meio Ambiente…
        <div className="skeleton" />
      </div>
    );
  const cover = data.landCover;
  if (cover.status !== "real")
    return (
      <section className="panel">
        <h2>Uso e cobertura da terra</h2>
        <Pending item={cover} />
      </section>
    );
  const latest = cover.history.at(-1)!;
  const denom = cover.municipalArea.value * 100;
  const fire = data.fire;
  const water = data.water;
  const protection = data.protectedAreas;
  const selectedFire =
    fire.status === "real"
      ? fire.monthly.filter((r) => r.period.startsWith(fireYear))
      : [];
  const stations =
    water.status === "real"
      ? water.stations.filter(
          (s) => stationFilter === "all" || s.location === stationFilter,
        )
      : [];
  return (
    <div className="env-page">
      <section className="env-intro">
        <div>
          <span className="eyebrow">MEIO AMBIENTE EM NÚMEROS</span>
          <h2>
            O território, suas águas
            <br />e suas transformações.
          </h2>
          <p>
            Quatro dimensões independentes: cobertura da terra, vegetação, fogo
            e recursos hídricos. Cada uma mantém sua fonte e referência.
          </p>
          <span className="env-biome">
            <Leaf size={16} />
            {protection.status === "derived"
              ? protection.biomes.join(" / ")
              : "Bioma não confirmado"}{" "}
            · base IBGE
          </span>
        </div>
        <a className="env-download" href={dataUrl("environment.json")} download>
          <Download size={17} /> Baixar dados de Meio Ambiente
        </a>
      </section>
      <nav className="env-nav" aria-label="Seções de Meio Ambiente">
        {[
          ["env-cover", "Cobertura"],
          ["env-vegetation", "Vegetação"],
          ["env-change", "Mudanças"],
          ["env-fire", "Fogo"],
          ["env-water", "Água"],
          ["env-protection", "Proteção"],
          ["env-comparison", "Comparação"],
          ["env-method", "Fontes"],
        ].map(([id, label]) => (
          <a
            key={id}
            href={`#${id}`}
            onClick={(e) => {
              e.preventDefault();
              document
                .getElementById(id)
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          >
            {label}
          </a>
        ))}
      </nav>
      <div className="env-cards">
        {[
          ["native", "Vegetação nativa"],
          ["farmingWithoutPlantation", "Agropecuária, exceto silvicultura"],
          ["plantation", "Silvicultura"],
        ].map(([key, label]) => (
          <article className="env-card" key={key}>
            <span>{label}</span>
            <strong>
              {number(latest[key as keyof Omit<HistoryRow, "year">], 0)}{" "}
              <small>ha</small>
            </strong>
            <p>
              {number(
                (latest[key as keyof Omit<HistoryRow, "year">] / denom) * 100,
              )}
              % do território · {latest.year}
            </p>
            <small>Derivado · MapBiomas {cover.classes[0].collection}</small>
          </article>
        ))}
        <article className="env-card">
          <span>Focos de calor no ano</span>
          <strong>
            {fire.status === "real" && fire.currentYear
              ? number(fire.currentYear.count, 0)
              : "Não disponível"}
          </strong>
          <p>
            {fire.status === "real" && fire.currentYear
              ? `${fire.currentYear.year} · até ${fire.currentYear.through} (parcial)`
              : "Sem referência atual validada"}
          </p>
          <small>INPE · satélite de referência</small>
        </article>
        <article className="env-card">
          <span>Interseção cartográfica de UCs</span>
          <strong>
            {protection.status === "derived"
              ? `${number(protection.unionAreaHa)} ha`
              : "Não disponível"}
          </strong>
          <p>
            {protection.status === "derived"
              ? `${number(protection.sharePercent, 2)}% · estimativa cartográfica`
              : "Sem dados validados"}
          </p>
          <small>Derivado · CNUC + malha IBGE</small>
        </article>
      </div>
      <Section
        id="env-cover"
        title="Uso e cobertura da terra"
        description={`Coleção ${cover.classes[0].collection} · classificação Landsat 30 m · ${cover.reference}. Classes terminais da legenda oficial, sem somar pais e filhos.`}
      >
        <Bars
          title="Área por classe"
          unit="ha"
          rows={cover.classes
            .filter((c) => c.latest.areaHa > 0)
            .map((c) => ({
              label: c.name.replace(/^[\d.]+\s*/, ""),
              value: c.latest.areaHa,
              color: c.color,
            }))}
        />
        <div className="table-wrap">
          <table>
            <caption>
              Cobertura em {cover.reference} · hectares e percentual derivado
            </caption>
            <thead>
              <tr>
                <th>Classe / código</th>
                <th>Nível</th>
                <th>Área (ha)</th>
                <th>% do município</th>
              </tr>
            </thead>
            <tbody>
              {cover.classes.map((c) => (
                <tr key={c.code}>
                  <th scope="row">
                    <span style={{ color: c.color }}>● </span>
                    {c.name}
                    <small>
                      Código {c.code} · Coleção {c.collection}
                    </small>
                  </th>
                  <td>{c.level}</td>
                  <td>{number(c.latest.areaHa)}</td>
                  <td>{number(c.latest.sharePercent, 2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          Área classificada: {number(cover.mappedAreaHa)} ha. Área territorial
          IBGE {cover.municipalArea.reference}: {number(denom)} ha. Diferença:{" "}
          {number(cover.areaDifferencePercent, 2)}%. {cover.shareMethodology}
        </p>
        <p>
          Na hierarquia MapBiomas, Agropecuária inclui Silvicultura. O card
          “exceto silvicultura” é uma subtração derivada para manter os usos
          separados.
        </p>
        <Source data={data} id="land" />
        <a href={dataUrl("exports/environment-land-cover.csv")} download>
          Baixar CSV de cobertura
        </a>
      </Section>
      <Section
        id="env-vegetation"
        title="Vegetação e florestas"
        description="Formação florestal nativa e floresta plantada são conceitos distintos."
      >
        <div className="env-facts">
          <div>
            <strong>{number(latest.forest, 0)} ha</strong>
            <span>Florestas nativas · {latest.year}</span>
          </div>
          <div>
            <strong>{number(latest.plantation, 0)} ha</strong>
            <span>Silvicultura · {latest.year}</span>
          </div>
          <div>
            <strong>{number(latest.urban, 0)} ha</strong>
            <span>Área urbanizada · {latest.year}</span>
          </div>
          <div>
            <strong>{number(latest.water, 0)} ha</strong>
            <span>Rio, lago e oceano · {latest.year}</span>
          </div>
        </div>
        <p>
          {data.vegetation.status === "derived" && data.vegetation.methodology}
        </p>
        <p>
          Área urbanizada não mede população urbana; área de água não é
          disponibilidade hídrica. A produção econômica florestal permanece em{" "}
          <a href="#agriculture">Agropecuária / PEVS</a>.
        </p>
        <Source data={data} id="land" />
      </Section>
      <Section
        id="env-change"
        title="Como o território mudou"
        description="Comparações dentro da mesma coleção; anos anteriores são reclassificados quando a coleção evolui."
      >
        <History
          rows={cover.history}
          keys={[
            "native",
            "farmingWithoutPlantation",
            "plantation",
            "urban",
            "water",
          ]}
        />
        <div className="env-filters">
          <label>
            De
            <select value={start} onChange={(e) => setStart(e.target.value)}>
              {cover.history.map((r) => (
                <option key={r.year}>{r.year}</option>
              ))}
            </select>
          </label>
          <label>
            Até
            <select value={end} onChange={(e) => setEnd(e.target.value)}>
              {cover.history.map((r) => (
                <option key={r.year}>{r.year}</option>
              ))}
            </select>
          </label>
          <label>
            Cobertura
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as typeof metric)}
            >
              {Object.entries(labels).map(([key, label]) => (
                <option value={key} key={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="env-callout" aria-live="polite">
          {changes(cover, start, end, metric)}
        </p>
        <details>
          <summary>Ver tabela histórica completa</summary>
          <div className="table-wrap">
            <table>
              <caption>
                1985–{cover.reference} · agregados derivados em ha
              </caption>
              <thead>
                <tr>
                  <th>Ano</th>
                  {keys.map((k) => (
                    <th key={k}>{labels[k]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cover.history.map((r) => (
                  <tr key={r.year}>
                    <th scope="row">{r.year}</th>
                    {keys.map((k) => (
                      <td key={k}>{number(r[k])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        <p>
          Mudança de classe não equivale a desmatamento ilegal. Não atribuímos
          causas à variação.
        </p>
      </Section>
      <Section
        id="env-fire"
        title="Fogo e queimadas"
        description="Focos de calor detectados; não uma contagem de incêndios individuais."
      >
        {fire.status === "real" ? (
          <>
            <div className="env-facts">
              <div>
                <strong>{number(fire.currentYear?.count, 0)}</strong>
                <span>
                  {fire.currentYear?.year} · parcial até{" "}
                  {fire.currentYear?.through}
                </span>
              </div>
              <div>
                <strong>{number(fire.previousYear?.count, 0)}</strong>
                <span>
                  {fire.previousYear?.year} ·{" "}
                  {fire.previousYear?.complete
                    ? "ano anterior completo"
                    : "ano anterior parcial"}
                </span>
              </div>
            </div>
            <History
              rows={fire.annual.map((r) => ({ year: r.year, focos: r.count }))}
              keys={["focos"]}
              unit="focos"
            />
            <div className="env-filters">
              <label>
                Focos por mês
                <select
                  value={fireYear}
                  onChange={(e) => setFireYear(e.target.value)}
                >
                  {fire.annual.map((r) => (
                    <option key={r.year}>{r.year}</option>
                  ))}
                </select>
              </label>
            </div>
            <Bars
              title={`Focos por mês · ${fireYear}`}
              unit="focos"
              rows={selectedFire.map((r) => ({
                label: r.period.slice(5),
                value: r.count,
                color: "#c75c39",
              }))}
            />
            <div className="table-wrap">
              <table>
                <caption>Contagens anuais · {fire.satellite}</caption>
                <thead>
                  <tr>
                    <th>Ano</th>
                    <th>Focos</th>
                    <th>Por 1.000 km² (derivado)</th>
                    <th>Cobertura</th>
                  </tr>
                </thead>
                <tbody>
                  {fire.annual.map((r) => (
                    <tr key={r.year}>
                      <th scope="row">{r.year}</th>
                      <td>{r.count}</td>
                      <td>{number(r.per1000Km2, 2)}</td>
                      <td>
                        {r.complete
                          ? "Ano completo"
                          : `Parcial até ${r.through}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary>Valores mensais do gráfico</summary>
              <div className="table-wrap">
                <table>
                  <caption>Focos por mês · {fireYear}</caption>
                  <thead>
                    <tr>
                      <th>Mês</th>
                      <th>Focos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedFire.map((r) => (
                      <tr key={r.period}>
                        <th scope="row">{r.period}</th>
                        <td>{number(r.count, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            <p>{fire.methodology}</p>
            <p>
              <a href={fire.methodologyUrl} target="_blank" rel="noreferrer">
                Metodologia INPE
              </a>{" "}
              ·{" "}
              <a href={dataUrl("exports/environment-fire.csv")} download>
                Baixar CSV de focos
              </a>
            </p>
            <p className="env-source">
              Fonte: INPE · AQUA_M-T · referências e URLs de cada arquivo em
              Fontes e metodologia.
            </p>
          </>
        ) : (
          <Pending item={fire} />
        )}
        <h3>Área queimada e desmatamento</h3>
        <Pending item={data.burnedArea} />
        <Pending item={data.deforestation} />
      </Section>
      <Section
        id="env-water"
        title="Água e recursos hídricos"
        description="Estações dentro de Turvo e referências regionais aparecem separadamente."
      >
        {water.status === "real" ? (
          <>
            <p>{water.methodology}</p>
            <EnvironmentMap data={data} />
            <div className="env-filters">
              <label>
                Localização
                <select
                  value={stationFilter}
                  onChange={(e) => setStationFilter(e.target.value)}
                >
                  <option value="all">Todas as referências</option>
                  <option value="inside">Dentro da malha de Turvo</option>
                  <option value="regional">
                    Fora de Turvo, referência regional
                  </option>
                </select>
              </label>
            </div>
            <div className="table-wrap">
              <table>
                <caption>
                  Inventário ANA · {stations.length} estações no recorte
                </caption>
                <thead>
                  <tr>
                    <th>Estação</th>
                    <th>Tipo / cadastro</th>
                    <th>Localização</th>
                    <th>Rio / bacia</th>
                    <th>Responsável</th>
                  </tr>
                </thead>
                <tbody>
                  {stations.map((s) => (
                    <tr key={s.code}>
                      <th scope="row">
                        {s.name}
                        <small>
                          ANA {s.code} · {s.latitude.toFixed(4)},{" "}
                          {s.longitude.toFixed(4)}
                        </small>
                      </th>
                      <td>
                        {s.type}
                        <small>
                          Operando: {s.operating} · Telemetria: {s.telemetric}
                        </small>
                      </td>
                      <td>
                        {s.location === "inside"
                          ? "Dentro de Turvo"
                          : "Regional · fora de Turvo"}
                        <small>
                          Cadastro: {s.sourceMunicipality} ·{" "}
                          {number(s.distanceToCentroidKm)} km ao centroide
                        </small>
                      </td>
                      <td>
                        {s.river ?? "Não informado"}
                        <small>
                          {s.basin} / {s.subBasin}
                        </small>
                      </td>
                      <td>
                        {s.agency}
                        <small>
                          Atualização cadastral:{" "}
                          {new Date(s.registryUpdatedAt).toLocaleDateString(
                            "pt-BR",
                            { timeZone: "UTC" },
                          )}
                        </small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3>Turvo nas bacias hidrográficas</h3>
            <p>
              As estações consultadas registram as bacias e sub-bacias acima. O
              inventário não substitui a delimitação municipal completa de
              bacias ou uma lista de todos os rios e nascentes.
            </p>
            <h3>Chuva, nível e vazão</h3>
            <Pending item={water.measurements} />
            <Source data={data} id="water" />
            <a href={dataUrl("exports/environment-water.csv")} download>
              Baixar inventário de estações
            </a>
          </>
        ) : (
          <Pending item={water} />
        )}
      </Section>
      <Section
        id="env-protection"
        title="Áreas protegidas"
        description="Unidade de conservação, APP, Reserva Legal e CAR são conceitos distintos."
      >
        {protection.status === "derived" ? (
          <>
            <p>
              {protection.units.length} geometrias de UCs intersectam a malha de
              referência; {protection.declaredMunicipalityCount} delas menciona
              Turvo no cadastro. A diferença é mantida visível, sem reconciliar
              nomes e limites artificialmente.
            </p>
            <p>{protection.methodology}</p>
            <div className="table-wrap">
              <table>
                <caption>
                  CNUC · interseção aproximada, sem somar a área total da UC ao
                  município
                </caption>
                <thead>
                  <tr>
                    <th>Unidade</th>
                    <th>Esfera / grupo</th>
                    <th>Interseção (ha)</th>
                    <th>Cadastro menciona Turvo?</th>
                  </tr>
                </thead>
                <tbody>
                  {protection.units.map((u) => (
                    <tr key={u.code}>
                      <th scope="row">
                        {u.name}
                        <small>
                          {u.code} · {u.agency}
                        </small>
                      </th>
                      <td>
                        {u.sphere} · {u.category}
                        <small>{u.group}</small>
                      </td>
                      <td>{number(u.intersectionHa, 2)}</td>
                      <td>
                        {u.registryMentionsTurvo
                          ? "Sim"
                          : "Não — possível diferença cartográfica"}
                        <small>{u.listedMunicipalities}</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              União das interseções: {number(protection.unionAreaHa, 2)} ha (
              {number(protection.sharePercent, 3)}%). Pequenas faixas junto à
              divisa têm incerteza cartográfica; não usar para delimitar
              direitos ou imóveis.
            </p>
            <p>
              Bioma consultado: {protection.biomes.join(", ")}.{" "}
              {protection.biomeReference}{" "}
              <a
                href={protection.biomeSourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                Base IBGE / IBAMA
              </a>
              .
            </p>
            <Source data={data} id="protection" />
            <a
              href={dataUrl("exports/environment-protected-areas.csv")}
              download
            >
              Baixar CSV de UCs
            </a>
          </>
        ) : (
          <Pending item={protection} />
        )}
      </Section>
      <Section
        id="env-comparison"
        title="Turvo em perspectiva"
        description="Mesma coleção e ano. Percentuais derivados da área territorial IBGE; focos normalizados por 1.000 km²."
      >
        <div className="table-wrap">
          <table>
            <caption>
              Comparação municipal · cobertura {cover.reference}
            </caption>
            <thead>
              <tr>
                <th>Município</th>
                {keys.map((k) => (
                  <th key={k}>{labels[k]} (%)</th>
                ))}
                <th>
                  Focos / 1.000 km² ·{" "}
                  {fire.status === "real"
                    ? fire.reference.slice(0, 4)
                    : "indisponível"}{" "}
                  (parcial)
                </th>
              </tr>
            </thead>
            <tbody>
              {data.comparisons.map((p) => {
                const last = p.landCover.history.at(-1)!;
                const ha = p.landCover.municipalArea.value * 100;
                return (
                  <tr
                    key={p.municipalityCode}
                    className={
                      p.municipalityCode === "4127965" ? "env-own" : ""
                    }
                  >
                    <th scope="row">
                      {p.name}
                      <small>IBGE {p.municipalityCode}</small>
                    </th>
                    {keys.map((k) => (
                      <td key={k}>{number((last[k] / ha) * 100, 2)}%</td>
                    ))}
                    <td>{number(p.fire?.currentYear?.per1000Km2, 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p>
          Percentuais de vegetação e subconjuntos são cálculos do Observatório.
          Não representam uma nota ambiental; tamanho do território, cobertura e
          sensoriamento influenciam a comparação. Área protegida regional ainda
          não foi recortada para os outros municípios.
        </p>
      </Section>
      <Section
        id="env-method"
        title="Fontes e metodologia"
        description="Datas de coleta não são anos de referência. O navegador consulta apenas snapshots locais."
      >
        <details open>
          <summary>Como interpretar os indicadores</summary>
          <p>
            Cobertura da terra é classificação da superfície pela fonte.
            Vegetação nativa exclui silvicultura. Foco de calor é detecção
            térmica por satélite, e não um incêndio individual. Área protegida é
            uma estimativa de interseção com poligonais cadastradas. Indicadores
            calculados aparecem como derivados.
          </p>
          <p>
            Raster de cobertura, área queimada, desmatamento específico da Mata
            Atlântica, telemetria pública, saneamento e resíduos permanecem
            pendentes. Não há dados cadastrais de imóveis rurais.
          </p>
        </details>
        <h3>Clima e medições históricas</h3>
        <Pending item={data.climate} />
        <div className="env-sources">
          {data.sources.map((s) => (
            <details key={s.id}>
              <summary>
                {s.agency} · {s.id} · {s.reference}
              </summary>
              <dl>
                {Object.entries({
                  Dataset: s.dataset,
                  Referência: s.reference,
                  Coleção: s.collection ?? "Não se aplica",
                  Versão: s.version ?? "Conforme arquivo da fonte",
                  Unidade: s.unit,
                  Coleta: s.collectedAt,
                  Transformação:
                    s.transformation ?? "Filtro municipal e validação",
                  Licença: s.license ?? "Conforme órgão de origem",
                  "Código IBGE": "4127965",
                  URL: s.url,
                }).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>
                      {key === "URL" ? (
                        <a href={value} target="_blank" rel="noreferrer">
                          Consultar arquivo/serviço
                        </a>
                      ) : (
                        value
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
        </div>
        <p>
          <a
            href="https://github.com/Alantratch/observatorio-turvo-estatico/blob/main/docs/modulos/meio-ambiente.md"
            target="_blank"
            rel="noreferrer"
          >
            Documentação completa e limites
          </a>
        </p>
      </Section>
    </div>
  );
}
