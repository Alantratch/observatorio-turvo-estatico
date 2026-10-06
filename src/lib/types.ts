export interface Point { period: string; value: number }
export interface Indicator { id: string; module: string; title: string; value: number | null; unit: string; source: string; agency: string; reference: string; url: string; collectedAt: string | null; municipalityCode: string; status: 'real' | 'mock' | 'unavailable'; series: Point[]; note?: string }
export interface Dataset { schemaVersion: number; municipality: {code: string; name: string; state: string}; indicators: Indicator[]; collection: {attemptedAt: string | null; failures: string[]} }
