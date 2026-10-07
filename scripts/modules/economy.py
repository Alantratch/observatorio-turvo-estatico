"""Municipal GDP: official current prices, separate sector vintages, audited snapshots."""
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from scripts.common import atomic_write, number, read, request_json, preserve_collection_times
from scripts.sources.ibge import IBGE, CODE

MUNICIPALITIES = {CODE: 'Turvo', '4109401': 'Guarapuava', '4119608': 'Pitanga', '4113254': 'Laranjal'}
OFFICIAL = 'https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html'
NOTE = 'https://biblioteca.ibge.gov.br/visualizacao/livros/liv102094.pdf'
PESQUISAS = 'https://servicodados.ibge.gov.br/api/v1/pesquisas'
VARIABLES = {
    '37': ('Produto Interno Bruto a preços correntes', 'Mil Reais'),
    '543': ('Impostos, líquidos de subsídios, sobre produtos a preços correntes', 'Mil Reais'),
    '498': ('Valor adicionado bruto a preços correntes total', 'Mil Reais'),
    '513': ('Valor adicionado bruto a preços correntes da agropecuária', 'Mil Reais'),
    '516': ('Participação do valor adicionado bruto a preços correntes da agropecuária no valor adicionado bruto a preços correntes total', '%'),
    '517': ('Valor adicionado bruto a preços correntes da indústria', 'Mil Reais'),
    '520': ('Participação do valor adicionado bruto a preços correntes da indústria no valor adicionado bruto a preços correntes total', '%'),
    '6575': ('Valor adicionado bruto a preços correntes dos serviços, exclusive administração, defesa, educação e saúde públicas e seguridade social', 'Mil Reais'),
    '6574': ('Participação do valor adicionado bruto a preços correntes dos serviços, exclusive administração, defesa, educação e saúde públicas e seguridade social, no valor adicionado bruto a preços correntes total', '%'),
    '525': ('Valor adicionado bruto a preços correntes da administração, defesa, educação e saúde públicas e seguridade social', 'Mil Reais'),
    '528': ('Participação do valor adicionado bruto a preços correntes da administração, defesa, educação e saúde públicas e seguridade social no valor adicionado bruto a preços correntes total', '%'),
}
SECTORS = [
    ('agriculture', 'Agropecuária', '513', '516'),
    ('industry', 'Indústria', '517', '520'),
    ('services', 'Serviços, exceto administração pública', '6575', '6574'),
    ('publicAdministration', 'Administração, defesa, educação e saúde públicas e seguridade social', '525', '528'),
]
METHOD = 'gdp-municipal-reference-2010-current-prices'


def nominal_change(current, previous):
    if previous is None or previous <= 0 or current is None:
        return None
    return (current / previous - 1) * 100


def parse_capita(metadata, hierarchy, payload, code):
    """Validate revised-series concept through its parent, not the generic leaf name."""
    if len(metadata) != 1 or metadata[0]['id'] != 47001 or metadata[0]['pesquisa_id'] != 38 or metadata[0]['indicador'] != 'Série revisada' or metadata[0]['unidade'] != {'id': 'R$', 'classe': '$', 'multiplicador': 1}:
        raise ValueError('Metadados do PIB per capita divergentes')
    parent = next((i for i in hierarchy if i['id'] == 47000), None)
    if not parent or parent['indicador'] != 'PIB per capita' or not any(i['id'] == 47001 and i['indicador'] == 'Série revisada' and i['unidade'] == metadata[0]['unidade'] for i in parent['children']):
        raise ValueError('Conceito per capita não confirmado na pesquisa 38')
    if len(payload) != 1 or payload[0]['id'] != 47001 or len(payload[0]['res']) != 1 or payload[0]['res'][0]['localidade'] != code[:-1]:
        raise ValueError('Município/indicador per capita incorreto')
    rows, missing = [], []
    for period, raw in sorted(payload[0]['res'][0]['res'].items()):
        valid_period(period)
        value = number(raw, allow_missing=True)
        if value is None:
            missing.append({'period': period, 'rawSymbol': raw})
        elif value < 0:
            raise ValueError('PIB per capita negativo')
        else:
            rows.append({'period': period, 'value': value, 'variableId': '47001'})
    if not rows:
        raise ValueError('PIB per capita sem observações oficiais')
    return rows, missing


