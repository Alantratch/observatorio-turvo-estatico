"""Annual RAIS stock and revised Novo CAGED flows. Never derives stock from flows."""
import copy
import csv
import hashlib
import io
import json
import math
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from scripts.common import atomic_write, read
from scripts.sources import mte

SM = {'2024': 1412, '2025': 1518, '2026': 1621}
SM_URL = 'https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12797.htm'
PRIVACY_MIN = 5


def months_between(start, end):
    a, b = int(start[:4])*12+int(start[-2:])-1, int(end[:4])*12+int(end[-2:])-1
    if b<a or start<'202001' or not 1<=int(start[-2:])<=12 or not 1<=int(end[-2:])<=12:
        raise ValueError('Janela Novo CAGED inválida')
    return [f'{v//12:04}{v%12+1:02}' for v in range(a,b+1)]


def window_start(latest, length=24):
    v=int(latest[:4])*12+int(latest[-2:])-length
    return f'{v//12:04}{v%12+1:02}'


def empty_counts(): return {'admissions': 0, 'dismissals': 0, 'balance': 0}


def add_counts(target, sign, weight):
    if sign not in (-1,1): raise ValueError('Saldo de movimentação deve ser -1 ou 1')
    target['admissions' if sign==1 else 'dismissals'] += weight
    target['balance'] += sign*weight


def totals(rows):
    return {k:sum(row[k] for row in rows) for k in empty_counts()}


def validate_counts(row):
    for k in empty_counts():
        if type(row[k]) is not int: raise ValueError('Contagem não inteira')
    if row['admissions']<0 or row['dismissals']<0 or row['balance']!=row['admissions']-row['dismissals']:
        raise ValueError('Movimentações inconsistentes após ajustes')


def aggregate_caged(records, kind, publication, start, end, acc):
    for r in records:
        ref=r['competenciamov']
        if ref < start or ref>end: continue
        if not ref.isdigit() or not 1<=int(ref[-2:])<=12: raise ValueError('Competência inválida')
        if (kind=='EXC' and (r['indicadordeexclusao']!='1' or r['competenciaexc']!=publication)) or (kind!='EXC' and r['competenciadec']!=publication):
            raise ValueError('Arquivo não corresponde à competência de declaração/exclusão')
        if kind=='MOV' and (ref!=publication or r['indicadordeforadoprazo']!='0'): raise ValueError('MOV fora do prazo/período')
        if kind=='FOR' and r['indicadordeforadoprazo']!='1': raise ValueError('FOR sem indicador de atraso')
        sign=int(r['saldomovimentacao']); weight=-1 if kind=='EXC' else 1
        move=r['tipomovimentacao'].zfill(2)
        if move not in mte.CLASSIFICATIONS['movements']: raise ValueError('Tipo de movimento não catalogado')
        # Codes 97/98 are the eSocial admission/dismissal types; 99 is unknown and rejected.
        if (sign==1 and move not in ('10','20','25','35','70','97')) or (sign==-1 and move not in ('31','32','33','40','43','45','50','60','80','90','98')):
            raise ValueError('Tipo de movimento e sinal incompatíveis')
        group=mte.sector(r['secao']); cnae=r['subclasse'].zfill(7); cbo=r['cbo2002ocupacao'].zfill(6)
        if cnae not in mte.CLASSIFICATIONS['cnae']:
            if not cnae.isdigit() or len(cnae)!=7: raise ValueError('Código CNAE inválido')
            cnae='unknown'
        if cbo not in mte.CLASSIFICATIONS['cbo']:
            if not cbo.isdigit() or len(cbo)!=6: raise ValueError('Código CBO inválido')
            cbo='unknown'  # Valid code absent from published dictionary: no invented occupational title.
        key=(r['code'], ref); bucket=acc.setdefault(key, {'counts':empty_counts(), 'sectors':{}, 'activities':{}, 'occupations':{}, 'salarySum':0.0,'salaryCount':0})
        add_counts(bucket['counts'],sign,weight)
        for axis,value in [('sectors',group),('activities',cnae),('occupations',cbo)]:
            add_counts(bucket[axis].setdefault(value,empty_counts()),sign,weight)
        salary=mte.decimal(r['salario']); minimum=SM.get(ref[:4])
        if sign==1 and minimum and salary is not None and 0.3*minimum<=salary<=150*minimum and r['indtrabintermitente']=='0':
            bucket['salarySum']+=salary*weight; bucket['salaryCount']+=weight


