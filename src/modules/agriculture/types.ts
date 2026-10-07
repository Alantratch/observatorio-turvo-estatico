export type Status =
  | "real"
  | "derived"
  | "suppressed"
  | "notApplicable"
  | "unavailable";
export interface Metric {
  value: number | null;
  status: Status;
  unit: string;
  originalUnit?: string;
  rawSymbol?: string | null;
  variableId?: string;
  sourceId?: string;
  transformation?: string | null;
  formula?: string;
  inputs?: Record<string, unknown>;
  reason?: string | null;
}
export interface Point {
  reference: string;
  metrics: Record<string, Metric>;
  annualChanges: Record<string, number | null>;
}
export interface Product {
  id: string;
  categoryId: string;
  name: string;
  classificationId: string;
  categoryLevel: number;
  kind: "Temporária" | "Permanente" | null;
  rankEligible: boolean;
  rankNote: string | null;
  presentInLatest: boolean;
  latest: Point;
  series: Point[];
  sourceId: string;
}
export interface ProductBlock {
  status: "real";
  reference: string;
  sourceId: string;
  products: Product[];
  totals: Record<string, Metric>;
  annualChangeDefinition: {
    status: "derived";
    unit: string;
    formula: string;
    rule: string;
  };
}
export interface Livestock {
  herds: ProductBlock;
  products: ProductBlock;
  aquaculture: ProductBlock;
  milkedCows: {
    status: "real";
    reference: string;
    sourceId: string;
    latest: { reference: string; metric: Metric };
    series: { reference: string; metric: Metric }[];
  };
  milkPerCow: Metric;
}
export interface Census {
  status: "real";
  reference: string;
  values: Record<string, Metric>;
  sourceIds: string[];
  note: string;
}
export interface Scope {
  municipalityCode: string;
  name: string;
  state: "PR";
  crops: ProductBlock;
  livestock: Livestock;
  forestry: { extraction: ProductBlock; silviculture: ProductBlock };
  agriculturalCensus: Census;
}
export interface Source {
  id: string;
  agency: "IBGE";
  research: string;
  table: string;
  title: string;
  variables: { id: number; nome: string; unidade: string }[];
  classifications: { id: string; categories: Record<string, string> }[];
  periods: string[];
  reference: string;
  publishedPeriods: { id: string; modificacao: string }[];
  municipalityCodes: string[];
  url: string;
  officialUrl: string;
  metadataUrl: string;
  collectedAt: string;
  transformations: string[];
  methodology: string;
}
export interface AgricultureData {
  schemaVersion: 1;
  municipality: { code: "4127965"; name: "Turvo"; state: "PR" };
  summary: {
    reference: string;
    cropCount: number;
    leadingCropId: string | null;
    productionValue: Metric;
    note: string;
  };
  crops: ProductBlock;
  livestock: Livestock;
  forestry: Scope["forestry"];
  agriculturalCensus: Census;
  comparisons: Scope[];
  sources: Source[];
  classificationSources: Record<string, string>;
  collection: { attemptedAt: string; failures: string[] };
  quality: {
    yieldCheck: string;
    warnings: { product: string; reference: string; message: string }[];
  };
}
