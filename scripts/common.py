"""Small standard-library helpers shared by ETLs."""
import gzip
import json
import math
import os
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

SIDRA_MISSING = {'-', '..', '...', 'X'}


def request_json(url, timeout=25, attempts=3):
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'ObservatorioTurvo/0.2 (public-data)', 'Accept-Encoding': 'identity'}), timeout=timeout) as response:
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise ValueError('Resposta excede limite de 5 MB')
                if raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                if len(raw) > 5_000_000:
                    raise ValueError('Resposta descompactada excede limite de 5 MB')
                return json.loads(raw)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def number(value, allow_missing=False, sidra_zero=False):
    # SIDRA defines '-' as absolute zero, unlike X (suppressed), .. and ... .
    # Conversion is explicit and opt-in; raw responses retain the original symbol.
    if sidra_zero and str(value).strip() == '-':
        return 0.0
    if value is None or str(value).strip() in SIDRA_MISSING:
        if allow_missing:
            return None
        raise ValueError(f'Célula ausente/suprimida: {value!r}')
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('Valor não finito')
    return parsed


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            temporary = handle.name
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def read(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
