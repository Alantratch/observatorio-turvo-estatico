"""Education Básica: school aggregates and published municipal INEP indicators."""
import copy
import csv
import io
import json
import math
import re
import tempfile
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from scripts.common import atomic_write,read
from scripts.sources import inep

STAGES={'EDU_BAS':'Educação básica','ED_INF':'Educação infantil','CRE':'Creche','PRE':'Pré-escola','FUN':'Ensino fundamental','FUN_AI':'Anos iniciais','FUN_AF':'Anos finais','MED':'Ensino médio','EJA':'EJA','EJA_FUN':'EJA fundamental','EJA_MED':'EJA médio'}
ENROLMENTS={'total':'QT_MAT_BAS','infant':'QT_MAT_INF','nursery':'QT_MAT_INF_CRE','preschool':'QT_MAT_INF_PRE','fundamental':'QT_MAT_FUND','initial':'QT_MAT_FUND_AI','final':'QT_MAT_FUND_AF','secondary':'QT_MAT_MED','professional':'QT_MAT_PROF','eja':'QT_MAT_EJA','special':'QT_MAT_ESP','fullTime':'QT_MAT_BAS_INT'}
RESOURCES={'water':('Água potável',['IN_AGUA_POTAVEL']),'electricity':('Energia da rede pública',['IN_ENERGIA_REDE_PUBLICA']),'sewage':('Esgoto da rede pública',['IN_ESGOTO_REDE_PUBLICA']),'internet':('Internet',['IN_INTERNET']),'studentInternet':('Internet para alunos',['IN_INTERNET_ALUNOS']),'broadband':('Banda larga',['IN_BANDA_LARGA']),'computers':('Laboratório de informática',['IN_LABORATORIO_INFORMATICA']),'library':('Biblioteca ou sala de leitura',['IN_BIBLIOTECA','IN_SALA_LEITURA']),'sports':('Quadra esportiva',['IN_QUADRA_ESPORTES']),'accessibility':('Recursos de acessibilidade',['IN_ACESSIBILIDADE_INEXISTENTE']),'food':('Alimentação escolar',['IN_ALIMENTACAO'])}


def numeric(value,unit='%',count=False):
    if value is None or str(value).strip() in ('','--','-','ND','*','**','***','..','...'):return None
    n=float(str(value).strip().replace(',','.'))
    if not math.isfinite(n) or n<0 or (unit=='%' and n>100) or (unit=='IDEB' and n>10):raise ValueError(f'Valor inválido {value!r} ({unit})')
    if count and n!=int(n):raise ValueError('Contagem não inteira')
    return int(n) if count else n


def network(value):
    text=str(value).strip().title()
    special={'Total - Estadual E Municipal':'Estadual e Municipal','Total - Federal, Estadual E Municipal':'Pública','Total - Federal, Estadual, Municipal E Privada':'Total'}
    if text in special:return special[text]
    if text.startswith('Total'):return 'Total'
    if text.startswith('Pública'):return 'Pública'
    if text.startswith('Privada'):return 'Privada'
    if text in ('Municipal','Estadual','Federal'):return text
    raise ValueError(f'Rede não reconhecida: {value!r}')


def source_id(file):
    suffix=next((s for s in ('anos_iniciais','anos_finais','ensino_medio','regioes_ufs') if s in file['url']),'') if file['key']=='ideb' else ''
    return file['key']+'-'+file['reference']+('-'+suffix if suffix else '')


def metric(source,code,net,location,stage,kind,value,field,reference=None,unit='%'):
    n=numeric(value,unit)
    return {'code':code,'state':'PR','network':net,'location':location,'stage':stage,'metric':kind,'modality':'Regular' if source['key'] in ('ideb','saeb') else 'EJA' if 'EJA' in stage else 'Conforme universo do indicador INEP','value':n,'unit':unit,'reference':str(reference or source['reference']),'sourceId':source['id'],'field':field,'status':'available' if n is not None else 'notDisclosed'}


