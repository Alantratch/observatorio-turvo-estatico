"""CNES institutional normalization. No individual identifiers are emitted."""
import math
import re
from collections import Counter

MUNICIPALITIES = {'4127965': 'Turvo', '4109401': 'Guarapuava', '4119608': 'Pitanga', '4113254': 'Laranjal'}
DATASUS_CODES = {code[:6]: code for code in MUNICIPALITIES}
TYPE_URL = 'https://cnes2.datasus.gov.br/Mod_Ind_Unidade.asp?VEstado=00'
MANAGEMENT = {'M': 'Municipal', 'E': 'Estadual', 'D': 'Dupla', 'S': 'Sem gestão'}
URGENT = {'20', '21', '42', '73', '76'}
HOSPITAL = {'05', '07', '62'}


def cnes_code(value):
    value = str(value).strip()
    if not re.fullmatch(r'\d{1,7}', value) or int(value) == 0:
        raise ValueError('Código CNES inválido')
    return value.zfill(7)


def count(value):
    if value is None or str(value).strip() == '':
        raise ValueError('Contagem ausente não é zero')
    number = float(value)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError('Contagem inválida')
    return int(number)


def flag(value):
    if value is None or str(value).strip() == '':
        return None
    number = count(value)
    if number not in (0, 1):
        raise ValueError('Flag inválida')
    return bool(number)


def ownership(code):
    # Legal nature, NEVER management/esfera administrativa. Mixed-economy
    # companies are kept separate; nonprofit does not prove philanthropy.
    if code.startswith('1') or code == '2011':
        return 'Pública'
    if code == '2038':
        return 'Economia mista'
    if code.startswith('2') or code.startswith('4'):
        return 'Privada'
    if code.startswith('3'):
        return 'Sem fins lucrativos'
    return 'Não informada'


def normalize_network(raw_rows, labels):
    result = {code: {} for code in MUNICIPALITIES}
    scanned = 0
    for row in raw_rows:
        scanned += 1
        if not {'CO_IBGE', 'CO_UF', 'CO_CNES', 'CO_MOTIVO_DESAB', 'CO_AMBULATORIAL_SUS', 'TP_UNIDADE', 'CO_NATUREZA_JUR'}.issubset(row):
            raise ValueError('Campos CNES obrigatórios ausentes')
        code = DATASUS_CODES.get(row['CO_IBGE'].strip())
        if not code:
            continue
        if row['CO_UF'].strip() != '41':
            raise ValueError('CNES de município paranaense com UF divergente')
        cnes = cnes_code(row['CO_CNES'])
        if row.get('CO_UNIDADE', '').strip() != code[:6] + cnes:
            raise ValueError('Identidade territorial CNES divergente')
        kind = str(count(row['TP_UNIDADE'])).zfill(2)
        if kind not in labels:
            raise ValueError('Tipo CNES desconhecido: ' + kind)
        legal = row['CO_NATUREZA_JUR'].strip()
        if legal and not re.fullmatch(r'\d{4}', legal):
            raise ValueError('Natureza jurídica inválida')
        management = row['TP_GESTAO'].strip()
        if management not in MANAGEMENT and management:
            raise ValueError('Gestão CNES desconhecida')
        sus = row['CO_AMBULATORIAL_SUS'].strip()
        if sus not in ('SIM', 'NAO', ''):
            raise ValueError('Atendimento ambulatorial SUS desconhecido')
        reason = row['CO_MOTIVO_DESAB'].strip()
        if reason and not re.fullmatch(r'\d{2}', reason):
            raise ValueError('Motivo de desativação inválido')
        coordinates = None
        try:
            lat, lon = float(row.get('NU_LATITUDE', '')), float(row.get('NU_LONGITUDE', ''))
            if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0, 0):
                coordinates = {'latitude': lat, 'longitude': lon}
        except (TypeError, ValueError):
            pass
        item = {'cnes': cnes, 'municipalityCode': code, 'state': 'PR', 'name': row['NO_FANTASIA'].strip(), 'typeCode': kind, 'type': labels[kind], 'management': MANAGEMENT.get(management, 'Não informada'), 'legalNatureCode': legal or None, 'ownership': ownership(legal), 'municipalOwnership': legal in ('1031', '1244'), 'active': not reason, 'deactivationCode': reason or None, 'ambulatorySus': {'SIM': True, 'NAO': False, '': None}[sus], 'sus': True if sus == 'SIM' else None, 'ubs': kind == '02', 'urgent': kind in URGENT, 'hospital': kind in HOSPITAL, 'address': ' '.join(v for v in (row.get('NO_LOGRADOURO', '').strip(), row.get('NU_ENDERECO', '').strip()) if v), 'neighborhood': row.get('NO_BAIRRO', '').strip() or None, 'postalCode': row.get('CO_CEP', '').strip() or None, 'coordinates': coordinates, 'services': {k: flag(row.get(f)) for k, f in [('ambulatory', 'ST_ATEND_AMBULATORIAL'), ('hospital', 'ST_ATEND_HOSPITALAR'), ('support', 'ST_SERVICO_APOIO'), ('surgicalCenter', 'ST_CENTRO_CIRURGICO'), ('obstetricCenter', 'ST_CENTRO_OBSTETRICO'), ('neonatalCenter', 'ST_CENTRO_NEONATAL')]}, 'sourceId': 'cnes', 'cnesUrl': 'https://cnes2.datasus.gov.br/Exibe_Ficha_Estabelecimento.asp?VCo_Unidade=' + code[:6] + cnes}
        if not item['name']:
            raise ValueError('Estabelecimento sem nome')
        previous = result[code].get(cnes)
        if previous and previous != item:
            raise ValueError('CNES duplicado com informações divergentes')
        result[code][cnes] = item
    if not scanned or any(not items for items in result.values()):
        raise ValueError('Arquivo incompleto ou sem municípios esperados; ausência não é zero')
    return {code: sorted(items.values(), key=lambda r: (not r['active'], r['name'], r['cnes'])) for code, items in result.items()}, scanned


