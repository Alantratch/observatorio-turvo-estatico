"""Population ETL: one validated municipal snapshot, entirely from official IBGE responses."""
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from scripts.common import atomic_write, number, read, request_json, preserve_collection_times
from scripts.sources.ibge import CODE, IBGE

# IDs and names checked against official metadata before integration (2026-10-06).
SEX = {'6794': 'Total', '4': 'Homens', '5': 'Mulheres'}
RACE = {'95251': 'Total', '2776': 'Branca', '2777': 'Preta', '2778': 'Amarela', '2779': 'Parda', '2780': 'Indígena'}
AGES = {'100362': 'Total', '93070': '0 a 4 anos', '93084': '5 a 9 anos', '93085': '10 a 14 anos', '93086': '15 a 19 anos', '93087': '20 a 24 anos', '93088': '25 a 29 anos', '93089': '30 a 34 anos', '93090': '35 a 39 anos', '93091': '40 a 44 anos', '93092': '45 a 49 anos', '93093': '50 a 54 anos', '93094': '55 a 59 anos', '93095': '60 a 64 anos', '93096': '65 a 69 anos', '93097': '70 a 74 anos', '93098': '75 a 79 anos', '49108': '80 a 84 anos', '49109': '85 a 89 anos', '60040': '90 a 94 anos', '60041': '95 a 99 anos', '6653': '100 anos ou mais'}
# Use disjoint level-1 age categories; never sum their overlapping single-year children.
AGE_GROUPS = [('0–4', ['93070']), ('5–9', ['93084']), ('10–14', ['93085']), ('15–19', ['93086']), ('20–29', ['93087', '93088']), ('30–39', ['93089', '93090']), ('40–49', ['93091', '93092']), ('50–59', ['93093', '93094']), ('60–69', ['93095', '93096']), ('70–79', ['93097', '93098']), ('80+', ['49108', '49109', '60040', '60041', '6653'])]
SITUATION = {'6795': 'Total', '1': 'Urbana', '2': 'Rural'}
DEFINITION_URL = 'https://www.ibge.gov.br/biblioteca/visualizacao/periodicos/3105/cd_2022_etnico_racial.pdf'


def select(rows, variable, period, **categories):
    matches = [r['value'] for r in rows if r['variable'] == variable and r['period'] == period and r['categories'] == categories]
    if len(matches) != 1 or matches[0] is None:
        raise ValueError('Célula requerida ausente ou ambígua')
    return matches[0]


def metric(identifier, title, value, unit, period, source, concept, methodology):
    return {'id': identifier, 'title': title, 'value': value, 'unit': unit, 'reference': period, 'sourceId': source['id'], 'source': source['title'], 'agency': 'IBGE', 'url': source['url'], 'collectedAt': source['collectedAt'], 'municipalityCode': CODE, 'status': 'real', 'concept': concept, 'methodology': methodology}


def distribution(rows, dimension, categories, total_id, fixed, source_id):
    total = select(rows, '93', '2022', **{**fixed, dimension: total_id})
    if total <= 0:
        raise ValueError('População total deve ser positiva')
    items = [{'categoryId': key, 'category': name, 'value': select(rows, '93', '2022', **{**fixed, dimension: key})} for key, name in categories.items() if key != total_id]
    if sum(i['value'] for i in items) != total:
        raise ValueError('Categorias não somam o total do mesmo universo')
    for item in items:
        item['percent'] = item['value'] / total * 100
    return {'status': 'real', 'reference': '2022', 'sourceIds': [source_id], 'unit': 'pessoas', 'total': total, 'rows': items}


def age_groups(rows):
    result = []
    for label, identifiers in AGE_GROUPS:
        male = sum(select(rows, '93', '2022', **{'86': '95251', '2': '4', '287': i}) for i in identifiers)
        female = sum(select(rows, '93', '2022', **{'86': '95251', '2': '5', '287': i}) for i in identifiers)
        total = sum(select(rows, '93', '2022', **{'86': '95251', '2': '6794', '287': i}) for i in identifiers)
        if male + female != total:
            raise ValueError('Faixa etária inconsistente no mesmo universo')
        result.append({'ageGroup': label, 'categoryIds': identifiers, 'male': male, 'female': female, 'total': total})
    return result


def external_source(identifier, title, research, url, metadata_url, now, reference, methodology, **extra):
    return dict(id=identifier, agency='IBGE', research=research, title=title, table=None, variables=[], classifications=[], periods=[reference], reference=reference, url=url, officialUrl=url, metadataUrl=metadata_url, collectedAt=now, transformations=[], methodology=methodology, **extra)


