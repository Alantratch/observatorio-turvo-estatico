import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
// Use the project's existing compiler; no new test runtime or dependency.
const compiled = ts.transpileModule(readFileSync(new URL('../src/modules/population/data.ts', import.meta.url), 'utf8'), {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const { narratives, loadPopulation } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const official = JSON.parse(readFileSync(new URL('../public/data/population.json', import.meta.url), 'utf8'));

test('narrative keeps census and estimate years and concepts separate', () => {
  const text = narratives(official).estimate;
  assert.match(text, new RegExp(`estimada de Turvo em ${official.summary['population-estimate'].reference}`));
  assert.match(text, /Censo registrou 14\.231 pessoas em 2022/);
});
test('growth uses the compatible baseline rather than raw 2010 census', () => {
  assert.match(narratives(official).growth, /1,12% \(157 pessoas\)/);
  assert.match(narratives(official).growth, /territorial compatibilizada/);
});
test('older share is calculated from all 60+ groups and the same universe', () => {
  assert.match(narratives(official).older, /15,49%/);
  assert.match(narratives(official).older, /2\.205 pessoas/);
});
test('negative change produces a descriptive decrease without causal claims', () => {
  const data = structuredClone(official);
  data.growth.absoluteChange = -100;
  data.growth.percentChange = -1;
  assert.match(narratives(data).growth, /diminuiu 1% \(100 pessoas\)/);
  assert.doesNotMatch(narratives(data).growth, /porque|migração|jovens foram/i);
});
test('zero change is described as stable', () => {
  const data = structuredClone(official);
  data.growth.absoluteChange = 0;
  data.growth.percentChange = 0;
  assert.match(narratives(data).growth, /não variou/);
});

test('local snapshot loads with an abort signal', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/data/population.json');
    assert.ok(options.signal instanceof AbortSignal);
    return new Response(JSON.stringify(official), {status:200});
  });
  assert.equal((await loadPopulation(new AbortController().signal)).municipality.code, '4127965');
});
test('missing local snapshot produces the recoverable error message', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('', {status:404}));
  await assert.rejects(loadPopulation(new AbortController().signal), /não está disponível/);
});
test('wrong municipality or schema never renders as official', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({...official, municipality:{code:'4109401'}})));
  await assert.rejects(loadPopulation(new AbortController().signal), /incompatível/);
});
