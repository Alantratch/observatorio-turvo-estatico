"""Monthly CNES institutional ETL; validated static snapshots, no runtime API."""
import copy
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.common import atomic_write, read
from scripts.sources import datasus
from scripts.sources.cnes import MUNICIPALITIES, TYPE_URL, normalize_network, normalize_beds, summarize

SLUGS = {'cnes': 'cnes-cadastro-nacional-de-estabelecimentos-de-saude', 'beds': 'hospitais-e-leitos', 'region': 'macrorregiao-de-saude'}
UNAVAILABLE = {
    'teams': ('Equipes de Atenção Primária', 'A API atual não oferece série municipal validada de equipes nesta integração. UBS não são equipes.', 'https://egestoraps.saude.gov.br/'),
    'coverage': ('Cobertura da Atenção Primária', 'Não foi localizada uma exportação pública automatizável com metodologia atual validada. Não estimamos cobertura por número de equipes.', 'https://egestoraps.saude.gov.br/'),
    'professionals': ('Vínculos profissionais', 'O endpoint antigo foi descontinuado. O endpoint atual exige validação de competência, vínculos e CBO; não publicamos listagem nominal.', 'https://apidadosabertos.saude.gov.br/v1/'),
    'production': ('Produção assistencial SIA/SIH', 'Etapa posterior: definir território de atendimento ou residência antes de agregar procedimentos e internações.', 'https://datasus.saude.gov.br/acesso-a-informacao/producao-hospitalar-sih-sus/'),
    'epidemiology': ('Vigilância e indicadores de saúde', 'Etapa posterior: usar agregados oficiais e política documentada de divulgação de células pequenas.', 'https://dadosabertos.saude.gov.br/')}


def unavailable(key):
    title, reason, url = UNAVAILABLE[key]
    return {'status': 'unavailable', 'title': title, 'value': None, 'reference': None, 'competence': None, 'municipalityCode': '4127965', 'agency': 'Ministério da Saúde', 'collectedAt': None, 'url': url, 'reason': reason}


def in_ring(point, ring):
    x, y = point
    inside = False
    previous = ring[-1]
    for current in ring:
        ax, ay = previous
        bx, by = current
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        previous = current
    return inside


def in_geometry(point, geometry):
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    return any(in_ring(point, polygon[0]) and not any(in_ring(point, hole) for hole in polygon[1:]) for polygon in polygons)


def source_metadata(key, dataset, item, stats, now):
    return {'id': key, 'source': 'Ministério da Saúde / DATASUS / CNES' if key != 'region' else 'Ministério da Saúde / Regionalização do SUS', 'agency': 'Ministério da Saúde', 'dataset': dataset['title'], 'catalogUrl': datasus.PORTAL + SLUGS[key], 'url': item['url'], 'resourceId': item['id'], 'publishedAt': item['last_modified'], 'collectedAt': now, 'municipalityCodes': list(MUNICIPALITIES), 'unit': {'cnes': 'estabelecimentos', 'beds': 'leitos', 'region': 'identificação territorial'}[key], 'format': 'CSV/ZIP', **stats}


