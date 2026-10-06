"""Offline integrity and failure tests using small, official IBGE response fixtures."""
import copy
import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.common import number, atomic_write
from scripts.sources.ibge import parse_aggregates, check_metadata, IBGE
from scripts.modules import population

FIXTURES = Path(__file__).parent / 'fixtures/population'
DATA = Path(__file__).resolve().parents[1] / 'public/data'


def fixture(name):
    return json.loads((FIXTURES / f'{name}.json').read_text())


class AggregateParsingTests(unittest.TestCase):
    def parse(self, payload=None, periods=None, variables=None):
        return parse_aggregates(payload or fixture('census'), variables or {'93': ('População residente', 'Pessoas'), '6318': ('Área da unidade territorial', 'Quilômetros quadrados'), '614': ('Densidade demográfica', 'Habitante por quilômetro quadrado')}, periods or ['2022'], {})

    def test_official_aggregate_fixture(self):
        rows = self.parse()
        self.assertEqual(population.select(rows, '93', '2022'), 14231)
        self.assertEqual(population.select(rows, '614', '2022'), 15.16)

    def test_wrong_locality(self):
        payload = fixture('census')
        payload[0]['resultados'][0]['series'][0]['localidade']['id'] = '4109401'
        with self.assertRaisesRegex(ValueError, 'Município'): self.parse(payload)

    def test_wrong_period(self):
        with self.assertRaisesRegex(ValueError, 'Período'): self.parse(periods=['2025'])

    def test_wrong_unit(self):
        payload = fixture('census'); payload[0]['unidade'] = 'Mil pessoas'
        with self.assertRaisesRegex(ValueError, 'unidade'): self.parse(payload)

    def test_absent_cell(self):
        payload = fixture('census'); payload[0]['resultados'][0]['series'][0]['serie'] = {}
        with self.assertRaisesRegex(ValueError, 'incompleta'): self.parse(payload)

    def test_duplicate_cell(self):
        payload = fixture('census'); payload.append(copy.deepcopy(payload[0]))
        with self.assertRaisesRegex(ValueError, 'duplicada'): self.parse(payload)

    def test_missing_symbols_never_become_zero(self):
        for symbol in ['X', '..', '...', None]:
            with self.subTest(symbol=symbol):
                payload = fixture('census'); payload[0]['resultados'][0]['series'][0]['serie']['2022'] = symbol
                with self.assertRaises(ValueError): self.parse(payload)
                self.assertIsNone(number(symbol, allow_missing=True))

    def test_absolute_zero_is_explicit_and_keeps_symbol(self):
        payload = fixture('census'); payload[0]['resultados'][0]['series'][0]['serie']['2022'] = '-'
        parsed = self.parse(payload)
        self.assertEqual(parsed[0]['value'], 0)
        self.assertEqual(parsed[0]['rawSymbol'], '-')
        # Generic parsing does not silently assume the SIDRA convention.
        with self.assertRaises(ValueError): number('-')

    def test_non_finite_values(self):
        for value in ['NaN', 'inf', '-inf']:
            with self.subTest(value=value), self.assertRaises(ValueError): number(value)

    def test_fractional_population_is_rejected(self):
        payload = fixture('census'); payload[0]['resultados'][0]['series'][0]['serie']['2022'] = '14231.5'
        with self.assertRaisesRegex(ValueError, 'inteira'): self.parse(payload)

    def test_metadata_has_verified_categories(self):
        meta = fixture('metadata-9606')
        check_metadata(meta, {'93': ('População residente', 'Pessoas')}, {'86': population.RACE, '2': population.SEX, '287': population.AGES})
        bad = copy.deepcopy(population.SEX); bad['4'] = 'Categoria inventada'
        with self.assertRaisesRegex(ValueError, 'Categorias'):
            check_metadata(meta, {'93': ('População residente', 'Pessoas')}, {'2': bad})

    def test_missing_municipal_level(self):
        meta = fixture('metadata-9606'); meta['nivelTerritorial']['Administrativo'].remove('N6')
        with self.assertRaisesRegex(ValueError, 'municipal'):
            check_metadata(meta, {'93': ('População residente', 'Pessoas')}, {})

    def test_unexpected_category(self):
        payload = fixture('race'); payload[0]['resultados'][0]['classificacoes'][0]['categoria'] = {'999': 'Desconhecida'}
        with self.assertRaisesRegex(ValueError, 'Categoria'):
            parse_aggregates(payload, {'93': ('População residente', 'Pessoas')}, ['2022'], {'86': population.RACE, '2': {'6794': 'Total'}, '287': {'100362': 'Total'}})

    def test_unpublished_period_is_rejected_before_requesting_values(self):
        client = IBGE('2026-10-06T12:00:00Z')
        with patch('scripts.sources.ibge.request_json', side_effect=[fixture('metadata-9606'), [{'id': '2022'}]]) as request:
            with self.assertRaisesRegex(ValueError, 'Período não publicado'):
                client.aggregate('age', '9606', {'93': ('População residente', 'Pessoas')}, {}, ['2025'])
            self.assertEqual(request.call_count, 2)

    def test_age_aggregation_from_real_fixture(self):
        rows = parse_aggregates(fixture('age-sex'), {'93': ('População residente', 'Pessoas')}, ['2022'], {'86': {'95251': 'Total'}, '2': population.SEX, '287': population.AGES})
        grouped = population.age_groups(rows)
        self.assertEqual(len(grouped), 11)
        self.assertEqual(sum(r['total'] for r in grouped), 14231)
        self.assertEqual(sum(r['male'] for r in grouped), 7205)
        self.assertEqual(sum(r['female'] for r in grouped), 7026)
        self.assertTrue(all(r['male'] + r['female'] == r['total'] for r in grouped))

    def test_distribution_percentages_from_real_fixture(self):
        rows = parse_aggregates(fixture('race'), {'93': ('População residente', 'Pessoas')}, ['2022'], {'86': population.RACE, '2': {'6794': 'Total'}, '287': {'100362': 'Total'}})
        distribution = population.distribution(rows, '86', population.RACE, '95251', {'2': '6794', '287': '100362'}, 'race')
        self.assertAlmostEqual(sum(r['percent'] for r in distribution['rows']), 100)
        self.assertEqual([r['category'] for r in distribution['rows']], ['Branca', 'Preta', 'Amarela', 'Parda', 'Indígena'])


