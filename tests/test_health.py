import copy,csv,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from scripts.modules import health as h
from scripts.sources import cnes as c,datasus as d
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests/fixtures/health'
def fixture(name):return json.loads((FIX/(name+'.json')).read_text())
def snapshot():return json.loads((ROOT/'public/data/health.json').read_text())
def normalized(rows=None):return c.normalize_network(rows if rows is not None else fixture('cnes'),fixture('types'))[0]
class NetworkTests(unittest.TestCase):
 def test_turvo_only_excludes_homonym_sc(self):
  records=normalized();self.assertEqual(set(records),set(c.MUNICIPALITIES));self.assertTrue(all(r['municipalityCode']=='4127965' for r in records['4127965']))
 def test_cnes_leading_zero_restoration(self):
  self.assertEqual(c.cnes_code('204056'),'0204056')
  for value in ('0','12345678','NaN','abc'):
   with self.assertRaises(ValueError):c.cnes_code(value)
 def test_identical_duplicate_deduplicated(self):
  rows=fixture('cnes');n=normalized(rows);self.assertEqual(n,normalized(rows+[copy.deepcopy(rows[0])]))
 def test_conflicting_duplicate_rejected(self):
  rows=fixture('cnes');r=copy.deepcopy(rows[0]);r['NO_FANTASIA']='Divergente'
  with self.assertRaisesRegex(ValueError,'duplicado'):normalized(rows+[r])
 def test_inactive_not_counted(self):
  records=normalized()['4127965'];s=c.summarize(records);self.assertEqual(s['inactive'],1);self.assertEqual(s['active'],len(records)-1);self.assertFalse(next(r for r in records if r['cnes']=='2742284')['active'])
 def test_ambulatory_sus_does_not_deny_samu(self):
  r=next(r for r in normalized()['4127965'] if r['cnes']=='4206916');self.assertFalse(r['ambulatorySus']);self.assertIsNone(r['sus']);self.assertTrue(r['urgent'])
 def test_unknown_sus_separate(self):
  rows=fixture('cnes');rows[0]['CO_AMBULATORIAL_SUS']='';r=normalized(rows)['4127965'];s=c.summarize(r);self.assertEqual(s['sus']['ambulatoryUnknown'],1);self.assertEqual(s['sus']['ambulatoryYes']+s['sus']['ambulatoryNo']+s['sus']['ambulatoryUnknown'],s['active'])
 def test_gym_not_urgency_and_ubs_type_only(self):
  r=next(r for r in normalized()['4127965'] if r['typeCode']=='74');self.assertFalse(r['urgent']);self.assertFalse(r['ubs']);self.assertTrue(all(r['typeCode']=='02' for r in normalized()['4127965'] if r['ubs']))
 def test_management_does_not_imply_public_ownership(self):
  r=next(r for r in normalized()['4127965'] if r['cnes']=='0802891');self.assertEqual(r['management'],'Municipal');self.assertEqual(r['ownership'],'Privada');self.assertFalse(r['municipalOwnership'])
 def test_nonprofit_not_municipal_or_philanthropic_assumption(self):
  r=next(r for r in normalized()['4127965'] if r['cnes']=='2741962');self.assertEqual(r['ownership'],'Sem fins lucrativos');self.assertFalse(r['municipalOwnership'])
 def test_group_totals_equal_active(self):
  s=c.summarize(normalized()['4127965']);self.assertTrue(all(sum(r['count'] for r in s[k])==s['active'] for k in ('byType','byOwnership','byManagement')))
 def test_state_identity_type_and_flag_invalid(self):
  for key,value in [('CO_UF','42'),('CO_UNIDADE','4218800204056'),('TP_UNIDADE','999'),('CO_AMBULATORIAL_SUS','TALVEZ'),('ST_ATEND_HOSPITALAR','2')]:
   rows=fixture('cnes');rows[0][key]=value
   with self.assertRaises(ValueError,msg=key):normalized(rows)
 def test_missing_network_not_zero(self):
  with self.assertRaisesRegex(ValueError,'ausência não é zero'):normalized([])
 def test_infinite_coordinates_not_published(self):
  rows=fixture('cnes');rows[0]['NU_LATITUDE']='NaN';self.assertIsNone(next(r for r in normalized(rows)['4127965'] if r['cnes']==c.cnes_code(rows[0]['CO_CNES']))['coordinates'])