def protected_categories(rows, labels):
    """Release one dimension; merge any positive count 1..4 into Others.
    If Others would itself reveal a small count, merge the smallest visible group.
    If the complete dimension is too small, suppress the entire breakdown.
    """
    visible=[]; other=[]
    for code,count in rows.items():
        validate_counts(count)
        if not count['admissions'] and not count['dismissals']: continue
        record={'code':code,'label':labels[code],**count}
        (other if any(0<v<PRIVACY_MIN for v in [count['admissions'],count['dismissals']]) else visible).append(record)
    if other:
        combined=totals(other)
        while visible and any(0<v<PRIVACY_MIN for v in [combined['admissions'],combined['dismissals']]):
            other.append(min(visible,key=lambda r:r['admissions']+r['dismissals'])); visible.remove(other[-1]); combined=totals(other)
        if any(0<v<PRIVACY_MIN for v in [combined['admissions'],combined['dismissals']]): return [],'suppressed'
        visible.append({'code':'other','label':'Outras categorias (agregadas)',**combined})
    return sorted(visible,key=lambda r:(-r['admissions'],r['label'])),'aggregated' if other else 'complete'


def finalize_caged(acc, start, latest, manifests, collected_at):
    expected=months_between(start,latest); output={}
    for code in mte.MUNICIPALITIES:
        rows=[]; all_sectors=[]; all_occupations=[]; all_activities=[]
        for month in expected:
            b=acc.get((code,month), {'counts':empty_counts(),'sectors':{},'activities':{},'occupations':{},'salarySum':0.,'salaryCount':0})
            validate_counts(b['counts'])
            if b['salaryCount']<0: raise ValueError('Amostra salarial negativa')
            sectors=[{'code':k,'label':v,**b['sectors'].get(k,empty_counts())} for k,v in mte.SECTORS.items()]
            for axis in ['sectors','activities','occupations']:
                for count in b[axis].values():validate_counts(count)
                if totals(b[axis].values())!=b['counts']:raise ValueError('Total por classificação divergente')
            occupations,op=protected_categories(b['occupations'],{**mte.CLASSIFICATIONS['cbo'],'unknown':'Ocupações sem descrição validada (agregadas)'})
            activities,ap=protected_categories(b['activities'],{**mte.CLASSIFICATIONS['cnae'],'unknown':'Atividades sem descrição validada (agregadas)'})
            ref=month[:4]+'-'+month[-2:]
            rows.append({'period':ref,**b['counts'],'admissionSalary':round(b['salarySum']/b['salaryCount'],2) if b['salaryCount']>=PRIVACY_MIN else None,'salarySample':b['salaryCount'] if b['salaryCount']>=PRIVACY_MIN else None,'salaryStatus':'available' if month[:4] in SM and b['salaryCount']>=PRIVACY_MIN else 'unavailable'})
            all_sectors += [{'period':ref,**r} for r in sectors]
            all_occupations += [{'period':ref,**r} for r in occupations]
            all_activities += [{'period':ref,**r} for r in activities]
            if month==latest: breakdown={'sectors':sectors,'occupations':occupations,'activities':activities,'occupationPrivacy':op,'activityPrivacy':ap,'occupationDictionaryComplete':'unknown' not in b['occupations'],'activityDictionaryComplete':'unknown' not in b['activities']}
        year=latest[:4]; ytd_rows=[r for r in rows if r['period'].startswith(year+'-')]
        def window(wanted):
            selected=[r for r in rows if r['period'].replace('-','') in wanted]
            if len(selected)!=len(wanted): return {'status':'unavailable','reason':'Janela incompleta; não somamos meses ausentes.'}
            return {'status':'available','from':selected[0]['period'],'to':selected[-1]['period'],**totals(selected)}
        output[code]={'status':'available','latestReference':rows[-1]['period'],'adjustedThrough':rows[-1]['period'],'sourceId':'caged','methodology':'novo-caged-MOV-FOR-EXC-2021','unit':'movimentações de vínculos celetistas','collectedAt':collected_at,'monthly':rows,'yearToDate':window(months_between(year+'01',latest)),'rolling12Months':window(months_between(window_start(latest,12),latest)),**breakdown,'sectorSeries':all_sectors,'occupationSeries':all_occupations,'activitySeries':all_activities,'salaryMethod':'Média do salário mensal declarado (salário), admissões não intermitentes entre 0,3 e 150 salários mínimos da competência; ajustes FOR e EXC aplicados. Nominal, não é renda populacional. Amostra mínima de 5.'}
    return output


