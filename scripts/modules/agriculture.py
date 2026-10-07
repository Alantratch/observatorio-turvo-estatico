"""PAM, PPM, PEVS and agricultural census: audited municipal static snapshots."""
import copy
import csv
import io
import json
import math
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from scripts.common import atomic_write, read
from scripts.sources.ibge import AgriculturalIBGE

CONFIG = Path(__file__).resolve().parents[1] / 'sources/agriculture-tables.json'
MUNICIPALITIES = {'4127965': 'Turvo', '4109401': 'Guarapuava', '4119608': 'Pitanga', '4113254': 'Laranjal', '41': 'Paraná'}
CELL_STATUSES = {'real', 'suppressed', 'notApplicable', 'unavailable', 'derived'}
PAM_NOTES = 'https://sidra.ibge.gov.br/pesquisa/pam/tabelas'


def cell(row, source, unit_override=None):
    unit = unit_override or row['originalUnit']
    factor = 1000 if unit == 'Mil Reais' else 1
    return {'value': None if row['value'] is None else row['value'] * factor, 'status': row['status'], 'rawSymbol': row['rawSymbol'], 'unit': 'R$' if factor == 1000 else unit, 'originalUnit': row['originalUnit'], 'variableId': row['variable'], 'sourceId': source, 'transformation': 'Mil Reais × 1000 → R$ nominal' if factor == 1000 else 'Unidade física corrigida conforme nota PAM (abacaxi/coco: mil frutos e frutos/ha)' if unit_override else None}


def derived(value, unit, formula, inputs, reason=None):
    return {'value': value, 'unit': unit, 'status': 'derived' if value is not None else 'unavailable', 'formula': formula, 'inputs': inputs, 'reason': reason if value is None else None}


def annual_change(current, previous, period, prior_period):
    if current is None or previous is None or previous <= 0 or int(period) - int(prior_period) != 1:
        return None
    return (current / previous - 1) * 100


def crop_kinds(client):
    kinds = {}
    for table, kind in [('1612', 'Temporária'), ('1613', 'Permanente')]:
        metadata, _ = client.load_metadata(table)
        if str(metadata['id']) != table or metadata['pesquisa'] != 'Produção Agrícola Municipal':
            raise ValueError('Metadados de lavouras temporárias/permanentes divergentes')
        for c in metadata['classificacoes']:
            for item in c['categorias']:
                if str(item['id']) != '0':
                    name = item['nome']
                    if name in kinds and kinds[name] != kind:
                        raise ValueError('Produto classificado nas duas lavouras')
                    kinds[name] = kind
    return kinds


def product_block(key, spec, rows, metadata, source, code, config, kinds):
    classification = spec['classification']
    cats = next((c['categorias'] for c in metadata['classificacoes'] if str(c['id']) == classification), [])
    categories = {str(c['id']): c for c in cats}
    periods = sorted({r['period'] for r in rows})
    reference = periods[-1]
    scope = [r for r in rows if r['municipalityCode'] == code]
    if not scope:
        raise ValueError('Ausência territorial não é zero')
    index = {(r['categories'].get(classification, 'total'), r['period'], r['variable']): r for r in scope}
    products = []
    totals = {}
    for category_id, category in categories.items():
        series = []
        selected_periods = periods if code == '4127965' else [reference]
        for period in selected_periods:
            metrics = {}
            for name, variable in spec['metrics'].items():
                row = index[(category_id, period, variable['variable'])]
                override = config['pamUnitExceptions'].get(category_id, {}).get(name) if key == 'pam' else None
                metrics[name] = cell(row, source, override)
            changes = {}
            if series:
                previous = series[-1]
                for metric, value in metrics.items():
                    before = previous['metrics'][metric]
                    changes[metric] = annual_change(value['value'], before['value'], period, previous['reference']) if value['unit'] == before['unit'] else None
            series.append({'reference': period, 'metrics': metrics, 'annualChanges': changes})
        latest = series[-1]
        if category_id == '0':
            totals = latest['metrics']
            continue
        present = any(c['value'] is not None and c['value'] > 0 or c['status'] == 'suppressed' for c in latest['metrics'].values())
        historical = any(c['value'] is not None and c['value'] > 0 or c['status'] == 'suppressed' for p in series for c in p['metrics'].values())
        # Keep every current comparison cell, but only meaningful municipal
        # series (including official suppressed cells and mate's confirmed zero).
        if code == '4127965' and not historical and not (key == 'extraction' and category_id == '3406'):
            continue
        name = category['nome']
        kind = kinds.get(name) if key == 'pam' else None
        if key == 'pam' and not kind:
            raise ValueError('Produto PAM sem classificação de lavoura confirmada: ' + name)
        products.append({'id': f'{spec["table"]}-{category_id}', 'categoryId': category_id, 'name': name, 'classificationId': classification, 'categoryLevel': category['nivel'], 'kind': kind, 'rankEligible': key != 'pam' or category_id not in ('40140', '40141'), 'rankNote': 'Subdivisão do café total; não somar ao total.' if key == 'pam' and category_id in ('40140', '40141') else None, 'presentInLatest': present, 'latest': latest, 'series': series if code == '4127965' else [], 'sourceId': source})
    return {'status': 'real', 'reference': reference, 'sourceId': source, 'products': products, 'totals': totals, 'annualChangeDefinition': {'status': 'derived', 'unit': '%', 'formula': '(atual / anterior - 1) × 100', 'rule': 'Mesma métrica/unidade e anos consecutivos; base zero, ausente ou suprimida → null. Valor em R$ mede variação nominal.'}}