def collect(now):
    ibge = IBGE(now)
    census = ibge.aggregate('census', '4714', {'93': ('População residente', 'Pessoas'), '6318': ('Área da unidade territorial', 'Quilômetros quadrados'), '614': ('Densidade demográfica', 'Habitante por quilômetro quadrado')}, {}, ['2022'], methodology='Censo Demográfico 2022. Densidade publicada pelo IBGE, com a área territorial de referência do Censo; não recalculada com área de 2025.')
    total = select(census, '93', '2022')
    if total <= 0:
        raise ValueError('População censitária inválida')
    estimates = ibge.aggregate('estimates', '6579', {'9324': ('População residente estimada', 'Pessoas')}, {}, methodology='Estimativas anuais do IBGE, referência 1º de julho. Não são contagens censitárias. Revisões e mudanças de limites podem afetar comparações.')
    history = ibge.aggregate('census-history', '202', {'93': ('População residente', 'Pessoas')}, {'2': {'0': 'Total'}, '1': {'0': 'Total'}}, allow_missing=True, transformations=['Omitir apenas períodos explicitamente sem informação (...); preservar no arquivo bruto. Não interpolar.'], methodology='Censos conforme publicados para cada período. Limites municipais podem variar; não usar diferenças brutas como crescimento territorialmente compatibilizado.')
    ibge.sources[-1]['reference'] = ', '.join(row['period'] for row in history if row['value'] is not None)
    omitted = [row['period'] for row in history if row['value'] is None]
    ibge.sources[-1]['transformations'].append('Períodos sem informação para Turvo, omitidos do gráfico: ' + ', '.join(omitted))
    growth_rows = ibge.aggregate('census-growth', '4709', {'93': ('População residente', 'Pessoas'), '5936': ('Variação absoluta da população residente 2010 compatibilizada', 'Pessoas'), '10605': ('Taxa de crescimento geométrico', '%')}, {}, ['2022'], transformations=['Base 2010 compatibilizada = população 2022 − variação absoluta oficial. Percentual = variação absoluta / base compatibilizada × 100. Taxa geométrica: valor oficial, não recalculado.'], methodology='Comparação 2010–2022 com a população 2010 compatibilizada aos limites territoriais de 2022.')
    age = ibge.aggregate('age-sex', '9606', {'93': ('População residente', 'Pessoas')}, {'86': {'95251': 'Total'}, '2': SEX, '287': AGES}, ['2022'], transformations=['Somar somente categorias etárias disjuntas de nível 1 nos 11 grupos publicados na interface. Percentuais calculados sobre o total desta tabela.'], methodology='População residente, total de cor ou raça, por sexo e idade. Sexo conforme categorias Homens e Mulheres do IBGE.')
    race_rows = ibge.aggregate('race', '9606', {'93': ('População residente', 'Pessoas')}, {'86': RACE, '2': {'6794': 'Total'}, '287': {'100362': 'Total'}}, ['2022'], transformations=['Percentual = quantidade / total de cor ou raça desta tabela × 100.'], methodology='Cor ou raça conforme categorias declaradas da fonte. Indígena é a categoria de cor ou raça; não equivale ao universo ampliado de indígenas que inclui o quesito “se considera indígena”.')
    demographic = ibge.aggregate('demographic', '9756', {'9175': ('Índice de envelhecimento (Idosos: 60 anos ou mais de idade)', 'Razão'), '10613': ('Idade mediana', 'Anos'), '8845': ('Razão de sexo', 'Razão')}, {'86': {'95251': 'Total'}}, ['2010', '2022'], methodology='Total de cor ou raça. Envelhecimento: pessoas de 60+ por 100 de 0–14; idade mediana: separa a metade mais jovem da mais velha; razão de sexo: homens por 100 mulheres. Definições oficiais na publicação étnico-racial do Censo 2022.')
    ibge.sources[-1]['definitionUrl'] = DEFINITION_URL
    urban = ibge.aggregate('urban-rural', '9923', {'93': ('População residente', 'Pessoas')}, {'1': SITUATION}, ['2022'], transformations=['Percentual = quantidade / total da tabela × 100.'], methodology='Situação urbana ou rural do domicílio conforme a classificação do Censo 2022. Não inferida por ocupação ou atividade econômica.')
    homes = ibge.aggregate('households', '9922', {'381': ('Domicílios particulares permanentes ocupados', 'Domicílios'), '382': ('Moradores em domicílios particulares permanentes ocupados', 'Pessoas'), '5930': ('Média de moradores em domicílios particulares permanentes ocupados', 'Pessoas')}, {'1': {'6795': 'Total'}}, ['2022'], methodology='Somente domicílios particulares permanentes ocupados. Moradores deste universo não precisam igualar a população residente total. Média oficial arredondada pelo IBGE.')

    # API Pesquisas indicator 29167: area, confirmed by its name, unit and multiplier.
    area_meta_url = 'https://servicodados.ibge.gov.br/api/v1/pesquisas/indicadores/29167'
    area_url = f'{area_meta_url}/resultados/{CODE}'
    area_meta = request_json(area_meta_url)
    if len(area_meta) != 1 or area_meta[0]['id'] != 29167 or area_meta[0]['indicador'] != 'Área da unidade territorial' or area_meta[0]['unidade'] != {'id': 'km²', 'classe': 'N', 'multiplicador': 1}:
        raise ValueError('Metadados territoriais divergentes')
    area_payload = request_json(area_url)
    if len(area_payload) != 1 or area_payload[0]['id'] != 29167 or len(area_payload[0]['res']) != 1:
        raise ValueError('Resposta territorial incompleta')
    area_locality = area_payload[0]['res'][0]
    # Pesquisas uses the six-digit municipal code (without the IBGE check digit).
    if area_locality['localidade'] != CODE[:-1]:
        raise ValueError('Município territorial incorreto')
    area_series = area_locality['res']
    area_period = max(area_series)
    area_value = number(area_series[area_period])
    if area_value <= 0 or int(area_period) > datetime.now(timezone.utc).year:
        raise ValueError('Área/período inválido')
    ibge.sources.append(external_source('territorial-area', 'Área da unidade territorial', 'Áreas territoriais / IBGE Cidades', area_url, area_meta_url, now, area_period, 'Área territorial anual publicada pelo IBGE. Não utilizar como denominador da densidade censitária 2022.', indicator='29167'))
    ibge.sources[-1]['variables'] = [{'id': '29167', 'name': 'Área da unidade territorial', 'unit': 'km²'}]
    ibge.raw['territorial-area'] = {'metadata': area_meta, 'response': area_payload, 'url': area_url}

    locality_url = f'https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{CODE}'
    locality = request_json(locality_url)
    if str(locality['id']) != CODE or locality['nome'] != 'Turvo' or locality['microrregiao']['mesorregiao']['UF']['sigla'] != 'PR':
        raise ValueError('Localidade divergente')
    ibge.raw['locality'] = {'response': locality, 'url': locality_url}
    ibge.sources.append(external_source('locality', 'Identificação municipal e regiões geográficas', 'API de Localidades', locality_url, locality_url, now, 'Cadastro vigente na coleta', 'Regiões imediata e intermediária conforme cadastro oficial do IBGE; não confundir com antigas microrregiões.'))
    map_url = f'https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{CODE}?formato=application/vnd.geo%2Bjson&qualidade=intermediaria&periodo=2022'
    map_meta_url = f'https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{CODE}/metadados?periodo=2022'
    geometry, map_meta = request_json(map_url), request_json(map_meta_url)
    validate_geometry(geometry)
    if len(map_meta) != 1 or map_meta[0]['id'] != CODE:
        raise ValueError('Metadados da malha divergentes')
    ibge.sources.append(external_source('municipal-boundary', 'Contorno municipal de Turvo', 'API de Malhas', map_url, map_meta_url, now, '2022', 'Malha de referência 2022, qualidade intermediária fornecida pelo IBGE. Contorno informativo; não é limite cadastral de precisão e não representa necessariamente a área publicada em 2025.'))
    ibge.raw['municipal-boundary'] = {'metadata': map_meta, 'response': geometry, 'url': map_url}
    source = {s['id']: s for s in ibge.sources}
    latest_estimate = max(r['period'] for r in estimates)
    summary = {
        'population-estimate': metric('population-estimate', 'População estimada', select(estimates, '9324', latest_estimate), 'pessoas', latest_estimate, source['estimates'], 'Estimativa da população residente em 1º de julho; não é contagem censitária.', 'estimate'),
        'population-census': metric('population-census', 'População residente — Censo', total, 'pessoas', '2022', source['census'], 'Contagem de população residente no Censo Demográfico 2022.', 'census'),
        'population-density': metric('population-density', 'Densidade demográfica', select(census, '614', '2022'), 'hab/km²', '2022', source['census'], 'Densidade oficial censitária 2022. Não recalculada com a área territorial mais recente.', 'census'),
        'territorial-area': metric('territorial-area', 'Área territorial', area_value, 'km²', area_period, source['territorial-area'], 'Área da unidade territorial na edição anual informada pelo IBGE.', 'territory'),
    }
    population_history = [{'period': r['period'], 'value': r['value'], 'methodology': 'census', 'sourceId': 'census-history'} for r in history if r['value'] is not None]
    population_history.append({'period': '2022', 'value': total, 'methodology': 'census', 'sourceId': 'census'})
    growth_value = select(growth_rows, '5936', '2022')
    growth_baseline = total - growth_value
    if select(growth_rows, '93', '2022') != total or growth_baseline <= 0:
        raise ValueError('Base de crescimento incompatível')
    grouped_age = age_groups(age)
    age_total = select(age, '93', '2022', **{'86': '95251', '2': '6794', '287': '100362'})
    if sum(i['total'] for i in grouped_age) != age_total:
        raise ValueError('Idades incompletas')
    for group in grouped_age:
        group['percent'] = group['total'] / age_total * 100
    demographic_metrics = [
        metric('median-age', 'Idade mediana', select(demographic, '10613', '2022', **{'86': '95251'}), 'anos', '2022', source['demographic'], 'Idade que separa a metade mais jovem da metade mais velha da população.', 'census'),
        metric('aging-index', 'Índice de envelhecimento', select(demographic, '9175', '2022', **{'86': '95251'}), 'pessoas de 60+ / 100 de 0–14', '2022', source['demographic'], 'Pessoas de 60 anos ou mais por 100 pessoas de zero a 14 anos. Razão publicada pelo IBGE.', 'census'),
        metric('sex-ratio', 'Razão de sexo', select(demographic, '8845', '2022', **{'86': '95251'}), 'homens / 100 mulheres', '2022', source['demographic'], 'Número de homens por 100 mulheres na população considerada.', 'census'),
    ]
    result = {
        'schemaVersion': 1,
        'municipality': {'code': CODE, 'name': locality['nome'], 'state': 'PR'},
        'summary': summary,
        'populationHistory': {'status': 'real', 'sourceIds': ['census-history', 'census'], 'rows': population_history},
        'estimateHistory': {'status': 'real', 'sourceIds': ['estimates'], 'rows': [{'period': r['period'], 'value': r['value'], 'methodology': 'estimate', 'sourceId': 'estimates'} for r in estimates]},
        'growth': {'status': 'real', 'sourceIds': ['census-growth'], 'from': '2010', 'to': '2022', 'compatibleBaseline': growth_baseline, 'absoluteChange': growth_value, 'percentChange': growth_value / growth_baseline * 100, 'annualGeometricRate': select(growth_rows, '10605', '2022')},
        'ageSex': {'status': 'real', 'sourceIds': ['age-sex'], 'reference': '2022', 'unit': 'pessoas', 'total': age_total, 'rows': grouped_age},
        'sex': distribution(age, '2', SEX, '6794', {'86': '95251', '287': '100362'}, 'age-sex'),
        'race': distribution(race_rows, '86', RACE, '95251', {'2': '6794', '287': '100362'}, 'race'),
        'urbanRural': distribution(urban, '1', SITUATION, '6795', {}, 'urban-rural'),
        'demographicIndicators': {'status': 'real', 'sourceIds': ['demographic'], 'reference': '2022', 'indicators': demographic_metrics, 'rows': [{'period': period, 'medianAge': select(demographic, '10613', period, **{'86': '95251'}), 'agingIndex': select(demographic, '9175', period, **{'86': '95251'}), 'sexRatio': select(demographic, '8845', period, **{'86': '95251'})} for period in ['2010', '2022']]},
        'households': {'status': 'real', 'sourceIds': ['households'], 'reference': '2022', 'indicators': [metric('occupied-households', 'Domicílios particulares permanentes ocupados', select(homes, '381', '2022', **{'1': '6795'}), 'domicílios', '2022', source['households'], 'Domicílios particulares permanentes ocupados; exclui domicílios coletivos e improvisados.', 'census'), metric('residents-per-household', 'Média de moradores por domicílio', select(homes, '5930', '2022', **{'1': '6795'}), 'pessoas / domicílio', '2022', source['households'], 'Média oficial de moradores em domicílios particulares permanentes ocupados.', 'census')], 'residents': select(homes, '382', '2022', **{'1': '6795'})},
        'territory': {'status': 'real', 'sourceIds': ['territorial-area', 'locality', 'municipal-boundary'], 'geometryReference': '2022', 'region': locality['microrregiao']['mesorregiao']['UF']['regiao']['nome'], 'immediateRegion': locality['regiao-imediata']['nome'], 'intermediateRegion': locality['regiao-imediata']['regiao-intermediaria']['nome'], 'geometry': geometry},
        'sources': ibge.sources,
        'collection': {'attemptedAt': now, 'lastSuccessAt': now, 'failures': [], 'policy': 'Preservação integral do último snapshot se qualquer coleta/validação requerida falhar.'},
    }
    validate(result)
    return result, ibge.raw