def rais_table(path, collected_at):
    sheets=mte.xlsx_rows(path); rows=sheets.get('TABELA 4')
    if not rows: raise ValueError('RAIS sem TABELA 4 municipal')
    header=next((r for r in rows if 'Código' in r.values() and 'UF' in r.values()),None)
    if not header: raise ValueError('Layout municipal RAIS alterado')
    hindex=rows.index(header); years=rows[hindex+1]
    group=None; columns=defaultdict(dict); codecol=next(k for k,v in header.items() if v=='Código'); ufcol=next(k for k,v in header.items() if v=='UF')
    label_map={v:k for k,v in mte.SECTORS.items()}; label_map['Total']='total'
    for col,value in header.items():
        if value in label_map:group=label_map[value]
        year=years.get(col)
        if group and year and re_year(year):columns[year][group]=col
    if not columns or any(set(c)!=set(mte.SECTORS)|{'total'} for c in columns.values()):raise ValueError('Grupos/anos RAIS inesperados')
    result={}; evidence=[]
    for r in rows[hindex+2:]:
        code=mte.territory(r.get(codecol), '41' if r.get(ufcol)=='PR' else '')
        if not code:continue
        if code in result:raise ValueError('Município duplicado na tabela RAIS')
        series=[]
        for year,cols in sorted(columns.items()):
            stock=int(r[cols['total']]); sectors=[{'code':k,'label':v,'stock':int(r[cols[k]]),'share':round(int(r[cols[k]])/stock*100,2) if stock else 0} for k,v in mte.SECTORS.items()]
            if sum(s['stock'] for s in sectors)!=stock:raise ValueError('Soma setorial RAIS divergente do total oficial')
            series.append({'period':year,'stock':stock,'sectors':sectors})
        result[code]={'status':'available','reference':series[-1]['period'],'stock':{'value':series[-1]['stock'],'unit':'vínculos formais ativos em 31/12'},'sectors':series[-1]['sectors'],'series':series,'sourceId':'rais','methodology':'rais-active-31dec-table4-esocial-2023','collectedAt':collected_at,'remuneration':{'status':'unavailable','value':None,'reason':'Tabela municipal 4 não publica remuneração; requer microdados de vínculos validados.'},'establishments':{'status':'unavailable','value':None,'reason':'Sem integração validada da RAIS Estabelecimento. Não contamos empresas a partir dos vínculos.'}}
        evidence.append(r)
    if set(result)!=set(mte.MUNICIPALITIES):raise ValueError('Tabela RAIS sem os quatro municípios')
    return result, {'sheet':'TABELA 4','header':header,'periods':years,'rows':evidence}


def re_year(value):return str(value).isdigit() and 2023<=int(value)<=2100


def revisions(previous, current, now):
    old={r['period']:r for r in previous.get('monthly',[])}; changes=[]
    for row in current.get('monthly',[]):
        before=old.get(row['period'])
        if before and any(before.get(k)!=row.get(k) for k in ['admissions','dismissals','balance','admissionSalary']):
            changes.append({'period':row['period'],'revisionDetectedAt':now,'previous':{k:before.get(k) for k in ['admissions','dismissals','balance','admissionSalary']},'current':{k:row.get(k) for k in ['admissions','dismissals','balance','admissionSalary']}})
    return changes