def census_block(rows, people_rows, code, reference):
    def select(data, variable, typology):
        matches = [r for r in data if r['municipalityCode'] == code and r['variable'] == variable and r['categories']['829'] == typology and r['period'] == reference]
        if len(matches) != 1:
            raise ValueError('Célula estrutural ausente/duplicada')
        return matches[0]
    values = {}
    for prefix, typology in [('', '46302'), ('family', '46304'), ('nonFamily', '46303')]:
        for name, variable in [('Establishments', '183'), ('Area', '184')]:
            key = (prefix + name) if prefix else name[0].lower() + name[1:]
            values[key] = cell(select(rows, variable, typology), 'census')
        values[prefix + 'People' if prefix else 'people'] = cell(select(people_rows, '185', typology), 'censusPeople')
    total, family = values['establishments']['value'], values['familyEstablishments']['value']
    values['familyShare'] = derived(family / total * 100 if family is not None and total else None, '%', 'Estabelecimentos de agricultura familiar / total × 100', {'numerator': 'familyEstablishments', 'denominator': 'establishments', 'reference': reference}, 'Sem denominador válido.')
    for metric in ('Establishments', 'Area', 'People'):
        total_key = metric[0].lower() + metric[1:]
        nums = [values[k]['value'] for k in (total_key, 'family' + metric, 'nonFamily' + metric)]
        if all(n is not None for n in nums) and not math.isclose(nums[0], nums[1] + nums[2], abs_tol=2):
            raise ValueError('Tipologia familiar/não familiar diverge do total censitário')
    return {'status': 'real', 'reference': reference, 'values': values, 'sourceIds': ['census', 'censusPeople'], 'note': 'Censo Agropecuário estrutural. Classificação familiar oficial do IBGE; pessoal ocupado não é emprego formal RAIS.'}


def quality(data):
    warnings = []
    for p in data['crops']['products']:
        for point in p['series']:
            m = point['metrics'];production, area, yield_ = m['production'], m['harvestedArea'], m['yield']
            planted = m['plantedOrIntendedArea']['value']
            if area['value'] is not None and planted is not None and area['value'] > planted:
                warnings.append({'product': p['name'], 'reference': point['reference'], 'message': 'Área colhida maior que plantada/destinada, conforme valores oficiais; não corrigido pelo Observatório.'})
            if production['value'] is None or not area['value'] or yield_['value'] is None:
                continue
            if production['unit'] == 'Toneladas' and yield_['unit'] == 'Quilogramas por Hectare' or production['unit'] == 'Mil frutos' and yield_['unit'] == 'Frutos por Hectare':
                expected = production['value'] * 1000 / area['value']
                if abs(yield_['value'] - expected) > max(1, expected * .03):
                    warnings.append({'product': p['name'], 'reference': point['reference'], 'message': 'Rendimento oficial difere mais de 3% da razão quantidade/área; unidades e valores preservados.'})
    return {'yieldCheck': 'Verificação aproximada, tolerância max(1 unidade, 3%) para arredondamento. Não substitui rendimento oficial.', 'warnings': warnings}


