"""Official IBGE fixtures plus deliberately corrupted cells; no live network."""
import copy,csv,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.modules import agriculture as a
from scripts.sources import ibge as i
ROOT=Path(__file__).resolve().parents[1]
def snapshot():return json.loads((ROOT/'public/data/agriculture.json').read_text())
def fixture():return json.loads((ROOT/'tests/fixtures/agriculture/pam-subset.json').read_text())
def parse(f):return i.parse_agricultural(f['response'],f['metadata'],['214','8331','216','112','215'],['2024','2025'],{'782':{str(c['id']):c['nome'] for c in f['metadata']['classificacoes'][0]['categorias']}},{'4127965':'N6'})
def crop(d,id):return next(p for p in d['crops']['products'] if p['categoryId']==id)
class AgriculturalParserTests(unittest.TestCase):
 def test_real_complete_cube(self):self.assertEqual(len(parse(fixture())),40)
 def test_absolute_zero_not_absence(self):self.assertEqual(i.agricultural_symbol('-'),{'value':0,'status':'real','rawSymbol':'-'})
 def test_hidden_symbols_never_zero(self):
  for raw,status in [('X','suppressed'),('..','notApplicable'),('...','unavailable')]:self.assertEqual(i.agricultural_symbol(raw),{'value':None,'status':status,'rawSymbol':raw})
 def test_negative_nonfinite_invalid(self):
  for raw in ['-1','nan','inf','garbage']:
   with self.assertRaises(ValueError):i.agricultural_symbol(raw)
 def test_wrong_turvo_sc_rejected(self):
  f=fixture();f['response'][0]['resultados'][0]['series'][0]['localidade']['id']='4218806'
  with self.assertRaisesRegex(ValueError,'Município'):parse(f)
 def test_wrong_state_rejected(self):
  f=fixture();f['response'][0]['resultados'][0]['series'][0]['localidade']['nome']='Turvo (SC)'
  with self.assertRaisesRegex(ValueError,'UF'):parse(f)
 def test_wrong_unit_rejected(self):
  f=fixture();f['response'][0]['unidade']='Cabeças'
  with self.assertRaisesRegex(ValueError,'Unidade'):parse(f)
 def test_wrong_variable_rejected(self):
  f=fixture();f['response'][0]['variavel']='Valor da produção'
  with self.assertRaisesRegex(ValueError,'Variável'):parse(f)
 def test_missing_cell_not_zero(self):
  f=fixture();del f['response'][0]['resultados'][0]['series'][0]['serie']['2025']
  with self.assertRaisesRegex(ValueError,'incompleto'):parse(f)
 def test_duplicate_cell_rejected(self):
  f=fixture();f['response'][0]['resultados'].append(copy.deepcopy(f['response'][0]['resultados'][0]))
  with self.assertRaisesRegex(ValueError,'duplicada'):parse(f)
 def test_changed_category_rejected(self):
  f=fixture();f['response'][0]['resultados'][0]['classificacoes'][0]['categoria']={'40124':'Produto inventado'}
  with self.assertRaisesRegex(ValueError,'categoria'):parse(f)
 def test_category_specific_milk_and_egg_units(self):
  raw=json.loads((ROOT/'public/data/agriculture/raw/animal.json').read_text());variable=next(v for v in raw['metadata']['variaveis'] if v['id']==106);cats=raw['metadata']['classificacoes'][0]['categorias'];self.assertEqual(i.agricultural_unit(variable,next(c for c in cats if c['id']==2682),'2025'),'Mil litros');self.assertEqual(i.agricultural_unit(variable,next(c for c in cats if c['id']==2685),'2025'),'Mil dúzias')
 def test_historical_currency_range_and_future_revision(self):
  unit={'unidade':'Mil Reais [1994 a 2026]'};self.assertEqual(i.agricultural_unit(unit,None,'2026'),'Mil Reais')
  with self.assertRaises(ValueError):i.agricultural_unit(unit,None,'1993')
 def test_unit_override_pam_is_not_quantity_conversion(self):
  rows=parse(fixture());r=next(r for r in rows if r['variable']=='214' and r['categories']['782']=='40092');c=a.cell(r,'pam','Mil frutos');self.assertEqual(c['unit'],'Mil frutos');self.assertEqual(c['value'],r['value']);self.assertEqual(c['originalUnit'],'Toneladas')
 def test_currency_conversion_once(self):
  r=next(r for r in parse(fixture()) if r['variable']=='215' and r['categories']['782']=='40124' and r['period']=='2025');c=a.cell(r,'pam');self.assertEqual(c['value'],139258000);self.assertEqual(c['unit'],'R$');self.assertEqual(c['originalUnit'],'Mil Reais')
