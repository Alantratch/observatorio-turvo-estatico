export interface Group {label:string;count:number}
export interface NetworkSummary {
 status:'real';sourceId:string;reference:string;competence:null;
 registered:number;active:number;inactive:number;public:number;municipal:number;ubs:number;hospitals:number;urgent:number;
 byType:Group[];byManagement:Group[];byOwnership:Group[];
 sus:{ambulatoryYes:number;ambulatoryNo:number;ambulatoryUnknown:number;ambulatoryPercent:number|null;ambulatoryPercentStatus:'derived';ambulatoryPercentFormula:string;generalTotal:null;generalUnknown:number};
}
export interface Establishment {
 cnes:string;municipalityCode:string;state:'PR';name:string;typeCode:string;type:string;management:string;legalNatureCode:string|null;ownership:string;municipalOwnership:boolean;active:boolean;deactivationCode:string|null;ambulatorySus:boolean|null;sus:true|null;ubs:boolean;urgent:boolean;hospital:boolean;address:string;neighborhood:string|null;postalCode:string|null;coordinates:{latitude:number;longitude:number}|null;mapEligible:boolean;services:Record<string,boolean|null>;sourceId:string;cnesUrl:string;
}
export interface BedRecord {municipalityCode:string;state:'PR';cnes:string;name:string;reference:string;existing:number;sus:number;icuExisting:number;icuSus:number;sourceId:string}
export interface BedTotal {municipalityCode:string;reference:string;existing:number;sus:number;icuExisting:number;icuSus:number;hospitals:number;zeroConfirmed:boolean;sourceId:string}
export interface Pending {status:'unavailable';title:string;value:null;reference:null;competence:null;municipalityCode:string;agency:string;collectedAt:null;url:string;reason:string}
export interface Source {id:string;source:string;agency:string;dataset:string;catalogUrl:string;url:string;resourceId:string;publishedAt:string;collectedAt:string;reference:string;competence:string|null;format:string;sha256:string;bytes:number;concept:string;transformation:string;typeClassificationUrl?:string}
export interface HealthData {
 schemaVersion:1;municipality:{code:'4127965';name:'Turvo';state:'PR'};summary:NetworkSummary;
 network:{status:'real';reference:string;referenceType:'dailySnapshot';competence:null;unit:string;sourceId:string;establishments:Establishment[];nationalRowsRead:number;activeDefinition:string;susDefinition:string};
 primaryCare:{status:'real';sourceId:string;reference:string;competence:null;ubs:number;teams:Pending;coverage:Pending};
 beds:{status:'real';reference:string;competence:string;unit:string;sourceId:string;records:BedRecord[];series:BedTotal[];summary:BedTotal;nationalRowsRead:number};
 region:{status:'real';sourceId:string;reference:string;code:string;name:string;macroCode:string;macroName:string};
 professionals:Pending;production:Pending;epidemiology:Pending;
 comparison:{municipalityCode:string;name:string;state:'PR';network:NetworkSummary;beds:BedTotal}[];
 map:{geometry:{type:'Polygon'|'MultiPolygon';coordinates:number[][][]|number[][][][]}|null;geometryReference:string|null;geometrySourceUrl:string;coordinateConcept:string;shown:number};
 sources:Source[];collection:{attemptedAt:string;failures:string[]};
}
