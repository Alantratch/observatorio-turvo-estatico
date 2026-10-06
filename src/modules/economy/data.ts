import type {EconomyData,EconomyMunicipality,EconomySeries} from './types';
export const economyUrl=(path:string)=>`${import.meta.env?.BASE_URL??'/'}data/${path}`;
export const currency=(value:number)=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
export const compactCurrency=(value:number)=>Math.abs(value)>=1e9?`${currency(value/1e9)} bi`:Math.abs(value)>=1e6?`${currency(value/1e6)} mi`:currency(value);
export const percent=(value:number)=>`${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(value)}%`;
export const collectedDate=(value:string)=>new Date(value).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'});
export async function loadEconomy(signal?:AbortSignal):Promise<EconomyData> {
 const response=await fetch(economyUrl('economy.json'),{signal});
 if(!response.ok)throw new Error('O snapshot local de Economia não está disponível. Tente novamente.');
 const data=await response.json() as EconomyData;
 if(data.schemaVersion!==1||data.municipality?.code!=='4127965'||data.methodology?.prices!=='current'||!data.gdp?.series?.length||!data.gdpPerCapita?.series?.length||!data.sectorComposition?.series?.length||!Array.isArray(data.sources)||!Array.isArray(data.comparisons))throw new Error('Snapshot de Economia incompatível. Consulte o responsável pelos dados.');
 return data;
}
export function narratives(data:EconomyMunicipality) {
 const latest=data.gdp.latest,capita=data.gdpPerCapita.latest;
 const structure=data.sectorComposition.series.at(-1)!;
 const main=structure.sectors.find(s=>s.id===structure.leadingSector)!;
 const change=latest.nominalChange;
 return {gdp:`O PIB de ${data.municipality.name} alcançou ${currency(latest.value)} em ${latest.period}.`,
  change:change==null?'A variação nominal não está disponível para esta observação.':`Entre ${latest.from} e ${latest.period}, o PIB nominal ${change>0?'aumentou':change<0?'diminuiu':'não variou'}${change===0?'.':` ${percent(Math.abs(change))}.`} Valores a preços correntes não representam crescimento econômico real descontado da inflação.`,
  capita:`O PIB per capita em ${capita.period} foi de ${currency(capita.value)}.`,
  sector:`Na última abertura setorial disponível, de ${structure.period}, ${main.label} respondeu por ${percent(main.share)} do valor adicionado.`};
}
export function compatibleSeries(current:EconomySeries,peer:EconomySeries) {return current.unit===peer.unit&&current.methodology===peer.methodology&&current.latest.period===peer.latest.period;}
export function comparisonRows(data:EconomyData) {
 const own=data.sectorComposition.series.at(-1)!;
 return [data,...data.comparisons].map(item=>{
  const sector=item.sectorComposition.series.at(-1)!;
  const structureCompatible=sector.period===own.period&&item.sectorComposition.methodology===data.sectorComposition.methodology&&item.sectorComposition.unit===data.sectorComposition.unit&&item.sectorComposition.denominator===data.sectorComposition.denominator;
  const latest=item.gdp.latest;
  return {code:item.municipality.code,name:item.municipality.name,gdp:compatibleSeries(data.gdp,item.gdp)?latest:null,
   capita:compatibleSeries(data.gdpPerCapita,item.gdpPerCapita)?item.gdpPerCapita.latest:null,
   change:compatibleSeries(data.gdp,item.gdp)&&latest.from===data.gdp.latest.from&&latest.annual===data.gdp.latest.annual?latest.nominalChange??null:null,
   composition:structureCompatible?sector:null};
 });
}