def validate(data):
    if data['schemaVersion']!=1 or data['municipality']['code']!='4127965':raise ValueError('Schema/território incorreto')
    if set(data['comparisons'])!=set(mte.MUNICIPALITIES):raise ValueError('Comparadores ausentes')
    for code,peer in data['comparisons'].items():
        if peer['municipality']['code']!=code or peer['municipality']['state']!='PR':raise ValueError('Território divergente')
        rais=peer['rais'];caged=peer['caged']
        if rais['status']=='available':
            remuneration=rais.get('remuneration',{})
            if remuneration.get('status')=='available':
                if not math.isfinite(remuneration['value']) or remuneration['value']<=0 or not PRIVACY_MIN<=remuneration['sample']<=rais['stock']['value']:raise ValueError('Remuneração/amostra RAIS inválida')
                if remuneration['missingOrZero']+remuneration['sample']!=rais['stock']['value']:raise ValueError('Cobertura salarial RAIS inválida')
            if not rais['collectedAt'] or rais['stock']['value']!=sum(r['stock'] for r in rais['sectors']):raise ValueError('RAIS inválida')
            for row in rais['series']:
                if row['stock']<0 or row['stock']!=sum(r['stock'] for r in row['sectors']):raise ValueError('Série RAIS inválida')
        if caged['status']=='available':
            proof=caged.get('validation',{})
            if proof.get('status')=='matched':
                if any(proof['nationalCounts'][k]!=proof['officialCounts'][k] for k in empty_counts()):raise ValueError('Controle nacional MTE divergente')
            monthly=caged['monthly']; periods=[r['period'] for r in monthly]
            expected=[m[:4]+'-'+m[-2:] for m in months_between(periods[0].replace('-',''),periods[-1].replace('-',''))]
            if periods!=expected or caged['latestReference']!=periods[-1]:raise ValueError('Série CAGED descontínua')
            for row in monthly:validate_counts(row)
            if totals(caged['sectors'])!={k:monthly[-1][k] for k in empty_counts()}:raise ValueError('CAGED setorial divergente')
            for key in ['yearToDate','rolling12Months']:
                window=caged[key]
                if window['status']=='available':
                    selected=[r for r in monthly if window['from']<=r['period']<=window['to']]
                    if any(window[k]!=totals(selected)[k] for k in empty_counts()):raise ValueError('Acumulado divergente')
                    if key=='yearToDate' and window['from']!=caged['latestReference'][:4]+'-01':raise ValueError('Acumulado sem janeiro')
                    if key=='rolling12Months' and len(selected)!=12:raise ValueError('Janela móvel sem 12 meses')
            for axis in ['occupations','activities']:
                if caged[axis] and totals(caged[axis])!={k:monthly[-1][k] for k in empty_counts()}:raise ValueError('Categorias protegidas sem conservação do total')
                for r in caged[axis]:
                    if any(0<r[k]<PRIVACY_MIN for k in ['admissions','dismissals']):raise ValueError('Célula pequena publicada')
    if data['rais']!=data['comparisons']['4127965']['rais'] or data['caged']!=data['comparisons']['4127965']['caged']:raise ValueError('Turvo e comparador divergentes')


