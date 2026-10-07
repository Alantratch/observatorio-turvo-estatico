import type {
  AgricultureData,
  Metric,
  Product,
  ProductBlock,
  Scope,
} from "./types";
export const metricLabels: Record<string, string> = {
  production: "Quantidade produzida",
  productionValue: "Valor da produção nominal",
  plantedOrIntendedArea: "Área plantada / destinada à colheita",
  harvestedArea: "Área colhida",
  yield: "Rendimento médio",
  herd: "Efetivo do rebanho",
};
export const units: Record<string, string> = {
  Toneladas: "t",
  Hectares: "ha",
  "Quilogramas por Hectare": "kg/ha",
  "Frutos por Hectare": "frutos/ha",
  Quilogramas: "kg",
  "Metros cúbicos": "m³",
  Cabeças: "cabeças",
  Unidades: "estabelecimentos",
  "Mil litros": "mil litros",
  "Mil dúzias": "mil dúzias",
  "Mil frutos": "mil frutos",
  "Mil árvores": "mil árvores",
  Pessoas: "pessoas",
};
export const dataUrl = (file: string) =>
  `${import.meta.env.BASE_URL}data/${file}`;
export const shortName = (s: string) => s.replace(/^\d+(?:\.\d+)*\s*-\s*/, "");
export function format(
  value: number | null | undefined,
  unit = "",
  compact = false,
) {
  if (value == null) return "Não disponível";
  if (unit === "R$")
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: compact ? 1 : 0,
      ...(compact ? { notation: "compact" as const } : {}),
    }).format(value);
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: unit === "%" ? 2 : unit.includes("por vaca") ? 1 : 0, ...(compact ? { notation: "compact" as const } : {}) }).format(value)}${unit === "%" ? "%" : unit ? " " + (units[unit] ?? unit) : ""}`;
}
export function cellText(c: Metric | undefined, compact = false) {
  if (!c) return "Não disponível";
  if (c.status === "suppressed") return "Suprimido (X)";
  if (c.status === "notApplicable") return "Não se aplica (..)";
  if (c.status === "unavailable") return "Não disponível (...)";
  return format(c.value, c.unit, compact);
}
export function rankProducts(
  block: ProductBlock,
  metric: string,
  kind = "all",
  unit?: string,
) {
  return block.products
    .filter(
      (p) =>
        p.presentInLatest &&
        p.rankEligible &&
        (kind === "all" || p.kind === kind) &&
        p.latest.metrics[metric] &&
        (!unit || p.latest.metrics[metric].unit === unit),
    )
    .sort(
      (a, b) =>
        (b.latest.metrics[metric]?.value ?? -1) -
          (a.latest.metrics[metric]?.value ?? -1) ||
        a.name.localeCompare(b.name, "pt-BR"),
    );
}
export function share(product: Metric, total: Metric) {
  return product.value != null &&
    total.value != null &&
    total.value > 0 &&
    product.unit === total.unit
    ? (product.value / total.value) * 100
    : null;
}
export function comparable(
  local: Metric | undefined,
  peer: Metric | undefined,
  year: string,
  peerYear: string,
) {
  return local && peer && local.unit === peer.unit && year === peerYear
    ? peer
    : undefined;
}
export function stateShare(
  local: Metric,
  state: Metric,
  year: string,
  stateYear: string,
) {
  const value = comparable(local, state, year, stateYear);
  return local.value != null && value?.value != null && value.value > 0
    ? (local.value / value.value) * 100
    : null;
}
export function variationText(p: Product, metric: string) {
  const current = p.latest.metrics[metric],
    change = p.latest.annualChanges[metric];
  if (change == null)
    return "Variação anual não calculada: base zero/ausente, unidade distinta ou falta de ano anterior.";
  return `${metricLabels[metric]} de ${shortName(p.name)} ${current.unit === "R$" ? "apresentou variação nominal" : "variou"} ${format(change, "%")} em ${p.latest.reference}, em relação a ${Number(p.latest.reference) - 1}.`;
}
export function narrative(data: AgricultureData) {
  const leading = rankProducts(data.crops, "productionValue").find(
    (p) => p.latest.metrics.productionValue.value !== null,
  );
  return leading
    ? `Em ${data.crops.reference}, ${shortName(leading.name)} teve o maior valor da produção agrícola registrado em Turvo: ${cellText(leading.latest.metrics.productionValue)}. Sua área colhida foi ${cellText(leading.latest.metrics.harvestedArea)}, com rendimento médio de ${cellText(leading.latest.metrics.yield)}. Os valores monetários são nominais e não representam PIB ou VAB.`
    : "Não há valores divulgados suficientes para identificar a cultura de maior valor.";
}
export function localScope(data: AgricultureData): Scope {
  return {
    municipalityCode: "4127965",
    name: "Turvo",
    state: "PR",
    crops: data.crops,
    livestock: data.livestock,
    forestry: data.forestry,
    agriculturalCensus: data.agriculturalCensus,
  };
}
export function validate(data: AgricultureData): AgricultureData {
  const fail = () => {
    throw Error(
      "Arquivo de Agropecuária incompatível ou com dados inválidos para Turvo/PR.",
    );
  };
  if (
    data?.schemaVersion !== 1 ||
    data?.municipality?.code !== "4127965" ||
    data?.municipality?.state !== "PR" ||
    !Array.isArray(data.sources) ||
    !Array.isArray(data.comparisons) ||
    !Array.isArray(data.collection?.failures) ||
    !Array.isArray(data.crops?.products) ||
    !data.livestock ||
    !data.forestry ||
    !data.agriculturalCensus
  )
    fail();
  const sourceIds = new Set(data.sources.map((s) => s.id));
  if (
    sourceIds.size !== 9 ||
    data.sources.length !== 9 ||
    data.sources.some(
      (s) =>
        s.agency !== "IBGE" ||
        !s.url.startsWith(
          "https://servicodados.ibge.gov.br/api/v3/agregados/",
        ) ||
        !/^\d{4}$/.test(s.reference) ||
        !s.collectedAt,
    )
  )
    fail();
  const codes = ["4127965", "4109401", "4119608", "4113254", "41"];
  function walk(v: unknown) {
    if (Array.isArray(v)) {
      v.forEach(walk);
      return;
    }
    if (v && typeof v === "object") {
      const r = v as Record<string, unknown>;
      if ("value" in r && "status" in r) {
        const status = String(r.status),
          value = r.value;
        if (
          ![
            "real",
            "derived",
            "suppressed",
            "notApplicable",
            "unavailable",
          ].includes(status) ||
          !r.unit
        )
          fail();
        if (
          ["real", "derived"].includes(status) &&
          (typeof value !== "number" ||
            !Number.isFinite(value) ||
            (value < 0 && r.unit !== "%"))
        )
          fail();
        if (
          ["suppressed", "notApplicable", "unavailable"].includes(status) &&
          value !== null
        )
          fail();
        if (
          ["Cabeças", "Pessoas", "Unidades"].includes(String(r.unit)) &&
          typeof value === "number" &&
          !Number.isInteger(value)
        )
          fail();
        if (
          r.sourceId &&
          r.variableId &&
          !data.sources
            .find((s) => s.id === r.sourceId)
            ?.variables.some((v) => String(v.id) === r.variableId)
        )
          fail();
        if (
          ["X", "..", "..."].includes(String(r.rawSymbol)) &&
          status !==
            (
              {
                X: "suppressed",
                "..": "notApplicable",
                "...": "unavailable",
              } as Record<string, string>
            )[String(r.rawSymbol)]
        )
          fail();
        if (
          (status === "suppressed" && r.rawSymbol !== "X") ||
          (status === "derived" && !r.formula) ||
          (r.sourceId && !sourceIds.has(String(r.sourceId)))
        )
          fail();
      }
      if (
        "municipalityCode" in r &&
        !codes.includes(String(r.municipalityCode))
      )
        fail();
      if (
        "reference" in r &&
        r.reference !== null &&
        !/^\d{4}$/.test(String(r.reference))
      )
        fail();
      Object.values(r).forEach(walk);
    }
  }
  walk(data);
  if (
    new Set(data.comparisons.map((r) => r.municipalityCode)).size !== 4 ||
    data.comparisons.some(
      (r) => r.municipalityCode === "4127965" || r.state !== "PR",
    )
  )
    fail();
  for (const scope of [localScope(data), ...data.comparisons]) {
    for (const block of [
      scope.crops,
      scope.livestock.herds,
      scope.livestock.products,
      scope.livestock.aquaculture,
      ...Object.values(scope.forestry),
    ]) {
      if (
        !Array.isArray(block.products) ||
        block.status !== "real" ||
        block.reference !==
          data.sources.find((s) => s.id === block.sourceId)?.reference
      )
        fail();
      const ids = new Set<string>();
      for (const p of block.products) {
        if (
          ids.has(p.id) ||
          p.sourceId !== block.sourceId ||
          p.latest.reference !== block.reference ||
          !Array.isArray(p.series)
        )
          fail();
        ids.add(p.id);
        const periods = p.series.map((r) => r.reference);
        if (
          new Set(periods).size !== periods.length ||
          periods.join() !== [...periods].sort().join() ||
          (p.series.length &&
            JSON.stringify(p.latest) !== JSON.stringify(p.series.at(-1)))
        )
          fail();
        for (const point of [p.latest, ...p.series])
          if (
            !data.sources
              .find((s) => s.id === p.sourceId)
              ?.periods.includes(point.reference) ||
            Object.values(point.annualChanges).some(
              (v) =>
                v !== null && (typeof v !== "number" || !Number.isFinite(v)),
            )
          )
            fail();
        for (const c of Object.values(p.latest.metrics))
          if (c.unit === "R$" && c.originalUnit !== "Mil Reais") fail();
      }
    }
    const census = scope.agriculturalCensus,
      v = census.values;
    if (
      census.reference !==
        data.sources.find((s) => s.id === "census")?.reference ||
      census.reference !==
        data.sources.find((s) => s.id === "censusPeople")?.reference
    )
      fail();
    const family = v.familyEstablishments.value,
      total = v.establishments.value;
    if (
      v.familyShare.value !==
      (family !== null && total ? (family / total) * 100 : null)
    )
      fail();
    const milk = scope.livestock.products.products.find(
        (p) => p.categoryId === "2682",
      ),
      cows = scope.livestock.milkedCows;
    const quantity = milk?.latest.metrics.production;
    const expected =
      milk &&
      milk.latest.reference === cows.reference &&
      quantity?.unit === "Mil litros" &&
      quantity.value !== null &&
      cows.latest.metric.value
        ? (quantity.value * 1000) / cows.latest.metric.value
        : null;
    if (scope.livestock.milkPerCow.value !== expected) fail();
  }
  const ranked = rankProducts(data.crops, "productionValue").filter(
    (p) => p.latest.metrics.productionValue.value !== null,
  );
  if (
    data.summary.leadingCropId !== (ranked[0]?.id ?? null) ||
    data.summary.cropCount !==
      data.crops.products.filter((p) => p.presentInLatest && p.rankEligible)
        .length ||
    JSON.stringify(data.summary.productionValue) !==
      JSON.stringify(data.crops.totals.productionValue)
  )
    fail();
  if (JSON.stringify(data).includes('"mock"')) fail();
  return data;
}
export async function loadAgriculture(signal?: AbortSignal) {
  const r = await fetch(dataUrl("agriculture.json"), { signal });
  if (!r.ok)
    throw Error("Não foi possível carregar o snapshot de Agropecuária.");
  return validate(await r.json());
}