def machine_rows(sheet,regional=False):
    headers=None;human=[]
    for row in sheet.values:
        if headers is None:
            human.append(row)
            if 'CO_MUNICIPIO' in row or (regional and any(str(v).startswith('VL_OBSERVADO_') for v in row)):
                headers=list(row)
                if regional:
                    labels=next((r for r in human if 'Rede' in r and any('Unidade da Federação' in str(v) for v in r)),None)
                    if labels is None:raise ValueError('Cabeçalho territorial da UF ausente')
                    headers[labels.index('Rede')]='REDE'
                    headers[next(i for i,v in enumerate(labels) if 'Unidade da Federação' in str(v))]='NO_UF'
                valid=[v for v in headers if v is not None]
                duplicates={v for v in valid if valid.count(v)>1}
                # Official UF/AI 2025 repeats an unused rendimento header. We use
                # observed IDEB only; reject duplicate territorial/IDEB fields.
                if duplicates-{'VL_INDICADOR_REND_2023'}:raise ValueError('Colunas duplicadas')
                headers=[None if h in duplicates else h for h in headers]
            continue
        values={k:v for k,v in zip(headers,row) if k is not None}
        if regional:
            if values.get('NO_UF')!='Paraná':continue
            values['CO_MUNICIPIO']='41';values['SG_UF']='PR'
        elif str(values.get('CO_MUNICIPIO')) not in inep.MUNICIPALITIES:continue
        if values.get('SG_UF')!='PR' and values.get('CO_UF')!=41:raise ValueError('Indicador de UF divergente')
        yield values
    if headers is None:raise ValueError('Cabeçalho municipal oficial ausente')


def indicators(path,source):
    key=source['key'];out=[]
    for member,book in inep.workbooks(path):
        for sheet in book:
            if key=='saeb' and sheet.title not in ('Municípios','Estados'):continue
            if key=='literacy' and sheet.title=='Variáveis':continue
            regional=key=='ideb' and 'regioes_ufs' in source['url']
            if key=='saeb' and sheet.title=='Estados':continue # No same-schema municipal code; state handled separately later.
            stage='Anos iniciais' if 'iniciais' in member.lower() or '(AI)' in sheet.title else 'Anos finais' if 'finais' in member.lower() or '(AF)' in sheet.title else 'Ensino médio'
            for r in machine_rows(sheet,regional):
                code=str(r['CO_MUNICIPIO']);net=network(r.get('REDE',r.get('NO_TP_REDE',r.get('NO_DEPENDENCIA',r.get('DEPENDENCIA_ADM')))));loc=r.get('NO_CATEGORIA',r.get('LOCALIZACAO','Total'))
                if loc not in ('Total','Urbana','Rural'):raise ValueError('Localização inválida')
                ref=r.get('NU_ANO_CENSO',r.get('ANO_SAEB',r.get('ANO',source['reference'])))
                if str(ref)!=source['reference']:raise ValueError('Referência escolar divergente')
                if key=='ideb':
                    found=False
                    for field,v in r.items():
                        if re.fullmatch(r'VL_OBSERVADO_20\d{2}',str(field)):
                            out.append(metric(source,code,net,loc,stage,'ideb',v,field,field[-4:],'IDEB'));found=True
                    if not found:raise ValueError('Campos IDEB ausentes')
                elif key=='literacy':
                    for field,v in r.items():
                        if re.fullmatch(r'PC_ALUNO_ALFABETIZADO_20\d{2}',field):out.append(metric(source,code,net,loc,'2º ano do ensino fundamental','literacy',v,field,field[-4:]))
                        if field==f'META_FINAL_{ref}':out.append(metric(source,code,net,loc,'2º ano do ensino fundamental','literacyTarget',v,field))
                        if field=='PC_AVALIADOS_LP':out.append(metric(source,code,net,loc,'2º ano do ensino fundamental','literacyParticipation',v,field))
                elif key=='saeb':
                    for s,num in [('Anos iniciais','5'),('Anos finais','9'),('Ensino médio regular','12')]:
                        for subject,col in [('Língua Portuguesa','LP'),('Matemática','MT')]:
                            field=f'MEDIA_{num}_{col}'
                            if field not in r:raise ValueError('Proficiência SAEB ausente')
                            out.append(metric(source,code,net,loc,s,subject,r[field],field,unit='pontos SAEB'))
                elif key=='flow':
                    for field,v in r.items():
                        m=re.fullmatch(r'([123])_CAT_(FUN|FUN_AI|FUN_AF|MED)',field)
                        if m:
                            group,stem=m.groups();kind={'1':'flowApproval','2':'flowRepetition','3':'flowDropout'}[group]
                            out.append(metric(source,code,net,loc,STAGES[stem],kind,v,field))
                else:
                    for field,v in r.items():
                        m=re.fullmatch(r'(EDU_BAS|ED_INF|CRE|PRE|FUN|FUN_AI|FUN_AF|MED|EJA|EJA_FUN|EJA_MED)_CAT_(\d)',field)
                        if not m:continue
                        stem,group=m.groups();kind=f'{key}{group}' if key in ('afd','ied','ird') else key
                        out.append(metric(source,code,net,loc,STAGES[stem],kind,v,field,unit='alunos/turma' if key=='atu' else 'horas/dia' if key=='had' else '%'))
        book.close()
    if not out:raise ValueError(f'{key}: nenhum indicador dos municípios foi lido')
    return out


