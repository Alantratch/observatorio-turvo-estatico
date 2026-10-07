"""IBGE aggregates adapter preserving periods, units and classification dimensions."""
from itertools import product
from urllib.parse import urlencode, quote
from scripts.common import number, request_json

BASE = 'https://servicodados.ibge.gov.br/api/v3/agregados'
CODE = '4127965'


def check_metadata(meta, variables, classifications):
    if 'N6' not in sum(meta['nivelTerritorial'].values(), []):
        raise ValueError('Tabela sem nível municipal N6')
    by_variable = {str(v['id']): v for v in meta['variaveis']}
    for identifier, (name, unit) in variables.items():
        item = by_variable.get(identifier)
        if not item or item['nome'] != name or item['unidade'] != unit:
            raise ValueError(f'Metadados divergentes: variável {identifier}')
    by_class = {str(c['id']): c for c in meta['classificacoes']}
    for identifier, categories in classifications.items():
        if identifier not in by_class:
            raise ValueError(f'Classificação inexistente {identifier}')
        actual = {str(c['id']): c['nome'] for c in by_class[identifier]['categorias']}
        if any(actual.get(k) != name for k, name in categories.items()):
            raise ValueError(f'Categorias divergentes na classificação {identifier}')


def aggregate_url(table, periods, variables, classifications, code=CODE):
    params = {'localidades': f'N6[{code}]'}
    if classifications:
        params['classificacao'] = '|'.join(f'{key}[{",".join(values)}]' for key, values in classifications.items())
    return f'{BASE}/{table}/periodos/{quote("|".join(periods))}/variaveis/{quote("|".join(variables))}?{urlencode(params)}'


def parse_aggregates(payload, variables, periods, classifications, code=CODE, allow_missing=False):
    """Require every requested cell exactly once. Missing is distinct from numeric zero."""
    rows = []
    seen = set()
    expected = set()
    class_keys = sorted(classifications)
    combos = product(*(classifications[key] for key in class_keys)) if class_keys else [()]
    for categories in combos:
        for variable in variables:
            for period in periods:
                expected.add((variable, period, tuple(zip(class_keys, categories))))
    for variable in payload:
        identifier = variable['id']
        if identifier not in variables or variable['unidade'] != variables[identifier][1] or variable['variavel'] != variables[identifier][0]:
            raise ValueError('Variável/unidade inesperada na resposta')
        for result in variable['resultados']:
            categories = {}
            for classification in result['classificacoes']:
                key = classification['id']
                if key in categories or key not in classifications or len(classification['categoria']) != 1:
                    raise ValueError('Classificação ausente, duplicada ou inesperada')
                category, label = next(iter(classification['categoria'].items()))
                if classifications[key].get(category) != label:
                    raise ValueError('Categoria inesperada na resposta')
                categories[key] = category
            if set(categories) != set(classifications):
                raise ValueError('Classificações incompletas')
            for series in result['series']:
                locality = series['localidade']
                if locality['id'] != code or locality['nivel']['id'] != 'N6':
                    raise ValueError('Município/nível incorreto')
                for period, raw in series['serie'].items():
                    key = (identifier, period, tuple(sorted(categories.items())))
                    if key not in expected or key in seen:
                        raise ValueError('Período inesperado ou célula duplicada')
                    seen.add(key)
                    value = number(raw, allow_missing=allow_missing, sidra_zero=True)
                    if value is not None and value < 0 and identifier not in {'5936', '10605'}:
                        raise ValueError('Valor negativo inesperado')
                    if identifier in {'93', '9324', '381', '382', '5936'} and value is not None and value != int(value):
                        raise ValueError('Contagem populacional não inteira')
                    rows.append({'variable': identifier, 'period': period, 'categories': categories, 'value': value, 'rawSymbol': raw if raw in {'-', '..', '...', 'X'} else None})
    if seen != expected:
        raise ValueError(f'Resposta incompleta: faltam {len(expected - seen)} células')
    return rows