def build(client, config, collected_at):
    inputs = {}
    kinds = crop_kinds(client)
    for key, spec in config['tables'].items():
        inputs[key] = client.agricultural(key, spec, window=1 if key.startswith('census') else 10)
    references = {key: max(r['period'] for r in rows) for key, (rows, _) in inputs.items()}
    if references['census'] != references['censusPeople']:
        raise ValueError('Referências censitárias distintas; não combinar')
    all_data = {}
    for code in MUNICIPALITIES:
        blocks = {key: product_block(key, config['tables'][key], rows, metadata, key, code, config, kinds) for key, (rows, metadata) in inputs.items() if config['tables'][key]['classification'] and not key.startswith('census')}
        cows = [r for r in inputs['milkedCows'][0] if r['municipalityCode'] == code]
        cows.sort(key=lambda r: r['period'])
        cow_series = [{'reference': r['period'], 'metric': cell(r, 'milkedCows')} for r in cows if code == '4127965' or r['period'] == references['milkedCows']]
        milk = next((p for p in blocks['animal']['products'] if p['categoryId'] == '2682'), None)
        cow_cell = cow_series[-1]['metric']
        numerator = milk['latest']['metrics']['production'] if milk else None
        compatible = milk and milk['latest']['reference'] == cow_series[-1]['reference'] and numerator['unit'] == 'Mil litros'
        milk_yield = derived(numerator['value'] * 1000 / cow_cell['value'] if compatible and numerator['value'] is not None and cow_cell['value'] else None, 'Litros por vaca ordenhada/ano', 'Leite (mil litros) × 1000 / vacas ordenhadas', {'reference': cow_series[-1]['reference'], 'sourceIds': ['animal', 'milkedCows']}, 'Exige mesmo ano, fonte PPM e denominador positivo.')
        all_data[code] = {'municipalityCode': code, 'name': MUNICIPALITIES[code], 'state': 'PR', 'crops': blocks['pam'], 'livestock': {'herds': blocks['herds'], 'products': blocks['animal'], 'aquaculture': blocks['aquaculture'], 'milkedCows': {'status': 'real', 'reference': references['milkedCows'], 'sourceId': 'milkedCows', 'latest': cow_series[-1], 'series': cow_series}, 'milkPerCow': milk_yield}, 'forestry': {'extraction': blocks['extraction'], 'silviculture': blocks['silviculture']}, 'agriculturalCensus': census_block(inputs['census'][0], inputs['censusPeople'][0], code, references['census'])}
    turvo = all_data['4127965']
    data = {'schemaVersion': 1, 'municipality': {'code': '4127965', 'name': 'Turvo', 'state': 'PR'}, **{k: turvo[k] for k in ('crops', 'livestock', 'forestry', 'agriculturalCensus')}, 'comparisons': [all_data[k] for k in MUNICIPALITIES if k != '4127965'], 'sources': client.sources, 'classificationSources': {'temporary': 'https://servicodados.ibge.gov.br/api/v3/agregados/1612/metadados', 'permanent': 'https://servicodados.ibge.gov.br/api/v3/agregados/1613/metadados', 'pamUnitNotes': PAM_NOTES}, 'collection': {'attemptedAt': collected_at, 'failures': []}}
    crops = [p for p in data['crops']['products'] if p['presentInLatest'] and p['rankEligible']]
    positive = [p for p in crops if p['latest']['metrics']['productionValue']['value'] is not None]
    leader = max(positive, key=lambda p: p['latest']['metrics']['productionValue']['value']) if positive else None
    data['summary'] = {'reference': data['crops']['reference'], 'cropCount': len(crops), 'leadingCropId': leader['id'] if leader else None, 'productionValue': data['crops']['totals']['productionValue'], 'note': 'Total publicado pelo IBGE na categoria Total PAM, não PIB nem VAB. Área colhida não representa hectares únicos de território.'}
    data['quality'] = quality(data)
    validate(data)
    return data