class BedsTests(unittest.TestCase):
 def test_real_hospital_49_sus(self):
  beds=c.normalize_beds(fixture('beds'));r=next(r for r in beds['series'] if r['municipalityCode']=='4127965' and r['reference']=='202608');self.assertEqual((r['existing'],r['sus'],r['icuExisting']),(49,49,0))
 def test_zero_confirmed_only_after_nonempty_complete_iteration(self):
  r=next(r for r in c.normalize_beds(fixture('beds'))['series'] if r['municipalityCode']=='4113254');self.assertTrue(r['zeroConfirmed']);self.assertEqual(r['existing'],0)
  with self.assertRaises(ValueError):c.normalize_beds([])
 def test_beds_competence_duplicates_and_sus_bound(self):
  rows=fixture('beds');self.assertEqual(c.normalize_beds(rows)['records'],c.normalize_beds(rows+[copy.deepcopy(rows[0])])['records'])
  for key,value in [('COMP','202613'),('UF','SC'),('LEITOS_SUS','50'),('LEITOS_EXISTENTES',''),('UTI_TOTAL_SUS','1')]:
   rows=fixture('beds');rows[0][key]=value
   with self.assertRaises(ValueError,msg=key):c.normalize_beds(rows)
 def test_icu_not_added_to_total(self):
  rows=fixture('beds');rows[0]['UTI_TOTAL_EXIST']='2';rows[0]['UTI_TOTAL_SUS']='2';r=c.normalize_beds(rows)['records'][0];self.assertEqual(r['existing'],49);self.assertEqual(r['icuExisting'],2)
 def test_invalid_count_never_silent_zero(self):
  for v in (None,'','NaN','inf','-1','2.5'):
   with self.assertRaises(ValueError):c.count(v)
