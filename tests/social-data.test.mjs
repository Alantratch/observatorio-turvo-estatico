import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(
  new URL("../src/modules/social/data.ts", import.meta.url),
  "utf8",
).replaceAll("import.meta.env.BASE_URL", JSON.stringify("/"));
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { parseSocial, reference, number, cell, narrative, loadSocial } =
  await import(
    `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
  );
const snapshot = JSON.parse(
  readFileSync(new URL("../public/data/social.json", import.meta.url), "utf8"),
);
test("official social snapshot accepts distinct source periods", () => {
  assert.equal(parseSocial(snapshot).bolsaFamilia.reference, "202609");
  assert.equal(snapshot.bpc.reference, "202608");
});
test("rejects homonymous Turvo SC", () => {
  const d = structuredClone(snapshot);
  d.municipality.code = "4218806";
  assert.throws(() => parseSocial(d));
});
test("rejects unsafe published suppression", () => {
  const d = structuredClone(snapshot);
  d.cadunico.families.status = "suppressed";
  assert.throws(() => parseSocial(d));
});
test("rejects negative/nonfinite", () => {
  const d = structuredClone(snapshot);
  d.cadunico.people.value = -1;
  assert.throws(() => parseSocial(d));
  d.cadunico.people.value = NaN;
  assert.throws(() => parseSocial(d));
});
test("monthly references are human readable", () =>
  assert.equal(reference("202609"), "setembro de 2026"));
test("daily network extraction is distinct from annual Censo", () => {
  assert.equal(reference("2026-09-25"), "25/09/2026");
  assert.equal(reference("2025"), "2025");
});
test("currency preserves published cents", () =>
  assert.match(number(319340.15, "R$"), /319\.340,15/));
test("missing and protected values are distinct from confirmed zero", () => {
  assert.equal(
    cell({ ...snapshot.cadunico.families, value: null, status: "unavailable" }),
    "Indisponível",
  );
  assert.equal(
    cell({ ...snapshot.cadunico.families, value: null, status: "suppressed" }),
    "Suprimido",
  );
  assert.equal(cell({ ...snapshot.cadunico.families, value: 0 }), "0");
});
test("narrative distinguishes families and people without causality", () => {
  const t = narrative(snapshot);
  assert.match(t, /2\.995 famílias/);
  assert.match(t, /7\.696 pessoas/);
  assert.doesNotMatch(t, /mais pobre|porque|gestão reduziu/);
});
test("social fetch failure is actionable", async () => {
  const old = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false });
  try {
    await assert.rejects(loadSocial(), /carregar/);
  } finally {
    globalThis.fetch = old;
  }
});
test("standalone compare removed, thematic comparison retained", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(app, /active===['"]compare['"]|matchingPeer|setPeers/);
  assert.match(app, /SocialAssistancePage/);
  const catalog = readFileSync(
    new URL("../src/modules/catalog.ts", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(catalog, /Comparador Municipal/);
  assert.match(catalog, /['"]social['"]/);
  const economy = readFileSync(
    new URL("../src/modules/economy/EconomyPage.tsx", import.meta.url),
    "utf8",
  );
  assert.match(economy, /compar/i);
});
test("available comparison has same year and explicit derived metadata", () => {
  for (const r of snapshot.comparisons) {
    const c = r.peoplePer100;
    assert.equal(c.status, "derived");
    assert.equal(c.denominatorReference, c.numeratorReference.slice(0, 4));
    assert.ok(Math.abs(c.value - (c.numerator / c.denominator) * 100) < 0.011);
  }
});
