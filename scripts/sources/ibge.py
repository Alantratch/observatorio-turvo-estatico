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


def aggregate_url(table, periods, variables, classifications):
    params = {'localidades': f'N6[{CODE}]'}
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

    def aggregate(self, identifier, table, variables, classifications, periods=None, allow_missing=False, transformations=(), methodology=''):
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
        url = aggregate_url(table, periods, variables, classifications)
        payload = request_json(url)
        rows = parse_aggregates(payload, variables, periods, classifications, allow_missing=allow_missing)
        self.raw[identifier] = {'metadata': meta, 'periods': published, 'response': payload, 'url': url, 'collectedAt': self.collected_at}
        self.sources.append({'id': identifier, 'agency': 'IBGE', 'research': meta['pesquisa'], 'table': table, 'title': meta['nome'], 'variables': [{'id': key, 'name': name, 'unit': unit} for key, (name, unit) in variables.items()], 'classifications': [{'id': key, 'categories': values} for key, values in classifications.items()], 'periods': periods, 'reference': ', '.join(periods), 'url': url, 'officialUrl': f'https://sidra.ibge.gov.br/tabela/{table}', 'metadataUrl': metadata_url, 'collectedAt': self.collected_at, 'transformations': list(transformations) + ["Símbolo SIDRA '-' = zero absoluto (conversão explícita); X, .. e ... nunca são convertidos em zero. Resposta bruta preservada."], 'methodology': methodology})
        return rows