class AgricultureSnapshotTests(unittest.TestCase):
 def test_official_snapshot_valid(self):self.assertEqual(a.validate(snapshot())['summary']['cropCount'],32)
 def test_crops_quantity_area_yield_distinct(self):
  m=crop(snapshot(),'40119')['latest']['metrics'];self.assertEqual(m['plantedOrIntendedArea']['value'],133);self.assertEqual(m['harvestedArea']['value'],130);self.assertEqual(m['production']['value'],2780);self.assertEqual(m['yield']['value'],21385)
 def test_ten_years_and_new_crops_have_gaps(self):
  d=snapshot();self.assertEqual([p['reference'] for p in crop(d,'40124')['series']],[str(n) for n in range(2016,2026)]);self.assertEqual(crop(d,'83389')['series'][0]['metrics']['production']['status'],'unavailable')
 def test_mate_sources_separate(self):
  d=snapshot();cult=crop(d,'40147');ex=next(p for p in d['forestry']['extraction']['products'] if p['categoryId']=='3406');self.assertEqual(cult['latest']['metrics']['production']['value'],25100);self.assertEqual(ex['latest']['metrics']['production']['value'],0);self.assertNotEqual(ex['sourceId'],cult['sourceId'])
 def test_herd_subgroups_not_summed(self):
  d=snapshot();h={p['categoryId']:p['latest']['metrics']['herd']['value'] for p in d['livestock']['herds']['products']};self.assertEqual(h['2670'],36000);self.assertEqual(h['32796'],56000);self.assertEqual(h['32793'],16800);self.assertEqual(d['livestock']['herds']['totals'],{})
 def test_milk_per_cow_derived(self):self.assertAlmostEqual(snapshot()['livestock']['milkPerCow']['value'],26500*1000/5980)
 def test_census_structural_not_annual(self):
  c=snapshot()['agriculturalCensus'];self.assertEqual(c['reference'],'2017');self.assertEqual(c['values']['establishments']['value'],1219);self.assertEqual(c['values']['familyEstablishments']['value'],859);self.assertEqual(c['values']['people']['value'],2804)
 def test_pevs_parent_and_child_not_summed(self):
  f=snapshot()['forestry']['silviculture'];self.assertEqual(f['totals']['productionValue']['value'],50652000);self.assertGreater(sum(p['latest']['metrics']['productionValue']['value'] or 0 for p in f['products']),f['totals']['productionValue']['value'])
 def test_official_rounding_not_rejected(self):
  f=snapshot()['livestock']['aquaculture'];self.assertEqual(f['totals']['productionValue']['value'],279000);self.assertEqual(sum(p['latest']['metrics']['productionValue']['value'] or 0 for p in f['products']),280000)
 def test_comparisons_same_period_and_unit(self):
  d=snapshot();self.assertEqual({s['municipalityCode'] for s in d['comparisons']},{'4109401','4119608','4113254','41'});self.assertTrue(all(s['crops']['reference']==d['crops']['reference'] for s in d['comparisons']))
 def test_invalid_summary_source_symbol_count_history_rejected(self):
  for kind in ['summary','count','variable','symbol','integer','history','derived','source','currency']:
   d=snapshot();m=d['crops']['products'][0]['latest']['metrics']['production']
   if kind=='summary':d['summary']['leadingCropId']='invented'
   if kind=='count':d['summary']['cropCount']=1
   if kind=='variable':m['variableId']='99999'
   if kind=='symbol':m['rawSymbol']='X'
   if kind=='integer':d['agriculturalCensus']['values']['people']['value']=1.5
   if kind=='history':d['crops']['products'][0]['series'].reverse()
   if kind=='derived':d['livestock']['milkPerCow']['value']=1
   if kind=='source':d['sources'][0]['url']='https://example.com'
   if kind=='currency':d['summary']['productionValue']['originalUnit']='R$'
   with self.assertRaises(ValueError,msg=kind):a.validate(d)
 def test_nominal_change_and_zero_gap(self):
  self.assertEqual(a.annual_change(120,100,'2025','2024'),19.999999999999996);self.assertIsNone(a.annual_change(10,0,'2025','2024'));self.assertIsNone(a.annual_change(10,8,'2025','2023'));self.assertIsNone(a.annual_change(None,8,'2025','2024'))
 def test_offline_never_requests_network(self):
  with patch.object(a,'AgriculturalIBGE',side_effect=AssertionError('network')):self.assertEqual(a.update(ROOT/'public/data',offline=True)['crops']['reference'],'2025')
 def test_api_failure_preserves_all_existing_data(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t);original=snapshot();(path/'agriculture.json').write_text(json.dumps(original));(path/'sentinel.csv').write_text('untouched')
   with patch.object(a,'build',side_effect=TimeoutError('official API timeout')):result=a.update(path)
   result['collection']=original['collection'];self.assertEqual(result,original);self.assertEqual((path/'sentinel.csv').read_text(),'untouched')
 def test_first_failure_cannot_invent_snapshot(self):
  with tempfile.TemporaryDirectory() as t,patch.object(a,'build',side_effect=TimeoutError('API')):
   with self.assertRaises(TimeoutError):a.update(t)
   self.assertFalse((Path(t)/'agriculture.json').exists())
 def test_catalog_preserves_other_modules_removes_mock(self):
  with tempfile.TemporaryDirectory() as t:
   original=json.loads((ROOT/'public/data/indicators.json').read_text());before=[r for r in original['indicators'] if r['module']!='agriculture'];original['indicators'].append({'id':'soy','module':'agriculture','status':'mock'});(Path(t)/'indicators.json').write_text(json.dumps(original));a.update_catalog(snapshot(),t);after=json.loads((Path(t)/'indicators.json').read_text())['indicators'];self.assertEqual(sorted(before,key=lambda r:r['id']),sorted([r for r in after if r['module']!='agriculture'],key=lambda r:r['id']));self.assertFalse(any(r['id']=='soy' for r in after))
 def test_csv_preserves_units_null_status_and_code(self):
  with tempfile.TemporaryDirectory() as t:
   a.export_csv(snapshot(),t);rows=list(csv.DictReader(io.StringIO((Path(t)/'agriculture-crops.csv').read_text())));self.assertTrue(all(r['municipalityCode']=='4127965' for r in rows));self.assertTrue(any(r['value']=='' and r['status']=='unavailable' for r in rows));self.assertTrue(any(r['unit']=='R$' for r in rows))