class SnapshotTests(unittest.TestCase):
 def test_full_official_snapshot(self):
  data=h.validate(snapshot());self.assertEqual((data['summary']['registered'],data['summary']['active'],data['summary']['ubs'],data['summary']['public']),(54,31,6,12));self.assertEqual(data['beds']['summary']['sus'],49);self.assertEqual(data['summary']['sus']['ambulatoryYes'],11)
 def test_daily_not_monthly_or_collection_date(self):
  data=snapshot();self.assertIsNone(data['network']['competence']);self.assertEqual(data['network']['reference'],'2026-10-07');self.assertEqual(data['beds']['reference'],'202608');self.assertNotEqual(data['network']['reference'],data['sources'][0]['collectedAt'])
 def test_schema_and_counts_rejected(self):
  for mutate in ('schema','municipality','total','sus','duplicate','bed'):
   data=snapshot()
   if mutate=='schema':data['schemaVersion']=2
   elif mutate=='municipality':data['municipality']['code']='4218806'
   elif mutate=='total':data['summary']['active']+=1
   elif mutate=='sus':data['network']['establishments'][0]['ambulatorySus']=not data['network']['establishments'][0]['ambulatorySus']
   elif mutate=='duplicate':data['network']['establishments'].append(data['network']['establishments'][0])
   else:data['beds']['records'][0]['sus']=1000
   with self.assertRaises(ValueError,msg=mutate):h.validate(data)
 def test_no_individual_identifiers_or_mock(self):
  data=snapshot();text=json.dumps(data);self.assertNotIn('"mock"',text);self.assertNotIn('"nu_cnpj"',text);data['cpf']='sensitive'
  with self.assertRaisesRegex(ValueError,'pessoal'):h.validate(data)
 def test_http_failure_preserves_snapshot_and_exports(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp);old=snapshot();h.atomic_write(d/'health.json',old);(d/'exports').mkdir();(d/'exports/health-beds.csv').write_text('last valid')
   with patch.object(h.datasus,'catalog',side_effect=TimeoutError('Fonte indisponível')):result=h.update(d)
   self.assertEqual(result['network'],old['network']);self.assertEqual(result['beds'],old['beds']);self.assertEqual(result['sources'],old['sources']);self.assertTrue(result['collection']['failures']);self.assertEqual((d/'exports/health-beds.csv').read_text(),'last valid')
 def test_first_failure_does_not_create_fake_data(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(h.datasus,'catalog',side_effect=TimeoutError()):
   with self.assertRaises(TimeoutError):h.update(temp)
   self.assertFalse((Path(temp)/'health.json').exists())
 def test_offline_no_network(self):
  with patch.object(h.datasus,'download',side_effect=AssertionError('network')):self.assertEqual(h.update(ROOT/'public/data',offline=True)['summary']['active'],31)
 def test_repeat_publication_skips_download_and_collection_noise(self):
  data=snapshot();datasets={h.SLUGS[s['id']]:{'name':h.SLUGS[s['id']],'resources':[{'id':s['resourceId'],'url':s['url'],'last_modified':s['publishedAt'],'state':'active','format':'CSV'}]} for s in data['sources']}
  with tempfile.TemporaryDirectory() as temp:
   h.atomic_write(Path(temp)/'health.json',data)
   with patch.object(h.datasus,'catalog',side_effect=lambda slug,_:datasets[slug]),patch.object(h.datasus,'download',side_effect=AssertionError('not needed')):self.assertEqual(h.update(temp),data)
 def test_exports_institutional_no_professional_names(self):
  with tempfile.TemporaryDirectory() as temp:
   h.exports(snapshot(),temp);r=list(csv.DictReader(io.StringIO((Path(temp)/'health-establishments.csv').read_text())));self.assertEqual(len(r),54);self.assertNotIn('cpf',r[0]);self.assertEqual(len(list(csv.DictReader(io.StringIO((Path(temp)/'health-primary-care.csv').read_text())))),6)
 def test_local_publication_rollback(self):
  with tempfile.TemporaryDirectory() as temp:
   target=Path(temp)/'public';stage=Path(temp)/'stage';target.mkdir();stage.mkdir();(target/'a.json').write_text('old');(stage/'a.json').write_text('new');(stage/'b.json').write_text('fail')
   real=h.os.replace
   def replace(src,dst):
    if Path(dst).name=='b.json':raise OSError('disk')
    return real(src,dst)
   with patch.object(h.os,'replace',side_effect=replace):
    with self.assertRaises(OSError):h.publish(stage,target)
   self.assertEqual((target/'a.json').read_text(),'old');self.assertFalse((target/'b.json').exists())
 def test_map_polygon_and_hole(self):
  poly={'type':'Polygon','coordinates':[[[0,0],[5,0],[5,5],[0,5],[0,0]],[[1,1],[2,1],[2,2],[1,2],[1,1]]]};self.assertTrue(h.in_geometry((3,3),poly));self.assertFalse(h.in_geometry((1.5,1.5),poly));self.assertFalse(h.in_geometry((8,8),poly))
 def test_map_points_are_in_official_turvo_boundary(self):
  data=snapshot();self.assertEqual(data['map']['shown'],31)
  for r in data['network']['establishments']:
   if r['mapEligible']:self.assertTrue(h.in_geometry((r['coordinates']['longitude'],r['coordinates']['latitude']),data['map']['geometry']))
class SourceTests(unittest.TestCase):
 def test_zip_stream_encoding_and_header(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'x.zip'
   with zipfile.ZipFile(path,'w') as z:z.writestr('a.csv','a;b;c;d;e\nsaúde;2;3;4;5\n'.encode('cp1252'))
   self.assertEqual(list(d.rows(path))[0]['a'],'saúde')
 def test_multiple_csv_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'x.zip'
   with zipfile.ZipFile(path,'w') as z:z.writestr('a.csv','a;b;c;d;e');z.writestr('b.csv','a;b;c;d;e')
   with self.assertRaises(ValueError):list(d.rows(path))
 def test_resource_requires_official_host_and_publication(self):
  dataset={'resources':[{'state':'active','format':'CSV','url':'https://evil.invalid/a.zip','last_modified':'2026-10-07'}]}
  with self.assertRaises(ValueError):d.resource(dataset,lambda _:True)
 def test_https_required(self):
  with self.assertRaises(ValueError):d.download('http://invalid/',Path('/tmp/never-download'))
if __name__=='__main__':unittest.main()