def validate_geometry(geometry):
    if geometry['type'] != 'FeatureCollection' or len(geometry['features']) != 1:
        raise ValueError('Malha não é exclusiva do município')
    feature = geometry['features'][0]
    if feature['properties'].get('codarea') != CODE:
        raise ValueError('Código da geometria incorreto')
    geom = feature['geometry']
    if geom['type'] not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Geometria inesperada')
    polygons = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    for polygon in polygons:
        for ring in polygon:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('Anel inválido')
            for lon, lat in ring:
                if not math.isfinite(lon) or not math.isfinite(lat) or not (-52 < lon < -50 and -26 < lat < -24):
                    raise ValueError('Coordenadas fora do município esperado')


def validate(data):
    if data['schemaVersion'] != 1 or data['municipality']['code'] != CODE:
        raise ValueError('Schema/município inválido')
    sources = {source['id']: source for source in data['sources']}
    if len(sources) != len(data['sources']):
        raise ValueError('Fontes duplicadas')
    for source in sources.values():
        if not source['collectedAt'] or not source['agency'] == 'IBGE' or not source['url'].startswith('https://servicodados.ibge.gov.br/'):
            raise ValueError('Proveniência inválida')
    for indicator in list(data['summary'].values()) + data['demographicIndicators']['indicators'] + data['households']['indicators']:
        if indicator['status'] != 'real' or indicator['municipalityCode'] != CODE or indicator['sourceId'] not in sources or not indicator['concept'] or not indicator['reference'] or not indicator['collectedAt']:
            raise ValueError('Indicador inválido')
        if indicator['value'] <= 0:
            raise ValueError('Indicador não positivo')
    if data['summary']['population-census']['methodology'] != 'census' or data['summary']['population-estimate']['methodology'] != 'estimate':
        raise ValueError('Censo/estimativa confundidos')
    for key in ['populationHistory', 'estimateHistory', 'growth', 'ageSex', 'sex', 'race', 'urbanRural', 'demographicIndicators', 'households', 'territory']:
        section = data[key]
        if section['status'] != 'real' or any(identifier not in sources for identifier in section['sourceIds']):
            raise ValueError('Conjunto sem fonte oficial')
    for key, method in [('populationHistory', 'census'), ('estimateHistory', 'estimate')]:
        rows = data[key]['rows']
        if not rows or len({r['period'] for r in rows}) != len(rows) or any(r['value'] <= 0 or r['methodology'] != method or r['sourceId'] not in sources for r in rows):
            raise ValueError('História duplicada/inválida')
    for key in ['sex', 'race', 'urbanRural']:
        section = data[key]
        if len({r['categoryId'] for r in section['rows']}) != len(section['rows']) or sum(r['value'] for r in section['rows']) != section['total']:
            raise ValueError('Distribuição inconsistente')
        if abs(sum(r['percent'] for r in section['rows']) - 100) > 1e-8:
            raise ValueError('Percentuais não somam 100%')
        for row in section['rows']:
            if row['value'] < 0 or abs(row['percent'] - row['value'] / section['total'] * 100) > 1e-8:
                raise ValueError('Percentual inconsistente')
    age = data['ageSex']
    if len({r['ageGroup'] for r in age['rows']}) != len(age['rows']) or sum(r['total'] for r in age['rows']) != age['total']:
        raise ValueError('Idades incompletas')
    category_ids = [i for r in age['rows'] for i in r['categoryIds']]
    if len(set(category_ids)) != len(category_ids) or set(category_ids) != set(AGES) - {'100362'}:
        raise ValueError('Faixas sobrepostas/incompletas')
    for row in age['rows']:
        if row['male'] < 0 or row['female'] < 0 or row['male'] + row['female'] != row['total'] or abs(row['percent'] - row['total'] / age['total'] * 100) > 1e-8:
            raise ValueError('Idade/sexo inconsistente')
    for sex_id, field in [('4', 'male'), ('5', 'female')]:
        if sum(r[field] for r in age['rows']) != next(r['value'] for r in data['sex']['rows'] if r['categoryId'] == sex_id):
            raise ValueError('Totais sexo/idade inconsistentes no mesmo universo')
    growth = data['growth']
    if abs(growth['compatibleBaseline'] + growth['absoluteChange'] - data['summary']['population-census']['value']) > 1e-8 or abs(growth['percentChange'] - growth['absoluteChange'] / growth['compatibleBaseline'] * 100) > 1e-8:
        raise ValueError('Variação inconsistente')
    validate_geometry(data['territory']['geometry'])
    def finite(obj):
        if isinstance(obj, float) and not math.isfinite(obj):
            raise ValueError('Número não finito')
        if isinstance(obj, dict):
            for value in obj.values(): finite(value)
        elif isinstance(obj, list):
            for value in obj: finite(value)
    finite(data)


