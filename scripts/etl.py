"""ETL SIDRA sem dependências externas. Falhas preservam o último snapshot válido."""
import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

# Support both `python scripts/etl.py` and imports in offline unit tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.common import atomic_write, read, request_json
from scripts.modules.population import update as update_population
from scripts.modules.economy import update as update_economy
from scripts.modules.employment import update as update_employment

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'public' / 'data'
MUNICIPALITIES = {'4127965': 'Turvo', '4109401': 'Guarapuava', '4113254': 'Laranjal', '4119608': 'Pitanga'}
SOURCES = [
    ('population', 'population', 'População residente', '4714', '93', '2022', 'pessoas', 1),
    ('area', 'population', 'Área territorial', '4714', '6318', '2022', 'km²', 1),
    ('density', 'population', 'Densidade demográfica', '4714', '614', '2022', 'hab/km²', 1),
    ('gdp', 'economy', 'Produto Interno Bruto (PIB)', '5938', '37', 'all', 'R$', 1000),
]
EXPECTED_UNITS = {'93': 'Pessoas', '6318': 'Quilômetros quadrados', '614': 'Habitante por quilômetro quadrado', '37': 'Mil Reais', '543': 'Mil Reais'}

def normalize(rows, spec, code, collected_at):
    identifier, module, title, table, variable, _, unit, multiplier = spec
    points = []
    for row in rows[1:]:
        if row['D1C'] != code or row['D2C'] != variable: raise ValueError('Município ou variável divergente')
        if row['MN'].casefold() != EXPECTED_UNITS[variable].casefold(): raise ValueError('Unidade divergente: ' + row['MN'])
        if row['V'] in ('-', '...', '..', 'X'): continue
        value = float(row['V']) * multiplier
        if not math.isfinite(value) or value < 0: raise ValueError('Valor inválido')
        points.append({'period': row['D3C'], 'value': value})
    if not points: raise ValueError('Sem observações numéricas')
    points.sort(key=lambda p: p['period'])
    return dict(id=identifier, module=module, title=title, value=points[-1]['value'], unit=unit, source=f'IBGE / SIDRA · Tabela {table}', agency='IBGE', reference=points[-1]['period'], url=f'https://apisidra.ibge.gov.br/values/t/{table}/n6/{code}/v/{variable}/p/{spec[5]}', collectedAt=collected_at, municipalityCode=code, status='real', series=points, note='PIB nominal. Valores em mil reais convertidos para reais.' if identifier == 'gdp' else 'Referência temporal conforme fonte; coleta não equivale à publicação.')

def update(offline=False):
    catalog = read(DATA / 'indicators.json', {'schemaVersion': 1, 'municipality': {'code': '4127965', 'name': 'Turvo', 'state': 'PR'}, 'indicators': [], 'collection': {'attemptedAt': None, 'failures': []}})
    peers = read(DATA / 'comparison.json', {})
    if offline:
        validate(catalog)
        return catalog
    now = datetime.now(timezone.utc).isoformat()
    failures = []
    for code, name in MUNICIPALITIES.items():
        items = catalog['indicators'] if code == '4127965' else peers.setdefault(code, {'name': name, 'indicators': []})['indicators']
        for spec in SOURCES:
            # The dedicated module owns GDP once its validated snapshot exists.
            if spec[1] == 'economy' and (DATA / 'economy.json').exists():
                continue
            url = f'https://apisidra.ibge.gov.br/values/t/{spec[3]}/n6/{code}/v/{spec[4]}/p/{spec[5]}'
            try:
                indicator = normalize(request_json(url), spec, code, now)
                previous = next((item for item in items if item['id'] == spec[0]), None)
                # Retain collection time if the observation did not change, avoiding weekly noisy commits.
                if previous and previous['series'] == indicator['series'] and previous['status'] == 'real':
                    indicator['collectedAt'] = previous['collectedAt']
                items[:] = [item for item in items if item['id'] != spec[0]] + [indicator]
                print(f'OK {name}: {spec[0]} ({indicator["reference"]})')
            except Exception as exc:
                failures.append(f'{name}/{spec[0]}: {type(exc).__name__}: {exc}')
                print(f'FALHA {name}/{spec[0]}: {exc}')
    catalog['collection'] = {'attemptedAt': now, 'failures': failures}
    catalog['indicators'].sort(key=lambda i: (i['module'], i['id']))
    validate(catalog)
    atomic_write(DATA / 'indicators.json', catalog)
    atomic_write(DATA / 'comparison.json', peers)
    if failures: print(f'{len(failures)} falhas; snapshots anteriores preservados.')
    return catalog

def validate(data):
    assert data['schemaVersion'] == 1
    assert data['municipality']['code'] == '4127965'
    seen = set()
    for item in data['indicators']:
        assert item['id'] not in seen
        seen.add(item['id'])
        assert item['municipalityCode'] == '4127965'
        for field in ('source', 'agency', 'reference', 'url', 'unit', 'status'): assert item[field]
        assert item['url'].startswith('https://')
        assert item['status'] in ('real', 'mock', 'unavailable')
        if item['status'] == 'real': assert item['collectedAt'] and item['value'] is not None
        if item['status'] != 'real': assert item['collectedAt'] is None
        if item['value'] is not None: assert math.isfinite(item['value'])
        for point in item['series']: assert math.isfinite(point['value'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--module', choices=['all', 'population', 'economy', 'employment'], default='all', help='Atualizar um módulo ou todos')
    parser.add_argument('--offline', action='store_true', help='Validar snapshot sem consultar APIs')
    parser.add_argument('--source', choices=['all','rais','caged'], default='all', help='Somente Trabalho: bases independentes')
    parser.add_argument('--force', action='store_true', help='Reprocessar mesma divulgação e incorporar revisões')
    parser.add_argument('--rais-remuneration', action='store_true', help='Processar arquivo regional grande para remuneração RAIS; opcional/manual')
    parser.add_argument('--cache', help='Cache local não público de arquivos MTE')
    parser.add_argument('--latest', help='Competência CAGED explícita AAAAMM')
    parser.add_argument('--rais-year', type=int, help='Ano RAIS explícito')
    parser.add_argument('--window', type=int, choices=[12,24], default=24)
    options = parser.parse_args()
    if options.module == 'all':
        update(options.offline)
    failures = []
    if options.module in ('all', 'population'):
        failures += update_population(DATA, options.offline)['collection']['failures']
    if options.module in ('all', 'economy'):
        failures += update_economy(DATA, options.offline)['collection']['failures']
    # Heavy national microdata is intentionally excluded from the weekly all refresh.
    if options.module == 'employment':
        failures += update_employment(DATA, options.offline, options.source, options.force, options.cache, options.latest, options.rais_year, options.window, options.rais_remuneration)['collection']['failures']
    if failures and not options.offline:
        raise SystemExit(1)  # Snapshot remains usable; signal failed refresh.
