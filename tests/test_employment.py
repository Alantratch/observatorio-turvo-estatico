import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.sources import mte
from scripts.modules import employment as e

FIX=Path(__file__).parent/'fixtures'/'employment'
ROOT=Path(__file__).resolve().parents[1]


def rows(kind):
    with (FIX/(kind.lower()+'.csv')).open(encoding='utf-8') as h:return list(mte.caged_rows(h,kind))


def rais_fixture():
    d=json.loads((FIX/'rais-table4.json').read_text())
    with patch.object(mte,'xlsx_rows',return_value={'TABELA 4':[d['header'],d['periods'],*d['rows']]}):return e.rais_table('fixture.xlsx','2026-10-06T13:00:00Z')


class TerritorialTests(unittest.TestCase):
    def test_explicit_six_digit_and_state(self):
        self.assertEqual(mte.territory('412796','41'),'4127965')
        self.assertIsNone(mte.territory('4127965','41'))
        self.assertIsNone(mte.territory('412796','42'))
        self.assertIsNone(mte.territory('421880','42'))
        self.assertIsNone(mte.territory('421880','41'))
    def test_real_homonym_is_not_included(self):
        raw=(FIX/'mov.csv').read_text()
        self.assertIn('421880',raw)
        self.assertEqual(len(rows('MOV')),11)
        self.assertTrue(all(r['code']=='4127965' for r in rows('MOV')))
    def test_all_peers_have_verified_layout_names(self):
        for code,name in mte.MUNICIPALITIES.items():
            mtecode=next(k for k,v in mte.TERRITORIES.items() if v==code)
            self.assertIn(name.upper(),mte.CLASSIFICATIONS['municipalities'][mtecode].upper())