def export_csv(data, directory):
    exports = {
        'population-history.csv': (['period', 'value', 'methodology', 'sourceId'], data['populationHistory']['rows']),
        'population-estimates.csv': (['period', 'value', 'methodology', 'sourceId'], data['estimateHistory']['rows']),
        'population-age-sex.csv': (['ageGroup', 'male', 'female', 'total', 'percent'], data['ageSex']['rows']),
        'population-race.csv': (['category', 'value', 'percent'], data['race']['rows']),
    }
    for name, (fields, rows) in exports.items():
        handle = io.StringIO(newline='')
        writer = csv.DictWriter(handle, fieldnames=fields + ['reference', 'sourceUrl'], extrasaction='ignore')
        writer.writeheader()
        sources = {s['id']: s for s in data['sources']}
        section = data['ageSex'] if 'age-sex' in name else data['race'] if 'race' in name else None
        for row in rows:
            source_id = row.get('sourceId', section['sourceIds'][0] if section else '')
            writer.writerow({**row, 'reference': row.get('period', '2022'), 'sourceUrl': sources[source_id]['url']})
        # Export files are derived; population.json is the authoritative validated snapshot.
        (directory / name).write_text(handle.getvalue(), encoding='utf-8')


def sync_catalog(data, directory):
    path = directory / 'indicators.json'
    catalog = read(path, None)
    if catalog is None:
        return
    # Only replace this module. Economy and every other module remain byte-equivalent as objects.
    catalog['indicators'] = [i for i in catalog['indicators'] if i['module'] != 'population']
    for item in data['summary'].values():
        catalog['indicators'].append({**item, 'module': 'population', 'series': [{'period': item['reference'], 'value': item['value']}], 'note': item['concept']})
    catalog['indicators'].sort(key=lambda i: (i['module'], i['id']))
    atomic_write(path, catalog)


