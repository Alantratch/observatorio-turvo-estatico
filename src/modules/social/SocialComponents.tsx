import { useId, useState, type ReactNode } from "react";
import { ArrowDownToLine, ExternalLink } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  ReferenceLine,
} from "recharts";
import type { SocialMetric } from "./types";
import { cell, number, reference } from "./data";
export function Section({
  id,
  kicker,
  title,
  note,
  children,
}: {
  id: string;
  kicker: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel social-section" id={id}>
      <span className="eyebrow">{kicker}</span>
      <h2>{title}</h2>
      {note && <p className="social-intro">{note}</p>}
      {children}
    </section>
  );
}
export function Metadata({ metric }: { metric: SocialMetric }) {
  return (
    <details className="social-meta">
      <summary>Fonte e metodologia</summary>
      <dl>
        {Object.entries({
          Órgão: metric.agency,
          Base: metric.base,
          Indicador: metric.indicator,
          Referência: reference(metric.reference),
          Unidade: metric.unit,
          Território: metric.municipalityCode,
          Coleta: new Date(metric.collectedAt).toLocaleDateString("pt-BR", {
            timeZone: "UTC",
          }),
          Transformação: metric.transformation,
          Observação: metric.note,
        }).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <a href={metric.url} target="_blank" rel="noreferrer">
        Consultar fonte oficial <ExternalLink size={12} />
      </a>
      {metric.denominatorUrl && (
        <p>
          <a href={metric.denominatorUrl} target="_blank" rel="noreferrer">
            Denominador IBGE ({metric.denominatorReference})
          </a>
        </p>
      )}
    </details>
  );
}
export function MetricCard({
  metric,
  title,
}: {
  metric: SocialMetric;
  title: string;
}) {
  return (
    <article className="social-card">
      <span className={`social-status ${metric.status}`}>
        {metric.status === "real"
          ? "Dado oficial"
          : metric.status === "derived"
            ? "Cálculo do Observatório"
            : metric.status === "suppressed"
              ? "Dado protegido"
              : "Indisponível"}
      </span>
      <h3>{title}</h3>
      <strong>{cell(metric)}</strong>
      {metric.unit !== "R$" && metric.unit !== "%" && (
        <span className="social-unit">{metric.unit}</span>
      )}
      <p className="source">Referência: {reference(metric.reference)}</p>
      <Metadata metric={metric} />
    </article>
  );
}
export function MetricTable({
  rows,
}: {
  rows: { label: string; metric: SocialMetric }[];
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Indicador</th>
            <th>Valor</th>
            <th>Unidade</th>
            <th>Referência</th>
            <th>Fonte</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ label, metric }, i) => (
            <tr key={i}>
              <th scope="row">{label}</th>
              <td>{cell(metric)}</td>
              <td>{metric.unit}</td>
              <td>{reference(metric.reference)}</td>
              <td>
                <a href={metric.url} target="_blank" rel="noreferrer">
                  {metric.base}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Trend({
  points,
  title,
  unit,
  breakAt,
}: {
  points: { reference: string; metric: SocialMetric }[];
  title: string;
  unit: string;
  breakAt?: string;
}) {
  const [table, setTable] = useState(false);
  const id = useId();
  // A marked administrative transition must not be joined by a continuous line.
  const rows = points.map((p) => ({
    reference: p.reference,
    value: breakAt === p.reference ? null : p.metric.value,
  }));
  const present = points.some((p) => p.metric.value !== null);
  return (
    <div className="social-chart">
      <h3>{title}</h3>
      <span className="social-chart-unit">{unit} · referências mensais</span>
      {present ? (
        <div
          role="img"
          aria-label={`${title}. Série mensal em ${unit}. Tabela acessível disponível abaixo.`}
          className="social-chart-canvas"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={rows}
              margin={{ left: 10, right: 18, top: 12, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 4" vertical={false} />
              <XAxis
                dataKey="reference"
                tickFormatter={(p) =>
                  `${String(p).slice(4)}/${String(p).slice(2, 4)}`
                }
                minTickGap={35}
              />
              <YAxis
                tickFormatter={(v) =>
                  unit === "R$" ? `${Number(v) / 1000} mil` : number(v)
                }
                width={76}
                domain={["auto", "auto"]}
              />
              <Tooltip
                labelFormatter={(p) => reference(String(p))}
                formatter={(v) => [number(Number(v), unit), title]}
              />
              <Line
                type="linear"
                dataKey="value"
                stroke="#26735a"
                strokeWidth={2.5}
                dot={false}
                connectNulls={false}
              />
              {breakAt && (
                <ReferenceLine
                  x={breakAt}
                  stroke="#b77838"
                  strokeDasharray="4 4"
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="notice">Série indisponível nesta publicação.</p>
      )}
      <button
        className="social-table-toggle"
        onClick={() => setTable(!table)}
        aria-expanded={table}
        aria-controls={id}
      >
        {table ? "Ocultar" : "Ver"} tabela do histórico
      </button>
      {table && (
        <div id={id}>
          <MetricTable
            rows={points.map((p) => ({ label: title, metric: p.metric }))}
          />
        </div>
      )}
      {breakAt && (
        <p className="source">
          Quebra administrativa assinalada em {reference(breakAt)}. O ponto
          permanece na tabela; o gráfico interrompe a linha.
        </p>
      )}
    </div>
  );
}
export function Bars({
  rows,
  title,
  unit,
}: {
  rows: { label: string; metric: SocialMetric }[];
  title: string;
  unit: string;
}) {
  return (
    <div className="social-chart">
      <h3>{title}</h3>
      <div
        className="social-chart-canvas social-bars"
        role="img"
        aria-label={`${title}, em ${unit}. Valores na tabela abaixo.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows.map((r) => ({ label: r.label, value: r.metric.value }))}
            layout="vertical"
            margin={{ left: 0, right: 20 }}
          >
            <CartesianGrid strokeDasharray="3 4" horizontal={false} />
            <XAxis type="number" tickFormatter={(v) => number(v)} />
            <YAxis
              type="category"
              dataKey="label"
              width={165}
              tick={{ fontSize: 11 }}
            />
            <Tooltip formatter={(v) => [number(Number(v), unit), unit]} />
            <Bar dataKey="value" fill="#26735a" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <MetricTable rows={rows} />
    </div>
  );
}
export function Downloads() {
  return (
    <div className="social-downloads">
      <a href={`${import.meta.env.BASE_URL}data/social.json`} download>
        <ArrowDownToLine size={16} /> Baixar dados de Assistência Social (JSON)
      </a>
      {["cadunico", "bolsa-familia", "bpc", "suas", "services"].map((k) => (
        <a
          key={k}
          href={`${import.meta.env.BASE_URL}data/exports/social-${k}.csv`}
          download
        >
          CSV ·{" "}
          {{
            cadunico: "Cadastro Único",
            "bolsa-familia": "Bolsa Família",
            bpc: "BPC",
            suas: "Rede SUAS",
            services: "PAIF",
          }[k as "cadunico" | "bolsa-familia" | "bpc" | "suas" | "services"] ??
            k}
        </a>
      ))}
    </div>
  );
}