def sync_catalog(data_dir, data):
    catalog=read(Path(data_dir)/'indicators.json',{});items=catalog['indicators']; items[:]=[i for i in items if i['module']!='employment']
    r,c=data['rais'],data['caged']; spec=[('formal-employment-stock','Vínculos formais',r,'rais','vínculos', r.get('stock',{}).get('value'), [{'period':p['period'],'value':p['stock']} for p in r.get('series',[])]),('caged-balance','Saldo de vínculos no mês',c,'caged','vínculos',c.get('monthly',[{}])[-1].get('balance') if c.get('monthly') else None,[{'period':p['period'],'value':p['balance']} for p in c.get('monthly',[])])]
    for id,title,base,source,unit,value,series in spec:
        official=base['status']=='available';url=next(s['url'] for s in data['sources'] if s['id']==source)
        items.append({'id':id,'module':'employment','title':title,'value':value,'unit':unit,'source':'MTE / '+('RAIS' if source=='rais' else 'Novo CAGED'),'agency':'Ministério do Trabalho e Emprego','reference':base.get('reference',base.get('latestReference')) or 'Não disponível','url':url,'collectedAt':base.get('collectedAt') if official else None,'municipalityCode':'4127965','status':'real' if official else 'unavailable','series':series,'methodology':'rais-stock-31dec' if source=='rais' else 'novo-caged-adjusted-flows','note':'Vínculos, não pessoas únicas. RAIS: estoque anual. Novo CAGED: admissões menos desligamentos; saldo não é estoque.'})
    items.sort(key=lambda i:(i['module'],i['id']))
    atomic_write(Path(data_dir)/'indicators.json',catalog)


def exports(data_dir, data):
    directory=Path(data_dir)/'exports';directory.mkdir(exist_ok=True)
    specs={'caged-monthly':('caged','monthly',['period','admissions','dismissals','balance','admissionSalary','salarySample']),'caged-sectors':('caged','sectorSeries',['period','code','label','admissions','dismissals','balance']),'caged-occupations':('caged','occupationSeries',['period','code','label','admissions','dismissals','balance']),'caged-activities':('caged','activitySeries',['period','code','label','admissions','dismissals','balance']),'rais-stock':('rais','series',['period','stock','remunerationNominalDecember','remunerationSample','remunerationMissingOrZero','remunerationCollectedAt']),'rais-sectors':('rais','sectorSeries',['period','code','label','stock','share','remunerationNominalDecember','remunerationSample','remunerationCollectedAt'])}
    for name,(source,key,fields) in specs.items():
        output=io.StringIO();columns=['municipalityCode','municipality','state','source','collectedAt']+fields;writer=csv.DictWriter(output,fieldnames=columns,delimiter=';',extrasaction='ignore');writer.writeheader()
        for code,peer in data['comparisons'].items():
            base=peer[source]; rows=base.get(key,[])
            if key=='sectorSeries' and source=='rais':rows=[{'period':p['period'],**r} for p in base.get('series',[]) for r in p['sectors']]
            if name=='rais-stock':
                rows=[{**r,**({'remunerationNominalDecember':base.get('remuneration',{}).get('value'),'remunerationSample':base.get('remuneration',{}).get('sample'),'remunerationMissingOrZero':base.get('remuneration',{}).get('missingOrZero'),'remunerationCollectedAt':base.get('remuneration',{}).get('collectedAt')} if r['period']==base.get('reference') else {})} for r in rows]
            if name=='rais-sectors':
                salaries={s['code']:s for s in base.get('remuneration',{}).get('sectors',[])}
                rows=[{**r,**({'remunerationNominalDecember':salaries.get(r['code'],{}).get('value'),'remunerationSample':salaries.get(r['code'],{}).get('sample'),'remunerationCollectedAt':base.get('remuneration',{}).get('collectedAt')} if r['period']==base.get('reference') else {})} for r in rows]
            for r in rows:writer.writerow({'municipalityCode':code,'municipality':peer['municipality']['name'],'state':'PR','source':'RAIS' if source=='rais' else 'Novo CAGED','collectedAt':base.get('collectedAt'),**r})
        target=directory/(name+'.csv');temporary=target.with_suffix('.csv.part');temporary.write_text('\ufeff'+output.getvalue(),encoding='utf-8');os.replace(temporary,target)