class CagedTests(unittest.TestCase):
    def test_empty_or_multiple_cnae_sections_are_rejected(self):
        for section in ('', 'BC', 'HI', ' '):
            with self.assertRaises(ValueError): mte.sector(section)

    def aggregate(self,rs=None,kind='MOV',publication='202608',start='202608',end='202608'):
        a={};e.aggregate_caged(rows('MOV') if rs is None else rs,kind,publication,start,end,a);return a
    def test_real_admissions_dismissals_balance(self):
        a=self.aggregate()[('4127965','202608')]
        self.assertEqual(a['counts'],{'admissions':7,'dismissals':4,'balance':3})
        self.assertEqual(a['salaryCount'],7)
        self.assertAlmostEqual(a['salarySum'],14472.79)
    def test_sector_cnae_cbo_have_real_classification(self):
        a=self.aggregate()[('4127965','202608')]
        self.assertEqual(a['sectors']['industry']['dismissals'],2)
        self.assertEqual(a['activities']['2330302']['dismissals'],2)
        self.assertEqual(a['occupations']['784205']['dismissals'],2)
        self.assertIn('Alimentador',mte.CLASSIFICATIONS['cbo']['784205'])
        for axis in ['sectors','activities','occupations']:self.assertEqual(e.totals(a[axis].values()),a['counts'])
    def test_real_late_records_go_to_july(self):
        a=self.aggregate(rows('FOR'),'FOR','202608','202607','202608')
        self.assertEqual(a[('4127965','202607')]['counts']['admissions'],2)
        self.assertNotIn(('4127965','202608'),a)
    def test_real_exclusions_invert_original_event(self):
        a={};e.aggregate_caged(rows('EXC'),'EXC','202608','202001','202608',a)
        self.assertEqual(a[('4109401','202507')]['counts'],{'admissions':-1,'dismissals':-1,'balance':0})
    def test_exclusion_cancels_a_controlled_original(self):
        r=copy.deepcopy(rows('EXC')[1]); ref=r['competenciamov'];a={}
        original={**r,'competenciadec':ref,'indicadordeforadoprazo':'0'}
        e.aggregate_caged([original],'MOV',ref,ref,'202608',a)
        e.aggregate_caged([r],'EXC','202608',ref,'202608',a)
        self.assertEqual(a[(r['code'],ref)]['counts'],e.empty_counts())
    def test_declared_month_flags_sign_fail_safely(self):
        for change in [{'competenciadec':'202607'},{'indicadordeforadoprazo':'1'},{'saldomovimentacao':'0'},{'tipomovimentacao':'31'},{'secao':'Z'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.aggregate([{**rows('MOV')[0],**change}])
    def test_absent_zero_outlier_and_intermittent_salary_excluded(self):
        base=rows('MOV')[0]
        for change in [{'salario':''},{'salario':'0'},{'salario':'9999999'},{'indtrabintermitente':'1'}]:
            a=self.aggregate([{**base,**change}])[('4127965','202608')]
            self.assertEqual(a['salaryCount'],0);self.assertEqual(a['counts']['admissions'],1)
    def test_unknown_minimum_does_not_estimate_salary(self):
        r={**rows('MOV')[0],'competenciamov':'202701','competenciadec':'202701'}
        a=self.aggregate([r],publication='202701',start='202701',end='202701')
        self.assertEqual(a[('4127965','202701')]['salaryCount'],0)
    def test_unknown_cbo_grouped_without_invented_description(self):
        a=self.aggregate([{**rows('MOV')[0],'cbo2002ocupacao':'000001'}])[('4127965','202608')]
        self.assertIn('unknown',a['occupations']);self.assertEqual(a['counts']['admissions'],1)
    def test_unexpected_layout_and_truncated_line_fail(self):
        raw=(FIX/'mov.csv').read_text()
        for invalid in [raw.replace('competênciamov','periodo'),raw.replace(';uf;', ';uf;uf;'),raw+'202608;41\n']:
            with self.assertRaises(ValueError):list(mte.caged_rows(io.StringIO(invalid),'MOV'))
    def test_utf8_bom_and_latin1_normalization(self):
        raw=(FIX/'mov.csv').read_text()
        for encoding in ['utf-8-sig','cp1252']:
            reader=io.TextIOWrapper(io.BytesIO(raw.encode(encoding)),encoding=encoding)
            self.assertEqual(len(list(mte.caged_rows(reader,'MOV'))),11)
    def test_numeric_missing_nonfinite(self):
        self.assertIsNone(mte.decimal(''));self.assertEqual(mte.decimal('12,25'),12.25)
        for x in ['NaN','inf']:
            with self.assertRaises(ValueError):mte.decimal(x)
    def test_complete_ytd_and_rolling12(self):
        a={}
        for ref in e.months_between('202509','202608'):
            rs=[{**r,'competenciamov':ref,'competenciadec':ref} for r in rows('MOV')]
            e.aggregate_caged(rs,'MOV',ref,'202509','202608',a)
        d=e.finalize_caged(a,'202509','202608',[],'2026-10-06')['4127965']
        self.assertEqual(d['yearToDate']['balance'],24)
        self.assertEqual(d['rolling12Months']['balance'],36)
        self.assertEqual(d['yearToDate']['admissions'],56)
        self.assertEqual(d['monthly'][-1]['admissionSalary'],2067.54)
    def test_incomplete_windows_not_reported_as_zero(self):
        d=e.finalize_caged(self.aggregate(),'202608','202608',[],'2026-10-06')['4127965']
        self.assertEqual(d['yearToDate']['status'],'unavailable');self.assertEqual(d['rolling12Months']['status'],'unavailable')
    def test_revisions_preserve_previous_new_and_date(self):
        before={'monthly':[{'period':'2026-08','admissions':7,'dismissals':4,'balance':3,'admissionSalary':2067.54}]}
        after=copy.deepcopy(before);after['monthly'][0].update(admissions=8,balance=4)
        change=e.revisions(before,after,'2026-10-07')[0]
        self.assertEqual(change['previous']['balance'],3);self.assertEqual(change['current']['balance'],4)
        self.assertEqual(change['revisionDetectedAt'],'2026-10-07')
        self.assertFalse(e.revisions(before,before,'now'))
    def test_calendar_no_old_caged_bridge(self):
        self.assertEqual(e.window_start('202608',24),'202409')
        self.assertEqual(e.months_between('202512','202602'),['202512','202601','202602'])
        with self.assertRaises(ValueError):e.months_between('201912','202001')
    def test_negative_counts_and_wrong_balance_rejected(self):
        for r in [{'admissions':-1,'dismissals':0,'balance':-1},{'admissions':2,'dismissals':1,'balance':2}]:
            with self.assertRaises(ValueError):e.validate_counts(r)


class PrivacyTests(unittest.TestCase):
    def test_merge_small_and_complementary_cells(self):
        groups={'small':{'admissions':2,'dismissals':0,'balance':2},'big':{'admissions':10,'dismissals':5,'balance':5},'zero':e.empty_counts()}
        out,status=e.protected_categories(groups,{k:k for k in groups})
        self.assertEqual(e.totals(out),e.totals(groups.values()));self.assertEqual(status,'aggregated')
        self.assertTrue(all(not 0<r['admissions']<5 and not 0<r['dismissals']<5 for r in out))
    def test_entire_small_dimension_is_suppressed(self):
        self.assertEqual(e.protected_categories({'x':{'admissions':1,'dismissals':0,'balance':1}},{'x':'x'}),([],'suppressed'))
    def test_categories_preserve_totals_even_with_negative_balance(self):
        counts={'x':{'admissions':5,'dismissals':8,'balance':-3},'y':{'admissions':1,'dismissals':1,'balance':0}}
        out,_=e.protected_categories(counts,{'x':'x','y':'y'})
        self.assertEqual(e.totals(out),e.totals(counts.values()))


class RaisTests(unittest.TestCase):
    def test_real_stock_and_sectors_all_peers(self):
        r,_=rais_fixture();self.assertEqual(r['4127965']['stock']['value'],2763)
        self.assertEqual([x['stock'] for x in r['4127965']['series']],[2466,2513,2763])
        self.assertEqual(r['4109401']['stock']['value'],52702)
        self.assertEqual(sum(s['stock'] for s in r['4127965']['sectors']),2763)
    def test_table_sector_divergence_fails_zero_tolerance(self):
        d=json.loads((FIX/'rais-table4.json').read_text());d['rows'][0]['AF']=str(int(d['rows'][0]['AF'])+1)
        with patch.object(mte,'xlsx_rows',return_value={'TABELA 4':[d['header'],d['periods'],*d['rows']]}),self.assertRaises(ValueError):e.rais_table('x','now')
    def test_layout_and_missing_municipality_fail(self):
        d=json.loads((FIX/'rais-table4.json').read_text())
        for rs in [[d['periods'],*d['rows']],[d['header'],d['periods'],*d['rows'][:-1]]]:
            with patch.object(mte,'xlsx_rows',return_value={'TABELA 4':rs}),self.assertRaises(ValueError):e.rais_table('x','now')


class SnapshotTests(unittest.TestCase):
    def test_published_schema_and_no_mock_employment(self):
        d=json.loads((ROOT/'public/data/employment.json').read_text());e.validate(d)
        catalog=json.loads((ROOT/'public/data/indicators.json').read_text())
        self.assertTrue(all(i['status']!='mock' for i in catalog['indicators'] if i['module']=='employment'))
        self.assertNotIn('formal-jobs',[i['id'] for i in catalog['indicators']])
    def test_download_failure_preserves_last_valid_dataset(self):
        original=json.loads((ROOT/'public/data/employment.json').read_text())
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'employment.json').write_text(json.dumps(original));(p/'indicators.json').write_text((ROOT/'public/data/indicators.json').read_text())
            with patch.object(mte,'download',side_effect=ValueError('Download incompleto')):
                d=e.update(p,source='rais',force=True,latest='202608',rais_year=2025)
            self.assertEqual(d['rais'],original['rais']);self.assertEqual(d['caged'],original['caged']);self.assertTrue(d['collection']['failures'])
    def test_no_new_publication_does_not_download_or_write(self):
        original=json.loads((ROOT/'public/data/employment.json').read_text())
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);file=p/'employment.json';file.write_text(json.dumps(original));before=file.read_bytes()
            with patch.object(mte,'download') as mock:
                e.update(p,source='rais',latest='202608',rais_year=2025)
            mock.assert_not_called();self.assertEqual(file.read_bytes(),before)
    def test_discovery_failure_removes_original_mocks(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'indicators.json').write_text(json.dumps({'indicators':[{'id':'formal-jobs','module':'employment','status':'mock'}]}))
            with patch.object(mte,'discover',side_effect=OSError('FTP indisponível')):d=e.update(p)
            self.assertEqual(d['rais']['status'],'unavailable')
            c=json.loads((p/'indicators.json').read_text());self.assertEqual(len(c['indicators']),2);self.assertTrue(all(i['status']=='unavailable' for i in c['indicators']))
    def test_bad_schema_and_stock_are_rejected(self):
        original=json.loads((ROOT/'public/data/employment.json').read_text())
        for modify in ['schema','territory','stock']:
            d=copy.deepcopy(original)
            if modify=='schema':d['schemaVersion']=2
            elif modify=='territory':d['municipality']['code']='4218806'
            else:d['rais']['stock']['value']+=1
            with self.assertRaises(ValueError):e.validate(d)


