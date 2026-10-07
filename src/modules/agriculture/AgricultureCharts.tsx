import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Cell,
} from "recharts";
import { format } from "./data";
export interface ChartRow {
  label: string;
  value: number | null;
}
export function AgricultureChart({
  rows,
  title,
  unit,
  reference,
  bars = false,
}: {
  rows: ChartRow[];
  title: string;
  unit: string;
  reference: string;
  bars?: boolean;
}) {
  const available = rows.some((r) => r.value !== null);
  if (!available)
    return (
      <p>
        Nenhum valor divulgado neste recorte. Consulte a tabela de estados dos
        dados.
      </p>
    );
  return (
    <div
      className={bars ? "agri-chart agri-bar-chart" : "agri-chart"}
      style={
        bars ? { height: Math.max(230, rows.length * 35 + 65) } : undefined
      }
      role="img"
      aria-label={`${title} · ${reference} · ${unit}. Valores completos na tabela alternativa.`}
    >
      <ResponsiveContainer width="100%" height="100%">
        {bars ? (
          <BarChart
            data={rows.filter((r) => r.value !== null)}
            layout="vertical"
            margin={{ left: 0, right: 24, top: 12, bottom: 12 }}
          >
            <CartesianGrid horizontal={false} stroke="#e0e9df" />
            <XAxis
              type="number"
              tickFormatter={(v) => format(Number(v), "", true)}
              tick={{ fontSize: 10 }}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={135}
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              formatter={(v) => format(Number(v), unit)}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Bar
              dataKey="value"
              name={title}
              radius={[0, 4, 4, 0]}
              barSize={20}
              isAnimationActive={false}
            >
              {rows.map((r, i) => (
                <Cell key={r.label} fill={i === 0 ? "#2c6950" : "#83a18a"} />
              ))}
            </Bar>
          </BarChart>
        ) : (
          <LineChart
            data={rows}
            margin={{ left: 4, right: 18, top: 12, bottom: 12 }}
          >
            <CartesianGrid vertical={false} stroke="#e0e9df" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis
              width={75}
              tickFormatter={(v) => format(Number(v), "", true)}
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              formatter={(v) =>
                v == null ? "Não disponível" : format(Number(v), unit)
              }
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Line
              name={title}
              dataKey="value"
              type="linear"
              stroke="#2c6950"
              strokeWidth={2.5}
              dot={{ r: 4 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