def build(network_rows, bed_rows, region_rows, labels, sources, geometry=None):
    network, scanned = normalize_network(network_rows, labels)
    beds = normalize_beds(bed_rows)
    source = next(s for s in sources if s['id'] == 'cnes')
    reference = source['publishedAt'][:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', reference):
        raise ValueError('Data de referência CNES inválida')
    source['reference'] = reference
    source['competence'] = None
    source['concept'] = 'Exportação diária. Ativo = CO_MOTIVO_DESAB vazio, não comprovação de funcionamento ou atendimento em tempo real.'
    source['transformation'] = 'Filtro CO_IBGE de 6 dígitos e UF 41; CNES restaurado para 7 dígitos e deduplicado; natureza jurídica distinta da gestão; atendimento SUS limitado a CO_AMBULATORIAL_SUS.'
    bed_source = next(s for s in sources if s['id'] == 'beds')
    bed_source.update(reference=beds['reference'], competence=beds['reference'], concept='Capacidade hospitalar cadastrada; não vagas instantâneas.', transformation='Arquivo nacional completo lido até EOF; filtro PR/municípios, motivo de desabilitação vazio, deduplicação por CNES e competência. UTI mostrada separadamente, nunca adicionada ao total.')
    region_source = next(s for s in sources if s['id'] == 'region')
    region_source.update(reference=region_source['publishedAt'][:10], competence=None, concept='Divisão regional oficial do SUS, sem inferência por proximidade.', transformation='Filtro cod_municipio=412796 e sg_uf=PR. População da base regional não é denominador dos indicadores.')
    matching = [r for r in region_rows if r.get('cod_municipio') == '412796']
    if len(matching) != 1 or matching[0].get('sg_uf') != 'PR':
        raise ValueError('Região oficial de Turvo ausente/ambígua')
    r = matching[0]
    region = {'status': 'real', 'sourceId': 'region', 'reference': region_source['reference'], 'code': r['cod_regiao_de_saude'], 'name': r['regiao_de_saude'], 'macroCode': r['cod_macrorregiao_de_saude'], 'macroName': r['macrorregiao_de_saude']}
    summaries = {code: summarize(items) for code, items in network.items()}
    for s in summaries.values():
        s.update(reference=reference, competence=None, status='real', sourceId='cnes')
    establishments = network['4127965']
    for item in establishments:
        coords = item['coordinates']
        item['mapEligible'] = bool(item['active'] and coords and geometry and in_geometry((coords['longitude'], coords['latitude']), geometry))
    beds['summary'] = next(r for r in beds['series'] if r['municipalityCode'] == '4127965' and r['reference'] == beds['reference'])
    data = {'schemaVersion': 1, 'municipality': {'code': '4127965', 'name': 'Turvo', 'state': 'PR'}, 'summary': summaries['4127965'], 'network': {'status': 'real', 'sourceId': 'cnes', 'reference': reference, 'referenceType': 'dailySnapshot', 'competence': None, 'unit': 'estabelecimentos', 'establishments': establishments, 'nationalRowsRead': scanned, 'activeDefinition': source['concept'], 'susDefinition': 'CO_AMBULATORIAL_SUS informa atendimento ambulatorial ao SUS. NAO não prova ausência de outros serviços SUS. Total geral de atendimento SUS permanece indisponível.'}, 'primaryCare': {'status': 'real', 'sourceId': 'cnes', 'reference': reference, 'competence': None, 'ubs': summaries['4127965']['ubs'], 'teams': unavailable('teams'), 'coverage': unavailable('coverage')}, 'beds': beds, 'region': region, 'professionals': unavailable('professionals'), 'production': unavailable('production'), 'epidemiology': unavailable('epidemiology'), 'comparison': [{'municipalityCode': code, 'name': name, 'state': 'PR', 'network': summaries[code], 'beds': next(r for r in beds['series'] if r['municipalityCode'] == code and r['reference'] == beds['reference'])} for code, name in MUNICIPALITIES.items()], 'map': {'geometry': geometry, 'geometryReference': '2022' if geometry else None, 'geometrySourceUrl': 'https://servicodados.ibge.gov.br/api/v3/malhas/municipios/4127965?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio', 'coordinateConcept': 'Coordenadas declaradas no CNES; conferência no polígono IBGE não valida o endereço. Pontos podem coincidir ou ter imprecisão.', 'shown': sum(r['mapEligible'] for r in establishments)}, 'sources': sources, 'collection': {'attemptedAt': sources[0]['collectedAt'], 'failures': []}}
    validate(data)
    return data


def validate(data):
    if data.get('schemaVersion') != 1 or data.get('municipality') != {'code': '4127965', 'name': 'Turvo', 'state': 'PR'}:
        raise ValueError('Schema/município Saúde inválido')
    sources = {s['id']: s for s in data['sources']}
    if len(sources) != len(data['sources']) or not {'cnes', 'beds', 'region'}.issubset(sources):
        raise ValueError('Fontes Saúde incompletas')
    for source in sources.values():
        if source['agency'] != 'Ministério da Saúde' or not source['url'].startswith('https://') or not source['collectedAt']:
            raise ValueError('Metadados de fonte inválidos')
    if data['network']['competence'] is not None or data['network']['reference'] != sources['cnes']['reference']:
        raise ValueError('Não atribuir competência mensal a exportação diária')
    items = data['network']['establishments']
    seen = set()
    for item in items:
        if item['municipalityCode'] != '4127965' or item['state'] != 'PR' or not re.fullmatch(r'\d{7}', item['cnes']) or item['cnes'] in seen:
            raise ValueError('CNES/território/duplicação inválidos')
        seen.add(item['cnes'])
        if item['sourceId'] not in sources or type(item['active']) is not bool or item['active'] != (item['deactivationCode'] is None) or item['ambulatorySus'] not in (True, False, None) or item['sus'] != (True if item['ambulatorySus'] is True else None) or item['ownership'] not in ('Pública', 'Privada', 'Sem fins lucrativos', 'Economia mista', 'Não informada'):
            raise ValueError('Classificação CNES inválida')
    summary = summarize(items)
    if any(data['summary'][k] != v for k, v in summary.items()):
        raise ValueError('Totais da rede divergem dos estabelecimentos')
    for row in data['beds']['records'] + data['beds']['series']:
        if row['municipalityCode'] not in MUNICIPALITIES or not re.fullmatch(r'20\d{2}(0[1-9]|1[0-2])', row['reference']):
            raise ValueError('Território/competência de leitos inválidos')
        if any(type(row[k]) is not int or row[k] < 0 for k in ('existing', 'sus', 'icuExisting', 'icuSus')) or row['sus'] > row['existing'] or row['icuSus'] > row['icuExisting']:
            raise ValueError('Contagens de leitos inválidas')
    for row in data['beds']['series']:
        matching = [r for r in data['beds']['records'] if r['municipalityCode'] == row['municipalityCode'] and r['reference'] == row['reference']]
        if any(row[k] != sum(r[k] for r in matching) for k in ('existing', 'sus', 'icuExisting', 'icuSus')) or row['zeroConfirmed'] != (not matching):
            raise ValueError('Agregados de leitos divergentes')
    if {r['municipalityCode'] for r in data['comparison']} != set(MUNICIPALITIES):
        raise ValueError('Comparação municipal incompleta')
    # Institutional-only allowlist produced by normalizers; block accidental PII additions.
    serialized = json.dumps(data).lower()
    if any('"' + key + '"' in serialized for key in ('cpf', 'cns', 'nu_cpf', 'nu_cns', 'nu_cnpj', 'nu_telefone', 'ds_email', 'patient', 'no_profissional')):
        raise ValueError('Campo pessoal/desnecessário no snapshot público')
    if '"mock"' in serialized:
        raise ValueError('Saúde não admite dados fictícios')
    return data


def exports(data, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rows = [{k: r[k] for k in ('cnes', 'name', 'type', 'management', 'ownership', 'active', 'ambulatorySus', 'address', 'neighborhood')} | {'municipalityCode': '4127965', 'reference': data['network']['reference'], 'competence': None, 'sourceId': 'cnes'} for r in data['network']['establishments']]
    beds = [r for r in data['beds']['records'] if r['municipalityCode'] == '4127965']
    primary = [{'cnes': r['cnes'], 'name': r['name'], 'municipalityCode': '4127965', 'reference': data['network']['reference'], 'competence': None, 'sourceId': 'cnes', 'concept': 'Estabelecimento UBS, não equipe'} for r in data['network']['establishments'] if r['active'] and r['ubs']]
    for name, content in [('health-establishments', rows), ('health-beds', beds), ('health-primary-care', primary)]:
        fields = list(content[0]) if content else ['municipalityCode', 'reference', 'sourceId']
        text = io.StringIO(newline='')
        writer = csv.DictWriter(text, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(content)
        path = directory / (name + '.csv')
        with tempfile.NamedTemporaryFile('w', dir=directory, delete=False, encoding='utf-8') as f:
            f.write(text.getvalue())
            temporary = f.name
        os.replace(temporary, path)


def update_catalog(data, directory):
    path = Path(directory) / 'indicators.json'
    catalog = read(path, None)
    if not catalog:
        return
    catalog['indicators'] = [r for r in catalog['indicators'] if r['module'] != 'health']
    specs = [('health-establishments', 'Estabelecimentos de saúde ativos', data['summary']['active'], 'estabelecimentos', 'cnes'), ('health-ubs', 'Centros de Saúde / UBS ativos', data['summary']['ubs'], 'unidades', 'cnes'), ('health-public', 'Estabelecimentos públicos ativos', data['summary']['public'], 'estabelecimentos', 'cnes'), ('health-ambulatory-sus', 'Estabelecimentos com atendimento ambulatorial SUS', data['summary']['sus']['ambulatoryYes'], 'estabelecimentos', 'cnes'), ('health-beds', 'Leitos hospitalares cadastrados', data['beds']['summary']['existing'], 'leitos', 'beds'), ('health-beds-sus', 'Leitos SUS cadastrados', data['beds']['summary']['sus'], 'leitos', 'beds')]
    for id_, title, value, unit, key in specs:
        source = next(s for s in data['sources'] if s['id'] == key)
        catalog['indicators'].append({'id': id_, 'module': 'health', 'title': title, 'value': value, 'unit': unit, 'source': source['source'], 'agency': source['agency'], 'reference': source['reference'], 'url': source['url'], 'collectedAt': source['collectedAt'], 'municipalityCode': '4127965', 'status': 'real', 'series': [{'period': source['reference'], 'value': value}], 'note': source['concept'] + (' SUS restrito ao campo ambulatorial, não total geral.' if 'ambulatory' in id_ else '')})
    catalog['indicators'].sort(key=lambda r: (r['module'], r['id']))
    atomic_write(path, catalog)


def publish(stage, directory):
    """Replace staged files with rollback on any local publication error."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.health-backup-', dir=directory) as backup:
        replaced = []
        try:
            for file in sorted(Path(stage).rglob('*')):
                if not file.is_file():
                    continue
                rel = file.relative_to(stage)
                target = directory / rel
                saved = Path(backup) / rel
                existed = target.exists()
                if existed:
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(target, saved)
                target.parent.mkdir(parents=True, exist_ok=True)
                # Copy staging onto same filesystem before atomic replacement.
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    replacement = Path(handle.name)
                try:
                    shutil.copyfile(file, replacement)
                    os.replace(replacement, target)
                finally:
                    replacement.unlink(missing_ok=True)
                replaced.append((target, saved, existed))
        except Exception:
            for target, saved, existed in reversed(replaced):
                if existed:
                    os.replace(saved, target)
                else:
                    target.unlink(missing_ok=True)
            raise


def update(directory, offline=False, force=False, cache=None):
    directory = Path(directory)
    path = directory / 'health.json'
    previous = read(path, None)
    if offline:
        if not previous:
            raise ValueError('Snapshot Saúde ainda não disponível')
        return validate(previous)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with tempfile.TemporaryDirectory(prefix='turvo-health-') as temporary:
            datasets = {k: datasus.catalog(slug, temporary) for k, slug in SLUGS.items()}
            resources = {k: datasus.resource(d, (lambda r: bool(re.search(r'Leitos_csv_20\d{2}\.zip$', r['url']))) if k == 'beds' else lambda r: True) for k, d in datasets.items()}
            # Select most recent annual edition, NOT merely a recently touched old archive.
            candidates = [r for r in datasets['beds']['resources'] if re.search(r'Leitos_csv_20\d{2}\.zip$', r.get('url', '')) and r.get('format') == 'CSV' and r.get('state') == 'active']
            year = max(int(re.search(r'(20\d{2})\.zip$', r['url'])[1]) for r in candidates)
            resources['beds'] = datasus.resource(datasets['beds'], lambda r: r['url'].endswith(f'Leitos_csv_{year}.zip'))
            if previous and not force and not previous['collection']['failures'] and all(any(s['id'] == k and s['resourceId'] == r['id'] and s['url'] == r['url'] and s['publishedAt'] == r['last_modified'] for s in previous['sources']) for k, r in resources.items()):
                print('Saúde: publicações já processadas; nenhuma alteração.')
                return validate(previous)
            sources = []
            files = {}
            for k, item in resources.items():
                file = Path(temporary) / (k + '.zip')
                manifest = read(Path(cache) / 'health-manifest.json', {}) if cache else {}
                entry = manifest.get(k, {})
                if cache and (Path(cache) / (k + '.zip')).exists() and all(entry.get(f) == item.get(f) for f in ('id', 'url', 'last_modified')):
                    shutil.copyfile(Path(cache) / (k + '.zip'), file)
                    b = file.read_bytes()
                    stats = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
                    if stats['sha256'] != entry.get('sha256'):
                        raise ValueError('Hash do cache difere da edição oficial registrada')
                else:
                    stats = datasus.download(item['url'], file)
                files[k] = file
                sources.append(source_metadata(k, datasets[k], item, stats, now))
            type_path = Path(temporary) / 'types.html'
            datasus.download(TYPE_URL, type_path, 2_000_000)
            labels = datasus.type_labels(type_path)
            sources[0]['typeClassificationUrl'] = TYPE_URL
            population = read(directory / 'population.json', {})
            features = population.get('territory', {}).get('geometry', {}).get('features', [])
            geometry = next((f['geometry'] for f in features if str(f.get('properties', {}).get('codarea')) == '4127965'), None)
            data = build(datasus.rows(files['cnes']), datasus.rows(files['beds']), datasus.rows(files['region'], 'utf-8-sig'), labels, sources, geometry)
            if data['network']['nationalRowsRead'] < 100_000 or data['beds']['nationalRowsRead'] < 1_000:
                raise ValueError('Exportação nacional incompleta: volume insuficiente')
            # Stage and validate every deliverable before replacing the live snapshot.
            stage = Path(temporary) / 'publish'
            stage.mkdir()
            if (directory / 'indicators.json').exists():
                shutil.copyfile(directory / 'indicators.json', stage / 'indicators.json')
            exports(data, stage / 'exports')
            update_catalog(data, stage)
            atomic_write(stage / 'health.json', data)
            publish(stage, directory)
            print(f'Saúde: {data["summary"]["active"]} ativos, {data["summary"]["ubs"]} UBS; leitos {data["beds"]["reference"]}: {data["beds"]["summary"]["existing"]}.')
            return data
    except Exception as exc:
        if not previous:
            raise
        data = copy.deepcopy(validate(previous))
        data['collection'] = {'attemptedAt': now, 'failures': [f'{type(exc).__name__}: {exc}']}
        atomic_write(path, data)
        print('FALHA Saúde: último snapshot e downloads válidos preservados:', exc)
        return data
