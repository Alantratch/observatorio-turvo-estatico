import type {EmploymentData,Counts} from './types';
export const integer=(v:number|null|undefined)=>v==null?'—':new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0}).format(v);
export const signed=(v:number|null|undefined)=>v==null?'—':`${v>0?'+':''}${integer(v)}`;
export const money=(v:number|null|undefined)=>v==null?'Não disponível':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(v);
export function period(v:string|null|undefined) {if(!v)return 'Não disponível';if(/^\d{4}$/.test(v))return v;if(!/^\d{4}-\d{2}$/.test(v))return v;return new Intl.DateTimeFormat('pt-BR',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(`${v}-01T00:00:00Z`));}
export const date=(v:string|null)=>v?new Intl.DateTimeFormat('pt-BR',{timeZone:'UTC'}).format(new Date(v)):'Não coletado';
export const dataUrl=(file:string)=>`${import.meta.env?.BASE_URL??'/'}data/${file}`;
const validCounts=(r:Counts)=>[r.admissions,r.dismissals,r.balance].every(Number.isSafeInteger)&&r.admissions>=0&&r.dismissals>=0&&r.balance===r.admissions-r.dismissals;
export async function loadEmployment(signal?:AbortSignal):Promise<EmploymentData>{
 const response=await fetch(dataUrl('employment.json'),{signal});
 if(!response.ok)throw Error('O arquivo local de Trabalho e Emprego não está disponível. Tente novamente.');
 const data=await response.json() as EmploymentData;
 const r=data.rais,c=data.caged;
 if(data.schemaVersion!==1||data.municipality?.code!=='4127965'||data.municipality?.state!=='PR'||!r||!c||!Array.isArray(data.sources)||!Array.isArray(data.collection?.failures)||!data.comparisons||!['available','unavailable'].includes(r.status)||!['available','unavailable'].includes(c.status)||
 (r.status==='available'&&(!r.collectedAt||!r.stock||!Number.isSafeInteger(r.stock.value)||r.stock.value<0||!r.series?.length||!r.sectors?.length||r.sectors.reduce((a,s)=>a+s.stock,0)!==r.stock.value))||
 (c.status==='available'&&(!c.collectedAt||!c.monthly?.length||c.latestReference!==c.monthly.at(-1)?.period||c.monthly.some(row=>!validCounts(row)))))throw Error('Formato de Trabalho e Emprego incompatível. Consulte a coleta do observatório.');
 return data;
}
export function narratives(data:EmploymentData){
 const r=data.rais,c=data.caged,last=c.monthly.at(-1);
 const biggest=r.sectors?.reduce((a,b)=>a.stock>b.stock?a:b);
 return {
  monthly:c.status==='available'&&last?`Em ${period(last.period)}, Turvo registrou ${integer(last.admissions)} admissões e ${integer(last.dismissals)} desligamentos, resultando em saldo de ${signed(last.balance)} vínculos.`:'Movimentação mensal ainda sem coleta validada.',
  year:c.yearToDate?.status==='available'?`De ${period(c.yearToDate.from)} a ${period(c.yearToDate.to)}, o saldo acumulado foi de ${signed(c.yearToDate.balance)} vínculos.`:'Acumulado indisponível: a janela desde janeiro precisa estar completa.',
  rais:r.status==='available'?`Segundo a RAIS ${r.reference}, Turvo possuía ${integer(r.stock?.value)} vínculos formais ativos em 31 de dezembro.`:'Estoque anual ainda sem coleta validada.',
  sector:biggest?`Na RAIS ${r.reference}, ${biggest.label} apresentou o maior estoque: ${integer(biggest.stock)} vínculos (${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(biggest.share)}%).`:'Estrutura anual não disponível.'
 };
}
export function comparisonRows(data:EmploymentData){
 return Object.values(data.comparisons).map(peer=>{
 const rais=peer.rais.status==='available'&&data.rais.status==='available'&&peer.rais.reference===data.rais.reference&&peer.rais.sourceId===data.rais.sourceId&&Boolean(peer.rais.methodology)&&peer.rais.methodology===data.rais.methodology&&peer.rais.stock?.unit===data.rais.stock?.unit?peer.rais:null;
 const caged=peer.caged.status==='available'&&data.caged.status==='available'&&peer.caged.latestReference===data.caged.latestReference&&peer.caged.adjustedThrough===data.caged.adjustedThrough&&peer.caged.sourceId===data.caged.sourceId&&Boolean(peer.caged.methodology)&&peer.caged.methodology===data.caged.methodology&&peer.caged.unit===data.caged.unit?peer.caged:null;
 const ytd=caged?.yearToDate?.status==='available'&&data.caged.yearToDate?.status==='available'&&caged.yearToDate.from===data.caged.yearToDate.from&&caged.yearToDate.to===data.caged.yearToDate.to?caged.yearToDate:null;
 const remuneration=rais?.remuneration?.status==='available'&&data.rais.remuneration?.status==='available'&&rais.remuneration.unit===data.rais.remuneration.unit&&rais.remuneration.variable===data.rais.remuneration.variable?rais.remuneration.value:null;
 return {municipality:peer.municipality,rais,caged,last:caged?.monthly.at(-1),ytd,remuneration};
 });
}