def valid_period(period):
    if not isinstance(period, str) or not re.fullmatch(r'\d{4}', period) or not 1990 <= int(period) <= datetime.now(timezone.utc).year:
        raise ValueError('Período inválido')


def build_municipality(rows, capita_rows, capita_missing, code, name):
    index = {(r['variable'], r['period']): r for r in rows}
    periods = sorted({r['period'] for r in rows})
    source_id = f'accounts-{code}'
    capita_id = f'capita-{code}'
    def point(variable, period):
        value = index[(variable, period)]['value']
        return {'period': period, 'value': None if value is None else value * 1000, 'variableId': variable, 'sourceId': source_id}
    gdp = []
    for period in periods:
        p = point('37', period)
        if p['value'] is None:
            raise ValueError('Série de PIB incompleta; preservar snapshot')
        previous = gdp[-1] if gdp else None
        p['from'] = previous['period'] if previous else None
        p['nominalChange'] = nominal_change(p['value'], previous['value'] if previous else None)
        p['annual'] = bool(previous and int(period) - int(previous['period']) == 1)
        gdp.append(p)
    composition, unavailable = [], []
    for period in periods:
        required = ['498', '543'] + [v for _, _, value, share in SECTORS for v in [value, share]]
        cells = [index[(v, period)] for v in required]
        if any(c['value'] is None for c in cells):
            # Partial opening cannot silently erase a valid older composition or publish fragments.
            if not all(c['value'] is None for c in cells):
                raise ValueError(f'Abertura setorial parcial em {period}')
            if period not in {'2022', '2023'}:
                raise ValueError(f'Ausência setorial inesperada em {period}; revisar metodologia')
            unavailable.append({'period': period, 'reason': 'Abertura não divulgada pelo IBGE nesta edição.', 'cells': [{'variableId': c['variable'], 'rawSymbol': c['rawSymbol']} for c in cells]})
            continue
        total = point('498', period)['value']
        sectors = [{'id': key, 'label': label, **point(value_id, period), 'share': index[(share_id, period)]['value'], 'shareVariableId': share_id, 'shareUnit': '%', 'denominator': 'vab-total', 'unit': 'R$'} for key, label, value_id, share_id in SECTORS]
        composition.append({'period': period, 'vabTotal': total, 'vabVariableId': '498', 'sourceId': source_id, 'sectors': sectors, 'leadingSector': max(sectors, key=lambda s: s['share'])['id']})
    if not composition:
        raise ValueError('Nenhuma abertura setorial completa')
    taxes = [point('543', p) for p in periods if index[('543', p)]['value'] is not None]
    for tax in taxes:
        tax['shareOfGdp'] = tax['value'] / next(p['value'] for p in gdp if p['period'] == tax['period']) * 100
    capita = [{**p, 'sourceId': capita_id} for p in capita_rows]
    return {'municipality': {'code': code, 'name': name, 'state': 'PR'},
            'gdp': {'unit': 'R$', 'methodology': METHOD, 'sourceId': source_id, 'latest': gdp[-1], 'series': gdp},
            'gdpPerCapita': {'unit': 'R$ por habitante', 'methodology': METHOD, 'sourceId': capita_id, 'latest': capita[-1], 'series': capita, 'unavailable': capita_missing},
            'sectorComposition': {'unit': 'R$', 'shareUnit': '%', 'denominator': 'vab-total', 'methodology': METHOD, 'sourceId': source_id, 'latestPeriod': composition[-1]['period'], 'series': composition, 'unavailable': unavailable},
            'taxes': {'unit': 'R$', 'shareDenominator': 'gdp', 'methodology': METHOD, 'sourceId': source_id, 'latest': taxes[-1], 'series': taxes}}


