import copy
import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from scripts.common import atomic_write
from scripts.sources.ibge import parse_aggregates, check_metadata, aggregate_url
from scripts.modules import economy as e

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/fixtures/economy'

def fixture(name): return json.loads((FIX / f'{name}.json').read_text())

def snapshot(): return json.loads((ROOT / 'public/data/economy.json').read_text())


class EconomyParsingTests(unittest.TestCase):
    def parse(self, payload=None):
        return parse_aggregates(payload or fixture('aggregate-turvo'), e.VARIABLES, [p['id'] for p in fixture('periods')], {}, allow_missing=True)

    def test_official_metadata_and_tax_unit(self):
        check_metadata(fixture('metadata'), e.VARIABLES, {})
        self.assertEqual(e.VARIABLES['543'][1], 'Mil Reais')
        self.assertIn('Impostos', e.VARIABLES['543'][0])
        self.assertNotIn('capita', str(fixture('metadata')['variaveis']))

    def test_wrong_metadata_unit_rejected(self):
        meta = fixture('metadata'); meta['variaveis'][0]['unidade'] = 'Reais'
        with self.assertRaises(ValueError): check_metadata(meta, e.VARIABLES, {})

    def test_missing_municipal_level_rejected(self):
        meta = fixture('metadata'); meta['nivelTerritorial'] = {'Administrativo': ['N1']}
        with self.assertRaises(ValueError): check_metadata(meta, e.VARIABLES, {})

    def test_municipal_query_parameterized(self):
        self.assertIn('4109401', aggregate_url('5938', ['2023'], {'37': e.VARIABLES['37']}, {}, code='4109401'))

    def test_thousand_reais_conversion(self):
        rows = self.parse(); capita, missing = e.parse_capita(fixture('capita-meta'), fixture('indicators38'), fixture('capita-turvo'), e.CODE)
        result = e.build_municipality(rows, capita, missing, e.CODE, 'Turvo')
        self.assertEqual(result['gdp']['latest']['value'], 697870000)
        self.assertEqual(result['gdpPerCapita']['latest']['value'], 49038.74)
        self.assertEqual(result['taxes']['latest']['value'], 51801000)
        self.assertEqual(result['sectorComposition']['latestPeriod'], '2021')
        self.assertEqual(result['gdp']['latest']['period'], '2023')

    def test_wrong_municipality_unit_variable_and_level(self):
        for field, value in [('code','4109401'), ('unit','Reais'), ('variable','543'), ('level','N3')]:
            with self.subTest(field=field):
                payload = fixture('aggregate-turvo')
                if field=='code': payload[0]['resultados'][0]['series'][0]['localidade']['id']=value
                elif field=='unit': payload[0]['unidade']=value
                elif field=='variable': payload[0]['id']=value
                else: payload[0]['resultados'][0]['series'][0]['localidade']['nivel']['id']=value
                with self.assertRaises(ValueError): self.parse(payload)

    def test_special_symbols_are_explicit(self):
        for raw in ['X', '..', '...']:
            payload = fixture('aggregate-turvo'); payload[0]['resultados'][0]['series'][0]['serie']['2023']=raw
            rows = self.parse(payload); item = next(r for r in rows if r['variable']=='37' and r['period']=='2023')
            self.assertIsNone(item['value']); self.assertEqual(item['rawSymbol'],raw)
        payload = fixture('aggregate-turvo'); payload[0]['resultados'][0]['series'][0]['serie']['2023']='-'
        item = next(r for r in self.parse(payload) if r['variable']=='37' and r['period']=='2023')
        self.assertEqual(item['value'],0); self.assertEqual(item['rawSymbol'],'-')

    def test_negative_and_nonfinite_rejected(self):
        for raw in ['NaN', 'inf', '-1']:
            payload = fixture('aggregate-turvo'); payload[0]['resultados'][0]['series'][0]['serie']['2023']=raw
            with self.assertRaises(ValueError): self.parse(payload)

    def test_missing_duplicate_and_unexpected_period_rejected(self):
        for mode in ['missing','duplicate','extra']:
            payload = fixture('aggregate-turvo')
            if mode=='missing': del payload[0]['resultados'][0]['series'][0]['serie']['2023']
            elif mode=='duplicate':payload.append(copy.deepcopy(payload[0]))
            else:payload[0]['resultados'][0]['series'][0]['serie']['2099']='1'
            with self.assertRaises(ValueError):self.parse(payload)

    def test_unexpected_classification_rejected(self):
        payload=fixture('aggregate-turvo');payload[0]['resultados'][0]['classificacoes']=[{'id':'1','categoria':{'0':'Total'}}]
        with self.assertRaises(ValueError):self.parse(payload)

    def test_capita_official_revised_unit_and_parent(self):
        rows, _ = e.parse_capita(fixture('capita-meta'), fixture('indicators38'), fixture('capita-turvo'), e.CODE)
        self.assertEqual(rows[0]['period'],'2010');self.assertEqual(rows[-1]['value'],49038.74)
        for mode in ['unit','parent','code','survey','id']:
            meta,hierarchy,payload=fixture('capita-meta'),fixture('indicators38'),fixture('capita-turvo')
            if mode=='unit':meta[0]['unidade']['multiplicador']=1000
            elif mode=='parent':next(i for i in hierarchy if i['id']==47000)['indicador']='PIB total'
            elif mode=='code':payload[0]['res'][0]['localidade']='410940'
            elif mode=='survey':meta[0]['pesquisa_id']=1
            else:payload[0]['id']=47002
            with self.assertRaises(ValueError):e.parse_capita(meta,hierarchy,payload,e.CODE)

    def test_capita_missing_not_zero(self):
        payload=fixture('capita-turvo');payload[0]['res'][0]['res']['2009']=None
        rows,missing=e.parse_capita(fixture('capita-meta'),fixture('indicators38'),payload,e.CODE)
        self.assertNotIn('2009',[r['period'] for r in rows]);self.assertEqual(missing,[{'period':'2009','rawSymbol':None}])

    def test_partial_and_unexpected_sector_missing_rejected(self):
        rows=self.parse();capita,missing=e.parse_capita(fixture('capita-meta'),fixture('indicators38'),fixture('capita-turvo'),e.CODE)
        next(r for r in rows if r['period']=='2021' and r['variable']=='513')['value']=None
        with self.assertRaises(ValueError):e.build_municipality(rows,capita,missing,e.CODE,'Turvo')
        rows=self.parse()
        for r in rows:
            if r['period']=='2020' and r['variable']!='37':r['value']=None
        with self.assertRaises(ValueError):e.build_municipality(rows,capita,missing,e.CODE,'Turvo')

    def test_nominal_change(self):
        self.assertAlmostEqual(e.nominal_change(697870000,633524000),10.1568369943)
        self.assertAlmostEqual(e.nominal_change(90,100),-10)
        self.assertEqual(e.nominal_change(100,100),0)
        self.assertIsNone(e.nominal_change(100,0));self.assertIsNone(e.nominal_change(100,None))


