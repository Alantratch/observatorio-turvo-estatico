import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(
  new URL("../src/modules/agriculture/data.ts", import.meta.url),
  "utf8",
).replaceAll("import.meta.env.BASE_URL", JSON.stringify("/"));
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const {
  validate,
  loadAgriculture,
  rankProducts,
  cellText,
  narrative,
  share,
  stateShare,
  comparable,
  variationText,
  dataUrl,
} = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);
const snapshot = JSON.parse(
  readFileSync(
    new URL("../public/data/agriculture.json", import.meta.url),
    "utf8",
  ),
);
test("official agricultural snapshot validates", () => {
  assert.equal(validate(snapshot), snapshot);
  assert.equal(snapshot.summary.cropCount, 32);
});
test("crop ranking by value area and yield distinguish metrics", () => {
  assert.equal(
    rankProducts(snapshot.crops, "productionValue")[0].categoryId,
    "40124",
  );
  assert.equal(
    rankProducts(snapshot.crops, "harvestedArea")[0].categoryId,
    "40124",
  );
  assert.equal(
    rankProducts(snapshot.crops, "yield", "all", "Quilogramas por Hectare")[0]
      .name,
    "Tomate",
  );
});
test("permanent crops rank independently and quantities have one unit", () => {
  assert.equal(
    rankProducts(snapshot.crops, "productionValue", "Permanente")[0].categoryId,
    "40147",
  );
  assert.ok(
    rankProducts(snapshot.crops, "production", "all", "Toneladas").every(
      (p) => p.latest.metrics.production.unit === "Toneladas",
    ),
  );
});
test("subdivisions of total coffee cannot enter overall crop ranking", () => {
  const d = structuredClone(snapshot.crops);
  d.products.push({
    ...d.products[0],
    id: "coffee-child",
    rankEligible: false,
  });
  assert.ok(
    !rankProducts(d, "productionValue").some((p) => p.id === "coffee-child"),
  );
});
test("zero suppression and unavailable have different presentations", () => {
  assert.equal(
    cellText({ value: 0, unit: "Toneladas", status: "real" }),
    "0 t",
  );
  assert.equal(
    cellText({ value: null, unit: "Toneladas", status: "suppressed" }),
    "Suprimido (X)",
  );
  assert.match(
    cellText({ value: null, unit: "Toneladas", status: "unavailable" }),
    /Não disponível/,
  );
});
test("nominal narrative uses source period and no causal explanation", () => {
  assert.match(narrative(snapshot), /2025.*Soja/);
  assert.match(narrative(snapshot), /139.258.000/);
  assert.match(narrative(snapshot), /nominais/);
  assert.doesNotMatch(narrative(snapshot), /melhorou|causou|safra/);
});
test("variation describes metric and nominal currency", () => {
  assert.match(
    variationText(
      rankProducts(snapshot.crops, "productionValue")[0],
      "productionValue",
    ),
    /variação nominal/,
  );
});
test("comparison cannot mix years or physical units", () => {
  const c = { value: 10, unit: "Toneladas", status: "real" };
  assert.equal(
    comparable(c, { ...c, unit: "Mil frutos" }, "2025", "2025"),
    undefined,
  );
  assert.equal(comparable(c, c, "2025", "2024"), undefined);
  assert.equal(stateShare(c, c, "2025", "2024"), null);
  assert.equal(stateShare(c, { ...c, value: 100 }, "2025", "2025"), 10);
  assert.equal(share(c, { ...c, value: 0 }), null);
});
test("invalid identity sources history symbols units and summary reject", () => {
  for (const kind of [
    "code",
    "source",
    "period",
    "history",
    "symbol",
    "count",
    "variable",
    "currency",
  ]) {
    const d = structuredClone(snapshot),
      p = d.crops.products[0];
    if (kind === "code") d.municipality.code = "4218806";
    if (kind === "source") d.sources[0].agency = "Fake";
    if (kind === "period") p.latest.reference = "2024";
    if (kind === "history") p.series.reverse();
    if (kind === "symbol") p.latest.metrics.production.rawSymbol = "X";
    if (kind === "count") d.summary.cropCount = 1;
    if (kind === "variable") p.latest.metrics.production.variableId = "9999";
    if (kind === "currency")
      p.latest.metrics.productionValue.originalUnit = "R$";
    assert.throws(() => validate(d), /incompatível/, kind);
  }
});
test("lazy static fetch uses base path and abort signal", async (t) => {
  t.mock.method(globalThis, "fetch", async (url, opt) => {
    assert.equal(url, "/data/agriculture.json");
    assert.ok(opt.signal instanceof AbortSignal);
    return new Response(JSON.stringify(snapshot));
  });
  assert.equal(
    (await loadAgriculture(new AbortController().signal)).crops.reference,
    "2025",
  );
  assert.equal(
    dataUrl("exports/agriculture-crops.csv"),
    "/data/exports/agriculture-crops.csv",
  );
});
test("HTTP errors allow caller retry instead of fabricated data", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("", { status: 503 }),
  );
  await assert.rejects(loadAgriculture(), /carregar/);
});
test("hidden values cannot produce a leading culture narrative", () => {
  const d = structuredClone(snapshot);
  for (const p of d.crops.products) {
    p.latest.metrics.productionValue = {
      ...p.latest.metrics.productionValue,
      status: "suppressed",
      value: null,
      rawSymbol: "X",
    };
  }
  assert.match(narrative(d), /Não há valores divulgados suficientes/);
});