def summary(data, sources, code=CODE):
    by_id = {s['id']: s for s in sources}
    sector = data['sectorComposition']['series'][-1]
    leading = next(s for s in sector['sectors'] if s['id'] == sector['leadingSector'])
    entries = [
        ('gdp', 'Produto Interno Bruto (PIB)', data['gdp']['latest']['value'], 'R$', data['gdp']['latest']['period'], data['gdp']['sourceId'], 'Valor dos bens e serviços finais produzidos no território; preços correntes.'),
        ('gdp-per-capita', 'PIB per capita', data['gdpPerCapita']['latest']['value'], 'R$ por habitante', data['gdpPerCapita']['latest']['period'], data['gdpPerCapita']['sourceId'], 'Valor oficial do IBGE; não representa salário ou renda média dos moradores.'),
        ('gdp-nominal-change', 'Variação nominal do PIB', data['gdp']['latest']['nominalChange'], '%', data['gdp']['latest']['period'], data['gdp']['sourceId'], f"Comparação {data['gdp']['latest']['from']}–{data['gdp']['latest']['period']}; (atual/anterior − 1) × 100; sem descontar inflação."),
        ('economy-leading-sector', 'Principal atividade econômica', leading['share'], '% do VAB', sector['period'], data['sectorComposition']['sourceId'], leading['label']),
    ]
    return {id_: {'id': id_, 'title': title, 'value': value, 'unit': unit, 'reference': period, 'sourceId': sid, 'source': f"IBGE / {by_id[sid]['research']} · {('Tabela '+by_id[sid]['table']) if by_id[sid].get('table') else 'Indicador 47001'}", 'agency': 'IBGE', 'municipalityCode': code, 'collectedAt': by_id[sid]['collectedAt'], 'url': by_id[sid]['url'], 'methodology': METHOD, 'status': 'real', 'concept': concept} for id_, title, value, unit, period, sid, concept in entries}


def collect(now):
    ibge = IBGE(now)
    meta_url, hierarchy_url = f'{PESQUISAS}/indicadores/47001', f'{PESQUISAS}/38/indicadores'
    metadata, hierarchy = request_json(meta_url), request_json(hierarchy_url)
    municipalities = []
    for code, name in MUNICIPALITIES.items():
        rows = ibge.aggregate(f'accounts-{code}', '5938', VARIABLES, {}, allow_missing=True, code=code,
                              transformations=['Valores em Mil Reais × 1.000 → R$; percentuais oficiais preservados sem recalcular ou normalizar.', 'Variação nominal = (PIB atual / PIB anterior − 1) × 100; primeira observação/base zero = null.', 'Impostos/PIB × 100 é cálculo derivado; percentuais setoriais têm denominador VAB.'],
                              methodology='PIB dos Municípios, referência 2010, preços correntes. Serviços excluem administração pública. Não há abertura setorial, VAB total ou impostos em 2022/2023; manter anos independentes.')
        ibge.sources[-1]['definitionUrl'] = OFFICIAL
        url = f'{meta_url}/resultados/{code}'
        payload = request_json(url)
        capita, missing = parse_capita(metadata, hierarchy, payload, code)
        identifier = f'capita-{code}'
        ibge.raw[identifier] = {'metadata': metadata, 'hierarchy': hierarchy, 'response': payload, 'url': url}
        ibge.sources.append({'id': identifier, 'municipalityCode': code, 'agency': 'IBGE', 'research': 'Produto Interno Bruto dos Municípios', 'surveyId': '38', 'indicator': '47001', 'title': 'PIB per capita — série revisada', 'variables': [{'id': '47001', 'name': 'PIB per capita — série revisada', 'unit': 'R$', 'parentId': '47000'}], 'classifications': [], 'periods': [p['period'] for p in capita], 'reference': ', '.join(p['period'] for p in capita), 'url': url, 'officialUrl': OFFICIAL, 'metadataUrl': meta_url, 'hierarchyUrl': hierarchy_url, 'definitionUrl': OFFICIAL, 'collectedAt': now, 'transformations': ['Valor oficial em reais, multiplicador 1; não recalculado com população de outra pesquisa.', 'Pesquisas retorna código municipal de seis dígitos; validação explícita sem dígito verificador.', 'Somente série revisada (47001); série encerrada (47002) não concatenada.'], 'methodology': 'Indicador 47001 subordinado a PIB per capita (47000), pesquisa 38. PIB dividido pela população utilizada na metodologia oficial. Não é renda pessoal nem salário.'})
        municipalities.append(build_municipality(rows, capita, missing, code, name))
    own, *peers = municipalities
    result = {'schemaVersion': 1, **own, 'summary': summary(own, ibge.sources), 'comparisons': peers,
              'sources': ibge.sources, 'methodology': {'prices': 'current', 'referenceYear': '2010', 'sectorGapPeriods': ['2022', '2023'], 'sectorGapUrl': NOTE, 'officialUrl': OFFICIAL},
              'collection': {'attemptedAt': now, 'lastSuccessAt': now, 'failures': [], 'policy': 'Qualquer falha requerida preserva integralmente o último snapshot validado, inclusive comparações.'}}
    validate(result)
    return result, ibge.raw