class EconomySchemaTests(unittest.TestCase):
    def test_snapshot_schema_and_raw_provenance(self):
        data=snapshot();e.validate(data)
        for source in data['sources']:
            raw=json.loads((ROOT/'public/data'/source['rawPath']).read_text())
            self.assertEqual(raw['url'],source['url'])
        self.assertEqual(data['sectorComposition']['series'][-1]['leadingSector'],'industry')

    def reject(self, mutate):
        data=snapshot();mutate(data)
        with self.assertRaises((ValueError,StopIteration)):e.validate(data)

    def test_share_sum_rounding_allowed(self):
        data=snapshot(); row=data['sectorComposition']['series'][0]
        self.assertAlmostEqual(sum(s['share'] for s in row['sectors']),100,delta=.03)
        e.validate(data)

    def test_share_wrong_denominator_and_sum_rejected(self):
        self.reject(lambda d:d['sectorComposition']['series'][0]['sectors'][0].update(share=90))
        self.reject(lambda d:d['sectorComposition'].update(denominator='gdp'))
        self.reject(lambda d:d['taxes'].update(shareDenominator='vab-total'))

    def test_identity_and_sector_total_rejected(self):
        self.reject(lambda d:d['sectorComposition']['series'][0].update(vabTotal=100))
        self.reject(lambda d:d['taxes']['series'][0].update(value=1))

    def test_sector_ids_unit_period_and_principal_rejected(self):
        for changes in [{'id':'taxes'},{'unit':'Mil Reais'},{'period':'2023'},{'shareVariableId':'553'}]:
            self.reject(lambda d:d['sectorComposition']['series'][0]['sectors'][0].update(changes))
        self.reject(lambda d:d['sectorComposition']['series'][0].update(leadingSector='agriculture'))
        self.reject(lambda d:d['sectorComposition'].update(latestPeriod='2023'))

    def test_series_order_duplicate_and_finite_rejected(self):
        self.reject(lambda d:d['gdp']['series'].reverse())
        self.reject(lambda d:d['gdp']['series'].insert(0,copy.deepcopy(d['gdp']['series'][0])))
        self.reject(lambda d:d['gdp']['series'][0].update(value=float('nan')))
        self.reject(lambda d:d['gdpPerCapita'].update(unit='Mil Reais'))
        self.reject(lambda d:d['gdp']['series'][1].update(nominalChange=12))

    def test_summary_and_source_must_correspond(self):
        self.reject(lambda d:d['summary']['gdp'].update(value=1))
        self.reject(lambda d:d['sources'][0]['variables'][0].update(unit='Reais'))
        self.reject(lambda d:d['sources'][0].update(municipalityCode='9999999'))
        self.reject(lambda d:d.update(schemaVersion=2))

    def test_failure_keeps_all_numeric_data_and_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);data=snapshot();atomic_write(directory/'economy.json',data)
            (directory/'gdp.csv').write_text('existing export')
            with patch.object(e,'collect',side_effect=OSError('API down')),redirect_stdout(io.StringIO()):result=e.update(directory)
            for field in ['gdp','gdpPerCapita','sectorComposition','taxes','comparisons','sources','summary']:
                self.assertEqual(data[field],result[field])
            self.assertEqual(result['collection']['lastSuccessAt'],data['collection']['lastSuccessAt'])
            self.assertIn('API down',result['collection']['failures'][0])
            self.assertEqual((directory/'gdp.csv').read_text(),'existing export')

    def test_first_failure_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(e,'collect',side_effect=OSError('API down')):
                with self.assertRaises(RuntimeError):e.update(Path(folder))
            self.assertFalse((Path(folder)/'economy.json').exists())

    def test_invalid_candidate_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);previous=snapshot();atomic_write(directory/'economy.json',previous)
            invalid=copy.deepcopy(previous);invalid['gdp']['latest']['value']=-1
            with patch.object(e,'collect',return_value=(invalid,{})),redirect_stdout(io.StringIO()):result=e.update(directory)
            self.assertEqual(result['gdp'],previous['gdp']);self.assertTrue(result['collection']['failures'])

    def test_economy_only_catalog_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);catalog=json.loads((ROOT/'public/data/indicators.json').read_text());peers=json.loads((ROOT/'public/data/comparison.json').read_text())
            atomic_write(directory/'indicators.json',catalog);atomic_write(directory/'comparison.json',peers)
            e.sync_catalog(snapshot(),directory)
            updated=json.loads((directory/'indicators.json').read_text())
            self.assertEqual([i for i in updated['indicators'] if i['module']!='economy'],[i for i in catalog['indicators'] if i['module']!='economy'])
            updated_peers=json.loads((directory/'comparison.json').read_text())
            for code in peers:
                self.assertEqual([i for i in updated_peers[code]['indicators'] if i['module']!='economy'],[i for i in peers[code]['indicators'] if i['module']!='economy'])

    def test_csv_metadata_and_references(self):
        for filename in ['gdp.csv','gdp-per-capita.csv','economy-sectors.csv']:
            rows=list(csv.DictReader(io.StringIO((ROOT/'public/data'/filename).read_text())))
            self.assertEqual({r['municipalityCode'] for r in rows},set(e.MUNICIPALITIES))
            self.assertTrue(all(r['sourceUrl'].startswith('https://servicodados.ibge.gov.br/') and r['collectedAt'] for r in rows))
            if filename=='economy-sectors.csv':self.assertEqual(max(r['period'] for r in rows),'2021')
            else:self.assertEqual(max(r['period'] for r in rows),'2023')

    def test_published_snapshot_matches_all_raw_numeric_responses(self):
        data=snapshot();sources={s['id']:s for s in data['sources']}
        for item in [data,*data['comparisons']]:
            code=item['municipality']['code']
            accounts=json.loads((ROOT/'public/data'/sources[item['gdp']['sourceId']]['rawPath']).read_text())
            rows=parse_aggregates(accounts['response'],e.VARIABLES,sources[item['gdp']['sourceId']]['periods'],{},code=code,allow_missing=True)
            raw_capita=json.loads((ROOT/'public/data'/sources[item['gdpPerCapita']['sourceId']]['rawPath']).read_text())
            capita,missing=e.parse_capita(raw_capita['metadata'],raw_capita['hierarchy'],raw_capita['response'],code)
            rebuilt=e.build_municipality(rows,capita,missing,code,item['municipality']['name'])
            for key in ['gdp','gdpPerCapita','sectorComposition','taxes']:
                self.assertEqual(rebuilt[key],item[key])

    def test_offline_validation_performs_no_network(self):
        with patch.object(e,'request_json',side_effect=AssertionError('network forbidden')):
            e.update(ROOT/'public/data',offline=True)
