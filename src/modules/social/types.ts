export interface SocialMetric {
  value: number | null;
  status: "real" | "derived" | "unavailable" | "suppressed";
  unit: string;
  reference: string;
  municipalityCode: string;
  agency: string;
  base: string;
  indicator: string;
  sourceId: string;
  url: string;
  collectedAt: string;
  transformation: string;
  note: string;
  numerator?: number | null;
  denominator?: number | null;
  numeratorReference?: string;
  denominatorReference?: string;
  denominatorUrl?: string;
}
export interface SocialSource {
  id: string;
  title: string;
  agency: string;
  reference: string;
  url: string;
  collectedAt: string;
  contentHash: string;
  methodology: string;
  archiveHash?: string;
  variables?: string[];
}
export interface CadPoint {
  reference: string;
  families: SocialMetric;
  people: SocialMetric;
}
export interface BenefitPoint extends CadPoint {
  transferredValue: SocialMetric;
  averageBenefit: SocialMetric;
}
export interface BpcPoint {
  reference: string;
  elderly: SocialMetric;
  disabled: SocialMetric;
  total: SocialMetric;
  elderlyValue: SocialMetric;
  disabledValue: SocialMetric;
  transferredValue: SocialMetric;
}
export interface SocialUnit {
  id: string;
  type: string;
  institutionName: string;
  institutionalAddress: string;
  municipalityCode: string;
  state: string;
  reference: string;
  sourceId: string;
  situation: string;
  services: string[];
  coordinates: null;
  coordinateNote: string;
}
export interface PaifPoint {
  reference: string;
  reportingUnits: number;
  accompaniedFamilies: SocialMetric;
  newFamilies: SocialMetric;
  individualAttendances: SocialMetric;
}
export interface SocialData {
  schemaVersion: 1;
  municipality: { code: string; name: string; state: string };
  summary: SocialMetric[];
  cadunico: CadPoint & {
    income: {
      id: string;
      label: string;
      families: SocialMetric;
      people: SocialMetric;
    }[];
    incomeDefinition: {
      reference: string;
      url: string;
      checkedAtEdition: string;
      note: string;
    };
    registrationQuality: {
      updated: SocialMetric;
      updatedPercent: SocialMetric;
      notUpdated: SocialMetric;
    };
    series: CadPoint[];
    methodologyBreaks: { reference: string; note: string }[];
  };
  bolsaFamilia: BenefitPoint & { series: BenefitPoint[]; methodology: string };
  bpc: BpcPoint & { series: BpcPoint[]; methodology: string };
  suas: {
    reference: string;
    units: SocialUnit[];
    censusCounts: Record<string, SocialMetric>;
    cadSuasReference: string;
    cadSuasCounts: Record<string, SocialMetric>;
    note: string;
  };
  services: {
    reference: string | null;
    paif: PaifPoint[];
    paefi: { value: null; status: "unavailable"; note: string };
    note?: string;
  };
  comparisons: {
    municipalityCode: string;
    municipalityName: string;
    reference: string;
    families: SocialMetric;
    people: SocialMetric;
    peoplePer100: SocialMetric;
    cras: SocialMetric;
  }[];
  sources: SocialSource[];
  collection: { attemptedAt: string; failures: string[] };
  privacy: {
    policy: string;
    threshold: number;
    unavailable: {
      id: string;
      title: string;
      value: null;
      status: "unavailable";
      url: string;
      note: string;
    }[];
  };
}
