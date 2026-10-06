import type { Dataset } from './types';
export async function loadData(signal?: AbortSignal): Promise<Dataset> {
 const response = await fetch(`${import.meta.env.BASE_URL}data/indicators.json`, {signal});
 if (!response.ok) throw new Error('Não foi possível carregar o catálogo local.');
 const data = await response.json() as Dataset;
 if(data.schemaVersion !== 1 || !Array.isArray(data.indicators)) throw new Error('Formato de dados incompatível.');
 return data;
}
export const format = (value: number | null, unit: string) => value === null ? '—' : new Intl.NumberFormat('pt-BR', {maximumFractionDigits: unit === 'pessoas' ? 0 : 2, ...(unit === 'R$' ? {style:'currency',currency:'BRL'} : {})}).format(value);