def validate(data):
    if data['schemaVersion'] != 1 or data['municipality'] != {'code': CODE, 'name': 'Turvo', 'state': 'PR'} or data['methodology']['prices'] != 'current':
        raise ValueError('Schema/município/preços incompatíveis')
    sources = {s['id']: s for s in data['sources']}
    if len(sources) != len(data['sources']):
        raise ValueError('Fontes duplicadas')
    for source in sources.values():
        expected_variables = [{'id': key, 'name': name, 'unit': unit} for key, (name, unit) in VARIABLES.items()] if source.get('table') == '5938' else [{'id': '47001', 'name': 'PIB per capita — série revisada', 'unit': 'R$', 'parentId': '47000'}]
        if source['variables'] != expected_variables or source['classifications'] != [] or source['municipalityCode'] not in MUNICIPALITIES or (source.get('table') != '5938' and source.get('indicator') != '47001'):
            raise ValueError('Metadados da fonte inválidos')
        if source['agency'] != 'IBGE' or not source['collectedAt'] or not source['url'].startswith('https://servicodados.ibge.gov.br/') or not source['variables']:
            raise ValueError('Proveniência inválida')
    def finite(obj):
        if isinstance(obj, float) and not math.isfinite(obj): raise ValueError('Número não finito')
        if isinstance(obj, dict):
            for v in obj.values(): finite(v)
        elif isinstance(obj, list):
            for v in obj: finite(v)
    finite(data)
    all_items = [data, *data['comparisons']]
    if {d['municipality']['code'] for d in all_items} != set(MUNICIPALITIES) or len(all_items) != len(MUNICIPALITIES):
        raise ValueError('Comparações municipais incompletas/duplicadas')
    for item in all_items:
        code = item['municipality']['code']
        if item['municipality']['name'] != MUNICIPALITIES[code] or item['municipality']['state'] != 'PR': raise ValueError('Identidade municipal inválida')
        for key, unit, variable in [('gdp', 'R$', '37'), ('gdpPerCapita', 'R$ por habitante', '47001'), ('taxes', 'R$', '543')]:
            section = item[key]
            rows = section['series']
            if not rows or section['unit'] != unit or section['methodology'] != METHOD or section['latest'] != rows[-1]: raise ValueError('Série/unidade/latest inválidos')
            periods = [p['period'] for p in rows]
            if periods != sorted(set(periods)): raise ValueError('Série desordenada/duplicada')
            sid = section['sourceId']
            if sid not in sources or sources[sid]['municipalityCode'] != code: raise ValueError('Fonte do município incorreta')
            for p in rows:
                valid_period(p['period'])
                if not isinstance(p['value'], (int, float)) or p['value'] < 0 or p['sourceId'] != sid or p['variableId'] != variable or p['period'] not in sources[sid]['periods']: raise ValueError('Observação sem fonte válida')
        for i, p in enumerate(item['gdp']['series']):
            previous = item['gdp']['series'][i-1] if i else None
            change = nominal_change(p['value'], previous['value'] if previous else None)
            if p['from'] != (previous['period'] if previous else None) or p['annual'] != bool(previous and int(p['period']) - int(previous['period']) == 1) or (change is None and p['nominalChange'] is not None) or (change is not None and (p['nominalChange'] is None or abs(p['nominalChange'] - change) > 1e-9)):
                raise ValueError('Variação nominal inconsistente')
        composition = item['sectorComposition']
        periods = [p['period'] for p in composition['series']]
        if not periods or periods != sorted(set(periods)) or composition['latestPeriod'] != periods[-1] or composition['denominator'] != 'vab-total' or composition['unit'] != 'R$' or composition['shareUnit'] != '%' or composition['methodology'] != METHOD:
            raise ValueError('Referência/composição inválida')
        if composition['sourceId'] != item['gdp']['sourceId'] or item['taxes']['shareDenominator'] != 'gdp' or item['taxes']['sourceId'] != composition['sourceId']:
            raise ValueError('Denominador/fonte inconsistente')
        if periods != [p['period'] for p in item['taxes']['series']]: raise ValueError('Referências VAB/impostos inconsistentes')
        available_periods = sources[composition['sourceId']]['periods']
        if sorted(periods + [u['period'] for u in composition['unavailable']]) != sorted(available_periods): raise ValueError('Períodos da composição incompletos')
        if any(u['period'] not in data['methodology']['sectorGapPeriods'] or any(c['rawSymbol'] not in {'..', '...', 'X', None} for c in u['cells']) for u in composition['unavailable']): raise ValueError('Ausência setorial não documentada')
        if any(p in periods for p in [u['period'] for u in composition['unavailable']]): raise ValueError('Ano ausente associado a setores')
        for row in composition['series']:
            valid_period(row['period'])
            if row['vabTotal'] <= 0 or row['vabVariableId'] != '498' or row['sourceId'] != composition['sourceId']: raise ValueError('VAB inválido')
            if [s['id'] for s in row['sectors']] != [s[0] for s in SECTORS]: raise ValueError('Setores incompletos/incorretos')
            for sector, (key, label, value_id, share_id) in zip(row['sectors'], SECTORS):
                if sector['period'] != row['period'] or sector['label'] != label or sector['variableId'] != value_id or sector['shareVariableId'] != share_id or sector['unit'] != 'R$' or sector['shareUnit'] != '%' or sector['denominator'] != 'vab-total' or sector['sourceId'] != row['sourceId']: raise ValueError('Setor/variável/referência inválidos')
                if sector['value'] < 0 or not 0 <= sector['share'] <= 100 or abs(sector['share'] - sector['value'] / row['vabTotal'] * 100) > .02: raise ValueError('Participação setorial inconsistente')
            # Values rounded to thousand reais; tolerance up to four independently rounded sectors.
            if abs(sum(s['value'] for s in row['sectors']) - row['vabTotal']) > 4000 or abs(sum(s['share'] for s in row['sectors']) - 100) > .03: raise ValueError('Soma setorial inconsistente')
            if row['leadingSector'] != max(row['sectors'], key=lambda s:s['share'])['id']: raise ValueError('Atividade principal inválida')
            gdp = next(p['value'] for p in item['gdp']['series'] if p['period'] == row['period'])
            tax = next(p for p in item['taxes']['series'] if p['period'] == row['period'])
            if abs(gdp - row['vabTotal'] - tax['value']) > 2000: raise ValueError('Identidade PIB ≈ VAB + impostos inconsistente')
            if abs(tax['shareOfGdp'] - tax['value'] / gdp * 100) > 1e-9: raise ValueError('Participação impostos/PIB inconsistente')
    if data['summary'] != summary(data, data['sources']): raise ValueError('Resumo não corresponde às séries oficiais')
    if not data['collection']['lastSuccessAt'] or not isinstance(data['collection']['failures'], list): raise ValueError('Relatório de coleta inválido')


