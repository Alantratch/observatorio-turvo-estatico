import type {HealthData,Establishment} from './types';
export const codes=['4127965','4109401','4119608','4113254'];
export const dataUrl=(file:string)=>`${import.meta.env.BASE_URL}data/${file}`;
export const number=(n:number|null|undefined)=>n==null?'Não disponível':n.toLocaleString('pt-BR',{maximumFractionDigits:0});
export const reference=(r:string|null|undefined)=>!r?'Não informada':/^\d{6}$/.test(r)?new Date(+r.slice(0,4),+r.slice(4)-1,1).toLocaleDateString('pt-BR',{month:'long',year:'numeric'}):/^\d{4}-\d{2}-\d{2}$/.test(r)?r.split('-').reverse().join('/'):r;
export const susLabel=(s:boolean|null)=>s===true?'Sim':s===false?'Não':'Não informado';
export const typeShort:Record<string,string>={'01':'Posto de saúde','02':'Centro de Saúde / UBS','05':'Hospital geral','07':'Hospital especializado','22':'Consultório isolado','36':'Clínica / especialidades','39':'Apoio diagnóstico e terapia','42':'Unidade móvel de urgência','43':'Farmácia','68':'Central de gestão','71':'Apoio à Saúde da Família','74':'Academia da Saúde'};
export function filterEstablishments(items:Establishment[],query:string,filter:string,activeOnly:boolean){
 const normalize=(s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
 return items.filter(r=>(!activeOnly||r.active)&&normalize(`${r.name} ${r.cnes} ${r.address} ${r.neighborhood??''}`).includes(normalize(query))&&(filter==='all'||filter==='sus'&&r.ambulatorySus===true||filter==='public'&&r.ownership==='Pública'||filter==='municipal'&&r.municipalOwnership||filter==='private'&&r.ownership==='Privada'||filter==='nonprofit'&&r.ownership==='Sem fins lucrativos'||filter==='ubs'&&r.ubs||filter==='urgent'&&r.urgent));
}
export function validate(data:HealthData):HealthData {
 const fail=()=>{throw Error('Arquivo de Saúde incompatível ou com contagens inválidas para Turvo/PR.');};
 if(data?.schemaVersion!==1||data?.municipality?.code!=='4127965'||data?.municipality?.state!=='PR'||!Array.isArray(data.network?.establishments)||!Array.isArray(data.beds?.records)||!Array.isArray(data.beds?.series)||!Array.isArray(data.comparison)||!Array.isArray(data.sources)||!Array.isArray(data.collection?.failures))fail();
 const validCount=(v:number)=>Number.isInteger(v)&&v>=0;
 const ids=new Set(data.sources.map(s=>s.id));
 if(ids.size!==data.sources.length||!['cnes','beds','region'].every(id=>ids.has(id))||data.sources.some(s=>s.agency!=='Ministério da Saúde'||!s.url.startsWith('https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/')||!s.collectedAt))fail();
 if(!/^\d{4}-\d{2}-\d{2}$/.test(data.network.reference)||data.network.competence!==null||data.network.referenceType!=='dailySnapshot'||data.network.reference!==data.sources.find(s=>s.id==='cnes')?.reference)fail();
 const seen=new Set<string>();
 for(const r of data.network.establishments){
  if(r.municipalityCode!=='4127965'||r.state!=='PR'||!/^\d{7}$/.test(r.cnes)||seen.has(r.cnes)||!ids.has(r.sourceId)||typeof r.active!=='boolean'||r.active!==(r.deactivationCode===null)||![true,false,null].includes(r.ambulatorySus)||r.sus!==(r.ambulatorySus===true?true:null))fail();
  if(r.coordinates&&(!Number.isFinite(r.coordinates.latitude)||!Number.isFinite(r.coordinates.longitude)||Math.abs(r.coordinates.latitude)>90||Math.abs(r.coordinates.longitude)>180))fail();
  seen.add(r.cnes);
 }
 const active=data.network.establishments.filter(r=>r.active),s=data.summary;
 if(s.registered!==seen.size||s.active!==active.length||s.inactive!==seen.size-active.length||s.public!==active.filter(r=>r.ownership==='Pública').length||s.municipal!==active.filter(r=>r.municipalOwnership).length||s.ubs!==active.filter(r=>r.ubs).length||s.hospitals!==active.filter(r=>r.hospital).length||s.urgent!==active.filter(r=>r.urgent).length||s.sus.generalTotal!==null||s.sus.ambulatoryPercentStatus!=='derived'||s.sus.ambulatoryPercent!==(active.length?Math.round(s.sus.ambulatoryYes/active.length*10000)/100:null)||s.sus.ambulatoryYes!==active.filter(r=>r.ambulatorySus===true).length||s.sus.ambulatoryNo!==active.filter(r=>r.ambulatorySus===false).length||s.sus.ambulatoryUnknown!==active.filter(r=>r.ambulatorySus===null).length)fail();
 for(const groups of [s.byType,s.byManagement,s.byOwnership])if(!Array.isArray(groups)||groups.some(g=>!g.label||!validCount(g.count))||groups.reduce((n,g)=>n+g.count,0)!==s.active)fail();
 const bedIds=new Set<string>();
 for(const r of data.beds.records){const key=`${r.municipalityCode}/${r.reference}/${r.cnes}`;if(bedIds.has(key)||!/^\d{7}$/.test(r.cnes))fail();bedIds.add(key);}
 for(const r of [...data.beds.records,...data.beds.series])if(!codes.includes(r.municipalityCode)||!/^20\d{2}(0[1-9]|1[0-2])$/.test(r.reference)||!ids.has(r.sourceId)||![r.existing,r.sus,r.icuExisting,r.icuSus].every(validCount)||r.sus>r.existing||r.icuSus>r.icuExisting)fail();
 for(const r of data.beds.series){const rows=data.beds.records.filter(v=>v.municipalityCode===r.municipalityCode&&v.reference===r.reference);if(['existing','sus','icuExisting','icuSus'].some(k=>r[k as 'existing']!==rows.reduce((n,v)=>n+v[k as 'existing'],0))||r.hospitals!==rows.length||r.zeroConfirmed!==(rows.length===0))fail();}
 if(data.beds.reference!==data.beds.competence||data.beds.reference!==[...data.beds.series.map(r=>r.reference)].sort().at(-1)||data.beds.summary.municipalityCode!=='4127965'||data.beds.summary.reference!==data.beds.reference||!data.beds.series.some(r=>r.municipalityCode==='4127965'&&r.reference===data.beds.reference&&r.existing===data.beds.summary.existing&&r.sus===data.beds.summary.sus))fail();
 if(new Set(data.comparison.map(r=>r.municipalityCode)).size!==4||data.comparison.some(r=>!codes.includes(r.municipalityCode)||r.state!=='PR'||r.network.reference!==data.network.reference||r.beds.reference!==data.beds.reference||![r.network.active,r.network.ubs,r.network.sus.ambulatoryYes,r.beds.existing,r.beds.sus].every(validCount)))fail();
 for(const b of [data.primaryCare.teams,data.primaryCare.coverage,data.professionals,data.production,data.epidemiology])if(b.status!=='unavailable'||b.value!==null||!b.reason)fail();
 if(JSON.stringify(data).includes('"mock"'))fail();
 return data;
}
export async function loadHealth(signal?:AbortSignal){const response=await fetch(dataUrl('health.json'),{signal});if(!response.ok)throw Error('Não foi possível carregar o snapshot de Saúde.');return validate(await response.json());}
export function narrative(data:HealthData){const s=data.summary;return `Na exportação do CNES de ${reference(data.network.reference)}, Turvo registra ${number(s.active)} estabelecimentos sem motivo de desativação, de ${number(s.registered)} cadastros. São ${number(s.ubs)} Centros de Saúde/UBS e ${number(s.public)} estabelecimentos públicos. O campo ambulatorial informa atendimento SUS em ${number(s.sus.ambulatoryYes)} cadastros ativos. Isso não representa o total de serviços SUS nem uma avaliação da qualidade da rede.`;}