def blank():
    peers={code:{'municipality':{'code':code,'mteCode':next(k for k,v in mte.TERRITORIES.items() if v==code),'name':name,'state':'PR'},'rais':{'status':'unavailable','reference':None,'collectedAt':None,'reason':'Sem coleta validada'},'caged':{'status':'unavailable','latestReference':None,'collectedAt':None,'monthly':[],'reason':'Sem coleta validada'}} for code,name in mte.MUNICIPALITIES.items()}
    return {'schemaVersion':1,'municipality':peers['4127965']['municipality'],'comparisons':peers,'rais':peers['4127965']['rais'],'caged':peers['4127965']['caged'],'sources':[],'collection':{'attemptedAt':None,'lastSuccessAt':None,'failures':[]},'revisions':[]}


def source_info(id,ref,now,files):
    return {'id':id,'agency':'Ministério do Trabalho e Emprego / PDET','dataset':'RAIS' if id=='rais' else 'Novo CAGED','reference':ref if id=='rais' else (ref[:4]+'-'+ref[-2:] if ref.isdigit() else ref),'collectedAt':now,'url':mte.PORTAL+('/rais' if id=='rais' else '/novo-caged'),'microdataUrl':mte.PORTAL+'/microdados-rais-e-caged','territorialCodes':mte.TERRITORIES,'unit':'vínculos / movimentações / R$ nominais','classificationSources':{'cbo':mte.CLASSIFICATIONS.get('cboSource'), 'cnae':mte.CLASSIFICATIONS['source']},'layout':('RAIS Tabela 4 · cabeçalhos UF, Código, grupos e anos'+ ('; microdados RAIS 2025 CSV/COMT · cp1252 · 62 campos' if any(f['url'].endswith('.7z') for f in files) else '')) if id=='rais' else mte.LAYOUT,'concept':'Vínculos ativos em 31/12 do ano-base; não são pessoas únicas.' if id=='rais' else 'Movimentações celetistas; admissões menos desligamentos, ajustadas até a divulgação indicada. Não mede desemprego.','filters':'UF=41 e código municipal MTE explícito; quatro municípios PR','transformations':'Soma setorial validada contra estoque publicado' if id=='rais' else 'MOV + FOR − EXC por competência original; setores CNAE A / B–E / F / G / H–U; pequenas células CBO/CNAE agregadas (mínimo 5).','files':files}