class PopulationSnapshotTests(unittest.TestCase):
    def setUp(self): self.data = json.loads((DATA / 'population.json').read_text())

    def test_schema_and_audit_paths(self):
        population.validate(self.data)
        for source in self.data['sources']:
            self.assertTrue((DATA / source['rawPath']).exists())
            self.assertTrue(source['collectedAt'])

    def test_census_and_estimates_are_distinct(self):
        self.assertEqual(self.data['summary']['population-census']['value'], 14231)
        self.assertEqual(self.data['summary']['population-estimate']['reference'], max(row['period'] for row in self.data['estimateHistory']['rows']))
        self.assertTrue(all(row['methodology'] == 'census' for row in self.data['populationHistory']['rows']))
        self.assertTrue(all(row['methodology'] == 'estimate' for row in self.data['estimateHistory']['rows']))
        self.data['summary']['population-estimate']['methodology'] = 'census'
        with self.assertRaises(ValueError): population.validate(self.data)

    def test_compatible_growth_does_not_use_raw_2010(self):
        self.assertEqual(self.data['growth']['compatibleBaseline'], 14074)
        self.assertEqual(self.data['growth']['absoluteChange'], 157)
        self.assertEqual(next(r['value'] for r in self.data['populationHistory']['rows'] if r['period'] == '2010'), 13811)
        self.assertAlmostEqual(self.data['growth']['percentChange'], 157/14074*100)

    def test_wrong_snapshot_municipality(self):
        self.data['municipality']['code'] = '4109401'
        with self.assertRaises(ValueError): population.validate(self.data)

    def test_incomplete_distribution_rejected(self):
        self.data['race']['rows'].pop()
        with self.assertRaises(ValueError): population.validate(self.data)

    def test_percentages_are_consistent_not_only_sum(self):
        self.data['sex']['rows'][0]['percent'] += 1
        self.data['sex']['rows'][1]['percent'] -= 1
        with self.assertRaises(ValueError): population.validate(self.data)

    def test_age_categories_cannot_overlap(self):
        self.data['ageSex']['rows'][0]['categoryIds'] += ['93084']
        with self.assertRaises(ValueError): population.validate(self.data)

    def test_wrong_geometry_code(self):
        self.data['territory']['geometry']['features'][0]['properties']['codarea'] = '4109401'
        with self.assertRaises(ValueError): population.validate(self.data)

    def test_household_universe_is_not_forced_equal_to_total_population(self):
        self.assertEqual(self.data['households']['residents'], 14225)
        self.assertNotEqual(self.data['households']['residents'], self.data['summary']['population-census']['value'])
        population.validate(self.data)

    def test_network_failure_preserves_all_previous_values(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder); atomic_write(directory / 'population.json', self.data)
            with patch.object(population, 'collect', side_effect=OSError('offline')), redirect_stdout(io.StringIO()):
                result = population.update(directory)
            for key in self.data:
                if key != 'collection': self.assertEqual(result[key], self.data[key])
            self.assertEqual(result['collection']['lastSuccessAt'], self.data['collection']['lastSuccessAt'])
            self.assertTrue(result['collection']['failures'])

    def test_first_failed_collection_creates_no_fake_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(population, 'collect', side_effect=ValueError('Resposta incompleta')):
                with self.assertRaises(RuntimeError): population.update(folder)
            self.assertFalse((Path(folder) / 'population.json').exists())

    def test_snapshot_is_not_replaced_by_incomplete_candidate(self):
        # Simulate a parser/collector regression yielding an invalid candidate.
        invalid = copy.deepcopy(self.data); invalid['ageSex']['rows'].pop()
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder); atomic_write(directory / 'population.json', self.data)
            with patch.object(population, 'collect', return_value=(invalid, {})), redirect_stdout(io.StringIO()):
                result = population.update(directory)
            self.assertEqual(result['ageSex'], self.data['ageSex'])
            self.assertTrue(result['collection']['failures'])

    def test_non_population_catalog_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            original = json.loads((DATA / 'indicators.json').read_text())
            other = [row for row in original['indicators'] if row['module'] != 'population']
            atomic_write(directory / 'indicators.json', original)
            population.sync_catalog(self.data, directory)
            actual = json.loads((directory / 'indicators.json').read_text())
            self.assertEqual(other, [row for row in actual['indicators'] if row['module'] != 'population'])

    def test_csvs_keep_source_and_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            population.export_csv(self.data, Path(folder))
            for file in Path(folder).glob('*.csv'):
                rows = list(csv.DictReader(io.StringIO(file.read_text())))
                self.assertTrue(rows)
                self.assertTrue(all(r['reference'] and r['sourceUrl'].startswith('https://servicodados.ibge.gov.br/') for r in rows))

if __name__ == '__main__': unittest.main()
