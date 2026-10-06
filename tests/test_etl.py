import importlib.util
import json
import io
from contextlib import redirect_stdout
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('etl', Path(__file__).resolve().parents[1] / 'scripts/etl.py')
etl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etl)

class ETLTests(unittest.TestCase):
    def rows(self, **changes):
        row = {'D1C': '4127965', 'D2C': '37', 'D3C': '2023', 'V': '697870', 'MN': 'Mil Reais'}
        row.update(changes)
        return [{}, row]

    def test_currency_conversion(self):
        item = etl.normalize(self.rows(), etl.SOURCES[3], '4127965', '2026-10-06T00:00:00Z')
        self.assertEqual(item['value'], 697870000)
        self.assertEqual(item['reference'], '2023')

    def test_wrong_municipality_is_rejected(self):
        with self.assertRaises(ValueError):
            etl.normalize(self.rows(D1C='4109401'), etl.SOURCES[3], '4127965', 'now')

    def test_wrong_unit_is_rejected(self):
        with self.assertRaises(ValueError):
            etl.normalize(self.rows(MN='Reais'), etl.SOURCES[3], '4127965', 'now')

    def test_suppressed_values_are_not_zero(self):
        for value in ['-', '...', '..', 'X', 'NaN']:
            with self.assertRaises(ValueError):
                etl.normalize(self.rows(V=value), etl.SOURCES[3], '4127965', 'now')

    def test_snapshot_metadata(self):
        etl.validate(json.loads((etl.DATA / 'indicators.json').read_text()))

    def test_failure_keeps_snapshot(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            original = json.loads((etl.DATA / 'indicators.json').read_text())
            etl.atomic_write(data / 'indicators.json', original)
            with patch.object(etl, 'DATA', data), patch.object(etl, 'request_json', side_effect=OSError('offline')):
                with redirect_stdout(io.StringIO()):
                    result = etl.update()
            self.assertEqual(result['indicators'], sorted(original['indicators'], key=lambda i:(i['module'], i['id'])))
            self.assertEqual(len(result['collection']['failures']), 16)

if __name__ == '__main__': unittest.main()