def validate(data):
    if data.get('schemaVersion') != 1 or data.get('municipality') != {'code': '4127965', 'name': 'Turvo', 'state': 'PR'}:
        raise ValueError('Schema/município Agropecuária inválido')
    sources = {s['id']: s for s in data['sources']}
    if set(sources) != set(read(CONFIG, {})['tables']) or len(sources) != len(data['sources']):
        raise ValueError('Fontes agropecuárias incompletas/duplicadas')
    for s in sources.values():
        if s['agency'] != 'IBGE' or not s['url'].startswith('https://servicodados.ibge.gov.br/api/v3/agregados/') or not s['collectedAt'] or not re.fullmatch(r'\d{4}', s['reference']):
            raise ValueError('Proveniência agropecuária inválida')
    def walk(obj):
        if isinstance(obj, dict):
            if 'value' in obj and 'status' in obj:
                value, status = obj['value'], obj['status']
                if status not in CELL_STATUSES or not obj.get('unit'):
                    raise ValueError('Estado/unidade de célula inválido')
                if status in ('real', 'derived') and (type(value) not in (int, float) or not math.isfinite(value) or value < 0 and obj.get('unit') != '%'):
                    raise ValueError('Valor agropecuário inválido')
                if status in ('suppressed', 'notApplicable', 'unavailable') and value is not None:
                    raise ValueError('Ausente/suprimido não pode conter valor')
                if status == 'derived' and not obj.get('formula'):
                    raise ValueError('Derivado sem fórmula')
                if obj.get('sourceId') and obj['sourceId'] not in sources:
                    raise ValueError('Célula sem fonte oficial')
                if obj.get('rawSymbol') in ('X', '..', '...') and status != {'X':'suppressed','..':'notApplicable','...':'unavailable'}[obj['rawSymbol']]:
                    raise ValueError('Marcador oficial não corresponde ao estado')
                if status == 'real' and obj['unit'] in ('Cabeças','Unidades','Pessoas') and value != int(value):
                    raise ValueError('Contagem agropecuária não inteira')
                if obj.get('sourceId') and str(obj.get('variableId')) not in {str(v['id']) for v in sources[obj['sourceId']]['variables']}:
                    raise ValueError('Variável não pertence à fonte')
                if obj.get('unit') == 'R$' and obj.get('originalUnit') != 'Mil Reais':
                    raise ValueError('Conversão monetária sem unidade original confirmada')
                if status == 'suppressed' and obj.get('rawSymbol') != 'X':
                    raise ValueError('Supressão sem marcador oficial')
            for key, value in obj.items():
                if key == 'municipalityCode' and value not in MUNICIPALITIES:
                    raise ValueError('Território agropecuário inválido')
                if key == 'reference' and value is not None and not re.fullmatch(r'\d{4}', value):
                    raise ValueError('Referência agropecuária inválida')
                walk(value)
        elif isinstance(obj, list):
            for item in obj: walk(item)
    walk(data)
    for scope in [data, *data['comparisons']]:
        blocks = [scope['crops'], scope['livestock']['herds'], scope['livestock']['products'], scope['livestock']['aquaculture'], *scope['forestry'].values()]
        for block in blocks:
            if block['reference'] != sources[block['sourceId']]['reference']:
                raise ValueError('Referência da base diverge da fonte')
            ids = set()
            for p in block['products']:
                if p['id'] in ids or p['sourceId'] != block['sourceId']:
                    raise ValueError('Produto duplicado ou fonte incorreta')
                ids.add(p['id'])
                for point in [p['latest'], *p['series']]:
                    if point['reference'] not in sources[p['sourceId']]['periods'] or any(v is not None and (type(v) not in (float,int) or not math.isfinite(v)) for v in point['annualChanges'].values()):
                        raise ValueError('Período/variação agropecuária inválida')
                if [r['reference'] for r in p['series']] != sorted(set(r['reference'] for r in p['series'])) or p['series'] and p['latest'] != p['series'][-1] or p['latest']['reference'] != block['reference']:
                    raise ValueError('Histórico agropecuário inválido')
    if {c['municipalityCode'] for c in data['comparisons']} != set(MUNICIPALITIES) - {'4127965'}:
        raise ValueError('Comparações agropecuárias incompletas')
    for scope in [data,*data['comparisons']]:
        census=scope['agriculturalCensus'];v=census['values'];expected=v['familyEstablishments']['value']/v['establishments']['value']*100 if v['familyEstablishments']['value'] is not None and v['establishments']['value'] else None
        if census['reference'] != sources['census']['reference'] or census['reference'] != sources['censusPeople']['reference'] or v['familyShare']['value'] != expected:
            raise ValueError('Referência/cálculo censitário inválido')
        milk=next((p for p in scope['livestock']['products']['products'] if p['categoryId']=='2682'),None);cows=scope['livestock']['milkedCows'];numerator=milk['latest']['metrics']['production'] if milk else None
        expected=numerator['value']*1000/cows['latest']['metric']['value'] if milk and milk['latest']['reference']==cows['reference'] and numerator['unit']=='Mil litros' and numerator['value'] is not None and cows['latest']['metric']['value'] else None
        if scope['livestock']['milkPerCow']['value'] != expected:
            raise ValueError('Produção por vaca inconsistente')
    current=[p for p in data['crops']['products'] if p['presentInLatest'] and p['rankEligible']]
    valued=[p for p in current if p['latest']['metrics']['productionValue']['value'] is not None]
    leader=max(valued,key=lambda p:p['latest']['metrics']['productionValue']['value']) if valued else None
    if data['summary']['cropCount'] != len(current) or data['summary']['leadingCropId'] != (leader['id'] if leader else None):
        raise ValueError('Resumo agrícola inconsistente')
    if data['summary']['productionValue'] != data['crops']['totals']['productionValue']:
        raise ValueError('Total PAM divergente')
    if '"mock"' in json.dumps(data):
        raise ValueError('Agropecuária não admite mock')
    return data


