"""Official OpenDataSUS catalog and bounded temporary CSV/ZIP acquisition.

The current public catalog serves Next.js dataset metadata, not the former CKAN
API. National archives never enter public/data or the repository.
"""
import csv
import hashlib
import html
import io
import json
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PORTAL = 'https://dadosabertos.saude.gov.br/dataset/'
UA = 'ObservatorioTurvo/0.3 (municipal public institutional statistics)'


def download(url, target, max_bytes=90_000_000, attempts=3):
    if urlparse(url).scheme != 'https':
        raise ValueError('Fonte precisa utilizar HTTPS')
    for attempt in range(attempts):
        try:
            size = 0
            digest = hashlib.sha256()
            with urlopen(Request(url, headers={'User-Agent': UA}), timeout=40) as response, open(target, 'wb') as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError('Arquivo excede limite seguro')
                    digest.update(chunk)
                    output.write(chunk)
            if not size:
                raise ValueError('Fonte retornou arquivo vazio')
            return {'sha256': digest.hexdigest(), 'bytes': size}
        except Exception:
            Path(target).unlink(missing_ok=True)
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def catalog(slug, directory):
    path = Path(directory) / (slug + '.html')
    download(PORTAL + slug, path, 5_000_000)
    match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', path.read_text(), re.S)
    if not match:
        raise ValueError('Catálogo oficial mudou de formato')
    dataset = json.loads(match[1])['props']['pageProps']
    if dataset.get('name') != slug or not dataset.get('resources'):
        raise ValueError('Dataset ou recursos não correspondem ao solicitado')
    return dataset


def resource(dataset, predicate):
    matches = [r for r in dataset['resources'] if r.get('state') == 'active' and r.get('format', '').upper() == 'CSV' and predicate(r)]
    if not matches:
        raise ValueError('Nenhum recurso CSV oficial compatível')
    item = max(matches, key=lambda r: r.get('last_modified') or '')
    parsed = urlparse(item['url'])
    if parsed.netloc != 's3.sa-east-1.amazonaws.com' or not parsed.path.startswith('/ckan.saude.gov.br/') or not parsed.path.endswith('.zip'):
        raise ValueError('Recurso fora do armazenamento oficial conhecido')
    if not item.get('last_modified'):
        raise ValueError('Recurso sem data oficial de publicação')
    return item


def rows(path, encoding="cp1252"):
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.infolist() if m.filename.lower().endswith('.csv') and not m.is_dir()]
        if len(members) != 1 or members[0].file_size > 400_000_000:
            raise ValueError('ZIP precisa conter exatamente um CSV com tamanho validado')
        with archive.open(members[0]) as binary, io.TextIOWrapper(binary, encoding=encoding, newline='') as text:
            reader = csv.DictReader(text, delimiter=';')
            if len(reader.fieldnames or []) < 5:
                raise ValueError('Cabeçalho CSV inválido')
            yield from reader  # Full EOF/CRC check; do not stop after matching Turvo.


def type_labels(path):
    text = Path(path).read_text(encoding='latin1')
    labels = {code: html.unescape(re.sub('<[^>]+>', '', label)).strip() for code, label in re.findall(r'<a[^>]+VTipo=(\d{2})[^>]*>([^<]+)', text)}
    if not all(k in labels for k in ('01', '02', '05', '22', '42', '74')):
        raise ValueError('Tabela oficial de tipos CNES incompleta')
    return labels