class IBGE:
    def __init__(self, collected_at):
        self.collected_at = collected_at
        self.raw = {}
        self.sources = []
        self.metadata_cache = {}
        self.period_cache = {}

    def aggregate(self, identifier, table, variables, classifications, periods=None, allow_missing=False, transformations=(), methodology='', code=CODE):
        metadata_url = f'{BASE}/{table}/metadados'
        if table not in self.metadata_cache:
            self.metadata_cache[table] = request_json(metadata_url)
        meta = self.metadata_cache[table]
        if str(meta['id']) != table:
            raise ValueError('Tabela divergente')
        check_metadata(meta, variables, classifications)
        period_url = f'{BASE}/{table}/periodos'
        if table not in self.period_cache:
            self.period_cache[table] = request_json(period_url)
        published = self.period_cache[table]
        available = [p['id'] for p in published]
        periods = sorted(available) if periods is None else periods
        if not periods or any(p not in available for p in periods):
            raise ValueError('Período não publicado')
        url = aggregate_url(table, periods, variables, classifications, code)
        payload = request_json(url)
        rows = parse_aggregates(payload, variables, periods, classifications, code=code, allow_missing=allow_missing)
        self.raw[identifier] = {'metadata': meta, 'periods': published, 'response': payload, 'url': url, 'collectedAt': self.collected_at}
        self.sources.append({'id': identifier, 'municipalityCode': code, 'agency': 'IBGE', 'research': meta['pesquisa'], 'table': table, 'title': meta['nome'], 'variables': [{'id': key, 'name': name, 'unit': unit} for key, (name, unit) in variables.items()], 'classifications': [{'id': key, 'categories': values} for key, values in classifications.items()], 'periods': periods, 'reference': ', '.join(periods), 'url': url, 'officialUrl': f'https://sidra.ibge.gov.br/tabela/{table}', 'metadataUrl': metadata_url, 'collectedAt': self.collected_at, 'transformations': list(transformations) + ["Símbolo SIDRA '-' = zero absoluto (conversão explícita); X, .. e ... nunca são convertidos em zero. Resposta bruta preservada."], 'methodology': methodology})
        return rows

# Agricultural tables use classification-specific physical units and historical
# currencies. Keep this extension in the same IBGE connector; old module parsing
# and strict metadata contracts remain unchanged.
def agricultural_symbol(raw):
    statuses = {'X': 'suppressed', '..': 'notApplicable', '...': 'unavailable'}
    if raw in statuses:
        return {'value': None, 'status': statuses[raw], 'rawSymbol': raw}
    if raw == '-':
        return {'value': 0, 'status': 'real', 'rawSymbol': '-'}
    value = number(raw)
    if value < 0:
        raise ValueError('Agropecuária não aceita valores negativos')
    return {'value': int(value) if value.is_integer() else value, 'status': 'real', 'rawSymbol': None}


def agricultural_unit(variable, category, period):
    unit = variable['unidade']
    if unit.startswith('Vide categorias'):
        unit = category.get('unidade') if category else None
        return unit or 'Não aplicável'
    if 'Mil Reais [' in unit:
        import re
        interval = re.search(r'Mil Reais \[(\d{4}) a (\d{4})\]', unit)
        if not interval or not int(interval[1]) <= int(period) <= int(interval[2]):
            raise ValueError('Período fora do intervalo monetário confirmado em reais')
        return 'Mil Reais'
    return unit


def parse_agricultural(payload, metadata, variable_ids, periods, classifications, localities):
    """Validate a complete cube, retaining symbols and per-category units."""
    variables = {str(v['id']): v for v in metadata['variaveis']}
    category_metadata = {str(c['id']): {str(v['id']): v for v in c['categorias']} for c in metadata['classificacoes']}
    keys = sorted(classifications)
    combos = list(product(*(classifications[k] for k in keys))) if keys else [()]
    expected = {(code, variable, period, tuple(zip(keys, cats))) for code in localities for variable in variable_ids for period in periods for cats in combos}
    seen, rows = set(), []
    for variable in payload:
        identifier = variable['id']
        if identifier not in variable_ids or variable['variavel'] != variables[identifier]['nome']:
            raise ValueError('Variável agropecuária divergente')
        meta = variables[identifier]
        expected_payload_unit = '' if meta['unidade'].startswith('Vide categorias') else agricultural_unit(meta, None, periods[-1])
        if variable['unidade'] != expected_payload_unit:
            raise ValueError('Unidade agropecuária divergente')
        for result in variable['resultados']:
            categories = {}
            for classification in result['classificacoes']:
                key = classification['id']
                if key not in classifications or key in categories or len(classification['categoria']) != 1:
                    raise ValueError('Dimensão agropecuária inválida')
                category, label = next(iter(classification['categoria'].items()))
                if classifications[key].get(category) != label:
                    raise ValueError('Produto/categoria agropecuária divergente')
                categories[key] = category
            if set(categories) != set(classifications):
                raise ValueError('Dimensões agropecuárias incompletas')
            for series in result['series']:
                loc = series['localidade']
                code = loc['id']
                if code not in localities or loc['nivel']['id'] != localities[code] or (code != '41' and not loc['nome'].endswith('(PR)')):
                    raise ValueError('Município/UF/nível agropecuário divergente')
                category = category_metadata[keys[0]][categories[keys[0]]] if len(keys) == 1 else None
                for period, raw in series['serie'].items():
                    identity = (code, identifier, period, tuple(sorted(categories.items())))
                    if identity not in expected or identity in seen:
                        raise ValueError('Célula agropecuária duplicada ou período inesperado')
                    seen.add(identity)
                    rows.append({'municipalityCode': code, 'variable': identifier, 'period': period, 'categories': categories, 'originalUnit': agricultural_unit(meta, category, period), **agricultural_symbol(raw)})
    if seen != expected:
        raise ValueError(f'Cubo agropecuário incompleto: {len(expected - seen)} células ausentes')
    return rows