def synopsis_controls(path,source):
    controls=[]
    for member,book in inep.workbooks(path):
        sheets={sheet.title.strip():sheet for sheet in book}
        for name,kind in [('1.2','enrolments'),('2.2','teachers'),('3.2','schools'),('4.2','classes')]:
            if name not in sheets:raise ValueError(f'Sinopse: tabela {name} ausente')
            heads=[];positions=None
            for row in sheets[name].values:
                if positions is None:
                    heads.append(row)
                    if len(heads)>15:raise ValueError('Cabeçalho Sinopse não reconhecido')
                    group=next((h for h in heads if 'Rede Pública' in h and 'Rede Privada' in h),None)
                    sub=next((h for h in heads if 'Federal' in h and 'Estadual' in h and 'Municipal' in h),None)
                    territory=next((h for h in heads if 'Código do Município' in h and 'Unidade da Federação' in h),None)
                    if not(group and sub and territory):continue
                    positions={'code':territory.index('Código do Município'),'state':territory.index('Unidade da Federação'),'Total':group.index('Total'),'Privada':group.index('Rede Privada'),**{net:sub.index(net) for net in ('Federal','Estadual','Municipal')}}
                    continue
                code=str(row[positions['code']])
                if code not in inep.MUNICIPALITIES:continue
                if str(row[positions['state']]).strip()!='Paraná':raise ValueError('Sinopse UF divergente')
                for net in ('Total','Federal','Estadual','Municipal','Privada'):
                    controls.append({'code':code,'network':net,'reference':source['reference'],'kind':kind,'value':numeric(row[positions[net]],'contagem',True),'sheet':name,'sourceId':source['id']})
            if positions is None:raise ValueError('Sinopse sem cabeçalho territorial')
        book.close()
    if len(controls)!=80:raise ValueError('Sinopse: controles incompletos para os quatro municípios')
    return controls


def reconcile_controls(data):
    results=[]
    for control in data.get('officialControls',[]):
        row=next((r for r in data['census']['series'] if all(r[k]==control[k] for k in ('code','network','reference'))),None)
        if row is None:continue
        if control['kind']=='teachers':
            row['teachersOfficial']=control['value'];row['teachersSourceId']=control['sourceId'];continue
        actual=row['enrolments']['total'] if control['kind']=='enrolments' else row['activeSchools'] if control['kind']=='schools' else row['classes']
        if actual is None or actual!=control['value']:raise ValueError(f'Sinopse não confere: {control["code"]} {control["network"]} {control["kind"]}: {actual}/{control["value"]}')
        results.append({**control,'observed':actual,'status':'matched','tolerance':0})
    data['validation']={'officialChecks':results,'reference':max((r['reference'] for r in results),default=None),'status':'matched' if len(results)==60 and all(r['reference']==data['census']['reference'] for r in results) else 'pending','note':'Matrículas, escolas ativas e turmas conferidas com Sinopse 1.2, 3.2 e 4.2 nos quatro municípios e cinco redes. Docentes únicos lidos diretamente da tabela 2.2; não somados.'}


