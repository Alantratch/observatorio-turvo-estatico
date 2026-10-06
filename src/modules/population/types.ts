export interface PopulationSource {
  id: string; agency: string; research: string; table: string | null; title: string;
  variables: {id: string; name: string; unit: string}[];
  classifications: {id: string; categories: Record<string, string>}[];
  periods: string[]; reference: string; url: string; officialUrl: string; metadataUrl: string;
  collectedAt: string; transformations: string[]; methodology: string; definitionUrl?: string; rawPath?: string; indicator?: string;
}
export interface PopulationMetric {
  id: string; title: string; value: number; unit: string; reference: string; sourceId: string;
  source: string; agency: string; url: string; collectedAt: string; municipalityCode: string;
  status: 'real'; concept: string; methodology: 'census' | 'estimate' | 'territory';
}
export interface HistoryPoint { period: string; value: number; methodology: 'census' | 'estimate'; sourceId: string }
export interface DistributionRow { categoryId: string; category: string; value: number; percent: number }
export interface Distribution { status: 'real'; reference: string; sourceIds: string[]; unit: string; total: number; rows: DistributionRow[] }
export interface AgeSex { ageGroup: string; categoryIds: string[]; male: number; female: number; total: number; percent: number }
export interface Boundary { type: 'FeatureCollection'; features: {type: 'Feature'; properties: {codarea: string}; geometry: {type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][]}}[] }
export interface PopulationData {
  schemaVersion: 1; municipality: {code: string; name: string; state: string}; summary: Record<string, PopulationMetric>;
  populationHistory: {status: 'real'; sourceIds: string[]; rows: HistoryPoint[]};
  estimateHistory: {status: 'real'; sourceIds: string[]; rows: HistoryPoint[]};
  growth: {status: 'real'; sourceIds: string[]; from: string; to: string; compatibleBaseline: number; absoluteChange: number; percentChange: number; annualGeometricRate: number};
  ageSex: {status: 'real'; sourceIds: string[]; reference: string; unit: string; total: number; rows: AgeSex[]};
  sex: Distribution; race: Distribution; urbanRural: Distribution;
  demographicIndicators: {status: 'real'; sourceIds: string[]; reference: string; indicators: PopulationMetric[]; rows: {period: string; medianAge: number; agingIndex: number; sexRatio: number}[]};
  households: {status: 'real'; sourceIds: string[]; reference: string; indicators: PopulationMetric[]; residents: number};
  territory: {status: 'real'; sourceIds: string[]; geometryReference: string; region: string; immediateRegion: string; intermediateRegion: string; geometry: Boundary};
  sources: PopulationSource[]; collection: {attemptedAt: string; lastSuccessAt: string; failures: string[]; policy: string};
}