def summarize(items):
    active = [r for r in items if r['active']]
    def groups(key):
        return [{'label': k, 'count': n} for k, n in sorted(Counter(r[key] for r in active).items(), key=lambda r: (-r[1], r[0]))]
    positive = sum(r['ambulatorySus'] is True for r in active)
    negative = sum(r['ambulatorySus'] is False for r in active)
    return {'registered': len(items), 'active': len(active), 'inactive': len(items) - len(active), 'public': sum(r['ownership'] == 'Pública' for r in active), 'municipal': sum(r['municipalOwnership'] for r in active), 'ubs': sum(r['ubs'] for r in active), 'hospitals': sum(r['hospital'] for r in active), 'urgent': sum(r['urgent'] for r in active), 'byType': groups('type'), 'byManagement': groups('management'), 'byOwnership': groups('ownership'), 'sus': {'ambulatoryYes': positive, 'ambulatoryNo': negative, 'ambulatoryUnknown': len(active) - positive - negative, 'ambulatoryPercent': round(positive / len(active) * 100, 2) if active else None, 'ambulatoryPercentStatus': 'derived', 'ambulatoryPercentFormula': 'ambulatoryYes / active * 100', 'generalTotal': None, 'generalUnknown': len(active) - positive}}


def normalize_beds(raw_rows):
    records = {}
    periods = set()
    scanned = 0
    for row in raw_rows:
        scanned += 1
        if not {'COMP', 'CO_IBGE', 'UF', 'CNES', 'LEITOS_EXISTENTES', 'LEITOS_SUS', 'MOTIVO_DESABILITACAO', 'UTI_TOTAL_EXIST', 'UTI_TOTAL_SUS'}.issubset(row):
            raise ValueError('Campos de leitos obrigatórios ausentes')
        period = row['COMP'].strip()
        if not re.fullmatch(r'20\d{2}(0[1-9]|1[0-2])', period):
            raise ValueError('Competência de leitos inválida')
        periods.add(period)
        code = DATASUS_CODES.get(row['CO_IBGE'].strip())
        if not code:
            continue
        if row['UF'].strip() != 'PR':
            raise ValueError('UF de leitos divergente')
        if row['MOTIVO_DESABILITACAO'].strip():
            continue
        cnes = cnes_code(row['CNES'])
        item = {'municipalityCode': code, 'state': 'PR', 'cnes': cnes, 'name': row['NOME_ESTABELECIMENTO'].strip(), 'reference': period, 'existing': count(row['LEITOS_EXISTENTES']), 'sus': count(row['LEITOS_SUS']), 'icuExisting': count(row['UTI_TOTAL_EXIST']), 'icuSus': count(row['UTI_TOTAL_SUS']), 'sourceId': 'beds'}
        if item['sus'] > item['existing'] or item['icuSus'] > item['icuExisting']:
            raise ValueError('Leitos SUS excedem existentes')
        key = (code, period, cnes)
        if key in records and records[key] != item:
            raise ValueError('Leitos duplicados divergentes')
        records[key] = item
    if not scanned or not periods or not records:
        raise ValueError('Arquivo de leitos vazio; ausência não é zero')
    # Full national export is read to EOF before confirming an absent municipal
    # record as zero in each observed competence. Unknown API responses never do.
    totals = []
    for code in MUNICIPALITIES:
        for period in sorted(periods):
            matching = [r for r in records.values() if r['municipalityCode'] == code and r['reference'] == period]
            totals.append({'municipalityCode': code, 'reference': period, **{field: sum(r[field] for r in matching) for field in ('existing', 'sus', 'icuExisting', 'icuSus')}, 'hospitals': len(matching), 'zeroConfirmed': not matching, 'sourceId': 'beds'})
    return {'status': 'real', 'reference': max(periods), 'competence': max(periods), 'unit': 'leitos', 'sourceId': 'beds', 'records': sorted(records.values(), key=lambda r: (r['reference'], r['municipalityCode'], r['cnes'])), 'series': totals, 'nationalRowsRead': scanned}