def aggregate_schools(rows,year):
    indexed={}
    for r in rows:
        identifier=r['CO_ENTIDADE']
        if not re.fullmatch(r'\d{8}',identifier):raise ValueError('Código INEP da escola inválido')
        if identifier in indexed:
            if indexed[identifier]!=r:raise ValueError('Escola duplicada com registros divergentes')
            continue
        if r['SG_UF']!='PR' or r['CO_MUNICIPIO'] not in inep.MUNICIPALITIES or r['NU_ANO_CENSO']!=str(year):raise ValueError('Censo territorial/ano divergente')
        if r['TP_DEPENDENCIA'] not in inep.NETWORKS or r['TP_LOCALIZACAO'] not in inep.LOCATIONS or r['TP_SITUACAO_FUNCIONAMENTO'] not in inep.SITUATIONS:raise ValueError('Código escolar desconhecido')
        indexed[identifier]=r
    records=[];schools=[];infra=[]
    for code in inep.MUNICIPALITIES:
        territorial=[r for r in indexed.values() if r['CO_MUNICIPIO']==code];active=[r for r in territorial if r['TP_SITUACAO_FUNCIONAMENTO']=='1' and r.get('QT_MAT_BAS') not in (None,'','--')]
        missing=[r for r in territorial if r['TP_SITUACAO_FUNCIONAMENTO']=='1' and r.get('QT_MAT_BAS') in (None,'','--')]
        if any(r.get('IN_REGULAR')=='1' or r.get('IN_EJA')=='1' or r.get('IN_PROF')=='1' for r in missing):raise ValueError('Escola com escolarização declarada e matrículas ausentes')
        if not active:raise ValueError(f'{code}: nenhuma escola ativa; confirmar cobertura antes de publicar zero')
        for net in ('Total',*inep.NETWORKS.values()):
            group=[r for r in active if net=='Total' or inep.NETWORKS[r['TP_DEPENDENCIA']]==net]
            counts={k:sum(numeric(r.get(field),unit='matrículas',count=True) or 0 for r in group) if all(r.get(field) not in (None,'','--') for r in group) else None for k,field in ENROLMENTS.items()}
            if counts['total'] is None:raise ValueError('Total de matrículas ausente nas escolas ativas')
            for total,a,b in [('infant','nursery','preschool'),('fundamental','initial','final')]:
                if all(counts[k] is not None for k in (total,a,b)) and counts[total]!=counts[a]+counts[b]:raise ValueError('Subetapas não reconciliadas')
            def summed(field):return sum(int(r[field]) for r in group) if all(r.get(field) not in (None,'') for r in group) else None
            records.append({'code':code,'state':'PR','reference':str(year),'network':net,'enrolments':counts,'activeSchools':len(group),'teachingPosts':summed('QT_DOC_BAS'),'classes':summed('QT_TUR_BAS'),'locations':[{'label':label,'schools':sum(r['TP_LOCALIZACAO']==loc for r in group),'enrolments':sum(int(r['QT_MAT_BAS']) for r in group if r['TP_LOCALIZACAO']==loc)} for loc,label in inep.LOCATIONS.items()]})
            for k,(label,fields) in RESOURCES.items():
                values=[]
                for r in group:
                    flags=[numeric(r.get(f),unit='boolean',count=True) for f in fields]
                    if any(v not in (None,0,1) for v in flags):raise ValueError('Flag escolar inválida')
                    value=1 if 1 in flags else 0 if all(v==0 for v in flags) else None
                    if k=='accessibility' and value is not None:value=1-value
                    values.append(value)
                known=[v for v in values if v is not None];yes=sum(known)
                infra.append({'code':code,'network':net,'reference':str(year),'id':k,'label':label,'fields':fields,'withResource':yes,'considered':len(known),'activeSchools':len(group),'missing':len(group)-len(known),'percent':round(yes/len(known)*100,2) if known else None})
        for r in territorial:
            schools.append({'code':r['CO_ENTIDADE'],'municipalityCode':code,'name':r['NO_ENTIDADE'],'network':inep.NETWORKS[r['TP_DEPENDENCIA']],'location':inep.LOCATIONS[r['TP_LOCALIZACAO']],'situation':inep.SITUATIONS[r['TP_SITUACAO_FUNCIONAMENTO']],'active':r['TP_SITUACAO_FUNCIONAMENTO']=='1','inBasicEducationUniverse':r.get('QT_MAT_BAS') not in (None,'','--'),'reference':str(year),'stages':[k for k,f in ENROLMENTS.items() if k not in ('total','special','fullTime') and numeric(r.get(f),unit='matrículas',count=True) not in (None,0)]})
    return records,schools,infra


