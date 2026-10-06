"""MTE/PDET transports, versioned layouts and bounded-memory readers (stdlib).
7-Zip is a system tool because the official archives are .7z, not ZIP.
"""
import csv
import ftplib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

PORTAL = 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/estatisticas-trabalho'
BASE = os.environ.get('MTE_BASE_URL', 'ftp://ftp.mtps.gov.br/pdet/microdados').rstrip('/')
MUNICIPALITIES = {'4127965': 'Turvo', '4109401': 'Guarapuava', '4119608': 'Pitanga', '4113254': 'Laranjal'}
TERRITORIES = {'412796': '4127965', '410940': '4109401', '411960': '4119608', '411325': '4113254'}
CLASSIFICATIONS = json.loads(Path(__file__).with_name('mte-classifications.json').read_text())
SECTORS = {'agriculture': 'Agropecuária', 'industry': 'Indústria', 'construction': 'Construção', 'commerce': 'Comércio', 'services': 'Serviços'}
CAGED_COMMON = 'competenciamov regiao uf municipio secao subclasse saldomovimentacao cbo2002ocupacao categoria graudeinstrucao idade horascontratuais racacor sexo tipoempregador tipoestabelecimento tipomovimentacao tipodedeficiencia indtrabintermitente indtrabparcial salario tamestabjan indicadoraprendiz origemdainformacao competenciadec'.split()
CAGED_TAIL = {'MOV': 'indicadordeforadoprazo unidadesalariocodigo valorsalariofixo'.split(), 'FOR': 'indicadordeforadoprazo unidadesalariocodigo valorsalariofixo'.split(), 'EXC': 'competenciaexc indicadordeexclusao indicadordeforadoprazo unidadesalariocodigo valorsalariofixo'.split()}
REMOTE_STATUS = {}
LAYOUT = 'Novo CAGED movimentações · revisão 2022-08-31 · 28/30 campos'


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower())


def territory(mte_code, uf):
    """Explicit layout-confirmed six-digit mapping AND UF, never a name match."""
    return TERRITORIES.get(str(mte_code)) if str(uf) == '41' else None


def sector(section):
    if len(section) != 1: raise ValueError(f'Seção CNAE não reconhecida: {section!r}')
    if section == 'A': return 'agriculture'
    if section in 'BCDE': return 'industry'
    if section == 'F': return 'construction'
    if section == 'G': return 'commerce'
    if section in 'HIJKLMNOPQRSTU': return 'services'
    raise ValueError(f'Seção CNAE não reconhecida: {section!r}')


def decimal(value):
    from math import isfinite
    if value is None or str(value).strip() in ('', 'NA', 'N/A', 'IGNORADO'): return None
    v = float(str(value).strip().replace(',', '.'))
    if not isfinite(v): raise ValueError('Número não finito')
    return v


def _ftp(parsed):
    f = ftplib.FTP(parsed.hostname, timeout=90, encoding='latin1')
    f.login()
    return f


def listing(relative):
    parsed = urlparse(BASE)
    if parsed.scheme != 'ftp':
        raise ValueError('Descoberta automática requer FTP oficial; configure MTE_MANIFEST_URL para origem HTTPS')
    with _ftp(parsed) as f:
        f.cwd(unquote(parsed.path) + '/' + relative)
        result = []
        f.retrlines('LIST', result.append)
    return result


def discover():
    manifest = os.environ.get('MTE_MANIFEST_URL')
    if manifest:
        with urlopen(manifest, timeout=40) as r: return json.load(r)
    years = [int(row.split()[-1]) for row in listing('NOVO CAGED') if row.split()[-1].isdigit() and len(row.split()[-1]) == 4]
    months = []
    for y in sorted(years)[-3:]:
        months += [row.split()[-1] for row in listing(f'NOVO CAGED/{y}') if re.fullmatch(r'20\d{4}', row.split()[-1])]
    rais_years = [int(row.split()[-1]) for row in listing('RAIS') if re.fullmatch(r'20\d{2}', row.split()[-1])]
    if not months or not rais_years: raise ValueError('Nenhum período oficial encontrado')
    return {'caged': max(months), 'rais': max(rais_years), 'availableMonths': sorted(months)}