class FullETLFixtureTests(unittest.TestCase):
 def test_all_nine_official_responses_build_same_valid_snapshot(self):
  expected=snapshot();mapping={}
  for source in expected['sources']:
   raw=json.loads((ROOT/'public/data/agriculture/raw'/f"{source['id']}.json").read_text());mapping[source['url']]=raw['response'];mapping[source['metadataUrl']]=raw['metadata'];mapping[i.BASE+'/'+source['table']+'/periodos']=raw['periods']
  classifications=json.loads((ROOT/'public/data/agriculture/classifications.json').read_text())
  for table in ('1612','1613'):
   mapping[i.BASE+'/'+table+'/metadados']=classifications['metadata'][table];mapping[i.BASE+'/'+table+'/periodos']=[{'id':'2025'}]
  with patch.object(i,'request_json',side_effect=lambda url:copy.deepcopy(mapping[url])):
   client=i.AgriculturalIBGE(expected['collection']['attemptedAt']);actual=a.build(client,json.loads(a.CONFIG.read_text()),expected['collection']['attemptedAt'])
  # Collection dates are provenance of individual requests, not data values.
  actual['sources']=expected['sources'];self.assertEqual(actual,expected)
class RevisionTests(unittest.TestCase):
 def test_revised_historical_value_is_not_skipped_when_latest_year_same(self):
  original=fixture();revised=copy.deepcopy(original);v=next(v for v in revised['response'] if v['id']=='215');r=next(r for r in v['resultados'] if '40124' in r['classificacoes'][0]['categoria']);r['series'][0]['serie']['2024']='120000';before=parse(original);after=parse(revised);pick=lambda rows:next(r for r in rows if r['variable']=='215' and r['categories']['782']=='40124' and r['period']=='2024')['value'];self.assertNotEqual(pick(before),pick(after));self.assertEqual(max(r['period'] for r in before),max(r['period'] for r in after))
 def test_identical_response_keeps_dates_and_does_not_publish(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t);previous=snapshot();(path/'agriculture.json').write_text(json.dumps(previous));raws={}
   for source in previous['sources']:
    raw=json.loads((ROOT/'public/data/agriculture/raw'/f"{source['id']}.json").read_text());p=path/'agriculture/raw'/f"{source['id']}.json";p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(raw));raws[source['id']]=raw
   def build(client,config,now):
    result=copy.deepcopy(previous);result['collection']['attemptedAt']=now
    for source in result['sources']:source['collectedAt']=now
    client.raw=copy.deepcopy(raws)
    for raw in client.raw.values():raw['collectedAt']=now
    return result
   with patch.object(a,'build',side_effect=build),patch('scripts.modules.health.publish',side_effect=AssertionError('no noisy writes')):self.assertEqual(a.update(path),previous)
