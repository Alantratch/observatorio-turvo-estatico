import { useState } from "react";
import type { EnvironmentData, Geometry } from "./types";
import { number } from "./data";
function rings(g: Geometry): number[][][] {
  const found: number[][][] = [];
  function visit(v: unknown): void {
    if (!Array.isArray(v)) return;
    if (v.length && Array.isArray(v[0]) && typeof v[0][0] === "number") {
      found.push(v as number[][]);
      return;
    }
    v.forEach(visit);
  }
  visit(g.coordinates);
  return found;
}
export default function EnvironmentMap({ data }: { data: EnvironmentData }) {
  const [layer, setLayer] = useState("stations");
  const outline = data.geometry.features.flatMap((f) => rings(f.geometry));
  const coords = outline.flat();
  const xs = coords.map((p) => p[0]),
    ys = coords.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const middleY = (minY + maxY) / 2;
  const aspect =
    ((maxX - minX) * Math.cos((middleY * Math.PI) / 180)) / (maxY - minY);
  const width = 500;
  const height = width / aspect;
  const project = (lon: number, lat: number) => [
    ((lon - minX) / (maxX - minX)) * width,
    ((maxY - lat) / (maxY - minY)) * height,
  ];
  const path = (g: Geometry) =>
    rings(g)
      .map(
        (r) =>
          "M" + r.map((p) => project(p[0], p[1]).join(",")).join("L") + "Z",
      )
      .join(" ");
  const stations =
    data.water.status === "real"
      ? data.water.stations.filter((s) => s.location === "inside")
      : [];
  const fire = data.fire;
  const currentYear = fire.reference?.slice(0, 4);
  const points =
    fire.status === "real"
      ? fire.points.filter((p) => p.date.slice(0, 4) === currentYear)
      : [];
  const units =
    data.protectedAreas.status === "derived" ? data.protectedAreas.units : [];
  return (
    <figure className="env-map">
      <div className="env-filters">
        <label>
          Camada do mapa
          <select value={layer} onChange={(e) => setLayer(e.target.value)}>
            <option value="stations">
              Estações dentro da malha ({stations.length})
            </option>
            <option value="fire">
              Focos no ano mais recente ({points.length})
            </option>
            <option value="protection">
              Interseções de UCs ({units.length})
            </option>
          </select>
        </label>
      </div>
      <svg
        viewBox={`-15 -15 ${width + 30} ${height + 30}`}
        role="img"
        aria-label="Limite IBGE de Turvo com pontos ou áreas ambientais. Detalhes nas tabelas abaixo."
      >
        {data.geometry.features.map((f, i) => (
          <path
            key={i}
            d={path(f.geometry)}
            fill="#eef2e8"
            stroke="#71816c"
            strokeWidth="1.5"
            fillRule="evenodd"
          />
        ))}
        {layer === "stations" &&
          stations.map((s) => {
            const [x, y] = project(s.longitude, s.latitude);
            return (
              <circle
                key={s.code}
                cx={x}
                cy={y}
                r="5"
                fill={s.type === "Pluviométrica" ? "#3d77a5" : "#25704a"}
              >
                <title>
                  {s.code} · {s.name} · {s.type}
                </title>
              </circle>
            );
          })}
        {layer === "fire" &&
          points.map((p) => {
            const [x, y] = project(p.longitude, p.latitude);
            return (
              <circle
                key={p.id}
                cx={x}
                cy={y}
                r="3"
                fill="#c75c39"
                opacity=".75"
              >
                <title>
                  {p.date} · {p.satellite}
                </title>
              </circle>
            );
          })}
        {layer === "protection" &&
          units.map((u) => (
            <path
              key={u.code}
              d={path(u.geometry)}
              fill="#3e8b5c"
              opacity=".7"
              fillRule="evenodd"
            >
              <title>
                {u.name} · {number(u.intersectionHa)} ha de interseção
                cartográfica
              </title>
            </path>
          ))}
      </svg>
      <figcaption>
        Malha IBGE 2022, qualidade intermediária. Pontos INPE mantêm a
        atribuição municipal da fonte e podem diferir do limite simplificado.
        UCs são interseções cartográficas, não demarcação legal. Não é um mapa
        de cobertura do solo; raster classificado permanece pendente.
      </figcaption>
    </figure>
  );
}