def download(url, destination, attempts=3):
    """Atomic cache, server-size check and SHA256. Hash is local evidence, not an MTE signature."""
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    stamp = destination.with_suffix(destination.suffix + '.manifest.json')
    parsed = urlparse(url); remote = REMOTE_STATUS.get(url)
    if destination.exists() and stamp.exists():
        try:
            meta = json.loads(stamp.read_text())
            for attempt in range(attempts):
                try:
                    if remote is not None: break
                    if parsed.scheme == 'ftp':
                        with _ftp(parsed) as f:
                            f.voidcmd('TYPE I')
                            remote = {'bytes': f.size(unquote(parsed.path)), 'modified': f.sendcmd('MDTM '+unquote(parsed.path))}
                    elif parsed.scheme == 'https':
                        with urlopen(Request(url, method='HEAD'), timeout=90) as response:
                            remote = {'bytes': int(response.headers.get('Content-Length', 0)), 'modified': response.headers.get('Last-Modified'), 'etag': response.headers.get('ETag')}
                    break
                except Exception:
                    if attempt+1 == attempts:
                        remote = None  # Cannot confirm freshness: download and validate again.
                    else: time.sleep(2 ** attempt)
            if remote is not None and destination.stat().st_size == meta['bytes'] and hash_file(destination) == meta['sha256'] and meta['url'] == url and meta.get('remote') == remote:
                return meta
        except (ValueError, KeyError):
            pass  # Invalid manifest is a cache miss, never trusted data.
    partial = destination.with_suffix(destination.suffix + '.part')
    for attempt in range(attempts):
        try:
            parsed = urlparse(url); digest = hashlib.sha256(); size = 0
            with partial.open('wb') as handle:
                def write(chunk):
                    nonlocal size
                    handle.write(chunk); digest.update(chunk); size += len(chunk)
                if parsed.scheme == 'ftp':
                    with _ftp(parsed) as f:
                        f.voidcmd('TYPE I'); expected = f.size(unquote(parsed.path))
                        remote = {'bytes':expected,'modified':f.sendcmd('MDTM '+unquote(parsed.path))}
                        f.retrbinary('RETR ' + unquote(parsed.path), write, blocksize=262144)
                elif parsed.scheme == 'https':
                    with urlopen(Request(url, headers={'User-Agent': 'ObservatorioTurvo/0.3'}), timeout=90) as r:
                        expected = int(r.headers.get('Content-Length', 0)) or None
                        remote = {'bytes':expected or 0,'modified':r.headers.get('Last-Modified'),'etag':r.headers.get('ETag')}
                        while chunk := r.read(262144): write(chunk)
                else: raise ValueError('Origem deve usar HTTPS ou FTP')
            if size < 32 or (expected is not None and size != expected):
                raise ValueError(f'Download incompleto: {size}/{expected}')
            if destination.suffix == '.7z':
                with partial.open('rb') as archive: signature = archive.read(6)
                if signature != b'7z\xbc\xaf\x27\x1c': raise ValueError('Assinatura 7z inválida')
            meta = {'url': url, 'bytes': size, 'sha256': digest.hexdigest(), 'remote': remote}
            os.replace(partial, destination); stamp.write_text(json.dumps(meta) + '\n')
            return meta
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt + 1 == attempts: raise
            time.sleep(2 ** attempt)


def archive_url(kind, month):
    return BASE + '/NOVO%20CAGED/' + month[:4] + '/' + month + f'/CAGED{kind}{month}.7z'