def validate(data):
    if data['schemaVersion']!=1 or data['municipality']!={'code':'4127965','name':'Turvo','state':'PR'}:raise ValueError('Schema/território Educação inválido')
    seen=set()
    for s in data['schools']:
        key=(s['municipalityCode'],s['code'])
        if key in seen:raise ValueError('Escola repetida no catálogo')
        seen.add(key)
        if not re.fullmatch(r'\d{8}',s['code']) or s['municipalityCode'] not in inep.MUNICIPALITIES:raise ValueError('Código de escola/município inválido')
    seen=set()
    for row in data['indicators']:
        key=tuple(row[k] for k in ('sourceId','code','network','location','stage','metric','reference'))
        if key in seen:raise ValueError('Indicador duplicado')
        seen.add(key)
        if row['code'] not in (*inep.MUNICIPALITIES,'41') or row['state']!='PR' or row['sourceId'] not in {s['id'] for s in data['sources']}:raise ValueError('Indicador sem proveniência territorial')
        if row['location'] not in ('Total','Urbana','Rural') or row['network'] not in ('Total','Pública','Federal','Estadual','Municipal','Privada','Estadual e Municipal'):raise ValueError('Recorte educacional inválido')
        if row['status']!=('notDisclosed' if row['value'] is None else 'available'):raise ValueError('Estado de divulgação incoerente')
        numeric(row['value'],row['unit'])
    groups={}
    for r in data['indicators']:
        if r['metric'].startswith('flow') and r['value'] is not None:groups.setdefault(tuple(r[k] for k in ('code','network','location','stage','reference')),[]).append(r['value'])
    for g in groups.values():
        if len(g)==3 and abs(sum(g)-100)>.21:raise ValueError('Rendimento não soma 100% dentro do arredondamento')
    for r in data['census']['series']:
        if r['code'] not in inep.MUNICIPALITIES or r['state']!='PR':raise ValueError('Censo de território inválido')
        for v in r['enrolments'].values():numeric(v,'matrículas',True)
    for r in data['infrastructure']:
        if r['considered']+r['missing']!=r['activeSchools'] or r['withResource']>r['considered']:raise ValueError('Denominador escolar incoerente')
        for k in ('considered','missing','activeSchools','withResource'):numeric(r[k],'escolas',True)
        numeric(r['percent'])
        expected=round(r['withResource']/r['considered']*100,2) if r['considered'] else None
        if r['percent']!=expected:raise ValueError('Percentual escolar não confere com denominador')


def empty():return {'schemaVersion':1,'municipality':{'code':'4127965','name':'Turvo','state':'PR'},'summary':{},'census':{'reference':None,'series':[]},'schools':[],'infrastructure':[],'indicators':[],'sources':[],'collection':{'failures':[]},'limitations':['Matrículas não são estudantes únicos.','Docências somadas por escola não deduplicam professores entre escolas.','Educação especial e profissional são recortes sobrepostos; não somar todas as modalidades.']}


