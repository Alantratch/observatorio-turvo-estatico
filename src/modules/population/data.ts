import type {PopulationData} from './types';
export const populationUrl = (path: string) => `${(import.meta.env?.BASE_URL ?? '/')}data/${path}`;
export const count = (value: number, decimals=0) => new Intl.NumberFormat('pt-BR',{maximumFractionDigits:decimals}).format(value);
export const percent = (value: number) => `${count(value,2)}%`;
export const date = (value: string) => new Date(value).toLocaleDateString('pt-BR', {timeZone: 'America/Sao_Paulo'});
export async function loadPopulation(signal: AbortSignal): Promise<PopulationData> {
  const response = await fetch(populationUrl('population.json'), {signal});
  if (!response.ok) throw new Error('O arquivo de População não está disponível. Tente novamente.');
  const data = await response.json() as PopulationData;
  if (data.schemaVersion !== 1 || data.municipality?.code !== '4127965' || !data.summary?.['population-census'] || !Array.isArray(data.ageSex?.rows) || !Array.isArray(data.sources) || !data.territory?.geometry || !data.collection) throw new Error('O snapshot de População tem formato incompatível.');
  return data;
}
// Pure descriptive calculations. No generated interpretation or causal claims.
export function narratives(data: PopulationData) {
  const estimate = data.summary['population-estimate'];
  const growth = data.growth;
  const older = data.ageSex.rows.filter(row=>['60–69','70–79','80+'].includes(row.ageGroup)).reduce((sum,row)=>sum+row.total,0);
  const first = data.demographicIndicators.rows[0];
  const last = data.demographicIndicators.rows[data.demographicIndicators.rows.length-1];
  return {
    estimate: `A população estimada de Turvo em ${estimate.reference} é de ${count(estimate.value)} pessoas. O último Censo registrou ${count(data.summary['population-census'].value)} pessoas em ${data.summary['population-census'].reference}.`,
    growth: `Entre os Censos de ${growth.from} e ${growth.to}, a população ${growth.absoluteChange===0?'não variou':`${growth.absoluteChange<0?'diminuiu':'aumentou'} ${percent(Math.abs(growth.percentChange))} (${count(Math.abs(growth.absoluteChange))} pessoas)`}, na comparação territorial compatibilizada do IBGE.`,
    older: `Pessoas de 60 anos ou mais representam ${percent(older/data.ageSex.total*100)} da população considerada em ${data.ageSex.reference} (${count(older)} pessoas).`,
    aging: `O índice de envelhecimento passou de ${count(first.agingIndex,2)} em ${first.period} para ${count(last.agingIndex,2)} em ${last.period}, segundo a tabela 9756.`,
  };
}