class DownloadTests(unittest.TestCase):
    class Response(io.BytesIO):
        headers={'Content-Length':'100'}
    def test_incomplete_download_keeps_old_file(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'data.xlsx';p.write_bytes(b'previous valid snapshot')
            with patch.object(mte,'urlopen',return_value=self.Response(b'short')),self.assertRaises(ValueError):mte.download('https://example.org/data.xlsx',p,attempts=1)
            self.assertEqual(p.read_bytes(),b'previous valid snapshot');self.assertFalse(p.with_suffix('.xlsx.part').exists())
    def test_bad_7z_signature_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=self.Response(b'x'*100)
            with patch.object(mte,'urlopen',return_value=r),self.assertRaises(ValueError):mte.download('https://example.org/data.7z',Path(t)/'data.7z',attempts=1)



class RaisMicrodataTests(unittest.TestCase):
    def load(self):
        with (FIX/'rais-2025.csv').open(encoding='cp1252') as h:return list(mte.rais_rows(h,2025))
    def expected(self,rows):
        values={code:{'stock':{'value':0},'sectors':[{'code':key,'stock':0} for key in mte.SECTORS]} for code in mte.MUNICIPALITIES}
        for r in rows:
            if r['indvinculoativo3112codigo']=='1' and r['indvinculoabandonadocodigo']=='0':
                p=values[r['code']];p['stock']['value']+=1;key=e.rais_sector(r['cnae20classecodigo']);next(s for s in p['sectors'] if s['code']==key)['stock']+=1
        return values
    def test_real_2025_csv_delimiter_encoding_and_abandoned(self):
        rs=self.load();self.assertEqual(len(rs),16);self.assertTrue(any(r['indvinculoabandonadocodigo']=='1' for r in rs));self.assertTrue(any(r['indvinculoativo3112codigo']=='0' for r in rs))
        expected=self.expected(rs);actual=e.rais_remuneration(rs,expected)['4127965']
        self.assertEqual(actual['stock'],expected['4127965']['stock']['value']);self.assertLess(actual['stock'],len(rs));self.assertEqual(actual['missingOrZero']+actual['sample'],actual['stock'])
        self.assertEqual(actual['variable'],'Vl Rem Dezembro Nom')
    def test_stock_divergence_prevents_remuneration_publication(self):
        rs=self.load();expected=self.expected(rs);expected['4127965']['stock']['value']+=1
        with self.assertRaises(ValueError):e.rais_remuneration(rs,expected)
    def test_new_layout_or_year_fails_before_values(self):
        text=(FIX/'rais-2025.csv').read_text(encoding='cp1252')
        with self.assertRaises(ValueError):list(mte.rais_rows(io.StringIO(text),2026))
        with self.assertRaises(ValueError):list(mte.rais_rows(io.StringIO(text.replace('Vl Rem Dezembro Nom','Renda média')),2025))
    def test_fields_are_mapped_by_names_not_fixed_positions(self):
        raw=(FIX/'rais-2025.csv').read_text(encoding='cp1252');source=list(csv.reader(io.StringIO(raw),delimiter=','));out=io.StringIO();writer=csv.writer(out,delimiter=',');writer.writerows([list(reversed(r)) for r in source])
        self.assertEqual(list(mte.rais_rows(io.StringIO(out.getvalue()),2025)),self.load())
    def test_abandoned_and_inactive_salary_never_enters_mean(self):
        rs=self.load();before=e.rais_remuneration(rs,self.expected(rs))
        modified=[{**r,'vlremdezembronom':'999999999'} if r['indvinculoabandonadocodigo']=='1' or r['indvinculoativo3112codigo']=='0' else r for r in rs]
        self.assertEqual(e.rais_remuneration(modified,self.expected(rs)),before)

if __name__=='__main__':unittest.main()
