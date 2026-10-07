import {
  BarChart,
  Bar,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from "recharts";
import { number, colors, labels } from "./data";
export function Bars({
  rows,
  title,
  unit,
}: {
  rows: { label: string; value: number | null; color?: string }[];
  title: string;
  unit: string;
}) {
  const horizontal = rows.some((r) => r.label.length > 15);
  return (
    <div
      className="env-chart"
      style={horizontal ? { height: rows.length * 36 + 60 } : undefined}
      role="img"
      aria-label={`${title}. Valores na tabela alternativa.`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{ left: 4, right: 12, bottom: 15 }}
        >
          <CartesianGrid vertical={false} stroke="#e1e8df" />
          {horizontal ? (
            <>
              <XAxis
                type="number"
                tickFormatter={(v) => number(Number(v), 0)}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={140}
                tick={{ fontSize: 10 }}
                tickFormatter={(v) =>
                  String(v).length > 23
                    ? String(v).slice(0, 22) + "…"
                    : String(v)
                }
                interval={0}
              />
            </>
          ) : (
            <>
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
              <YAxis tickFormatter={(v) => number(Number(v), 0)} width={55} />
            </>
          )}
          <Tooltip formatter={(v) => [`${number(Number(v))} ${unit}`, title]} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {rows.map((r, i) => (
              <Cell key={i} fill={r.color ?? "#368367"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function History({
  rows,
  keys,
  unit = "ha",
}: {
  rows: Record<string, string | number>[];
  keys: string[];
  unit?: string;
}) {
  return (
    <div
      className="env-chart"
      role="img"
      aria-label={`Evolução anual em ${unit}. Valores na tabela alternativa.`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ left: 4, right: 15 }}>
          <CartesianGrid vertical={false} stroke="#e1e8df" />
          <XAxis dataKey="year" tick={{ fontSize: 11 }} />
          <YAxis width={65} tickFormatter={(v) => number(Number(v), 0)} />
          <Tooltip formatter={(v) => `${number(Number(v))} ${unit}`} />
          <Legend />
          {keys.map((k) => (
            <Line
              key={k}
              dataKey={k}
              name={labels[k] ?? k}
              stroke={colors[k] ?? "#c75c39"}
              dot={false}
              strokeWidth={2.5}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
