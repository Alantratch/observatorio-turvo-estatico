import { Download, ExternalLink, MapPin } from 'lucide-react';
import type { ReactNode } from 'react';
import type { PopulationMetric, PopulationSource, Boundary, Distribution } from './types';
import { count, percent, date, populationUrl } from './data';
export function Section({id,eyebrow,title,description,children}: {id:string;eyebrow:string;title:string;description?:string;children:ReactNode}) {
  return <section className="panel pop-section" id={id}><header className="pop-section-heading"><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>{description&&<p>{description}</p>}</header>{children}</section>;
}
export function SourceNote({sources,reference}: {sources:PopulationSource[];reference?:string}) {
  return <div className="pop-source-notes">{sources.map(source=><details key={source.id}><summary><span>Fonte: {source.agency} · {source.research} · {source.table?`Tabela ${source.table}`:source.indicator?`Indicador ${source.indicator}`:source.title}<br/>Referência: {reference??source.reference} · Coleta: {date(source.collectedAt)}</span><span className="pop-more">Método e fonte ↗</span></summary><div className="pop-source-detail"><p>{source.methodology}</p>{source.variables.length>0&&<p><b>Variáveis:</b> {source.variables.map(v=>`${v.id} · ${v.name} (${v.unit})`).join('; ')}</p>}{source.classifications.length>0&&<details><summary>Ver classificações e categorias usadas</summary>{source.classifications.map(c=><p key={c.id}><b>Classificação {c.id}:</b> {Object.entries(c.categories).map(([id,name])=>`${id} · ${name}`).join('; ')}</p>)}</details>}{source.transformations.length>0&&<ul>{source.transformations.map(t=><li key={t}>{t}</li>)}</ul>}<div className="pop-source-links"><a href={source.url} target="_blank" rel="noreferrer">Ver consulta oficial <ExternalLink size={12}/></a><a href={source.metadataUrl} target="_blank" rel="noreferrer">Metadados oficiais</a>{source.definitionUrl&&<a href={source.definitionUrl} target="_blank" rel="noreferrer">Definições do IBGE</a>}</div></div></details>)}</div>;
}
export function MetricCard({metric,source}: {metric:PopulationMetric;source:PopulationSource}) {
  return <article className={`indicator pop-metric ${metric.methodology}`}><div className="card-top"><span>{metric.title}</span><span className="badge real">IBGE</span></div><strong>{count(metric.value,metric.unit==='km²'?3:2)}</strong><div className="unit">{metric.unit} · {metric.reference}</div><p className="pop-concept">{metric.concept}</p><SourceNote sources={[source]} reference={metric.reference}/></article>;
}
export function DistributionTable({data}: {data:Distribution}) {
  return <div className="table-wrap"><table><caption>Quantidade e participação · {data.reference}</caption><thead><tr><th scope="col">Categoria</th><th scope="col">Pessoas</th><th scope="col">Participação</th></tr></thead><tbody>{data.rows.map(row=><tr key={row.categoryId}><th scope="row">{row.category}</th><td>{count(row.value)}</td><td>{percent(row.percent)}</td></tr>)}<tr><th scope="row">Total do universo</th><td>{count(data.total)}</td><td>100%</td></tr></tbody></table></div>;
}
export function DownloadLink({path,children}: {path:string;children:ReactNode}) {
  return <a className="pop-download" href={populationUrl(path)} download><Download size={15}/>{children}</a>;
}
export function BoundaryMap({boundary}: {boundary:Boundary}) {
  const geometry=boundary.features[0].geometry;
  const polygons=geometry.type==='Polygon'?[geometry.coordinates as number[][][]]:geometry.coordinates as number[][][][];
  const points=polygons.flat(2);
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  // Simple local equirectangular projection, with longitude scaled at the mean latitude.
  const correction=Math.cos((minY+maxY)/2*Math.PI/180);
  const scale=Math.min(330/((maxX-minX)*correction),270/(maxY-minY));
  const width=(maxX-minX)*correction*scale,height=(maxY-minY)*scale;
  const path=polygons.map(polygon=>polygon.map(ring=>ring.map((point,index)=>`${index===0?'M':'L'}${(35+(330-width)/2+(point[0]-minX)*correction*scale).toFixed(2)},${(30+(270-height)/2+(maxY-point[1])*scale).toFixed(2)}`).join(' ')+' Z').join(' ')).join(' ');
  return <div className="pop-map"><svg viewBox="0 0 400 330" role="img" aria-labelledby="turvo-map-title turvo-map-description"><title id="turvo-map-title">Contorno municipal de Turvo, Paraná</title><desc id="turvo-map-description">Malha oficial do IBGE de 2022, em qualidade intermediária. Mapa informativo sem base externa.</desc><defs><pattern id="map-grid" width="25" height="25" patternUnits="userSpaceOnUse"><path d="M 25 0 L 0 0 0 25" fill="none" stroke="#dce8df" strokeWidth="0.6"/></pattern></defs><rect width="400" height="330" fill="url(#map-grid)"/><path d={path} fill="#d3e9de" fillRule="evenodd" stroke="#2a7056" strokeWidth="2"/><text x="366" y="25" textAnchor="middle" fontSize="11" fill="#527867">N</text><path d="M366 33 L361 45 L371 45 Z" fill="#527867"/></svg><span><MapPin size={13}/> Turvo / PR · Malha 2022</span></div>;
}
