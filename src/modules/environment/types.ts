export type Missing = {
  status: "unavailable";
  value: null;
  reference: null;
  reason: string;
  url: string;
};
export interface AreaPoint {
  year: string;
  areaHa: number;
  sharePercent: number;
}
export interface CoverClass {
  code: number;
  name: string;
  level: number;
  hierarchy: string;
  color: string;
  collection: string;
  series: AreaPoint[];
  latest: AreaPoint;
}
export type HistoryRow = {
  year: string;
  native: number;
  forest: number;
  farming: number;
  farmingWithoutPlantation: number;
  plantation: number;
  urban: number;
  water: number;
  pasture: number;
  agriculture: number;
};
export interface LandCover {
  status: "real";
  reference: string;
  classes: CoverClass[];
  history: HistoryRow[];
  mappedAreaHa: number;
  municipalArea: {
    value: number;
    reference: string;
    unit: string;
    url: string;
  };
  areaDifferencePercent: number;
  shareMethodology: string;
}
export interface FirePoint {
  id: string;
  municipalityCode: string;
  date: string;
  satellite: string;
  latitude: number;
  longitude: number;
  biome: string | null;
}
export interface FireAnnual {
  year: string;
  count: number;
  complete: boolean;
  through: string;
  per1000Km2: number;
  coverageMonths: number;
}
export interface Fire {
  status: "real";
  reference: string;
  satellite: string;
  annual: FireAnnual[];
  monthly: { period: string; count: number | null; available: boolean }[];
  points: FirePoint[];
  currentYear: FireAnnual | null;
  previousYear: FireAnnual | null;
  methodology: string;
  methodologyUrl: string;
}
export interface Station {
  code: string;
  name: string;
  type: string;
  latitude: number;
  longitude: number;
  location: "inside" | "regional";
  sourceMunicipality: string;
  sourceMunicipalityCode: number;
  distanceToCentroidKm: number;
  operating: string;
  telemetric: string;
  agency: string;
  basin: string;
  subBasin: string;
  river: string | null;
  registryUpdatedAt: number;
}
export interface Geometry {
  type: string;
  coordinates: unknown[];
}
export interface ProtectedUnit {
  code: string;
  name: string;
  sphere: string;
  category: string;
  group: string;
  agency: string;
  listedMunicipalities: string;
  registryMentionsTurvo: boolean;
  intersectionHa: number;
  syncedAt: number;
  geometry: Geometry;
}
export interface EnvironmentData {
  schemaVersion: 1;
  municipality: { code: string; name: string; state: string };
  landCover: LandCover | Missing;
  vegetation:
    | {
        status: "derived";
        nativeCodes: number[];
        nativeAreaHa: number;
        forestAreaHa: number;
        plantationAreaHa: number;
        methodology: string;
      }
    | Missing;
  fire: Fire | Missing;
  water:
    | {
        status: "real";
        stations: Station[];
        measurements: Missing;
        methodology: string;
      }
    | Missing;
  protectedAreas:
    | {
        status: "derived";
        units: ProtectedUnit[];
        unionAreaHa: number;
        sharePercent: number;
        declaredMunicipalityCount: number;
        methodology: string;
        biomes: string[];
        biomeReference: string;
        biomeSourceUrl: string;
      }
    | Missing;
  climate: Missing;
  burnedArea: Missing;
  deforestation: Missing;
  comparisons: {
    municipalityCode: string;
    name: string;
    landCover: LandCover;
    fire?: Fire;
  }[];
  sources: {
    id: string;
    agency: string;
    dataset: string;
    url: string;
    reference: string;
    collectedAt: string;
    unit: string;
    collection?: string;
    version?: string;
    license?: string;
    transformation?: string;
    sha256?: string;
  }[];
  geometry: { type: string; features: { geometry: Geometry }[] };
  collection: {
    failures: string[];
    attemptedAt: string;
    lastSuccessAt: string;
    policy: string;
  };
}