class AgriculturalIBGE(IBGE):
    def load_metadata(self, table):
        if table not in self.metadata_cache:
            self.metadata_cache[table] = request_json(f'{BASE}/{table}/metadados')
            self.period_cache[table] = request_json(f'{BASE}/{table}/periodos')
        return self.metadata_cache[table], self.period_cache[table]

    def agricultural(self, identifier, spec, window=10):
        table = spec['table']
        metadata, available = self.load_metadata(table)
        if str(metadata['id']) != table or metadata['pesquisa'] != spec['research']:
            raise ValueError('Pesquisa/agregado agropecuário divergente')
        variables = {str(v['id']): v for v in metadata['variaveis']}
        selected = [v['variable'] for v in spec['metrics'].values()]
        for metric in spec['metrics'].values():
            actual = variables.get(metric['variable'])
            if not actual or actual['nome'] != metric['name']:
                raise ValueError('Conceito da variável agropecuária mudou')
            # Range suffix may advance when a new year is published; physical
            # concepts may not silently change. Resolved monetary unit checked below.
            if 'Mil Reais [' not in metric['metadataUnit'] and actual['unidade'] != metric['metadataUnit']:
                raise ValueError('Unidade de metadados agropecuários mudou')
        if spec.get('classifications'):
            classifications = spec['classifications']
        else:
            classifications = {str(c['id']): {str(v['id']): v['nome'] for v in c['categorias']} for c in metadata['classificacoes']}
        check_metadata(metadata, {i: (variables[i]['nome'], variables[i]['unidade']) for i in selected}, classifications)
        if 'N3' not in sum(metadata['nivelTerritorial'].values(), []):
            raise ValueError('Tabela agropecuária sem nível estadual N3')
        if spec['classification'] and spec['classification'] not in classifications:
            raise ValueError('Classificação de produto alterada')
        periods = sorted(p['id'] for p in available)[-window:]
        import re
        if not periods or any(not re.fullmatch(r'\d{4}', p) or int(p) < 1994 for p in periods):
            raise ValueError('Período agropecuário inválido ou moeda incompatível')
        localities = {'4127965': 'N6', '4109401': 'N6', '4119608': 'N6', '4113254': 'N6', '41': 'N3'}
        params = {'localidades': 'N6[4127965,4109401,4119608,4113254]|N3[41]'}
        if classifications:
            params['classificacao'] = '|'.join(f'{k}[{",".join(values)}]' for k, values in classifications.items())
        url = f'{BASE}/{table}/periodos/{quote("|".join(periods))}/variaveis/{quote("|".join(selected))}?{urlencode(params)}'
        payload = request_json(url)
        rows = parse_agricultural(payload, metadata, selected, periods, classifications, localities)
        self.raw[identifier] = {'metadata': metadata, 'periods': available, 'response': payload, 'url': url, 'collectedAt': self.collected_at}
        self.sources.append({'id': identifier, 'agency': 'IBGE', 'research': metadata['pesquisa'], 'table': table, 'title': metadata['nome'], 'variables': [variables[i] for i in selected], 'classifications': [{'id': k, 'categories': v} for k, v in classifications.items()], 'periods': periods, 'reference': periods[-1], 'publishedPeriods': available, 'municipalityCodes': list(localities), 'url': url, 'officialUrl': f'https://sidra.ibge.gov.br/tabela/{table}', 'metadataUrl': f'{BASE}/{table}/metadados', 'collectedAt': self.collected_at, 'transformations': ["'-' = zero absoluto; X = suprimido, .. = não aplicável, ... = indisponível; nenhum valor oculto é inferido.", 'Mil Reais × 1000 → R$ nominal; unidades físicas obtidas da variável/categoria e das notas oficiais PAM.'], 'methodology': 'Censo estrutural separado das pesquisas anuais; categorias totais e subgrupos não somados.'})
        return rows, metadata
