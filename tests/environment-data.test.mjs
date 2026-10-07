import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(
  new URL("../src/modules/environment/data.ts", import.meta.url),
  "utf8",
).replaceAll("import.meta.env.BASE_URL", JSON.stringify("/municipal/"));
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { parseEnvironment, changes, number, dataUrl, loadEnvironment } =
  await import(
    `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
  );
const raw = JSON.parse(
  readFileSync(
    new URL("../public/data/environment.json", import.meta.url),
    "utf8",
  ),
);
test("official environment delivery is accepted", () =>
  assert.equal(parseEnvironment(raw), raw));
test("Turvo SC cannot be rendered as Turvo PR", () => {
  const d = structuredClone(raw);
  d.municipality.code = "4218806";
  assert.throws(() => parseEnvironment(d));
});
test("unsupported snapshot schema rejected", () =>
  assert.throws(() => parseEnvironment({ ...raw, schemaVersion: 2 })));
test("no synthetic zero for unavailable blocks", () =>
  assert.throws(() =>
    parseEnvironment({ ...raw, climate: { ...raw.climate, value: 0 } }),
  ));
test("malformed land area rejected", () => {
  const d = structuredClone(raw);
  d.landCover.classes[0].latest.areaHa = -1;
  assert.throws(() => parseEnvironment(d));
});
test("missing months cannot be zero", () => {
  const d = structuredClone(raw);
  d.fire.monthly.push({ period: "2099-12", available: false, count: 0 });
  assert.throws(() => parseEnvironment(d));
});
test("history controls enforce chronological selection", () =>
  assert.match(
    changes(raw.landCover, "2025", "2015", "native"),
    /ordem cronológica/,
  ));
test("deterministic narrative describes change without cause claims", () => {
  const text = changes(raw.landCover, "2015", "2025", "native");
  assert.match(text, /hectares/);
  assert.match(text, /mesma coleção/);
  assert.match(text, /não identifica causas ou legalidade/);
});
test("nullable format preserves absence", () => {
  assert.equal(number(null), "Não disponível");
  assert.equal(number(0), "0");
});
test("downloads honor deployment base path", () =>
  assert.equal(
    dataUrl("exports/environment-fire.csv"),
    "/municipal/data/exports/environment-fire.csv",
  ));
test("loading errors reported instead of fabricated fallback values", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: false, status: 503 });
    await assert.rejects(loadEnvironment(), /503/);
  } finally {
    globalThis.fetch = original;
  }
});