def export_csv(data, directory):
    sources = {s['id']: s for s in data['sources']}
    datasets = [data, *data['comparisons']]
    for filename, key in [('gdp.csv', 'gdp'), ('gdp-per-capita.csv', 'gdpPerCapita'), ('economy-sectors.csv', 'sectorComposition')]:
        fields = ['municipalityCode', 'municipality', 'period', 'unit', 'value', 'variableId', 'sourceId', 'sourceUrl', 'collectedAt']
        fields += ['from', 'nominalChange', 'annual'] if key == 'gdp' else ['sector', 'share', 'shareVariableId', 'denominator', 'vabTotal'] if key == 'sectorComposition' else []
        out = io.StringIO(newline=''); writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for item in datasets:
            for row in item[key]['series']:
                points = [{**s, 'sector': s['label'], 'vabTotal': row['vabTotal']} for s in row['sectors']] if key == 'sectorComposition' else [row]
                for p in points:
                    source = sources[p['sourceId']]
                    writer.writerow({**p, 'unit': item[key]['unit'], 'municipalityCode': item['municipality']['code'], 'municipality': item['municipality']['name'], 'sourceUrl': source['url'], 'collectedAt': source['collectedAt']})
        path = directory / filename
        # Derived CSVs replaced atomically too, including on interrupted local runs.
        temporary = path.with_suffix('.csv.tmp'); temporary.write_text(out.getvalue(), encoding='utf-8'); temporary.replace(path)