def enrich_metadata(data):
    data['census']['units']={'enrolments':'matrículas','activeSchools':'escolas','classes':'turmas','teachingPosts':'docências somadas por escola','teachersOfficial':'docentes deduplicados no universo da Sinopse'}
    for r in data['infrastructure']:r['unit']='%'
    for r in data['indicators']:
        key=next(s['key'] for s in data['sources'] if s['id']==r['sourceId'])
        r['modality']='Regular' if key in ('ideb','saeb') else 'EJA' if 'EJA' in r['stage'] else 'Conforme universo do indicador INEP'
    for source in data['sources']:
        source['fieldsUsed']=sorted({r['field'] for r in data['indicators'] if r['sourceId']==source['id']})
        if source['key']=='synopsis':source['fieldsUsed']=['Código do Município','Unidade da Federação','Total','Rede Pública','Rede Privada','Federal','Estadual','Municipal']
        if source['key']=='census':
            expected={'NU_ANO_CENSO','CO_MUNICIPIO','SG_UF','CO_ENTIDADE','NO_ENTIDADE','TP_DEPENDENCIA','TP_LOCALIZACAO','TP_SITUACAO_FUNCIONAMENTO','IN_REGULAR','IN_EJA','IN_PROF','QT_DOC_BAS','QT_TUR_BAS',*ENROLMENTS.values(),*(f for _,fields in RESOURCES.values() for f in fields)}
            source['fieldsUsed']=sorted(expected & set(source.get('fieldsAvailable',expected)))
            source['fieldsAvailable']=source['fieldsUsed']
            source['transformations']=['Junção dos agregados por CO_ENTIDADE na edição com tabelas separadas; filtro IBGE + UF + ano.', 'Resumo: escolas em atividade com matrículas da educação básica informadas; estabelecimentos exclusivamente fora desse universo não recebem matrículas zero.', 'Soma de matrículas e turmas por rede/localização; educação especial/profissional não adicionadas ao total.', 'Docências por escola não são docentes únicos; docentes oficiais lidos da Sinopse 2.2. Infraestrutura usa apenas flags conhecidos, com denominador por recurso.']
        elif source['key']=='ideb':source['transformations']+=['Somente VL_OBSERVADO_AAAA; sem média entre etapas; metas do primeiro ciclo não extrapoladas. Cabeçalho duplicado de rendimento VL_INDICADOR_REND_2023 na planilha UF/AI 2025 é ignorado, pois não é usado nesta integração.'] if not any('VL_OBSERVADO' in t for t in source['transformations']) else []
    data['limitations']=list(dict.fromkeys(data['limitations']+['Escolarização declarada com total ausente causa falha; estabelecimentos fora do universo de matrículas são identificados separadamente no catálogo.','Indicadores anuais de formação, rendimento, distorção e condições de ensino: edição 2025 nesta primeira integração; séries anteriores serão ampliadas.','A reorganização do Censo 2025 em quatro tabelas foi validada pelo dicionário; mudanças de etapas e oferta ao longo da série exigem cautela.','Mapa de escolas, ENEM, Educação Superior e financiamento ficam para evolução própria.']))


def exports(directory,data):
    target=Path(directory)/'exports';target.mkdir(exist_ok=True,parents=True)
    datasets={'education-enrolments':[{**{k:r[k] for k in ('code','network','reference','activeSchools','teachingPosts','classes','sourceId')},'teachersOfficial':r.get('teachersOfficial'),'teachersSourceId':r.get('teachersSourceId'),**r['enrolments']} for r in data['census']['series']],'education-schools':data['schools'],'education-infrastructure':data['infrastructure'],'education-ideb':[r for r in data['indicators'] if r['metric']=='ideb'],'education-flow':[r for r in data['indicators'] if r['metric'].startswith('flow')],'education-indicators':data['indicators']}
    for name,rows in datasets.items():
        if not rows:continue
        sources={s['id']:s for s in data['sources']}
        enriched=[]
        for r in rows:
            source=sources.get(r.get('sourceId')) or next((s for s in data['sources'] if s['key']=='census' and s['reference']==r['reference']),{})
            enriched.append({**r,'agency':'INEP','collectedAt':source.get('collectedAt'),'officialUrl':source.get('officialUrl'),'sourceUrl':source.get('url')})
        rows=enriched
        buf=io.StringIO();fields=list(dict.fromkeys(k for row in rows for k in row));writer=csv.DictWriter(buf,fields,extrasaction='raise',lineterminator='\n');writer.writeheader()
        writer.writerows({k:' | '.join(str(v) for v in value) if isinstance(value,list) else value for k,value in r.items()} for r in rows)
        (target/(name+'.csv')).write_text(buf.getvalue(),encoding='utf-8')


def sync_catalog(directory,data):
    path=Path(directory)/'indicators.json';catalog=read(path,None)
    if not catalog:return
    census=next((r for r in data['census']['series'] if r['code']=='4127965' and r['network']=='Total' and r['reference']==data['census']['reference']),None)
    if census:
        source=next(s for s in data['sources'] if s['id']==census['sourceId'])
        indicator={'id':'basic-education-enrolments','module':'education','title':'Matrículas na educação básica','value':census['enrolments']['total'],'unit':'matrículas','source':'INEP / Censo Escolar','agency':'INEP','reference':census['reference'],'url':source['officialUrl'],'collectedAt':source['collectedAt'],'municipalityCode':'4127965','status':'real','series':[{'period':r['reference'],'value':r['enrolments']['total']} for r in data['census']['series'] if r['code']=='4127965' and r['network']=='Total'],'note':'Todas as redes. Matrículas não representam estudantes únicos; educação especial não é somada como etapa.'}
    else:indicator={'id':'basic-education-enrolments','module':'education','title':'Matrículas na educação básica','value':None,'unit':'matrículas','source':'INEP / Censo Escolar','agency':'INEP','reference':'Não disponível','url':inep.PORTAL+inep.PAGES['census'],'collectedAt':None,'municipalityCode':'4127965','status':'unavailable','series':[]}
    catalog['indicators']=[i for i in catalog['indicators'] if i['module']!='education']+[indicator];catalog['indicators'].sort(key=lambda i:(i['module'],i['id']));atomic_write(path,catalog)


