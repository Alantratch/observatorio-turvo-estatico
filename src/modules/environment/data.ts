import type { EnvironmentData, HistoryRow, LandCover } from "./types";
export const labels: Record<string, string> = {
  native: "Vegetação nativa",
  forest: "Formação florestal e demais florestas nativas",
  farming: "Agropecuária (inclui silvicultura)",
  farmingWithoutPlantation: "Agropecuária, exceto silvicultura",
  plantation: "Silvicultura",
  urban: "Área urbanizada",
  water: "Rio, lago e oceano",
  pasture: "Pastagem",
  agriculture: "Agricultura",
};
export const colors: Record<string, string> = {
  native: "#25704a",
  forest: "#1f8d49",
  farmingWithoutPlantation: "#b49a41",
  plantation: "#7a5900",
  urban: "#c85652",
  water: "#3d77a5",
};
export function number(value: number | null | undefined, digits = 1) {
  return value == null
    ? "Não disponível"
    : value.toLocaleString("pt-BR", { maximumFractionDigits: digits });
}
export function dataUrl(name: string) {
  return `${import.meta.env.BASE_URL}data/${name}`;
}
export function parseEnvironment(raw: unknown): EnvironmentData {
  const d = raw as EnvironmentData;
  if (
    !d ||
    d.schemaVersion !== 1 ||
    d.municipality?.code !== "4127965" ||
    d.municipality?.state !== "PR" ||
    !Array.isArray(d.sources) ||
    !Array.isArray(d.comparisons)
  )
    throw new Error(
      "Arquivo de Meio Ambiente incompatível ou município incorreto.",
    );
  if (!d.landCover || !d.fire || !d.water || !d.protectedAreas)
    throw new Error("Snapshot ambiental incompleto.");
  for (const block of [
    d.landCover,
    d.fire,
    d.water,
    d.protectedAreas,
    d.climate,
    d.burnedArea,
    d.deforestation,
  ]) {
    if (
      !block ||
      !["real", "derived", "unavailable"].includes(block.status) ||
      (block.status === "unavailable" && block.value !== null)
    )
      throw new Error("Estado ambiental inválido.");
  }
  if (
    d.landCover.status === "real" &&
    (!d.landCover.classes.length ||
      d.landCover.classes.some(
        (c) =>
          !Number.isFinite(c.latest.areaHa) ||
          c.latest.areaHa < 0 ||
          !Number.isFinite(c.latest.sharePercent) ||
          !c.name ||
          !c.collection,
      ))
  )
    throw new Error("Cobertura da terra inválida.");
  if (
    d.fire.status === "real" &&
    d.fire.monthly.some(
      (r) =>
        r.available !== (r.count !== null) ||
        (r.count !== null && (!Number.isInteger(r.count) || r.count < 0)),
    )
  )
    throw new Error("Contagem de focos inválida.");
  return d;
}
export async function loadEnvironment(signal?: AbortSignal) {
  const response = await fetch(dataUrl("environment.json"), { signal });
  if (!response.ok)
    throw new Error(
      `Dados de Meio Ambiente indisponíveis (${response.status}).`,
    );
  return parseEnvironment(await response.json());
}
export function changes(
  cover: LandCover,
  start: string,
  end: string,
  key: keyof Omit<HistoryRow, "year">,
) {
  const a = cover.history.find((r) => r.year === start),
    b = cover.history.find((r) => r.year === end);
  if (!a || !b || start >= end)
    return "Escolha dois anos em ordem cronológica.";
  const delta = b[key] - a[key];
  return `Entre ${start} e ${end}, ${labels[key].toLocaleLowerCase("pt-BR")} ${delta < 0 ? "diminuiu" : "aumentou"} ${number(Math.abs(delta))} hectares (${number(a[key])} → ${number(b[key])} ha), na mesma coleção. Essa mudança de cobertura não identifica causas ou legalidade.`;
}