def sync_catalog(data, directory):
    def indicators(item):
        metrics = summary(item, data['sources'], item['municipality']['code'])
        result = []
        for metric in metrics.values():
            if metric['id'] == 'gdp': points = item['gdp']['series']
            elif metric['id'] == 'gdp-per-capita': points = item['gdpPerCapita']['series']
            else: points = [{'period': metric['reference'], 'value': metric['value']}]
            result.append({**metric, 'module': 'economy', 'series': [{'period': p['period'], 'value': p['value']} for p in points], 'note': metric['concept']})
        return result
    catalog = read(directory / 'indicators.json', None)
    if catalog:
        catalog['indicators'] = sorted([i for i in catalog['indicators'] if i['module'] != 'economy'] + indicators(data), key=lambda i:(i['module'],i['id']))
        atomic_write(directory / 'indicators.json', catalog)
    peers = read(directory / 'comparison.json', {})
    for item in data['comparisons']:
        code = item['municipality']['code']
        peer = peers.setdefault(code, {'name': item['municipality']['name'], 'indicators': []})
        peer['indicators'] = [i for i in peer['indicators'] if i['module'] != 'economy'] + indicators(item)
    atomic_write(directory / 'comparison.json', peers)


def update(directory, offline=False):
    directory = Path(directory); path = directory / 'economy.json'; previous = read(path, None)
    if offline:
        if previous is None: raise ValueError('Snapshot de Economia ausente')
        validate(previous); return previous
    now = datetime.now(timezone.utc).isoformat()
    try:
        candidate, raw = collect(now)
        validate(candidate)
        for identifier, payload in raw.items():
            payload.pop('collectedAt', None)
            digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
            relative = f'economy/raw/{identifier}-{digest}.json'
            atomic_write(directory / relative, payload)
            next(s for s in candidate['sources'] if s['id'] == identifier)['rawPath'] = relative
        validate(candidate)
        candidate = preserve_collection_times(candidate, previous)
        if candidate is previous:
            print("economy: fontes verificadas, sem alterações.")
            return previous
        export_csv(candidate, directory)
        sync_catalog(candidate, directory)
        atomic_write(path, candidate)
    except Exception as exc:
        if previous is None: raise RuntimeError(f'Economia: primeira coleta incompleta; nenhum número publicado: {exc}') from exc
        validate(previous)
        previous['collection']['attemptedAt'] = now
        previous['collection']['failures'] = [f'{type(exc).__name__}: {exc}']
        atomic_write(path, previous)
        print(f'Economia: snapshot preservado; {exc}'); return previous
    print(f'Economia: {len(candidate["sources"])} fontes; PIB {candidate["gdp"]["latest"]["period"]}, setores {candidate["sectorComposition"]["latestPeriod"]}.')
    return candidate