def update(data_dir, offline=False, source='all', force=False, cache=None, latest=None, rais_year=None, window=24, include_remuneration=False):
    data_dir=Path(data_dir);snapshot=data_dir/'employment.json'; previous=read(snapshot,blank())
    if offline:validate(previous);return previous
    now=datetime.now(timezone.utc).isoformat();data=copy.deepcopy(previous);failures=[];changed=False
    try:found=mte.discover() if not (latest and rais_year) else {'caged':latest,'rais':rais_year}
    except Exception as exc:
        data['collection']={**previous['collection'],'attemptedAt':now,'failures':[f'Descoberta MTE: {exc}']}
        if not data['sources']:data['sources']=[source_info(id,'Não disponível',None,[]) for id in ['rais','caged']]
        refresh_summary(data);validate(data);atomic_write(snapshot,data);exports(data_dir,data);sync_catalog(data_dir,data);return data
    with tempfile.TemporaryDirectory(prefix='turvo-mte-') as temp:
        directory=Path(cache or temp)
        if directory.resolve()==data_dir.resolve() or data_dir.resolve() in directory.resolve().parents:raise ValueError('Cache MTE deve ficar fora de public/data')
        directory.mkdir(parents=True,exist_ok=True)
        for id in ['rais','caged']:
            if source not in ['all',id]:continue
            ref=str(rais_year or found['rais']) if id=='rais' else latest or found['caged']
            current=previous[id].get('reference') if id=='rais' else (previous[id].get('latestReference') or '').replace('-','')
            if ref==current and not force and not (id=='rais' and include_remuneration and previous['rais'].get('remuneration',{}).get('status')!='available'):print(f'{id}: sem publicação nova; nenhum microdado baixado.');continue
            try:
                if id=='rais':
                    url=os.environ.get('MTE_RAIS_TABLE_URL',mte.PORTAL+f'/rais/rais-{ref}/rais-{ref}/rais-{ref}-tabelas.xlsx');path=directory/f'rais-{ref}-tables.xlsx';meta=mte.download(url,path)
                    result,evidence=rais_table(path,now);files=[meta]
                    if next(iter(result.values()))['reference']!=ref:raise ValueError('Ano da tabela RAIS divergente da descoberta')
                    if include_remuneration:
                        archive=directory/f'RAIS_VINC_PUB_SUL_{ref}.7z'
                        micro=mte.download(mte.BASE+f'/RAIS/{ref}/RAIS_VINC_PUB_SUL.7z',archive)
                        with mte.text_archive(archive,'cp1252') as stream:
                            remuneration=rais_remuneration(mte.rais_rows(stream,ref),result)
                        for code,values in remuneration.items():
                            values['collectedAt']=now;values['sourceFileSha256']=micro['sha256'];result[code]['remuneration']=values
                        files.append(micro)
                    elif ref==current:
                        # Table-only refresh cannot silently discard previously verified microdata.
                        for code,value in result.items():
                            old=previous['comparisons'][code]['rais']
                            if old.get('stock')==value['stock'] and old.get('sectors')==value['sectors']:
                                value['remuneration']=copy.deepcopy(old.get('remuneration',value['remuneration']))
                        oldsource=next((s for s in previous['sources'] if s['id']=='rais'),{})
                        files += [f for f in oldsource.get('files',[]) if f['url'].endswith('.7z')]
                    atomic_write(data_dir/'metadata'/'employment'/'rais-table4.json',{'source':meta,'collectedAt':now,**evidence})
                else:
                    start=window_start(ref,window);publications=months_between(start,ref);acc={};files=[];national=empty_counts()
                    if cache:mte.prime_remote_cache([mte.archive_url(kind,month) for month in publications for kind in ['MOV','FOR','EXC']])
                    for month in publications:
                        for kind in ['MOV','FOR','EXC']:
                            path=directory/f'CAGED{kind}{month}.7z';meta=mte.download(mte.archive_url(kind,month),path);files.append({**meta,'kind':kind,'publication':month})
                            with mte.text_archive(path) as stream:aggregate_caged(mte.caged_rows(stream,kind,national,ref),kind,month,start,ref,acc)
                            if not cache:path.unlink();path.with_suffix('.7z.manifest.json').unlink()
                        print(f'CAGED {month}: processado em streaming.',flush=True)
                    checks=read(Path(__file__).parents[1]/'config'/'employment-validation.json',{});check=checks.get(ref)
                    validate_counts(national)
                    if check and any(national[k]!=check[k] for k in empty_counts()):raise ValueError(f'Total nacional diverge do MTE (tolerância zero): {national}')
                    result=finalize_caged(acc,start,ref,files,now)
                    for value in result.values(): value['validation']={'status':'matched' if check else 'pending','nationalCounts':national,'officialCounts':check,'municipalIndependentCheck':'Conferência humana no ISPER/Perfil pendente; tabelas municipais não obtidas nesta coleta.'}
                for code,value in result.items():
                    if id=='caged':data['revisions']+= [{'municipalityCode':code,**r} for r in revisions(previous['comparisons'][code]['caged'],value,now)]
                    data['comparisons'][code][id]=value
                data['sources']=[s for s in data['sources'] if s['id']!=id]+[source_info(id,ref,now,files)];changed=True
            except Exception as exc:failures.append(f'{id}: {type(exc).__name__}: {exc}');print(f'FALHA {id}: {exc}',flush=True)
    data['rais']=data['comparisons']['4127965']['rais'];data['caged']=data['comparisons']['4127965']['caged']
    if not data['sources']:
        data['sources']=[source_info(id,'Não disponível',None,[]) for id in ['rais','caged']]
    else:
        for id in ['rais','caged']:
            if not any(s['id']==id for s in data['sources']):data['sources'].append(source_info(id,'Não disponível',None,[]))
    if not changed and not failures:return previous
    data['collection']={'attemptedAt':now,'lastSuccessAt':now if changed and not failures else previous['collection'].get('lastSuccessAt'),'failures':failures,'refreshPolicy':'CAGED mensal após nova publicação, janela de 24 meses; RAIS anual/manual; sem download semanal.','privacyMinimum':PRIVACY_MIN}
    refresh_summary(data);validate(data);atomic_write(snapshot,data);exports(data_dir,data);sync_catalog(data_dir,data)
    return data


