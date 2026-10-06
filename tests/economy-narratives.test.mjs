import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const code=ts.transpileModule(readFileSync(new URL('../src/modules/economy/data.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {narratives,loadEconomy,comparisonRows,currency,compactCurrency}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const official=JSON.parse(readFileSync(new URL('../public/data/economy.json',import.meta.url),'utf8'));

test('current GDP, official capita and sector vintages stay separate',()=>{
 const texts=narratives(official);
 assert.match(texts.gdp,/697\.870\.000,00 em 2023/);
 assert.match(texts.capita,/49\.038,74/);
 assert.match(texts.sector,/de 2021, Indústria respondeu por 33,85%/);
 assert.doesNotMatch(texts.sector,/2023/);
});
test('nominal description states base periods and current-price limitation',()=>{
 assert.match(narratives(official).change,/2022 e 2023, o PIB nominal aumentou 10,16%/);
 assert.match(narratives(official).change,/não representam crescimento econômico real/);
});
test('decline, stability and absent base are described without causation',()=>{
 const data=structuredClone(official);
 data.gdp.latest.nominalChange=-5;assert.match(narratives(data).change,/PIB nominal diminuiu 5%/);
 data.gdp.latest.nominalChange=0;assert.match(narratives(data).change,/PIB nominal não variou\./);
 data.gdp.latest.nominalChange=null;assert.match(narratives(data).change,/não está disponível/);
 assert.doesNotMatch(Object.values(narratives(data)).join(' '),/mais rico|porque|gerou.*emprego/i);
});
test('all four municipalities match each indicator separately',()=>{
 const rows=comparisonRows(official);
 assert.equal(rows.length,4);assert.ok(rows.every(r=>r.gdp&&r.capita&&r.composition&&r.change!==null));
 assert.equal(rows[0].gdp.period,'2023');assert.equal(rows[0].composition.period,'2021');
});
test('incompatible GDP year hides GDP and its change only',()=>{
 const data=structuredClone(official);data.comparisons[0].gdp.latest.period='2022';
 const row=comparisonRows(data)[1];assert.equal(row.gdp,null);assert.equal(row.change,null);assert.ok(row.capita);assert.ok(row.composition);
});
test('incompatible GDP unit and method are excluded',()=>{
 for(const changes of [{unit:'Mil Reais'},{methodology:'deflated'}]){
  const data=structuredClone(official);Object.assign(data.comparisons[0].gdp,changes);
  assert.equal(comparisonRows(data)[1].gdp,null);
 }
});
test('nominal changes require the same initial period and annual interval',()=>{
 const data=structuredClone(official);data.comparisons[0].gdp.latest.from='2021';
 assert.equal(comparisonRows(data)[1].change,null);
 data.comparisons[0].gdp.latest.from='2022';data.comparisons[0].gdp.latest.annual=false;
 assert.equal(comparisonRows(data)[1].change,null);
});
test('incompatible sector year, method and denominator are excluded',()=>{
 for(const mode of ['period','methodology','denominator']){
  const data=structuredClone(official);const peer=data.comparisons[0];
  if(mode==='period')peer.sectorComposition.series.at(-1).period='2020';
  else peer.sectorComposition[mode]=mode==='methodology'?'another':'gdp';
  const row=comparisonRows(data)[1];assert.equal(row.composition,null);assert.ok(row.gdp);
 }
});
test('per capita requires matching official unit and year',()=>{
 const data=structuredClone(official);data.comparisons[0].gdpPerCapita.unit='R$';
 assert.equal(comparisonRows(data)[1].capita,null);
 data.comparisons[0].gdpPerCapita.unit=data.gdpPerCapita.unit;data.comparisons[0].gdpPerCapita.latest.period='2021';
 assert.equal(comparisonRows(data)[1].capita,null);
});
test('currency formatting rounds only presentation',()=>{
 const value=official.gdp.latest.value;
 assert.match(compactCurrency(value),/697,87 mi/);assert.match(currency(value),/697\.870\.000,00/);
 assert.equal(official.gdp.latest.value,697870000);
});
test('local snapshot passes signal with no remote API',async t=>{
 t.mock.method(globalThis,'fetch',async(url,options)=>{assert.equal(url,'/data/economy.json');assert.ok(options.signal instanceof AbortSignal);return new Response(JSON.stringify(official));});
 assert.equal((await loadEconomy(new AbortController().signal)).municipality.code,'4127965');
});
test('missing snapshot is a recoverable error',async t=>{
 t.mock.method(globalThis,'fetch',async()=>new Response('',{status:404}));
 await assert.rejects(loadEconomy(),/não está disponível/);
});
test('incompatible schema, municipality, empty opening and real prices reject rendering',async t=>{
 let data;
 t.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify(data)));
 for(const mode of ['schema','municipality','sectors','prices']){
  data=structuredClone(official);
  if(mode==='schema')data.schemaVersion=2;
  else if(mode==='municipality')data.municipality.code='4109401';
  else if(mode==='sectors')data.sectorComposition.series=[];
  else data.methodology.prices='constant';
  await assert.rejects(loadEconomy(),/incompatível/);
 }
});