@contextmanager
def text_archive(path, encoding='utf-8-sig'):
    binary = os.environ.get('MTE_7ZIP') or shutil.which('7zz') or shutil.which('7z')
    if not binary: raise RuntimeError('Instale 7zip ou defina MTE_7ZIP. Os arquivos oficiais são .7z.')
    info = subprocess.run([binary, 'l', '-slt', str(path)], capture_output=True, text=True, check=True).stdout
    members = info.split('----------\n')[-1]
    paths = re.findall(r'^Path = (.+)$', members, re.M)
    if len(paths) != 1 or not paths[0].lower().endswith(('.txt','.csv','.comt')):
        raise ValueError('Esperado exatamente um TXT/CSV/COMT no arquivo oficial')
    proc = subprocess.Popen([binary, 'x', '-so', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with io.TextIOWrapper(proc.stdout, encoding=encoding, errors='strict') as stream:
            yield stream
            # Ensure decoder and CRC validation reach the end even with an early consumer exit.
            for _ in stream: pass
        error = proc.stderr.read().decode(errors='replace')
        if proc.wait() != 0: raise ValueError('Falha na descompactação/CRC: ' + error[:500])
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        proc.stderr.close()


def caged_rows(stream, kind, national=None, latest=None):
    reader = csv.reader(stream, delimiter=';'); headers = [normalized(x) for x in next(reader)]
    expected = set(CAGED_COMMON + CAGED_TAIL[kind])
    if len(headers) != len(set(headers)) or set(headers) != expected:
        raise ValueError(f'Layout {kind} inesperado: faltam {expected-set(headers)}, extras {set(headers)-expected}')
    positions = {name: headers.index(name) for name in headers}
    selected = ['competenciamov', 'competenciadec', 'uf', 'municipio', 'secao', 'subclasse', 'saldomovimentacao', 'cbo2002ocupacao', 'tipomovimentacao', 'salario', 'indtrabintermitente', 'indicadordeforadoprazo']
    if kind == 'EXC': selected += ['competenciaexc', 'indicadordeexclusao']
    for row in reader:
        if len(row) != len(headers): raise ValueError('Linha com quantidade incorreta de campos')
        if national is not None and row[positions['competenciamov']] == latest:
            sign = int(row[positions['saldomovimentacao']]); weight = -1 if kind == 'EXC' else 1
            if sign not in (-1, 1): raise ValueError('Sinal nacional inválido')
            national['admissions' if sign == 1 else 'dismissals'] += weight
            national['balance'] += sign * weight
        code = territory(row[positions['municipio']], row[positions['uf']])
        if not code: continue  # No per-national-row dict allocation.
        result = {name: row[positions[name]] for name in selected}; result['code'] = code
        yield result


def xlsx_rows(path):
    """Small official aggregate/layout workbooks only; never national microdata."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings = [''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        relns = '{http://schemas.openxmlformats.org/package/2006/relationships}'
        rels = {r.get('Id'): r.get('Target').lstrip('/') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns):
            path = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            if not path.startswith('xl/'): path = 'xl/' + path
            rows = []
            for row in ET.fromstring(z.read(path)).findall('.//s:row', ns):
                values = {}
                for c in row:
                    v = c.find('s:v', ns); val = v.text if v is not None else ''.join(c.itertext())
                    values[re.sub(r'\d+', '', c.get('r'))] = strings[int(val)] if c.get('t') == 's' and val else val
                rows.append(values)
            result[sheet.get('name')] = rows
        return result


def rais_rows(stream, year):
    layouts=json.loads(Path(__file__).with_name('mte-layouts.json').read_text())
    profile=layouts.get(f'rais-{year}')
    if not profile: raise ValueError(f'Layout microdados RAIS {year} ainda não validado. Estoque pode ser coletado da tabela municipal; reveja o layout antes de habilitar remuneração.')
    reader=csv.reader(stream,delimiter=profile['delimiter']);headers=[normalized(x) for x in next(reader)];expected=[normalized(x) for x in profile['headers']]
    if len(headers)!=len(set(headers)) or set(headers)!=set(expected):raise ValueError('Layout RAIS inesperado; não processamos índices sem contrato')
    fields=['municipiocodigo','indvinculoativo3112codigo','indvinculoabandonadocodigo','vlremdezembronom','cnae20classecodigo']
    positions={k:headers.index(k) for k in fields}
    for row in reader:
        if len(row)!=len(headers):raise ValueError('Registro RAIS truncado')
        municipality=row[positions['municipiocodigo']].strip()
        code=territory(municipality,municipality[:2])
        if not code:continue
        yield {'code':code,**{k:row[i].strip() for k,i in positions.items()}}


def hash_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(262144),b''):digest.update(block)
    return digest.hexdigest()


def prime_remote_cache(urls, attempts=3):
    """Check an FTP collection once with one connection, avoiding 72 logins on cache reuse."""
    if not urls or urlparse(urls[0]).scheme!='ftp':return
    for attempt in range(attempts):
        try:
            verified={}
            with _ftp(urlparse(urls[0])) as f:
                f.voidcmd('TYPE I')
                for url in urls:
                    parsed=urlparse(url)
                    if parsed.hostname!=urlparse(urls[0]).hostname or parsed.scheme!='ftp':raise ValueError('Inventário exige uma única origem FTP')
                    path=unquote(parsed.path)
                    verified[url]={'bytes':f.size(path),'modified':f.sendcmd('MDTM '+path)}
            REMOTE_STATUS.clear();REMOTE_STATUS.update(verified)
            return
        except Exception:
            if attempt+1==attempts:raise
            time.sleep(2 ** attempt)