def rais_sector(cnae_class):
    if not cnae_class.isdigit() or len(cnae_class)!=5:raise ValueError('Classe CNAE RAIS inválida')
    division=int(cnae_class[:2])
    if 1<=division<=3:return 'agriculture'
    if 5<=division<=39:return 'industry'
    if 41<=division<=43:return 'construction'
    if 45<=division<=47:return 'commerce'
    if 49<=division<=99:return 'services'
    raise ValueError('Divisão CNAE RAIS inválida')


def rais_remuneration(records, expected):
    aggregates={code:{'stock':0,'sectors':{k:{'stock':0,'sum':0.,'sample':0} for k in mte.SECTORS}} for code in mte.MUNICIPALITIES}
    for r in records:
        if r['indvinculoativo3112codigo'] not in ('0','1') or r['indvinculoabandonadocodigo'] not in ('0','1'):raise ValueError('Indicadores ativo/abandonado inválidos')
        if r['indvinculoativo3112codigo']!='1' or r['indvinculoabandonadocodigo']=='1':continue
        a=aggregates[r['code']];group=rais_sector(r['cnae20classecodigo']);a['stock']+=1;a['sectors'][group]['stock']+=1
        value=mte.decimal(r['vlremdezembronom'])
        if value is not None and value>0:a['sectors'][group]['sum']+=value;a['sectors'][group]['sample']+=1
        elif value is not None and value<0:raise ValueError('Remuneração nominal negativa')
    result={}
    for code,a in aggregates.items():
        official=expected[code]
        if a['stock']!=official['stock']['value'] or any(a['sectors'][s['code']]['stock']!=s['stock'] for s in official['sectors']):raise ValueError(f'RAIS microdados e tabela municipal divergentes para {code}; tolerância zero')
        sample=sum(s['sample'] for s in a['sectors'].values());total=sum(s['sum'] for s in a['sectors'].values())
        result[code]={'status':'available' if sample>=PRIVACY_MIN else 'unavailable','value':round(total/sample,2) if sample>=PRIVACY_MIN else None,'sample':sample if sample>=PRIVACY_MIN else None,'stock':a['stock'],'missingOrZero':a['stock']-sample,'unit':'R$ nominais · média de dezembro dos vínculos ativos com remuneração positiva; abandonados excluídos','variable':'Vl Rem Dezembro Nom','filters':'Ind Vínculo Ativo 31/12=1; Ind Vínculo Abandonado=0; remuneração de dezembro positiva; sem imputação e sem deflação','aggregation':'Média aritmética dos valores nominais positivos de dezembro, não remuneração média anual; indicador calculado pelo observatório a partir dos microdados MTE','validation':'Estoque e cinco setores conferidos exatamente com a Tabela 4 municipal; remuneração municipal não possui segundo total publicado nesta coleta.','sectors':[{'code':k,'label':mte.SECTORS[k],'value':round(s['sum']/s['sample'],2) if s['sample']>=PRIVACY_MIN else None,'sample':s['sample'] if s['sample']>=PRIVACY_MIN else None} for k,s in a['sectors'].items()]}
    return result


def refresh_summary(data):
    r,c=data['rais'],data['caged']
    data['summary']={'raisReference':r.get('reference'),'formalEmploymentStock':r.get('stock',{}).get('value'),'cagedReference':c.get('latestReference'),'cagedLatest':{k:c['monthly'][-1][k] for k in empty_counts()} if c.get('monthly') else None,'concepts':'RAIS estoque anual de vínculos ativos (exclui abandonados); Novo CAGED fluxos mensais revisáveis; vínculos e movimentos não são pessoas únicas.'}