def update(directory,offline=False,force=False,cache=None,year=None,history_start=2015):
    directory=Path(directory);snapshot=directory/'education.json';previous=read(snapshot,empty());data=copy.deepcopy(previous)
    if offline:validate(data);return data
    now=datetime.now(timezone.utc).isoformat();failures=[];changed=False;valid_data=copy.deepcopy(data)
    try:manifest=inep.discover(year,history_start)
    except Exception as exc:
        failures.append(f'Catálogo INEP: {exc}');manifest={}
    with tempfile.TemporaryDirectory(prefix='turvo-inep-') as tmp:
        folder=Path(cache or tmp)
        for key,files in manifest.items():
            for file in sorted(files,key=lambda f:f['reference']):
                identifier=source_id(file);old=next((s for s in data['sources'] if s['id']==identifier),None)
                if old and old['url']==file['url'] and not force:continue
                try:
                    path=folder/file['url'].rsplit('/',1)[-1];meta=inep.download(file['url'],path,force)
                    source={**file,**meta,'id':identifier,'agency':'INEP','collectedAt':now,'format':'CSV cp1252; separado por ponto e vírgula' if key=='census' else 'XLSX; cabeçalhos oficiais; openpyxl 3.1.5','transformations':['Filtro explícito de código IBGE e UF; ausentes preservados como null; sem imputação.']}
                    if key=='census':
                        observed_fields=set()
                        def observed_rows():
                            for raw in inep.census_rows(path,int(file['reference'])):
                                observed_fields.update(raw);yield raw
                        records,schools,infra=aggregate_schools(observed_rows(),int(file['reference']))
                        source['fieldsAvailable']=sorted(observed_fields)
                        for r in records:r['sourceId']=identifier
                        data['census']['series']=[r for r in data['census']['series'] if r['reference']!=file['reference']]+records
                        latest=max(r['reference'] for r in data['census']['series']);data['census']['reference']=latest
                        if file['reference']==latest:data['schools']=schools;data['infrastructure']=infra
                    elif key=='synopsis':
                        data['officialControls']=synopsis_controls(path,source)
                    else:
                        rows=indicators(path,source);data['indicators']=[r for r in data['indicators'] if r['sourceId']!=identifier]+rows
                    data['sources']=[s for s in data['sources'] if s['id']!=identifier]+[source]
                    reconcile_controls(data);validate(data);changed=True;print(f'{key} {file["reference"]}: validado.',flush=True)
                except Exception as exc:
                    # Per-source rollback, including schema failures; leave last valid values intact.
                    data=copy.deepcopy(previous if not data['sources'] else valid_data)
                    failures.append(f'{identifier}: {type(exc).__name__}: {exc}');print(f'FALHA {identifier}: {exc}',flush=True)
                valid_data=copy.deepcopy(data)
    if not changed and not failures and not previous['collection']['failures']:
        validate(previous);return previous # No new publication: no timestamp/commit churn.
    enrich_metadata(data)
    data['summary']=next((copy.deepcopy(r) for r in data['census']['series'] if r['code']=='4127965' and r['network']=='Total' and r['reference']==data['census']['reference']),{})
    data['census']['series'].sort(key=lambda r:(r['reference'],r['code'],r['network']))
    data['collection']={'attemptedAt':now,'lastSuccessAt':now if manifest and not failures else previous['collection'].get('lastSuccessAt'),'failures':failures,'policy':'Verificação mensal leve; downloads anuais/ciclos só quando nova edição; --force verifica revisões.'}
    validate(data);atomic_write(snapshot,data);exports(directory,data);sync_catalog(directory,data);return data