def update(directory, offline=False):
    directory = Path(directory)
    path = directory / 'population.json'
    previous = read(path, None)
    if offline:
        if previous is None:
            raise ValueError('Snapshot de população ausente')
        validate(previous)
        return previous
    now = datetime.now(timezone.utc).isoformat()
    try:
        candidate, raw = collect(now)
        # All responses are validated before any snapshot is replaced.
        for identifier, payload in raw.items():
            payload.pop('collectedAt', None)
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
            relative = f'population/raw/{identifier}-{digest}.json'
            atomic_write(directory / relative, payload)
            next(s for s in candidate['sources'] if s['id'] == identifier)['rawPath'] = relative
        validate(candidate)
        candidate = preserve_collection_times(candidate, previous)
        if candidate is previous:
            print("population: fontes verificadas, sem alterações.")
            return previous
        atomic_write(path, candidate)
    except Exception as exc:
        if previous is None:
            raise RuntimeError(f'População: primeira coleta incompleta; nenhum valor publicado: {exc}') from exc
        validate(previous)
        previous['collection']['attemptedAt'] = now
        previous['collection']['failures'] = [f'{type(exc).__name__}: {exc}']
        atomic_write(path, previous)
        print(f'População: snapshot preservado; falha de coleta: {exc}')
        return previous
    atomic_write(directory / 'population/turvo.geojson', candidate['territory']['geometry'])
    export_csv(candidate, directory)
    sync_catalog(candidate, directory)
    print(f'População: {len(candidate["sources"])} fontes verificadas; snapshot íntegro publicado.')
    return candidate