def export_csv(data, directory):
    directory = Path(directory);directory.mkdir(parents=True, exist_ok=True)
    blocks = {'crops': [data['crops']], 'livestock': [data['livestock']['herds'], data['livestock']['products'], data['livestock']['aquaculture']], 'forestry': list(data['forestry'].values())}
    for filename, groups in blocks.items():
        content = []
        for block in groups:
            for p in block['products']:
                for point in p['series']:
                    for metric, c in point['metrics'].items():
                        content.append({'municipalityCode': '4127965', 'productId': p['id'], 'product': p['name'], 'kind': p['kind'], 'reference': point['reference'], 'metric': metric, 'value': c['value'], 'unit': c['unit'], 'status': c['status'], 'rawSymbol': c['rawSymbol'], 'sourceId': c['sourceId'], 'variableId': c['variableId']})
        if filename == 'livestock':
            for point in data['livestock']['milkedCows']['series']:
                c = point['metric'];content.append({'municipalityCode':'4127965','productId':'94','product':'Vacas ordenhadas','kind':None,'reference':point['reference'],'metric':'milkedCows','value':c['value'],'unit':c['unit'],'status':c['status'],'rawSymbol':c['rawSymbol'],'sourceId':c['sourceId'],'variableId':c['variableId']})
        text = io.StringIO(newline='');fields = list(content[0]) if content else ['municipalityCode','reference','value','status']
        writer = csv.DictWriter(text, fieldnames=fields, lineterminator='\n');writer.writeheader();writer.writerows(content)
        (directory / f'agriculture-{filename}.csv').write_text(text.getvalue(), encoding='utf-8')
    with (directory/'agriculture-census.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['municipalityCode','reference','metric','value','unit','status','sourceId'],lineterminator='\n');writer.writeheader()
        for metric,c in data['agriculturalCensus']['values'].items():writer.writerow({'municipalityCode':'4127965','reference':data['agriculturalCensus']['reference'],'metric':metric,'value':c['value'],'unit':c['unit'],'status':c['status'],'sourceId':c.get('sourceId','derived')})


def update_catalog(data, directory):
    path=Path(directory)/'indicators.json';catalog=read(path,None)
    if not catalog:return
    catalog['indicators']=[i for i in catalog['indicators'] if i['module']!='agriculture']
    candidates=[('agriculture-pam-value','Valor da produção agrícola · PAM',data['summary']['productionValue'],data['crops']['reference']),('agriculture-census-establishments','Estabelecimentos agropecuários · Censo',data['agriculturalCensus']['values']['establishments'],data['agriculturalCensus']['reference'])]
    for category,title,block,metric in [('2670','Efetivo de bovinos',data['livestock']['herds'],'herd'),('2682','Produção de leite',data['livestock']['products'],'production'),('2685','Produção de ovos de galinha',data['livestock']['products'],'production'),('2687','Produção de mel de abelha',data['livestock']['products'],'production')]:
        p=next((p for p in block['products'] if p['categoryId']==category),None)
        if p:candidates.append(('agriculture-'+category,title,p['latest']['metrics'][metric],block['reference']))
    for id_,title,c,reference in candidates:
        if c['status']!='real':continue
        source=next(s for s in data['sources'] if s['id']==c['sourceId'])
        catalog['indicators'].append({'id':id_,'module':'agriculture','title':title,'value':c['value'],'unit':c['unit'],'source':f'IBGE / {source["research"]} · Tabela {source["table"]}','agency':'IBGE','reference':reference,'url':source['url'],'collectedAt':source['collectedAt'],'municipalityCode':'4127965','status':'real','series':[{'period':reference,'value':c['value']}],'note':'Valor da produção não é PIB/VAB; pesquisas anuais e Censo estrutural têm referências distintas.'})
    catalog['indicators'].sort(key=lambda i:(i['module'],i['id']));atomic_write(path,catalog)


def update(directory, offline=False):
    directory=Path(directory);path=directory/'agriculture.json';previous=read(path,None)
    if offline:
        if not previous:raise ValueError('Snapshot Agropecuária ainda não disponível')
        return validate(previous)
    now=datetime.now(timezone.utc).isoformat();client=AgriculturalIBGE(now)
    try:
        data=build(client,read(CONFIG,{}),now)
        if previous:
            for source in data['sources']:
                old=next((s for s in previous['sources'] if s['id']==source['id']),None)
                raw_previous=read(directory/'agriculture/raw'/f'{source["id"]}.json',None)
                new_raw=client.raw[source['id']]
                if old and raw_previous and all(raw_previous.get(k)==new_raw.get(k) for k in ('metadata','periods','response','url')):
                    source['collectedAt']=old['collectedAt'];new_raw['collectedAt']=old['collectedAt']
            comparable=copy.deepcopy(data);comparable['collection']=previous['collection']
            if comparable==previous and not previous['collection']['failures']:
                print('Agropecuária: referências e revisões verificadas; nenhuma alteração.');return previous
        # Existing repository publication mechanism is reused; independent module
        # writes only its own files and catalog, with rollback on local failure.
        from scripts.modules.health import publish
        with tempfile.TemporaryDirectory(prefix='turvo-agriculture-') as temporary:
            stage=Path(temporary)
            if (directory/'indicators.json').exists():shutil.copyfile(directory/'indicators.json',stage/'indicators.json')
            for key,raw in client.raw.items():atomic_write(stage/'agriculture/raw'/f'{key}.json',raw)
            atomic_write(stage/'agriculture/classifications.json',{'collectedAt':now,'kindByName':crop_kinds(client),'metadata':{t:client.metadata_cache[t] for t in ('1612','1613')}})
            export_csv(data,stage/'exports');update_catalog(data,stage);atomic_write(stage/'agriculture.json',data);publish(stage,directory)
        print(f'Agropecuária: PAM {data["crops"]["reference"]}, {data["summary"]["cropCount"]} produtos; Censo {data["agriculturalCensus"]["reference"]}.');return data
    except Exception as exc:
        if not previous:raise
        data=copy.deepcopy(validate(previous));data['collection']={'attemptedAt':now,'failures':[f'{type(exc).__name__}: {exc}']};atomic_write(path,data)
        print('FALHA Agropecuária: último snapshot completo preservado:',exc);return data
