import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const code=ts.transpileModule(readFileSync(new URL('../src/modules/employment/data.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {loadEmployment,narratives,comparisonRows,integer,signed,money,period}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const official=JSON.parse(readFileSync(new URL('../public/data/employment.json',import.meta.url),'utf8'));
test('narratives use exact municipal flows and annual stock with independent references',()=>{
 const text=narratives(official);
 assert.match(text.monthly,/agosto de 2026.*116 admissões.*93 desligamentos.*\+23 vínculos/);
 assert.match(text.year,/janeiro de 2026.*agosto de 2026.*\+295/);
 assert.match(text.rais,/RAIS 2025.*2\.763 vínculos formais ativos/);
 assert.match(text.sector,/Serviços.*1\.168.*42,27%/);
 assert.doesNotMatch(Object.values(text).join(' '),/por causa|devido|Prefeitura|taxa de emprego|pessoas empregadas/);
});
test('signed balances only: quantities and wages do not get a plus sign',()=>{
 assert.equal(signed(23),'+23');assert.equal(signed(-5),'-5');assert.equal(signed(0),'0');assert.equal(signed(null),'—');
 assert.equal(integer(2763),'2.763');assert.doesNotMatch(integer(116),/\+/);assert.match(money(2262.67),/2\.262,67/);
 assert.equal(period('2026-08'),'agosto de 2026');assert.equal(period('2025'),'2025');assert.equal(period(null),'Não disponível');assert.equal(period('Não disponível'),'Não disponível');
});
test('comparison covers the four peers with exactly matched years, months and methods',()=>{
 const rows=comparisonRows(official);assert.equal(rows.length,4);assert.ok(rows.every(r=>r.rais&&r.caged&&r.ytd));
 const turvo=rows.find(r=>r.municipality.name==='Turvo');assert.equal(turvo.last.balance,23);assert.equal(turvo.ytd.balance,295);assert.equal(turvo.rais.stock.value,2763);
});
test('different RAIS year/unit/method is hidden independently of CAGED',()=>{
 for(const mismatch of ['reference','unit','methodology']){
  const d=structuredClone(official),peer=d.comparisons['4109401'];
  if(mismatch==='unit')peer.rais.stock.unit='pessoas';else peer.rais[mismatch]='another';
  const row=comparisonRows(d).find(r=>r.municipality.code==='4109401');assert.equal(row.rais,null);assert.ok(row.caged);
 }
});
test('different CAGED competence, revision cutoff, unit or method is not comparable',()=>{
 for(const key of ['latestReference','adjustedThrough','unit','methodology']){
  const d=structuredClone(official);d.comparisons['4109401'].caged[key]='different';
  const r=comparisonRows(d).find(r=>r.municipality.code==='4109401');assert.equal(r.caged,null);assert.ok(r.rais);
 }
});
test('YTD requires the same January-to-latest interval',()=>{
 const d=structuredClone(official);d.comparisons['4109401'].caged.yearToDate.from='2026-02';
 const r=comparisonRows(d).find(r=>r.municipality.code==='4109401');assert.equal(r.ytd,null);assert.ok(r.last);
});
test('incompatible remuneration concept is not shown in comparison',()=>{
 const d=structuredClone(official);d.comparisons['4109401'].rais.remuneration.unit='R$ reais deflacionados';
 const r=comparisonRows(d).find(r=>r.municipality.code==='4109401');assert.ok(r.rais);assert.equal(r.remuneration,null);
});
test('narratives show unavailable data and never invented zero',()=>{
 const d=structuredClone(official);d.rais={status:'unavailable'};d.caged={status:'unavailable',monthly:[]};
 assert.match(narratives(d).monthly,/sem coleta/);assert.match(narratives(d).rais,/sem coleta/);assert.match(narratives(d).year,/indisponível/);
});
test('frontend loads one static snapshot with abort signal',async t=>{
 t.mock.method(globalThis,'fetch',async(url,options)=>{assert.equal(url,'/data/employment.json');assert.ok(options.signal instanceof AbortSignal);return new Response(JSON.stringify(official));});
 assert.equal((await loadEmployment(new AbortController().signal)).caged.latestReference,'2026-08');
});
test('404 is a recoverable error',async t=>{
 t.mock.method(globalThis,'fetch',async()=>new Response('',{status:404}));await assert.rejects(loadEmployment(),/não está disponível/);
});
test('bad schema, municipality, stock sum and monthly balance reject rendering',async t=>{
 let d;t.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify(d)));
 for(const kind of ['schema','territory','stock','balance']){
  d=structuredClone(official);
  if(kind==='schema')d.schemaVersion=2;else if(kind==='territory')d.municipality.code='4218806';else if(kind==='stock')d.rais.stock.value++;else d.caged.monthly.at(-1).balance++;
  await assert.rejects(loadEmployment(),/incompatível/);
 }
});
