"""Regression checks for scheduled refreshes and meaningful changes."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import etl
from scripts.common import atomic_write, preserve_collection_times
from scripts.modules import economy, population

DATA = Path(__file__).resolve().parents[1] / 'public/data'


def change_times(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'collectedAt', 'attemptedAt', 'lastSuccessAt'} and item:
                value[key] = '2026-10-08T00:00:00Z'
            else:
                change_times(item)
    elif isinstance(value, list):
        for item in value:
            change_times(item)


class RefreshTests(unittest.TestCase):
    def test_ibge_repeat_keeps_snapshot_and_export_bytes(self):
        for module in [population, economy]:
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                name = module.__name__.split('.')[-1]
                previous = json.loads((DATA / f'{name}.json').read_text())
                candidate = copy.deepcopy(previous)
                change_times(candidate)
                atomic_write(directory / f'{name}.json', previous)
                (directory / 'existing.csv').write_text('previous export')
                before = {p.name: p.read_bytes() for p in directory.iterdir()}
                with patch.object(module, 'collect', return_value=(candidate, {})), redirect_stdout(io.StringIO()):
                    result = module.update(directory)
                self.assertEqual(result, previous)
                self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_revision_and_source_metadata_are_meaningful(self):
        previous = {'value': 10, 'url': 'https://example.org/old', 'collectedAt': 'old', 'collection': {'failures': []}}
        for update in [{'value': 11}, {'url': 'https://example.org/revised'}, {'collection': {'failures': ['offline']}}]:
            candidate = {**previous, **update}
            self.assertIs(preserve_collection_times(candidate, previous), candidate)

    def test_success_clears_previous_error(self):
        previous = {'value': 10, 'collection': {'failures': ['offline']}}
        candidate = {'value': 10, 'collection': {'failures': []}}
        self.assertIs(preserve_collection_times(candidate, previous), candidate)

    def test_initial_connector_does_not_overwrite_dedicated_population(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            previous = json.loads((DATA / 'indicators.json').read_text())
            atomic_write(directory / 'indicators.json', previous)
            for name in ['population', 'economy']:
                (directory / f'{name}.json').write_text('{}')
            with patch.object(etl, 'DATA', directory), patch.object(etl, 'MUNICIPALITIES', {'4127965': 'Turvo'}), patch.object(etl, 'request_json') as request:
                result = etl.update()
            request.assert_not_called()
            self.assertEqual(result, previous)

    def test_cli_fails_when_only_initial_connector_fails(self):
        ok = {'collection': {'failures': []}}
        failed = {'collection': {'failures': ['Guarapuava/population: timeout']}}
        with patch.object(etl, 'update', return_value=failed), patch.object(etl, 'update_population', return_value=ok), patch.object(etl, 'update_economy', return_value=ok):
            self.assertEqual(etl.main([]), 1)
            self.assertEqual(etl.main(['--offline']), 0)
